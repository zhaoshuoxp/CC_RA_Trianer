using System;
using System.Collections.Generic;
using System.Diagnostics;

namespace Cnc3Trainer
{
    internal sealed class TickResult
    {
        internal bool PlayerReady;
        internal bool SessionChanged;
        internal int Money;
    }

    internal sealed class TrainerEngine : IDisposable
    {
        sealed class Patch
        {
            internal int Address;
            internal byte[] Original;
            internal byte[] Replacement;
        }

        const int VAR_PLAYER = 0x00;
        const int VAR_COMMON = 0x04;
        const int VAR_NAME = 0x08;
        const int VAR_POBJ = 0x0C;
        const int FLAG_GOD = 0x10;
        const int FLAG_SCENARIO = 0x14;
        const int FLAG_SHIELD = 0x18;
        const int FLAG_QUICK = 0x1C;
        const int FLAG_GLOBAL = 0x20;
        const int VAR_MINPROG = 0x24;

        ProcessMemory memory;
        GameProfile profile;
        int remote;
        int lastPlayer;
        int playerManagerGlobal;
        readonly List<Patch> patches = new List<Patch>();

        bool minimumMoney;
        bool unlimitedPower;
        int minimumTarget = 50000;

        internal bool IsConnected { get { return memory != null; } }
        internal bool PlayerReady { get { return lastPlayer != 0; } }
        internal string GameName { get { return profile == null ? "" : profile.DisplayName; } }
        internal string Version { get { return memory == null ? "" : memory.FileVersion; } }
        internal string Hash { get { return memory == null ? "" : memory.Sha256; } }
        internal int ProcessId { get { return memory == null ? 0 : memory.Process.Id; } }
        internal bool SupportsGlobalResource { get { return profile != null && profile.Kind == GameKind.KanesWrath; } }
        internal bool MinimumMoney { get { return minimumMoney; } set { minimumMoney = value; } }
        internal bool UnlimitedPower { get { return unlimitedPower; } set { unlimitedPower = value; } }
        internal int MinimumTarget { get { return minimumTarget; } set { minimumTarget = Math.Max(0, value); } }

        internal void Connect()
        {
            if (IsConnected) return;
            Process process = ProcessMemory.FindGameProcess();
            if (process == null) throw new InvalidOperationException("未找到游戏。请先进入《泰伯利亚战争》或《凯恩之怒》的单人地图。");
            GameProfile selected = GameProfile.ForProcessName(process.ProcessName);
            if (selected == null) throw new InvalidOperationException("发现的进程不是受支持的 C&C3 游戏进程。");

            ProcessMemory opened = null;
            try
            {
                opened = new ProcessMemory(process);
                if (!GameProfile.SupportedHashes.Contains(opened.Sha256))
                    throw new InvalidOperationException("此游戏文件尚未验证，已拒绝写入。\r\n版本: " + opened.FileVersion + "\r\nSHA-256: " + opened.Sha256);

                byte[] module = opened.ReadModule();
                int playerSite = opened.FindUnique(module, selected.PlayerPattern, "玩家资源");
                byte[] managerInstruction = opened.Read(playerSite - 0x23, 2);
                if (managerInstruction[0] != 0x8B || managerInstruction[1] != 0x0D)
                    throw new InvalidOperationException("玩家管理器入口不匹配，已拒绝连接。");
                int managerGlobal = opened.ReadInt32(playerSite - 0x21);
                int damageSite = opened.FindUnique(module, selected.DamagePattern, "伤害处理");
                int unitSite = opened.FindUnique(module, selected.UnitPattern, "单位归属");
                int shieldSite = opened.FindUnique(module, selected.ShieldPattern, "护盾处理");
                int quickSite = opened.FindUnique(module, selected.QuickPattern, "生产进度");
                int fanatic = opened.FindUnique(module, selected.FanaticPattern, "狂热者行为");
                int grenade = opened.FindUnique(module, selected.GrenadePattern, "榴弹兵行为");
                int globalSite = 0;
                if (selected.Kind == GameKind.KanesWrath)
                    globalSite = opened.FindUnique(module, selected.GlobalPattern, "全球征服资金");

                memory = opened; opened = null; profile = selected; playerManagerGlobal = managerGlobal;
                remote = memory.Allocate(0x1000);
                memory.WriteFloat(remote + VAR_MINPROG, 100.0f);

                InstallPlayerHook(playerSite, remote + 0x100);
                InstallGodHook(damageSite, remote + 0x200);
                InstallUnitHook(unitSite, fanatic, grenade, remote + 0x300);
                InstallShieldHook(shieldSite, remote + 0x600);
                InstallQuickHook(quickSite, remote + 0x800);
                if (globalSite != 0) InstallGlobalHook(globalSite, remote + 0xA00);
            }
            catch
            {
                try { Disconnect(); } catch { }
                if (opened != null) opened.Dispose();
                throw;
            }
        }

