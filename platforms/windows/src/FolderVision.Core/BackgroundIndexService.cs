using System.Collections.Concurrent;
using FileID.IpcSchema;

namespace FolderVision.Core;

/// <summary>
/// Standard-user fallback for volumes where USN access is unavailable. File
/// events only dirty a configured root; one incremental scan is debounced and
/// serialized through the persistent engine. The watcher never reads content.
/// </summary>
internal sealed class BackgroundIndexService : IAsyncDisposable
{
    private static readonly TimeSpan DebounceDelay = TimeSpan.FromSeconds(3);
    private static readonly TimeSpan BusyRetryDelay = TimeSpan.FromSeconds(30);
    private static readonly TimeSpan ScanTimeout = TimeSpan.FromHours(2);
    private static readonly TimeSpan VisionTimeout = TimeSpan.FromMinutes(5);
    private static readonly TimeSpan SettleSampleDelay = TimeSpan.FromSeconds(1);
    private static readonly TimeSpan SettleTimeout = TimeSpan.FromSeconds(30);

    private readonly EngineBroker _broker;
    private readonly string[] _roots;
    private readonly List<FileSystemWatcher> _watchers = new();
    private readonly ConcurrentDictionary<string, byte> _dirtyTargets = new(StringComparer.OrdinalIgnoreCase);
    private readonly ConcurrentDictionary<string, System.Threading.Timer> _debounceTimers = new(StringComparer.OrdinalIgnoreCase);
    private readonly SemaphoreSlim _wake = new(0, 1);
    private readonly CancellationTokenSource _shutdown = new();
    private readonly object _completionLock = new();
    private TaskCompletionSource<ScanResult>? _scanCompletion;
    private TaskCompletionSource<bool>? _visionCompletion;
    private Task? _worker;

    private enum ScanResult { Complete, Busy, Failed }

    public BackgroundIndexService(EngineBroker broker, IReadOnlyList<StorageZone> zones)
    {
        _broker = broker;
        _roots = MinimizeRoots(zones
            // Only explicitly auto-managed inboxes get always-on watchers.
            // IndexOnly roots (especially OneDrive) are still selectable in the
            // desktop app, but Core must not crawl or hydrate them at startup.
            .Where(zone => zone.Kind == StorageZoneKind.AutoManage)
            .Select(zone => zone.Path));
        _broker.EngineEventReceived += OnEngineEvent;
    }

    public void Start()
    {
        if (_worker is not null) return;
        foreach (var root in _roots)
        {
            TryAddWatcher(root);
        }
        _worker = RunAsync(_shutdown.Token);
        SetAutomationEnabled(!AutomationState.IsPaused);
        RequestCatchUp();
        CoreLog.Write($"background index started roots={_roots.Length} watchers={_watchers.Count}");
    }

    public void SetAutomationEnabled(bool enabled)
    {
        _ = ConfigureEngineAsync(enabled, _shutdown.Token);
    }

    private async Task ConfigureEngineAsync(bool enabled, CancellationToken cancellationToken)
    {
        try
        {
            await _broker.SendCommandAsync(
                new ConfigureBackgroundIndexCommand(_roots, enabled),
                cancellationToken);
            CoreLog.Write($"background USN configured roots={_roots.Length} enabled={enabled}");
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
        }
        catch (Exception ex)
        {
            CoreLog.Write($"background USN configuration failed: {ex.GetType().Name}");
        }
    }

    public void RequestCatchUp()
    {
        if (AutomationState.IsPaused) return;
        foreach (var root in _roots) MarkDirty(root);
    }

    private void TryAddWatcher(string root)
    {
        try
        {
            var watcher = new FileSystemWatcher(root)
            {
                IncludeSubdirectories = true,
                NotifyFilter = NotifyFilters.FileName | NotifyFilters.DirectoryName
                    | NotifyFilters.LastWrite | NotifyFilters.Size | NotifyFilters.CreationTime,
                InternalBufferSize = 32 * 1024,
                EnableRaisingEvents = false,
            };
            watcher.Created += (_, eventArgs) => OnChanged(root, eventArgs.FullPath);
            watcher.Changed += (_, eventArgs) => OnChanged(root, eventArgs.FullPath);
            watcher.Deleted += (_, eventArgs) => OnDeleted(root, eventArgs.FullPath);
            watcher.Renamed += (_, eventArgs) =>
            {
                OnDeleted(root, eventArgs.OldFullPath);
                OnChanged(root, eventArgs.FullPath);
                Debounce(root);
            };
            watcher.Error += (_, eventArgs) =>
            {
                CoreLog.Write($"watcher overflow/error root={Redact(root)} type={eventArgs.GetException()?.GetType().Name}");
                Debounce(root);
            };
            watcher.EnableRaisingEvents = true;
            _watchers.Add(watcher);
        }
        catch (Exception ex)
        {
            CoreLog.Write($"watcher unavailable root={Redact(root)}: {ex.GetType().Name}");
        }
    }

