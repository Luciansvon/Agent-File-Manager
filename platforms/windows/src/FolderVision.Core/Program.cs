using System.Threading;

namespace FolderVision.Core;

internal static class Program
{
    private const string MutexName = "Local\\FolderVision-Core-{F54A9E4A-8B87-4A72-9E2B-66ECA9B1C90A}";

    [STAThread]
    private static int Main(string[] args)
    {
        if (args.Contains("--self-test", StringComparer.OrdinalIgnoreCase))
        {
            return CoreSelfTest.Run();
        }

        // Safety gate during the M1 transport migration. The executable is
        // packaged now, but must not own a second engine until FileID.App has
        // switched from direct stdio spawning to the Core named pipe.
        if (!args.Contains("--activate", StringComparer.OrdinalIgnoreCase))
        {
            return 2;
        }

        using var mutex = new Mutex(initiallyOwned: true, MutexName, out var createdNew);
        if (!createdNew) return 0;

        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        using var context = new TrayApplicationContext();
        Application.Run(context);
        return 0;
    }
}