        void InstallPlayerHook(int site, int codeAddress)
        {
            X86Builder b = new X86Builder(codeAddress);
            b.Emit(0x89, 0x3D); b.EmitInt32(remote + VAR_PLAYER);          // mov [player],edi
            b.Emit(0x8B, 0x87); b.EmitInt32(0xE8);                       // mov eax,[edi+e8]
            b.Emit(0xA3); b.EmitInt32(remote + VAR_COMMON);              // mov [common],eax
            b.Emit(0x8B, 0x47, 0x40);                                    // mov eax,[edi+40]
            b.Emit(0xA3); b.EmitInt32(remote + VAR_NAME);                // mov [name],eax
            b.Emit(0x8B, 0x47, 0x60, 0x8B, 0x48, 0x10);                  // original
            b.JmpAbsolute(site + 6);
            InstallHook(site, 6, codeAddress, b.ToArray());
        }

        void InstallGodHook(int site, int codeAddress)
        {
            X86Builder b = new X86Builder(codeAddress);
            b.Emit(0x56);                                                 // push esi
            b.Emit(0x8B, 0x45, 0x08, 0x85, 0xC0);                        // mov eax,[ebp+8]; test eax,eax
            b.Jcc(0x89, "exit");                                         // jns exit
            b.Emit(0x3B, 0x0D); b.EmitInt32(remote + VAR_POBJ);          // cmp ecx,[pObj]
            b.Jcc(0x85, "exit");
            b.Emit(0x83, 0x3D); b.EmitInt32(remote + FLAG_GOD); b.Emit(0x00);
            b.Jcc(0x84, "exit");
            b.Emit(0xC7, 0x45, 0x08, 0, 0, 0, 0);                        // damage=0
            b.Emit(0x8B, 0x41, 0x10, 0x89, 0x41, 0x08);                  // hp=current max
            b.Emit(0xA3); b.EmitInt32(remote + VAR_POBJ);                // invalidate pointer
            b.Label("exit");
            b.Emit(0x5E, 0xF3, 0x0F, 0x10, 0x5D, 0x08);                  // pop esi; original
            b.JmpAbsolute(site + 5);
            InstallHook(site, 5, codeAddress, b.ToArray());
        }

