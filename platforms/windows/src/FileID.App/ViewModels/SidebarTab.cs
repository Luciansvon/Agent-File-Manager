// SidebarTab -- the six top-level destinations the sidebar exposes.
//
//'s tab enum (Library / People / Cleanup /
// Deep Analyze / Restructure / Settings). Each carries an id (persisted
// in app-settings.json), a label (displayed), and a Segoe Fluent glyph.

namespace FileID.ViewModels;

internal sealed record SidebarTab(string Id, string Label, string IconGlyph)
{
    public static SidebarTab Library => new("library", "Search", "");
    public static SidebarTab People => new("people", "People", ""); // People
    public static SidebarTab Cleanup => new("cleanup", "Cleanup", ""); // Delete
    public static SidebarTab DeepAnalyze => new("deepanalyze", "AI Rename", "");
    public static SidebarTab Restructure => new("restructure", "Inbox / Organize", "");
    public static SidebarTab Settings => new("settings", "Settings", ""); // Setting

    public static IReadOnlyList<SidebarTab> All { get; } = new[]
    {
        Library, Restructure, DeepAnalyze, Settings,
    };

    public static SidebarTab ById(string id) =>
        All.FirstOrDefault(t => t.Id == id) ?? Library;
}
