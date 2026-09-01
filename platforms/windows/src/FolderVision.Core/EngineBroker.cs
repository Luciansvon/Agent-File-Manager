using System.Diagnostics;
using System.IO.Pipes;
using System.Security.Cryptography;
using System.Text;
using FileID.Services;
using FileID.IpcSchema;

namespace FolderVision.Core;

internal sealed class EngineBroker : IAsyncDisposable
{
    private readonly CancellationTokenSource _shutdown = new();
    private readonly SemaphoreSlim _engineGate = new(1, 1);
    private readonly SemaphoreSlim _engineWriteGate = new(1, 1);
    private readonly SemaphoreSlim _clientWriteGate = new(1, 1);
    private Process? _engine;
    private StreamWriter? _engineInput;
    private StreamWriter? _clientOutput;
    private Task? _runTask;

    public event Action<string>? EngineEventReceived;

    public void Start()
    {
        _runTask ??= RunAsync(_shutdown.Token);
    }

    public Task SendCommandAsync(CommandPayload payload, CancellationToken cancellationToken)
    {
        var line = IpcCoder.Encode(IpcCommand.New(payload));
        return ForwardCommandAsync(line, cancellationToken);
    }

    private async Task RunAsync(CancellationToken cancellationToken)
    {
        await Task.WhenAll(
            MonitorEngineAsync(cancellationToken),
            AcceptClientsAsync(cancellationToken));
    }

    private async Task MonitorEngineAsync(CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            try
            {
                var process = await EnsureEngineStartedAsync(cancellationToken);
                await process.WaitForExitAsync(cancellationToken);
                CoreLog.Write($"engine exited code={process.ExitCode}");
                await ClearEngineAsync(process);
            }
            catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception ex)
            {
                CoreLog.Write($"engine monitor failed: {ex.GetType().Name}: {ex.Message}");
            }