        void InstallUnitHook(int site, int fanatic, int grenade, int codeAddress)
        {
            X86Builder b = new X86Builder(codeAddress);
            EmitMovEcxEsi(b, profile.UnitHpOffset);
            b.Emit(0x85, 0xC9); b.Jcc(0x84, "exit");
            b.Emit(0x8B, 0x4E, 0x04, 0x85, 0xC9); b.Jcc(0x84, "exit");
            b.Emit(0x8B, 0x49, 0x24, 0x85, 0xC9); b.Jcc(0x84, "exit");
            EmitMovEcxEsi(b, profile.UnitOwnerOffset);
            b.Emit(0x3B, 0x0D); b.EmitInt32(remote + VAR_COMMON);
            b.Jcc(0x84, "owned");
            b.Emit(0x83, 0x3D); b.EmitInt32(remote + FLAG_SCENARIO); b.Emit(0x00);
            b.Jcc(0x84, "exit");
            b.Emit(0x50, 0x53, 0x52);                                    // push eax,ebx,edx
            b.Emit(0x8B, 0x1D); b.EmitInt32(remote + VAR_NAME);
            b.Emit(0x8B, 0x96); b.EmitInt32(profile.UnitNameOffset);
            b.Emit(0x85, 0xDB); b.Jcc(0x84, "nameFailed");              // null player name
            b.Emit(0x85, 0xD2); b.Jcc(0x84, "nameFailed");              // null owner name
            b.Emit(0xB9); b.EmitInt32(32);
            b.Label("nameLoop");
            b.Emit(0x8A, 0x03);                                          // mov al,[ebx]
            b.Emit(0x3A, 0x02); b.Jcc(0x85, "nameFailed");
            b.Emit(0x84, 0xC0); b.Jcc(0x84, "nameMatched");             // both reached NUL
            b.Emit(0x43, 0x42, 0x49);                                    // inc ebx; inc edx; dec ecx
            b.Jcc(0x85, "nameLoop");
            b.Label("nameMatched");
            b.Emit(0x5A, 0x5B, 0x58);                                    // pop edx,ebx,eax
            b.Jmp("owned");
            b.Label("nameFailed");
            b.Emit(0x5A, 0x5B, 0x58);                                    // pop edx,ebx,eax
            b.Jmp("exit");
            b.Label("owned");
            EmitMovEcxEsi(b, profile.UnitMarkerOffset);
            b.Emit(0x85, 0xC9); b.Jcc(0x84, "exit");
            if (profile.Kind == GameKind.TiberiumWars)
            {
                b.Emit(0x8B, 0x4C, 0x24, 0x10, 0x81, 0xF9); b.EmitInt32(fanatic); b.Jcc(0x84, "exit");
                b.Emit(0x81, 0xF9); b.EmitInt32(grenade); b.Jcc(0x84, "exit");
            }
            EmitMovEcxEsi(b, profile.UnitHpOffset);
            b.Emit(0x89, 0x0D); b.EmitInt32(remote + VAR_POBJ);
            b.Label("exit");
            EmitMovEcxEsi(b, profile.UnitHpOffset);                       // original
            b.JmpAbsolute(site + 6);
            InstallHook(site, 6, codeAddress, b.ToArray());
        }

        static void EmitMovEcxEsi(X86Builder b, int offset)
        {
            b.Emit(0x8B, 0x8E); b.EmitInt32(offset);
        }

        void InstallShieldHook(int site, int codeAddress)
        {
            X86Builder b = new X86Builder(codeAddress);
            b.Emit(0x51);                                                 // push ecx
            b.Emit(0x83, 0x3D); b.EmitInt32(remote + FLAG_SHIELD); b.Emit(0x00); b.Jcc(0x84, "exit");
            b.Emit(0x8B, 0x7B, 0x0C, 0x85, 0xFF); b.Jcc(0x84, "exit");
            b.Emit(0x8B, 0x8F); b.EmitInt32(profile.UnitOwnerOffset);
            b.Emit(0x3B, 0x0D); b.EmitInt32(remote + VAR_COMMON); b.Jcc(0x85, "exit");
            b.Emit(0x8B, 0x8F); b.EmitInt32(profile.UnitMarkerOffset);
            b.Emit(0x85, 0xC9); b.Jcc(0x84, "exit");
            b.Emit(0x8B, 0x7B, 0x08, 0x85, 0xFF); b.Jcc(0x84, "exit");
            b.Emit(0x8B, 0x4F, (byte)profile.ShieldMaxOffset);
            b.Emit(0x89, 0x8E); b.EmitInt32(0x114);
            b.Emit(0x31, 0xC9, 0x89, 0x4D, 0xFC);
            b.Label("exit");
            b.Emit(0x59, 0x8D, 0xBE, 0x14, 0x01, 0x00, 0x00);             // pop ecx; original
            b.JmpAbsolute(site + 6);
            InstallHook(site, 6, codeAddress, b.ToArray());
        }

