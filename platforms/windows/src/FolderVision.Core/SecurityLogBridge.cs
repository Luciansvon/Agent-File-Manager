namespace FileID.Services;

internal static class DebugLog
{
    public static void Warn(string message) => FolderVision.Core.CoreLog.Write("security: " + message);
}

internal static class PathRedactor
{
    public static string Redact(string path)
    {
        if (string.IsNullOrWhiteSpace(path)) return string.Empty;
        return Path.GetFileName(path);
    }
}
