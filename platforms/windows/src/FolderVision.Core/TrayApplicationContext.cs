using System.Diagnostics;
using System.Drawing;

namespace FolderVision.Core;

internal sealed class TrayApplicationContext : ApplicationContext
{
    private readonly EngineBroker _broker = new();
    private readonly NotifyIcon _tray;
    private readonly ToolStripMenuItem _pauseItem;
    private readonly BackgroundIndexService _backgroundIndex;

    public TrayApplicationContext()
    {
        CorePaths.EnsureDirectories();
        StartupRegistration.EnsureRegistered();
        var zones = StorageZoneDiscovery.Discover();
        StorageZoneDiscovery.Save(zones);

        var menu = new ContextMenuStrip();
        menu.Items.Add("Open Folder Vision", null, (_, _) => OpenUi());
        _pauseItem = new ToolStripMenuItem();
        _pauseItem.Click += (_, _) => TogglePause();
        menu.Items.Add(_pauseItem);
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add("Exit Folder Vision Core", null, (_, _) => ExitThread());

        _tray = new NotifyIcon
        {
            Icon = SystemIcons.Application,
            Text = "Folder Vision - Active",
            ContextMenuStrip = menu,
            Visible = true,
        };
        _tray.DoubleClick += (_, _) => OpenUi();
        SyncPauseText();
        _broker.Start();
        _backgroundIndex = new BackgroundIndexService(_broker, zones);
        _backgroundIndex.Start();
        CoreLog.Write($"core started zones={zones.Count} paused={AutomationState.IsPaused}");
    }

    private void OpenUi()
    {
        var path = CorePaths.UiExecutable;
        if (!File.Exists(path))
        {
            CoreLog.Write("UI executable is unavailable");
            return;
        }
        Process.Start(new ProcessStartInfo(path) { UseShellExecute = true });
    }

    private void TogglePause()
    {
        AutomationState.SetPaused(!AutomationState.IsPaused);
        _backgroundIndex.SetAutomationEnabled(!AutomationState.IsPaused);
        if (!AutomationState.IsPaused)
        {
            _backgroundIndex.RequestCatchUp();
        }
        SyncPauseText();
        _tray.Text = AutomationState.IsPaused
            ? "Folder Vision - Automation paused"
            : "Folder Vision - Active";
    }

    private void SyncPauseText()
    {
        _pauseItem.Text = AutomationState.IsPaused ? "Resume Automation" : "Pause Automation";
    }

    protected override void ExitThreadCore()
    {
        _tray.Visible = false;
        _tray.Dispose();
        _backgroundIndex.DisposeAsync().AsTask().GetAwaiter().GetResult();
        _broker.DisposeAsync().AsTask().GetAwaiter().GetResult();
        CoreLog.Write("core stopped");
        base.ExitThreadCore();
    }
}