        void InstallQuickHook(int site, int codeAddress)
        {
            X86Builder b = new X86Builder(codeAddress);
            b.Emit(0xF3, 0x0F, 0x58, 0x4B, 0x1C);                        // original addss
            b.Emit(0x83, 0x3D); b.EmitInt32(remote + FLAG_QUICK); b.Emit(0x00); b.Jcc(0x84, "exit");
            b.Emit(0xA1); b.EmitInt32(remote + VAR_PLAYER);
            b.Emit(0x39, 0xC7); b.Jcc(0x85, "exit");
            b.Emit(0xF3, 0x0F, 0x5F, 0x0D); b.EmitInt32(remote + VAR_MINPROG);
            b.Label("exit"); b.JmpAbsolute(site + 5);
            InstallHook(site, 5, codeAddress, b.ToArray());
        }

        void InstallGlobalHook(int site, int codeAddress)
        {
            X86Builder b = new X86Builder(codeAddress);
            b.Emit(0x8B, 0x40, 0x08, 0x8B, 0x78, 0x74);                  // original
            b.Emit(0x83, 0x3D); b.EmitInt32(remote + FLAG_GLOBAL); b.Emit(0x00); b.Jcc(0x84, "exit");
            b.Emit(0x81, 0xFF); b.EmitInt32(1000000); b.Jcc(0x8D, "exit"); // jge
            b.Emit(0xBF); b.EmitInt32(1000000);
            b.Emit(0x89, 0x78, 0x74);
            b.Label("exit"); b.JmpAbsolute(site + 6);
            InstallHook(site, 6, codeAddress, b.ToArray());
        }

        void InstallHook(int site, int length, int codeAddress, byte[] code)
        {
            memory.Write(codeAddress, code);
            byte[] original = memory.Read(site, length);
            byte[] replacement = new byte[length];
            replacement[0] = 0xE9;
            Buffer.BlockCopy(BitConverter.GetBytes(codeAddress - (site + 5)), 0, replacement, 1, 4);
            for (int i = 5; i < length; i++) replacement[i] = 0x90;
            memory.WriteCode(site, replacement);
            patches.Add(new Patch { Address = site, Original = original, Replacement = replacement });
        }

        internal TickResult Tick()
        {
            TickResult result = new TickResult();
            if (!IsConnected) return result;
            if (memory.Process.HasExited) { Disconnect(); return result; }
            int player = memory.ReadInt32(remote + VAR_PLAYER);
            int common, name;
            int directPlayer;
            if (TryReadActivePlayer(out directPlayer, out common, out name))
            {
                player = directPlayer;
                if (memory.ReadInt32(remote + VAR_PLAYER) != player) memory.WriteInt32(remote + VAR_PLAYER, player);
                if (memory.ReadInt32(remote + VAR_COMMON) != common) memory.WriteInt32(remote + VAR_COMMON, common);
                if (memory.ReadInt32(remote + VAR_NAME) != name) memory.WriteInt32(remote + VAR_NAME, name);
            }
            if (!IsPointer(player))
            {
                if (lastPlayer != 0) { DisableAll(); lastPlayer = 0; result.SessionChanged = true; }
                return result;
            }
            if (lastPlayer != 0 && player != lastPlayer)
            {
                DisableAll();
                result.SessionChanged = true;
            }
            lastPlayer = player;
            result.PlayerReady = true;
            int resource = memory.ReadInt32(player + 0x60);
            if (resource > 0x10000 && resource < 0x7FFF0000)
            {
                int cash = memory.ReadInt32(resource + 0x04);
                int stored = memory.ReadInt32(resource + 0x10);
                long total = (long)cash + stored;
                if (minimumMoney && total < minimumTarget)
                {
                    cash += (int)(minimumTarget - total);
                    memory.WriteInt32(resource + 0x04, cash);
                    total = minimumTarget;
                }
                result.Money = total > int.MaxValue ? int.MaxValue : (int)total;
            }
            if (unlimitedPower)
            {
                int energy = memory.ReadInt32(player + 0x80);
                if (energy > 0x10000 && energy < 0x7FFF0000) memory.WriteInt32(energy + 0x08, 0);
            }
            return result;
        }

