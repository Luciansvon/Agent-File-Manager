// BulkRenameSheet code-behind. Uses a virtualized XAML ItemTemplate for rows.
// Apply emits engine `renameFiles` IPC with the entries for which the
// "include" checkbox is on.

using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using FileID.IpcSchema;
using FileID.ViewModels;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;

namespace FileID.Views.Library;

public sealed class RenamePlan
{
    public long FileId { get; init; }
    public string CurrentPath { get; init; } = string.Empty;
    public string ProposedName { get; set; } = string.Empty;
    public bool? Include { get; set; } = true;
    public string CurrentName => Path.GetFileName(CurrentPath);
}

public sealed partial class BulkRenameSheet : UserControl
{
    internal readonly ObservableCollection<RenamePlan> _items = new();

    public BulkRenameSheet()
    {
        InitializeComponent();
    }

    public void SetPlan(IReadOnlyList<RenamePlan> plan)
    {
        _items.Clear();
        foreach (var p in plan)
        {
            p.ProposedName = PreserveOriginalExtension(p);
            _items.Add(p);
        }
        SelectionText.Text = plan.Count == 1
            ? "1 rename pending. Toggle off any row you don't want."
            : $"{plan.Count} renames pending. Toggle off any row you don't want.";

        RenameRepeater.ItemsSource = _items;
    }

    public async Task<bool> CommitAsync()
    {
        var entries = _items
            .Where(p => p.Include == true
                        && !string.IsNullOrWhiteSpace(p.ProposedName)
                        && !p.ProposedName.Contains('/')
                        && !p.ProposedName.Contains('\\'))
            .Select(p => new RenameEntry(p.FileId, PreserveOriginalExtension(p)))
            .ToArray();

        if (entries.Length == 0)
        {
            StatusText.Text = "Nothing to rename — every row is excluded or has an empty name.";
            return false;
        }

        StatusText.Text = "Renaming...";
        try
        {
            // Snapshot inverse names by id, but only push the successful subset
            // after the engine replies. A partial batch must never try to undo a
            // row that was not renamed.
            var inverseById = _items
                .Where(p => p.Include == true
                            && !string.IsNullOrWhiteSpace(p.ProposedName)
                            && !p.ProposedName.Contains('/')
                            && !p.ProposedName.Contains('\\'))
                .ToDictionary(p => p.FileId, p => System.IO.Path.GetFileName(p.CurrentPath));

            var result = await EngineClient.Instance.WaitForBulkActionResultAsync(
                "renameFiles",
                () => EngineClient.Instance.RenameFilesAsync(entries),
                TimeSpan.FromSeconds(30));

            var successfulInverse = result.Messages
                .Where(message => message.Ok && message.FileId is long id && inverseById.ContainsKey(id))
                .Select(message => new RenameEntry(message.FileId!.Value, inverseById[message.FileId.Value]))
                .ToArray();
            if (successfulInverse.Length > 0)
            {
                Services.UndoStack.Instance.Push(
                    $"rename {successfulInverse.Length} file{(successfulInverse.Length == 1 ? "" : "s")}",
                    async () =>
                    {
                        try
                        {
                            var undoResult = await EngineClient.Instance.WaitForBulkActionResultAsync(
                                "renameFiles",
                                () => EngineClient.Instance.RenameFilesAsync(successfulInverse),
                                TimeSpan.FromSeconds(30));
                            return undoResult.Failed == 0
                                && undoResult.Succeeded == (uint)successfulInverse.Length;
                        }
                        catch { return false; }
                    });
            }

            if (result.Failed > 0)
            {
                // Surface per-file engine failures (in use, permission, name
                // collision). Keep the sheet open so the user can fix + retry;
                // do NOT report success.
                var first = result.Messages.FirstOrDefault(m => !m.Ok)?.Message
                            ?? "see logs for details";
                var body = result.Succeeded > 0
                    ? $"Renamed {result.Succeeded}; {result.Failed} failed — {first}"
                    : $"{result.Failed} rename(s) failed — {first}";
                StatusText.Text = body;
                await ShowAlertAsync("Rename incomplete", body);
                return false;
            }

            StatusText.Text = $"Renamed {result.Succeeded} file(s).";
            return true;
        }
        catch (Exception ex)
        {
            var msg = Services.SqliteErrorTranslator.Humanize(ex);
            StatusText.Text = $"Failed: {msg}";
            await ShowAlertAsync("Rename failed", msg);
            return false;
        }
    }

    private static string PreserveOriginalExtension(RenamePlan plan)
    {
        var candidate = (plan.ProposedName ?? string.Empty).Trim();
        var originalExtension = Path.GetExtension(plan.CurrentPath);
        if (candidate.Length == 0 || originalExtension.Length == 0
            || candidate.EndsWith(originalExtension, StringComparison.OrdinalIgnoreCase))
        {
            return candidate;
        }
        var suppliedExtension = Path.GetExtension(candidate);
        if (suppliedExtension.Length > 0)
        {
            candidate = Path.GetFileNameWithoutExtension(candidate);
        }
        return candidate + originalExtension;
    }

    private async Task ShowAlertAsync(string title, string body)
    {
        // ContentDialog.ShowAsync can throw on a broken XamlRoot (mid-shutdown,
        // tab re-host). Catch + log so a failed alert never escalates.
        try
        {
            if (XamlRoot is null) return;
            var dialog = new ContentDialog
            {
                XamlRoot = XamlRoot,
                Title = title,
                Content = body,
                CloseButtonText = "OK",
                DefaultButton = ContentDialogButton.Close,
            };
            await dialog.ShowAsync();
        }
        catch
        {
            // Best-effort surfacing; the in-sheet StatusText still carries the message.
        }
    }
}
