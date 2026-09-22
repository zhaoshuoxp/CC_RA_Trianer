using System;
using Cnc3Trainer;

internal static class UiSmoke
{
    [STAThread]
    public static int Main()
    {
        using (MainForm form = new MainForm())
        {
            Console.WriteLine("UI_OK {0}x{1}", form.ClientSize.Width, form.ClientSize.Height);
        }
        return 0;
    }
}