        bool TryReadActivePlayer(out int player, out int common, out int name)
        {
            player = common = name = 0;
            try
            {
                int manager = memory.ReadInt32(playerManagerGlobal);
                if (!IsPointer(manager)) return false;
                int primary = memory.ReadInt32(manager + 0x1C);
                if (!IsPointer(primary)) return true;
                byte[] firstFlag = memory.Read(primary + profile.PlayerFlagOneOffset, 1);
                byte[] secondFlag = memory.Read(primary + profile.PlayerFlagTwoOffset, 1);
                int candidate = firstFlag[0] == 0 && secondFlag[0] == 0
                    ? primary : memory.ReadInt32(manager + profile.PlayerAlternateOffset);
                if (!IsPointer(candidate)) return true;
                int resource = memory.ReadInt32(candidate + 0x60);
                int candidateCommon = memory.ReadInt32(candidate + 0xE8);
                int candidateName = memory.ReadInt32(candidate + 0x40);
                if (!IsPointer(resource) || !IsPointer(candidateCommon) || !IsPointer(candidateName)) return true;
                player = candidate; common = candidateCommon; name = candidateName;
                return true;
            }
            catch { return false; }
        }

        static bool IsPointer(int value) { return value > 0x10000 && value < 0x7FFF0000; }

        internal void SetMoney(int amount)
        {
            if (lastPlayer == 0) throw new InvalidOperationException("尚未读取到玩家数据，请先进入单人地图并连接游戏。");
            int resource = memory.ReadInt32(lastPlayer + 0x60);
            int stored = memory.ReadInt32(resource + 0x10);
            memory.WriteInt32(resource + 0x04, amount - stored);
        }

        internal void AddMoney(int amount)
        {
            TickResult tick = Tick();
            if (!tick.PlayerReady) throw new InvalidOperationException("尚未读取到玩家数据，请先进入单人地图并连接游戏。");
            long target = (long)tick.Money + amount;
            SetMoney((int)Math.Min(int.MaxValue, Math.Max(0, target)));
        }

        internal void SetGod(bool value) { WriteFlag(FLAG_GOD, value); }
        internal void SetScenarioProtection(bool value) { WriteFlag(FLAG_SCENARIO, value); }
        internal void SetShield(bool value) { WriteFlag(FLAG_SHIELD, value); }
        internal void SetQuick(bool value) { WriteFlag(FLAG_QUICK, value); }
        internal void SetGlobal(bool value) { if (SupportsGlobalResource) WriteFlag(FLAG_GLOBAL, value); }

        void WriteFlag(int offset, bool value)
        {
            if (!IsConnected) throw new InvalidOperationException("请先连接游戏。");
            memory.WriteInt32(remote + offset, value ? 1 : 0);
        }

        internal void DisableAll()
        {
            minimumMoney = false; unlimitedPower = false;
            if (memory == null || remote == 0) return;
            memory.WriteInt32(remote + FLAG_GOD, 0);
            memory.WriteInt32(remote + FLAG_SCENARIO, 0);
            memory.WriteInt32(remote + FLAG_SHIELD, 0);
            memory.WriteInt32(remote + FLAG_QUICK, 0);
            memory.WriteInt32(remote + FLAG_GLOBAL, 0);
        }

        internal bool IsGameForeground()
        {
            if (!IsConnected) return false;
            IntPtr window = NativeMethods.GetForegroundWindow(); uint pid;
            NativeMethods.GetWindowThreadProcessId(window, out pid);
            return pid == (uint)memory.Process.Id;
        }

        internal void Disconnect()
        {
            ProcessMemory current = memory;
            if (current == null) return;
            try
            {
                DisableAll();
                if (!current.Process.HasExited)
                {
                    for (int i = patches.Count - 1; i >= 0; i--)
                    {
                        Patch patch = patches[i];
                        byte[] present = current.Read(patch.Address, patch.Replacement.Length);
                        if (BytesEqual(present, patch.Replacement)) current.WriteCode(patch.Address, patch.Original);
                    }
                    current.Free(remote);
                }
            }
            finally
            {
                patches.Clear(); remote = 0; lastPlayer = 0; playerManagerGlobal = 0; profile = null; memory = null; current.Dispose();
            }
        }

        static bool BytesEqual(byte[] a, byte[] b)
        {
            if (a.Length != b.Length) return false;
            for (int i = 0; i < a.Length; i++) if (a[i] != b[i]) return false;
            return true;
        }

        public void Dispose() { Disconnect(); }
    }
}
