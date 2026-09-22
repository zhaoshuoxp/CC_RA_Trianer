using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

internal static class MemoryProbe
{
    const uint PROCESS_QUERY_INFORMATION = 0x0400;
    const uint PROCESS_VM_READ = 0x0010;
    const uint PROCESS_VM_WRITE = 0x0020;
    const uint PROCESS_VM_OPERATION = 0x0008;
    const uint MEM_COMMIT = 0x1000;
    const uint PAGE_GUARD = 0x100;
    const uint PAGE_NOACCESS = 0x01;

    [StructLayout(LayoutKind.Sequential)]
    struct MEMORY_BASIC_INFORMATION
    {
        public IntPtr BaseAddress;
        public IntPtr AllocationBase;
        public uint AllocationProtect;
        public UIntPtr RegionSize;
        public uint State;
        public uint Protect;
        public uint Type;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct RECT { public int Left, Top, Right, Bottom; }

    delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [DllImport("kernel32.dll", SetLastError = true)] static extern IntPtr OpenProcess(uint access, bool inherit, int pid);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool ReadProcessMemory(IntPtr process, IntPtr address, byte[] buffer, IntPtr size, out IntPtr read);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool WriteProcessMemory(IntPtr process, IntPtr address, byte[] buffer, IntPtr size, out IntPtr written);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
    [DllImport("kernel32.dll")] static extern IntPtr VirtualQueryEx(IntPtr process, IntPtr address, out MEMORY_BASIC_INFORMATION info, IntPtr length);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumWindowsProc callback, IntPtr lParam);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
    [DllImport("user32.dll")] static extern bool PrintWindow(IntPtr hWnd, IntPtr hdc, uint flags);

    static Process FindGame()
    {
        string[] names = { "cnc3game", "cnc3game.dat", "cnc3ep1", "cnc3ep1.dat" };
        foreach (string name in names)
        {
            Process[] ps = Process.GetProcessesByName(name);
            if (ps.Length > 0) return ps[0];
        }
        throw new InvalidOperationException("C&C 3 game process was not found.");
    }

    static IntPtr OpenGame(Process p, bool write)
    {
        uint access = PROCESS_QUERY_INFORMATION | PROCESS_VM_READ;
        if (write) access |= PROCESS_VM_WRITE | PROCESS_VM_OPERATION;
        IntPtr h = OpenProcess(access, false, p.Id);
        if (h == IntPtr.Zero) throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
        return h;
    }

    static IEnumerable<MEMORY_BASIC_INFORMATION> Regions(IntPtr h)
    {
        long address = 0;
        int mbiSize = Marshal.SizeOf(typeof(MEMORY_BASIC_INFORMATION));
        while (address < 0x7fff0000L)
        {
            MEMORY_BASIC_INFORMATION mbi;
            if (VirtualQueryEx(h, new IntPtr(address), out mbi, new IntPtr(mbiSize)) == IntPtr.Zero) break;
            long size = (long)mbi.RegionSize.ToUInt64();
            if (size <= 0) break;
            if (mbi.State == MEM_COMMIT && (mbi.Protect & (PAGE_GUARD | PAGE_NOACCESS)) == 0)
                yield return mbi;
            address = mbi.BaseAddress.ToInt64() + size;
        }
    }

    static void Modules(Process p)
    {
        Console.WriteLine("Process {0} PID={1} Path={2}", p.ProcessName, p.Id, p.MainModule.FileName);
        foreach (ProcessModule m in p.Modules)
            Console.WriteLine("0x{0:X8} 0x{1:X8} {2}", m.BaseAddress.ToInt64(), m.ModuleMemorySize, m.FileName);
        Console.WriteLine("Windows:");
        EnumWindows(delegate(IntPtr hwnd, IntPtr ignored)
        {
            uint pid;
            GetWindowThreadProcessId(hwnd, out pid);
            if (pid == (uint)p.Id)
            {
                StringBuilder title = new StringBuilder(512);
                GetWindowText(hwnd, title, title.Capacity);
                RECT r; GetWindowRect(hwnd, out r);
                Console.WriteLine("0x{0:X} visible={1} rect={2},{3},{4},{5} title={6}", hwnd.ToInt64(), IsWindowVisible(hwnd), r.Left, r.Top, r.Right, r.Bottom, title);
            }
            return true;
        }, IntPtr.Zero);
    }

    static void Screenshot(Process p, string file)
    {
        IntPtr target = IntPtr.Zero;
        RECT targetRect = new RECT();
        EnumWindows(delegate(IntPtr hwnd, IntPtr ignored)
        {
            uint pid; GetWindowThreadProcessId(hwnd, out pid);
            RECT r; GetWindowRect(hwnd, out r);
            if (pid == (uint)p.Id && IsWindowVisible(hwnd) && r.Right > r.Left && r.Bottom > r.Top)
            { target = hwnd; targetRect = r; return false; }
            return true;
        }, IntPtr.Zero);
        if (target == IntPtr.Zero) throw new InvalidOperationException("No visible game window found.");
        int width = targetRect.Right - targetRect.Left, height = targetRect.Bottom - targetRect.Top;
        using (Bitmap bmp = new Bitmap(width, height, PixelFormat.Format32bppArgb))
        using (Graphics g = Graphics.FromImage(bmp))
        {
            IntPtr hdc = g.GetHdc();
            bool ok = PrintWindow(target, hdc, 2);
            g.ReleaseHdc(hdc);
            bmp.Save(file, ImageFormat.Png);
            Console.WriteLine("Saved {0} ({1}x{2}, PrintWindow={3})", file, width, height, ok);
        }
    }

