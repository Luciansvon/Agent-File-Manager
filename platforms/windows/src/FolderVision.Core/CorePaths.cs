using System.Runtime.InteropServices;

namespace FolderVision.Core;

internal static class CorePaths
{
    public const string PipeName = "FolderVision.Core.v1";

    public static string Root { get; } = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "FolderVision");

    public static string LogsDirectory => Path.Combine(Root, "logs");
    public static string ConfigDirectory => Path.Combine(Root, "config");
    public static string CoreLogPath => Path.Combine(LogsDirectory, "core.log");
    public static string StorageZonesPath => Path.Combine(ConfigDirectory, "storage-zones.json");
    public static string AutomationPausedPath => Path.Combine(ConfigDirectory, "automation.paused");

    public static string EngineExecutable => ResolveExecutable(
        "FileIDEngine.exe",
        Path.Combine("engine", "target", TargetTriple, "release", "FileIDEngine.exe"),
        Path.Combine("engine", "target", TargetTriple, "debug", "FileIDEngine.exe"));

    public static string UiExecutable => ResolveExecutable(
        "FileID.exe",
        Path.Combine("FileID.App", "bin", ArchitectureLabel, "Debug", "net8.0-windows10.0.19041.0", RuntimeIdentifier, "FileID.exe"),
        Path.Combine("FileID.App", "bin", ArchitectureLabel, "Release", "net8.0-windows10.0.19041.0", RuntimeIdentifier, "publish", "FileID.exe"));

    private static string TargetTriple => RuntimeInformation.ProcessArchitecture == Architecture.Arm64
        ? "aarch64-pc-windows-msvc"
        : "x86_64-pc-windows-msvc";

    private static string ArchitectureLabel => RuntimeInformation.ProcessArchitecture == Architecture.Arm64
        ? "arm64"
        : "x64";

    private static string RuntimeIdentifier => RuntimeInformation.ProcessArchitecture == Architecture.Arm64
        ? "win-arm64"
        : "win-x64";

    public static void EnsureDirectories()
    {
        Directory.CreateDirectory(Root);
        Directory.CreateDirectory(LogsDirectory);
        Directory.CreateDirectory(ConfigDirectory);
    }

    private static string ResolveExecutable(string besideName, params string[] devTails)
    {
        var beside = Path.Combine(AppContext.BaseDirectory, besideName);
        if (File.Exists(beside)) return beside;

        foreach (var tail in devTails)
        {
            var candidate = Path.GetFullPath(Path.Combine(
                AppContext.BaseDirectory,
                "..", "..", "..", "..", "..",
                tail));
            if (File.Exists(candidate)) return candidate;
        }
        return beside;
    }
}