    private void OnChanged(string root, string path)
    {
        if (AutomationState.IsPaused || IsTemporaryName(path) || !IsCandidate(path)) return;
        Debounce(Directory.Exists(path) ? root : path);
    }

    private void OnDeleted(string root, string path)
    {
        if (AutomationState.IsPaused || string.IsNullOrWhiteSpace(path)) return;
        _ = MarkDeletedAsync(path, _shutdown.Token);
        // Keep the bounded root reconciliation as overflow/directory fallback.
        Debounce(root);
    }

    private async Task MarkDeletedAsync(string path, CancellationToken cancellationToken)
    {
        try
        {
            await _broker.SendCommandAsync(new MarkPathDeletedCommand(path), cancellationToken);
            CoreLog.Write($"background tombstone queued target={Redact(path)}");
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
        }
        catch (Exception ex)
        {
            CoreLog.Write($"background tombstone failed target={Redact(path)}: {ex.GetType().Name}");
        }
    }

    private void Debounce(string root, TimeSpan? delay = null)
    {
        var timer = _debounceTimers.GetOrAdd(root, key => new System.Threading.Timer(
            _ =>
            {
                if (!AutomationState.IsPaused) MarkDirty(key);
            },
            null,
            Timeout.InfiniteTimeSpan,
            Timeout.InfiniteTimeSpan));
        timer.Change(delay ?? DebounceDelay, Timeout.InfiniteTimeSpan);
    }

    private void MarkDirty(string root)
    {
        _dirtyTargets[root] = 0;
        if (_wake.CurrentCount == 0)
        {
            try { _wake.Release(); } catch (SemaphoreFullException) { }
        }
    }

    private async Task RunAsync(CancellationToken cancellationToken)
    {
        try
        {
            while (!cancellationToken.IsCancellationRequested)
            {
                await _wake.WaitAsync(cancellationToken);
                while (!AutomationState.IsPaused && TryTakeDirtyTarget(out var target))
                {
                    var result = await ScanTargetAsync(target, cancellationToken);
                    if (result != ScanResult.Complete)
                    {
                        Debounce(target, result == ScanResult.Busy ? BusyRetryDelay : TimeSpan.FromMinutes(5));
                    }
                }
            }
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
        }
    }

    private bool TryTakeDirtyTarget(out string target)
    {
        foreach (var candidate in _dirtyTargets.Keys.OrderBy(path => path, StringComparer.OrdinalIgnoreCase))
        {
            if (_dirtyTargets.TryRemove(candidate, out _))
            {
                target = candidate;
                return true;
            }
        }
        target = string.Empty;
        return false;
    }

    private async Task<ScanResult> ScanTargetAsync(string target, CancellationToken cancellationToken)
    {
        if (!Directory.Exists(target))
        {
            if (!File.Exists(target))
            {
                var owner = FindOwningRoot(target);
                if (owner is not null && !string.Equals(owner, target, StringComparison.OrdinalIgnoreCase))
                {
                    MarkDirty(owner);
                }
                return ScanResult.Complete;
            }
            if (!await WaitUntilSettledAsync(target, cancellationToken))
            {
                CoreLog.Write($"file not settled; retry queued target={Redact(target)}");
                return ScanResult.Busy;
            }
        }

        var completion = new TaskCompletionSource<ScanResult>(TaskCreationOptions.RunContinuationsAsynchronously);
        lock (_completionLock) _scanCompletion = completion;
        try
        {
            CoreLog.Write($"background incremental scan queued target={Redact(target)}");
            await _broker.SendCommandAsync(new StartScanCommand(target, Path.GetFileName(target), Rescan: false), cancellationToken);
            var result = await completion.Task.WaitAsync(ScanTimeout, cancellationToken);
            if (result == ScanResult.Complete && IsVisionInboxCandidate(target))
            {
                await AnalyzeInboxTargetAsync(target, cancellationToken);
            }
            return result;
        }
        catch (TimeoutException)
        {
            CoreLog.Write($"background scan timed out target={Redact(target)}");
            return ScanResult.Failed;
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            CoreLog.Write($"background scan failed target={Redact(target)}: {ex.GetType().Name}");
            return ScanResult.Failed;
        }
        finally
        {
            lock (_completionLock)
            {
                if (ReferenceEquals(_scanCompletion, completion)) _scanCompletion = null;
            }
        }
    }

