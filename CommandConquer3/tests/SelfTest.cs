using System;
using System.Threading;
using Cnc3Trainer;

internal static class SelfTest
{
    public static int Main()
    {
        using (TrainerEngine engine = new TrainerEngine())
        {
            try
            {
                engine.Connect();
                Console.WriteLine("CONNECTED {0} {1} PID={2}", engine.GameName, engine.Version, engine.ProcessId);
                for (int i = 0; i < 600; i++)
                {
                    TickResult tick = engine.Tick();
                    if (tick.PlayerReady)
                    {
                        Console.WriteLine("PLAYER_READY money={0}", tick.Money);
                        return 0;
                    }
                    Thread.Sleep(100);
                }
                Console.WriteLine("CONNECTED_BUT_PLAYER_NOT_CAPTURED");
                return 2;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine(ex);
                return 1;
            }
        }
    }
}
