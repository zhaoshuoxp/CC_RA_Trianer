using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Security.Cryptography;

namespace Cnc3Trainer
{
    internal sealed class ProcessMemory : IDisposable
    {
        internal readonly Process Process;
        internal readonly IntPtr Handle;
        internal readonly int BaseAddress;
        internal readonly int ModuleSize;
        internal readonly string FilePath;
        internal readonly string FileVersion;
        internal readonly string Sha256;

        internal ProcessMemory(Process process)
        {
            Process = process;
            uint access = NativeMethods.PROCESS_QUERY_INFORMATION | NativeMethods.PROCESS_VM_READ |
                          NativeMethods.PROCESS_VM_WRITE | NativeMethods.PROCESS_VM_OPERATION;
            Handle = NativeMethods.OpenProcess(access, false, process.Id);
            if (Handle == IntPtr.Zero) throw new Win32Exception(System.Runtime.InteropServices.Marshal.GetLastWin32Error());
            BaseAddress = process.MainModule.BaseAddress.ToInt32();
            ModuleSize = process.MainModule.ModuleMemorySize;
            FilePath = process.MainModule.FileName;
            FileVersion = process.MainModule.FileVersionInfo.FileVersion.Trim();
            using (FileStream stream = File.OpenRead(FilePath))
            using (SHA256 sha = SHA256.Create())
                Sha256 = BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "");
        }

        internal static Process FindGameProcess()
        {
            foreach (Process process in Process.GetProcesses())
            {
                string name;
                try { name = process.ProcessName.ToLowerInvariant(); }
                catch { continue; }
                if (name.Contains("cnc3game") || name.Contains("cnc3ep1")) return process;
            }
            return null;
        }

        internal byte[] Read(int address, int count)
        {
            byte[] buffer = new byte[count]; IntPtr read;
            if (!NativeMethods.ReadProcessMemory(Handle, new IntPtr(address), buffer, new IntPtr(count), out read) || read.ToInt32() != count)
                throw new Win32Exception(System.Runtime.InteropServices.Marshal.GetLastWin32Error(), "读取游戏内存失败");
            return buffer;
        }

        internal int ReadInt32(int address) { return BitConverter.ToInt32(Read(address, 4), 0); }

        internal void Write(int address, byte[] bytes)
        {
            IntPtr written;
            if (!NativeMethods.WriteProcessMemory(Handle, new IntPtr(address), bytes, new IntPtr(bytes.Length), out written) || written.ToInt32() != bytes.Length)
                throw new Win32Exception(System.Runtime.InteropServices.Marshal.GetLastWin32Error(), "写入游戏内存失败");
        }

        internal void WriteInt32(int address, int value) { Write(address, BitConverter.GetBytes(value)); }
        internal void WriteFloat(int address, float value) { Write(address, BitConverter.GetBytes(value)); }

        internal void WriteCode(int address, byte[] bytes)
        {
            uint oldProtect;
            if (!NativeMethods.VirtualProtectEx(Handle, new IntPtr(address), new IntPtr(bytes.Length), NativeMethods.PAGE_EXECUTE_READWRITE, out oldProtect))
                throw new Win32Exception(System.Runtime.InteropServices.Marshal.GetLastWin32Error());
            try { Write(address, bytes); NativeMethods.FlushInstructionCache(Handle, new IntPtr(address), new IntPtr(bytes.Length)); }
            finally { uint ignored; NativeMethods.VirtualProtectEx(Handle, new IntPtr(address), new IntPtr(bytes.Length), oldProtect, out ignored); }
        }

        internal int Allocate(int size)
        {
            IntPtr result = NativeMethods.VirtualAllocEx(Handle, IntPtr.Zero, new IntPtr(size), NativeMethods.MEM_COMMIT | NativeMethods.MEM_RESERVE, NativeMethods.PAGE_EXECUTE_READWRITE);
            if (result == IntPtr.Zero) throw new Win32Exception(System.Runtime.InteropServices.Marshal.GetLastWin32Error(), "无法分配游戏内存");
            long value = result.ToInt64();
            if (value > int.MaxValue) throw new InvalidOperationException("游戏内存分配超出 32 位地址范围");
            return (int)value;
        }

        internal void Free(int address)
        {
            if (address != 0) NativeMethods.VirtualFreeEx(Handle, new IntPtr(address), IntPtr.Zero, NativeMethods.MEM_RELEASE);
        }

        internal byte[] ReadModule() { return Read(BaseAddress, ModuleSize); }

        internal static byte?[] ParsePattern(string value)
        {
            string[] parts = value.Split(new char[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
            byte?[] pattern = new byte?[parts.Length];
            for (int i = 0; i < parts.Length; i++) pattern[i] = parts[i].Contains("?") ? (byte?)null : Convert.ToByte(parts[i], 16);
            return pattern;
        }

        internal static List<int> FindPattern(byte[] data, byte?[] pattern)
        {
            List<int> hits = new List<int>();
            for (int i = 0; i <= data.Length - pattern.Length; i++)
            {
                int j = 0;
                for (; j < pattern.Length; j++) if (pattern[j].HasValue && pattern[j].Value != data[i + j]) break;
                if (j == pattern.Length) hits.Add(i);
            }
            return hits;
        }

        internal int FindUnique(byte[] module, string pattern, string label)
        {
            List<int> hits = FindPattern(module, ParsePattern(pattern));
            if (hits.Count != 1) throw new InvalidOperationException(label + " 特征签名应唯一，实际找到 " + hits.Count + " 处");
            return BaseAddress + hits[0];
        }

        public void Dispose() { if (Handle != IntPtr.Zero) NativeMethods.CloseHandle(Handle); }
    }
}