    private async Task AnalyzeInboxTargetAsync(string target, CancellationToken cancellationToken)
    {
        try
        {
            var attributes = File.GetAttributes(target);
            if (IsCloudOnly(target, attributes))
            {
                CoreLog.Write($"background vision skipped cloud-only target={Redact(target)}");
                return;
            }
            var completion = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
            lock (_completionLock) _visionCompletion = completion;
            CoreLog.Write($"background local vision queued target={Redact(target)}");
            await _broker.SendCommandAsync(
                new DeepAnalyzeFolderCommand(target, "qwen3_vl_2b_ollama"),
                cancellationToken);
            var ok = await completion.Task.WaitAsync(VisionTimeout, cancellationToken);
            CoreLog.Write($"background local vision completed target={Redact(target)} ok={ok}");
        }
        catch (TimeoutException)
        {
            CoreLog.Write($"background local vision timed out target={Redact(target)}");
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            CoreLog.Write($"background local vision failed target={Redact(target)}: {ex.GetType().Name}");
        }
        finally
        {
            lock (_completionLock) _visionCompletion = null;
        }
    }

    private static async Task<bool> WaitUntilSettledAsync(string path, CancellationToken cancellationToken)
    {
        if (IsTemporaryName(path)) return false;
        var deadline = DateTime.UtcNow + SettleTimeout;
        (long Size, DateTime LastWriteUtc)? previous = null;
        var stableSamples = 0;

        while (DateTime.UtcNow < deadline)
        {
            cancellationToken.ThrowIfCancellationRequested();
            try
            {
                var attributes = File.GetAttributes(path);
                if (IsCloudOnly(path, attributes)) return true;

                var info = new FileInfo(path);
                var current = (info.Length, info.LastWriteTimeUtc);
                if (previous == current)
                {
                    stableSamples++;
                    if (stableSamples >= 2
                        && DateTime.UtcNow - current.LastWriteTimeUtc >= DebounceDelay
                        && CanOpenWithoutWriter(path)) return true;
                }
                else
                {
                    previous = current;
                    stableSamples = 0;
                }
            }
            catch (IOException)
            {
                stableSamples = 0;
            }
            catch (UnauthorizedAccessException)
            {
                stableSamples = 0;
            }
            await Task.Delay(SettleSampleDelay, cancellationToken);
        }
        return false;
    }