    static void ScanInt(Process p, int value, string file)
    {
        IntPtr h = OpenGame(p, false);
        try
        {
            List<string> hits = new List<string>();
            byte[] needle = BitConverter.GetBytes(value);
            foreach (MEMORY_BASIC_INFORMATION region in Regions(h))
            {
                long size64 = (long)region.RegionSize.ToUInt64();
                if (size64 > 256 * 1024 * 1024) continue;
                int size = (int)size64;
                byte[] buffer = new byte[size]; IntPtr read;
                if (!ReadProcessMemory(h, region.BaseAddress, buffer, new IntPtr(size), out read)) continue;
                int count = (int)read.ToInt64();
                for (int i = 0; i <= count - 4; i += 4)
                    if (buffer[i] == needle[0] && buffer[i + 1] == needle[1] && buffer[i + 2] == needle[2] && buffer[i + 3] == needle[3])
                        hits.Add((region.BaseAddress.ToInt64() + i).ToString("X8"));
            }
            File.WriteAllLines(file, hits.ToArray());
            Console.WriteLine("Found {0} aligned int32 matches for {1}; saved {2}", hits.Count, value, file);
        }
        finally { CloseHandle(h); }
    }

    static void FilterInt(Process p, int value, string input, string output)
    {
        IntPtr h = OpenGame(p, false);
        try
        {
            List<string> hits = new List<string>();
            byte[] buffer = new byte[4]; IntPtr read;
            foreach (string line in File.ReadAllLines(input))
            {
                long address;
                if (!long.TryParse(line, System.Globalization.NumberStyles.HexNumber, null, out address)) continue;
                if (ReadProcessMemory(h, new IntPtr(address), buffer, new IntPtr(4), out read) && read.ToInt64() == 4 && BitConverter.ToInt32(buffer, 0) == value)
                    hits.Add(line);
            }
            File.WriteAllLines(output, hits.ToArray());
            Console.WriteLine("Kept {0} matches for {1}; saved {2}", hits.Count, value, output);
        }
        finally { CloseHandle(h); }
    }

    static void WriteInt(Process p, long address, int value)
    {
        IntPtr h = OpenGame(p, true);
        try
        {
            byte[] buffer = BitConverter.GetBytes(value); IntPtr written;
            if (!WriteProcessMemory(h, new IntPtr(address), buffer, new IntPtr(4), out written) || written.ToInt64() != 4)
                throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
            Console.WriteLine("Wrote {0} to 0x{1:X8}", value, address);
        }
        finally { CloseHandle(h); }
    }

    static byte?[] ParsePattern(string pattern)
    {
        string[] parts = pattern.Split(new char[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
        byte?[] result = new byte?[parts.Length];
        for (int i = 0; i < parts.Length; i++)
            result[i] = parts[i].Contains("?") ? (byte?)null : Convert.ToByte(parts[i], 16);
        return result;
    }

    static List<int> FindPattern(byte[] data, int count, byte?[] pattern)
    {
        List<int> hits = new List<int>();
        for (int i = 0; i <= count - pattern.Length; i++)
        {
            int j = 0;
            for (; j < pattern.Length; j++) if (pattern[j].HasValue && data[i + j] != pattern[j].Value) break;
            if (j == pattern.Length) hits.Add(i);
        }
        return hits;
    }

    static void Aob(Process p, string patternText)
    {
        byte?[] pattern = ParsePattern(patternText);
        ProcessModule m = p.MainModule;
        IntPtr h = OpenGame(p, false);
        try
        {
            byte[] data = new byte[m.ModuleMemorySize]; IntPtr read;
            if (!ReadProcessMemory(h, m.BaseAddress, data, new IntPtr(data.Length), out read))
                throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
            List<int> hits = FindPattern(data, (int)read.ToInt64(), pattern);
            Console.WriteLine("{0} matches", hits.Count);
            foreach (int hit in hits) Console.WriteLine("0x{0:X8} (+0x{1:X})", m.BaseAddress.ToInt64() + hit, hit);
        }
        finally { CloseHandle(h); }
    }

    static void FileAob(string file, string patternText)
    {
        byte[] data = File.ReadAllBytes(file); byte?[] pattern = ParsePattern(patternText);
        List<int> hits = FindPattern(data, data.Length, pattern);
        Console.WriteLine("{0} matches in {1}", hits.Count, file);
        foreach (int hit in hits) Console.WriteLine("file+0x{0:X}", hit);
    }

    public static int Main(string[] args)
    {
        try
        {
            Process p = FindGame();
            if (args.Length == 0 || args[0] == "modules") Modules(p);
            else if (args[0] == "screenshot" && args.Length == 2) Screenshot(p, args[1]);
            else if (args[0] == "scan" && args.Length == 3) ScanInt(p, int.Parse(args[1]), args[2]);
            else if (args[0] == "filter" && args.Length == 4) FilterInt(p, int.Parse(args[1]), args[2], args[3]);
            else if (args[0] == "write" && args.Length == 3) WriteInt(p, Convert.ToInt64(args[1], 16), int.Parse(args[2]));
            else if (args[0] == "aob" && args.Length == 2) Aob(p, args[1]);
            else if (args[0] == "fileaob" && args.Length == 3) FileAob(args[1], args[2]);
            else throw new ArgumentException("Usage: modules | screenshot <png> | scan <int> <file> | filter <int> <input> <output> | write <hex-address> <int> | aob <pattern> | fileaob <file> <pattern>");
            return 0;
        }
        catch (Exception ex) { Console.Error.WriteLine(ex); return 1; }
    }
}
