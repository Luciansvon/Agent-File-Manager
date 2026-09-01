using System.Text.Json;

namespace FolderVision.Core;

internal enum StorageZoneKind
{
    AutoManage,
    IndexOnly,
    Protected,
}

internal sealed record StorageZone(string Path, StorageZoneKind Kind, string Reason);

internal static class StorageZoneDiscovery
{
    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true };

    private static readonly string[] ProtectedLeafNames =
    {
        "$recycle.bin",
        "system volume information",
        "recovery",
        "node_modules",
        ".git",
        ".svn",
        ".hg",
    };

    public static IReadOnlyList<StorageZone> Discover()
    {
        var zones = new Dictionary<string, StorageZone>(StringComparer.OrdinalIgnoreCase);
        var user = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);

        Add(zones, Path.Combine(user, "Downloads"), StorageZoneKind.AutoManage, "user downloads");
        Add(zones, Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), StorageZoneKind.IndexOnly, "desktop is opt-in index-only");
        Add(zones, Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), StorageZoneKind.IndexOnly, "documents are opt-in index-only");
        Add(zones, Environment.GetFolderPath(Environment.SpecialFolder.MyPictures), StorageZoneKind.IndexOnly, "pictures default to index-only");

        foreach (var variable in new[] { "OneDrive", "OneDriveConsumer", "OneDriveCommercial" })
        {
            Add(zones, Environment.GetEnvironmentVariable(variable), StorageZoneKind.IndexOnly, "OneDrive local content");
        }

        var systemRoot = Path.GetPathRoot(Environment.SystemDirectory);
        foreach (var drive in DriveInfo.GetDrives())
        {
            try
            {
                if (!drive.IsReady || drive.DriveType != DriveType.Fixed) continue;
                if (string.Equals(drive.RootDirectory.FullName, systemRoot, StringComparison.OrdinalIgnoreCase)) continue;
                Add(zones, drive.RootDirectory.FullName, StorageZoneKind.IndexOnly, "non-system fixed drive; promotion requires approval");
            }
            catch
            {
            }
        }

        foreach (var path in ProtectedRoots())
        {
            Add(zones, path, StorageZoneKind.Protected, "system or application-managed path");
        }

        return zones.Values
            .OrderBy(zone => zone.Kind)
            .ThenBy(zone => zone.Path, StringComparer.OrdinalIgnoreCase)
            .ToArray();
    }

    public static StorageZoneKind Classify(string path)
    {
        var canonical = Canonical(path);
        if (canonical is null) return StorageZoneKind.Protected;

        if (HasProtectedComponent(canonical)
            || ProtectedRoots().Any(root => IsWithin(canonical, root)))
        {
            return StorageZoneKind.Protected;
        }

        if (Directory.Exists(Path.Combine(canonical, ".git")))
        {
            return StorageZoneKind.IndexOnly;
        }

        foreach (var variable in new[] { "OneDrive", "OneDriveConsumer", "OneDriveCommercial" })
        {
            if (IsWithin(canonical, Environment.GetEnvironmentVariable(variable)))
            {
                return StorageZoneKind.IndexOnly;
            }
        }

        var user = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        var autoRoots = new[]
        {
            Path.Combine(user, "Downloads"),
        };
        if (autoRoots.Any(root => IsWithin(canonical, root)))
        {
            return StorageZoneKind.AutoManage;
        }

        if (IsWithin(canonical, Environment.GetFolderPath(Environment.SpecialFolder.MyPictures)))
        {
            return StorageZoneKind.IndexOnly;
        }

        var rootPath = Path.GetPathRoot(canonical);
        var systemRoot = Path.GetPathRoot(Environment.SystemDirectory);
        if (!string.IsNullOrWhiteSpace(rootPath)
            && !string.Equals(rootPath, systemRoot, StringComparison.OrdinalIgnoreCase))
        {
            return StorageZoneKind.IndexOnly;
        }

        return StorageZoneKind.Protected;
    }

    public static void Save(IReadOnlyList<StorageZone> zones)
    {
        CorePaths.EnsureDirectories();
        var json = JsonSerializer.Serialize(zones, JsonOptions);
        File.WriteAllText(CorePaths.StorageZonesPath, json);
    }

    private static IEnumerable<string> ProtectedRoots()
    {
        yield return Environment.GetFolderPath(Environment.SpecialFolder.Windows);
        yield return Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
        yield return Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86);
        yield return Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData);
        yield return Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        yield return Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
        var systemRoot = Path.GetPathRoot(Environment.SystemDirectory);
        if (!string.IsNullOrWhiteSpace(systemRoot))
        {
            yield return Path.Combine(systemRoot, "Recovery");
            yield return Path.Combine(systemRoot, "System Volume Information");
            yield return Path.Combine(systemRoot, "$Recycle.Bin");
        }
    }

    private static bool HasProtectedComponent(string path)
    {
        return path.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)
            .Any(component => ProtectedLeafNames.Contains(component, StringComparer.OrdinalIgnoreCase));
    }

    private static void Add(
        IDictionary<string, StorageZone> zones,
        string? path,
        StorageZoneKind kind,
        string reason)
    {
        var canonical = Canonical(path);
        if (canonical is null || !Directory.Exists(canonical)) return;
        if (zones.TryGetValue(canonical, out var existing) && existing.Kind >= kind) return;
        zones[canonical] = new StorageZone(canonical, kind, reason);
    }

    private static bool IsWithin(string path, string? root)
    {
        var canonicalRoot = Canonical(root);
        if (canonicalRoot is null) return false;
        return string.Equals(path, canonicalRoot, StringComparison.OrdinalIgnoreCase)
            || path.StartsWith(canonicalRoot + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase);
    }

    private static string? Canonical(string? path)
    {
        if (string.IsNullOrWhiteSpace(path)) return null;
        try
        {
            var full = Path.GetFullPath(path).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            return full.Length == 2 && full[1] == ':' ? full + Path.DirectorySeparatorChar : full;
        }
        catch
        {
            return null;
        }
    }
}