    private static bool CanOpenWithoutWriter(string path)
    {
        try
        {
            using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read);
            return stream.Length >= 0;
        }
        catch (IOException)
        {
            return false;
        }
        catch (UnauthorizedAccessException)
        {
            return false;
        }
    }

    private string? FindOwningRoot(string path) => _roots
        .Where(root => string.Equals(path, root, StringComparison.OrdinalIgnoreCase)
            || path.StartsWith(root.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar,
                StringComparison.OrdinalIgnoreCase))
        .OrderByDescending(root => root.Length)
        .FirstOrDefault();

    private static bool IsTemporaryName(string path)
    {
        var name = Path.GetFileName(path);
        if (name.StartsWith("~$", StringComparison.OrdinalIgnoreCase)) return true;
        return TemporaryExtensions.Contains(Path.GetExtension(name));
    }

    private static bool IsCloudOnly(string path, FileAttributes attributes)
        => CloudAttributesRequireSkip(
            (int)attributes,
            IsUnderConfiguredOneDriveRoot(path));

    internal static bool CloudAttributesRequireSkip(int attributes, bool underOneDriveRoot)
    {
        const int ReparsePoint = 0x0000_0400;
        const int Offline = 0x0000_1000;
        const int RecallOnOpen = 0x0004_0000;
        const int Pinned = 0x0008_0000;
        const int Unpinned = 0x0010_0000;
        const int RecallOnDataAccess = 0x0040_0000;
        if ((attributes & (Offline | RecallOnOpen | Unpinned | RecallOnDataAccess)) != 0)
        {
            return true;
        }
        return (attributes & ReparsePoint) != 0
            && (attributes & Pinned) == 0
            && underOneDriveRoot;
    }

    private static bool IsUnderConfiguredOneDriveRoot(string path)
    {
        string candidate;
        try { candidate = Path.GetFullPath(path); }
        catch { return false; }
        foreach (var variable in new[] { "OneDrive", "OneDriveConsumer", "OneDriveCommercial" })
        {
            var root = Environment.GetEnvironmentVariable(variable);
            if (string.IsNullOrWhiteSpace(root)) continue;
            string fullRoot;
            try { fullRoot = Path.TrimEndingDirectorySeparator(Path.GetFullPath(root)); }
            catch { continue; }
            if (candidate.Equals(fullRoot, StringComparison.OrdinalIgnoreCase)
                || candidate.StartsWith(fullRoot + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
        }
        return false;
    }

    private void OnEngineEvent(string line)
    {
        try
        {
            var payload = IpcCoder.Decode<IpcEvent>(line).Payload;
            TaskCompletionSource<ScanResult>? scanCompletion;
            TaskCompletionSource<bool>? visionCompletion;
            lock (_completionLock)
            {
                scanCompletion = _scanCompletion;
                visionCompletion = _visionCompletion;
            }
            switch (payload)
            {
                case ScanCompleteEvent:
                    scanCompletion?.TrySetResult(ScanResult.Complete);
                    break;
                case ErrorEvent error when error.Error.Kind == "scan_already_running":
                    scanCompletion?.TrySetResult(ScanResult.Busy);
                    break;
                case ErrorEvent error when error.Error.Kind is "discovery_failed" or "model_load_failed"
                    or "model_load_timeout" or "db_failed" or "scan_failed":
                    scanCompletion?.TrySetResult(ScanResult.Failed);
                    break;
                case DeepAnalyzeCompleteEvent completed:
                    visionCompletion?.TrySetResult(completed.Result.Failed == 0 && !completed.Result.Cancelled);
                    break;
                case ErrorEvent error when error.Error.Kind is "deep_analyze_busy" or "ollama_unavailable"
                    or "vlm_model_missing" or "llama_cpp_missing":
                    visionCompletion?.TrySetResult(false);
                    break;
            }
        }
        catch
        {
            // Other/newer engine frames are irrelevant to scheduler state.
        }
    }

    private static bool IsVisionInboxCandidate(string path)
    {
        if (!File.Exists(path)) return false;
        return VisionExtensions.Contains(Path.GetExtension(path));
    }

    private static bool IsCandidate(string path)
    {
        if (StorageZoneDiscovery.Classify(path) == StorageZoneKind.Protected) return false;
        var extension = Path.GetExtension(path).TrimStart('.');
        return extension.Length == 0 || SupportedExtensions.Contains(extension);
    }

    private static readonly HashSet<string> SupportedExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        "jpg", "jpeg", "png", "gif", "webp", "bmp", "tif", "tiff", "heic", "heif",
        "raw", "arw", "cr2", "nef", "dng", "pdf", "docx", "doc", "odt", "rtf", "txt",
        "md", "xls", "xlsx", "pptx", "csv", "json", "html", "htm", "mp4", "mov", "m4v", "avi",
        "mkv", "webm", "mp3", "wav", "flac", "ogg", "m4a", "aac", "opus",
    };

    private static readonly HashSet<string> TemporaryExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        ".crdownload", ".part", ".partial", ".tmp", ".download",
    };

    private static readonly HashSet<string> VisionExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff",
        ".heic", ".heif", ".avif", ".pdf", ".mp4", ".mov", ".m4v", ".webm",
    };

    private static string[] MinimizeRoots(IEnumerable<string> roots)
    {
        var selected = new List<string>();
        foreach (var root in roots.Distinct(StringComparer.OrdinalIgnoreCase).OrderBy(path => path.Length))
        {
            if (selected.Any(parent => root.StartsWith(parent.TrimEnd(Path.DirectorySeparatorChar)
                + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))) continue;
            selected.Add(root);
        }
        return selected.ToArray();
    }

    private static string Redact(string path) => Path.GetFileName(path.TrimEnd(Path.DirectorySeparatorChar)) is { Length: > 0 } name
        ? name
        : "drive-root";

    public async ValueTask DisposeAsync()
    {
        _broker.EngineEventReceived -= OnEngineEvent;
        _shutdown.Cancel();
        foreach (var watcher in _watchers) watcher.Dispose();
        foreach (var timer in _debounceTimers.Values) await timer.DisposeAsync();
        if (_worker is not null)
        {
            try { await _worker; } catch (OperationCanceledException) { }
        }
        _wake.Dispose();
        _shutdown.Dispose();
    }
}