            try
            {
                await Task.Delay(TimeSpan.FromSeconds(2), cancellationToken);
            }
            catch (OperationCanceledException)
            {
                break;
            }
        }
    }

    private async Task AcceptClientsAsync(CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            await using var pipe = new NamedPipeServerStream(
                CorePaths.PipeName,
                PipeDirection.InOut,
                1,
                PipeTransmissionMode.Byte,
                PipeOptions.Asynchronous | PipeOptions.CurrentUserOnly);
            try
            {
                await pipe.WaitForConnectionAsync(cancellationToken);
                await EnsureEngineStartedAsync(cancellationToken);
                await ServeClientAsync(pipe, cancellationToken);
            }
            catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
            {
                break;
            }
            catch (IOException ex)
            {
                CoreLog.Write($"pipe client disconnected: {ex.Message}");
            }
            catch (Exception ex)
            {
                CoreLog.Write($"pipe server failed: {ex.GetType().Name}: {ex.Message}");
            }
        }
    }

    private async Task ServeClientAsync(NamedPipeServerStream pipe, CancellationToken cancellationToken)
    {
        using var reader = new StreamReader(pipe, new UTF8Encoding(false), false, 16 * 1024, leaveOpen: true);
        using var writer = new StreamWriter(pipe, new UTF8Encoding(false), 16 * 1024, leaveOpen: true)
        {
            AutoFlush = true,
        };

        Volatile.Write(ref _clientOutput, writer);
        var boundedReader = new BoundedLineReader();
        CoreLog.Write("UI connected to core pipe");
        try
        {
            while (!cancellationToken.IsCancellationRequested && pipe.IsConnected)
            {
                string? line;
                try
                {
                    line = await boundedReader.ReadLineAsync(reader, cancellationToken);
                }
                catch (InvalidDataException ex)
                {
                    CoreLog.Write("UI command dropped: " + ex.Message);
                    continue;
                }
                if (line is null) break;
                await ForwardCommandAsync(line, cancellationToken);
            }
        }
        finally
        {
            Interlocked.CompareExchange(ref _clientOutput, null, writer);
            CoreLog.Write("UI disconnected from core pipe; engine remains active");
        }
    }

    private async Task<Process> EnsureEngineStartedAsync(CancellationToken cancellationToken)
    {
        await _engineGate.WaitAsync(cancellationToken);
        try
        {
            if (_engine is { HasExited: false }) return _engine;

            var enginePath = CorePaths.EngineExecutable;
            if (!File.Exists(enginePath))
            {
                throw new FileNotFoundException("FileIDEngine.exe is missing beside FolderVision.Core.", enginePath);
            }

            VerifyEngineIntegrity(enginePath);

            var startInfo = new ProcessStartInfo
            {
                FileName = enginePath,
                UseShellExecute = false,
                RedirectStandardInput = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
                StandardInputEncoding = new UTF8Encoding(false),
                StandardOutputEncoding = new UTF8Encoding(false),
                StandardErrorEncoding = new UTF8Encoding(false),
                WorkingDirectory = CorePaths.Root,
            };
            startInfo.Environment["FILEID_LOG"] = Environment.GetEnvironmentVariable("FILEID_LOG") ?? "info";

            var process = Process.Start(startInfo)
                ?? throw new InvalidOperationException("Process.Start returned null for FileIDEngine.exe.");
            process.StandardInput.AutoFlush = true;
            _engine = process;
            _engineInput = process.StandardInput;
            _ = PumpEngineOutputAsync(process, cancellationToken);
            _ = PumpEngineErrorsAsync(process, cancellationToken);
            CoreLog.Write($"engine started pid={process.Id}");
            return process;
        }
        finally
        {
            _engineGate.Release();
        }
    }

    private async Task ForwardCommandAsync(string line, CancellationToken cancellationToken)
    {
        await EnsureEngineStartedAsync(cancellationToken);
        await _engineWriteGate.WaitAsync(cancellationToken);
        try
        {
            var input = _engineInput ?? throw new IOException("Engine input is unavailable.");
            await input.WriteLineAsync(line.AsMemory(), cancellationToken);
            await input.FlushAsync(cancellationToken);
        }
        finally
        {
            _engineWriteGate.Release();
        }
    }

    private async Task PumpEngineOutputAsync(Process process, CancellationToken cancellationToken)
    {
        var boundedReader = new BoundedLineReader();
        try
        {
            while (!cancellationToken.IsCancellationRequested)
            {
                string? line;
                try
                {
                    line = await boundedReader.ReadLineAsync(process.StandardOutput, cancellationToken);
                }
                catch (InvalidDataException ex)
                {
                    CoreLog.Write("engine event dropped: " + ex.Message);
                    continue;
                }
                if (line is null) break;
                try
                {
                    EngineEventReceived?.Invoke(line);
                }
                catch (Exception ex)
                {
                    CoreLog.Write($"engine event observer failed: {ex.GetType().Name}: {ex.Message}");
                }
                var client = Volatile.Read(ref _clientOutput);
                if (client is null) continue;

                await _clientWriteGate.WaitAsync(cancellationToken);
                try
                {
                    if (ReferenceEquals(client, Volatile.Read(ref _clientOutput)))
                    {
                        await client.WriteLineAsync(line.AsMemory(), cancellationToken);
                        await client.FlushAsync(cancellationToken);
                    }
                }
                catch (IOException)
                {
                    Interlocked.CompareExchange(ref _clientOutput, null, client);
                }
                finally
                {
                    _clientWriteGate.Release();
                }
            }
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
        }
        catch (Exception ex)
        {
            CoreLog.Write($"engine stdout failed: {ex.GetType().Name}: {ex.Message}");
        }
    }

    private static void VerifyEngineIntegrity(string enginePath)
    {
        var expectedThumbprint = Environment.GetEnvironmentVariable("FILEID_EV_THUMBPRINT");
        var verdict = WinVerifyTrustChecker.Verify(enginePath, expectedThumbprint);
        switch (verdict)
        {
            case IntegrityVerdict.NotFound:
                throw new FileNotFoundException("FileIDEngine.exe disappeared before verification.", enginePath);
            case IntegrityVerdict.Untrusted:
                throw new InvalidDataException("FileIDEngine.exe failed Authenticode verification.");
            case IntegrityVerdict.Unsigned when !string.IsNullOrWhiteSpace(expectedThumbprint):
                throw new InvalidDataException("FileIDEngine.exe is unsigned but this build requires a signed engine.");
            case IntegrityVerdict.Unsigned:
                CoreLog.Write("engine is unsigned; accepted for local development");
                break;
            case IntegrityVerdict.Trusted:
                CoreLog.Write("engine Authenticode verification passed");
                break;
        }

        var verifiedHash = ComputeSha256(enginePath);
        var launchHash = ComputeSha256(enginePath);
        if (!CryptographicOperations.FixedTimeEquals(verifiedHash, launchHash))
        {
            throw new InvalidDataException("FileIDEngine.exe changed between verification and launch.");
        }
    }

    private static byte[] ComputeSha256(string path)
    {
        using var stream = new FileStream(
            path,
            FileMode.Open,
            FileAccess.Read,
            FileShare.Read,
            bufferSize: 128 * 1024,
            FileOptions.SequentialScan);
        using var sha = SHA256.Create();
        return sha.ComputeHash(stream);
    }

    private static async Task PumpEngineErrorsAsync(Process process, CancellationToken cancellationToken)
    {
        try
        {
            while (!cancellationToken.IsCancellationRequested)
            {
                var line = await process.StandardError.ReadLineAsync(cancellationToken);
                if (line is null) break;
                CoreLog.Write("engine: " + line);
            }
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
        }
        catch (Exception ex)
        {
            CoreLog.Write($"engine stderr failed: {ex.GetType().Name}: {ex.Message}");
        }
    }

    private async Task ClearEngineAsync(Process process)
    {
        await _engineGate.WaitAsync();
        try
        {
            if (!ReferenceEquals(_engine, process)) return;
            _engineInput?.Dispose();
            _engineInput = null;
            _engine.Dispose();
            _engine = null;
        }
        finally
        {
            _engineGate.Release();
        }
    }

    public async ValueTask DisposeAsync()
    {
        _shutdown.Cancel();
        var process = _engine;
        try { _engineInput?.Dispose(); } catch { }
        if (process is { HasExited: false })
        {
            try
            {
                using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(5));
                await process.WaitForExitAsync(timeout.Token);
            }
            catch
            {
                try { process.Kill(entireProcessTree: true); } catch { }
            }
        }
        if (_runTask is not null)
        {
            try { await _runTask; } catch (OperationCanceledException) { }
        }
        _shutdown.Dispose();
        _engineGate.Dispose();
        _engineWriteGate.Dispose();
        _clientWriteGate.Dispose();
    }
}
