using FileID.IpcSchema;

namespace FolderVision.Core;

internal static class CoreSelfTest
{
    private static readonly string[] BackgroundRoots = [@"C:\Photos", @"D:\Documents"];

    public static int Run()
    {
        var failures = new List<string>();
        var windows = Environment.GetFolderPath(Environment.SpecialFolder.Windows);
        Assert(StorageZoneDiscovery.Classify(windows) == StorageZoneKind.Protected, "Windows must be protected", failures);

        var user = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        var downloads = Path.Combine(user, "Downloads");
        Assert(StorageZoneDiscovery.Classify(downloads) == StorageZoneKind.AutoManage, "Downloads must be auto-manage", failures);
        Assert(BackgroundIndexService.CloudAttributesRequireSkip(0x0000_1000, false), "offline cloud files must be skipped", failures);
        Assert(BackgroundIndexService.CloudAttributesRequireSkip(0x0000_0400, true), "transitioning OneDrive reparse files must be skipped", failures);
        Assert(!BackgroundIndexService.CloudAttributesRequireSkip(0x0008_0400, true), "pinned OneDrive files must remain readable", failures);
        Assert(
            StorageZoneDiscovery.Classify(Path.Combine(downloads, ".git", "objects")) == StorageZoneKind.Protected,
            ".git internals must be protected",
            failures);

        foreach (var variable in new[] { "OneDrive", "OneDriveConsumer", "OneDriveCommercial" })
        {
            var root = Environment.GetEnvironmentVariable(variable);
            if (string.IsNullOrWhiteSpace(root)) continue;
            Assert(StorageZoneDiscovery.Classify(root) == StorageZoneKind.IndexOnly, "OneDrive must default to index-only", failures);
        }

        TestBoundedReader(failures);
        TestBackgroundIndexCommand(failures);

        if (failures.Count == 0)
        {
            Console.WriteLine("FolderVision.Core self-test PASS");
            return 0;
        }

        foreach (var failure in failures) Console.Error.WriteLine("FAIL: " + failure);
        return 1;
    }

    private static void TestBackgroundIndexCommand(ICollection<string> failures)
    {
        var command = IpcCommand.New(new ConfigureBackgroundIndexCommand(
            BackgroundRoots,
            Enabled: true));
        var encoded = IpcCoder.Encode(command);
        var decoded = IpcCoder.Decode<IpcCommand>(encoded);
        var payload = decoded.Payload as ConfigureBackgroundIndexCommand;
        Assert(payload is not null, "background index command must round-trip", failures);
        Assert(payload?.Enabled == true, "background index enabled flag must round-trip", failures);
        Assert(payload?.Roots.Count == 2, "background index roots must round-trip", failures);
    }

    private static void Assert(bool condition, string message, ICollection<string> failures)
    {
        if (!condition) failures.Add(message);
    }

    private static void TestBoundedReader(ICollection<string> failures)
    {
        using var stream = new MemoryStream(System.Text.Encoding.UTF8.GetBytes("first\r\nsecond\n"));
        using var reader = new StreamReader(stream, System.Text.Encoding.UTF8);
        var bounded = new BoundedLineReader(maxChars: 16);
        var first = bounded.ReadLineAsync(reader, CancellationToken.None).AsTask().GetAwaiter().GetResult();
        var second = bounded.ReadLineAsync(reader, CancellationToken.None).AsTask().GetAwaiter().GetResult();
        Assert(first == "first", "bounded reader must trim CRLF", failures);
        Assert(second == "second", "bounded reader must preserve consecutive frames", failures);

        using var oversizedStream = new MemoryStream(System.Text.Encoding.UTF8.GetBytes("12345\nok\n"));
        using var oversizedReader = new StreamReader(oversizedStream, System.Text.Encoding.UTF8);
        var small = new BoundedLineReader(maxChars: 4);
        try
        {
            _ = small.ReadLineAsync(oversizedReader, CancellationToken.None).AsTask().GetAwaiter().GetResult();
            failures.Add("bounded reader must reject an oversized complete frame");
        }
        catch (InvalidDataException)
        {
        }
        var recovered = small.ReadLineAsync(oversizedReader, CancellationToken.None).AsTask().GetAwaiter().GetResult();
        Assert(recovered == "ok", "bounded reader must recover after an oversized frame", failures);
    }
}
