namespace FolderVision.Core;

internal static class CoreLog
{
    private static readonly object Gate = new();

    public static void Write(string message)
    {
        try
        {
            CorePaths.EnsureDirectories();
            lock (Gate)
            {
                File.AppendAllText(
                    CorePaths.CoreLogPath,
                    $"{DateTimeOffset.UtcNow:O} {message}{Environment.NewLine}");
            }
        }
        catch
        {
        }
    }
}
