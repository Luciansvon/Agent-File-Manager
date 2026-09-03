namespace FolderVision.Core;

internal static class AutomationState
{
    public static bool IsPaused => File.Exists(CorePaths.AutomationPausedPath);

    public static void SetPaused(bool paused)
    {
        CorePaths.EnsureDirectories();
        if (paused)
        {
            File.WriteAllText(CorePaths.AutomationPausedPath, DateTimeOffset.UtcNow.ToString("O"));
        }
        else if (File.Exists(CorePaths.AutomationPausedPath))
        {
            File.Delete(CorePaths.AutomationPausedPath);
        }
    }
}
