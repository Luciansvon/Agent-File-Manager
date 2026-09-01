using Microsoft.Win32;

namespace FolderVision.Core;

internal static class StartupRegistration
{
    private const string RunKeyPath = @"Software\Microsoft\Windows\CurrentVersion\Run";
    private const string ValueName = "FolderVisionCore";

    public static void EnsureRegistered()
    {
        var executable = Environment.ProcessPath;
        if (string.IsNullOrWhiteSpace(executable) || !File.Exists(executable)) return;
        if (!string.Equals(
                Path.GetFileNameWithoutExtension(executable),
                "FolderVision.Core",
                StringComparison.OrdinalIgnoreCase))
        {
            return;
        }

        using var key = Registry.CurrentUser.CreateSubKey(RunKeyPath, writable: true);
        key?.SetValue(ValueName, $"\"{executable}\" --activate", RegistryValueKind.String);
    }
}
