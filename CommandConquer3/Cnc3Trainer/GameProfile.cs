using System;
using System.Collections.Generic;

namespace Cnc3Trainer
{
    internal enum GameKind { TiberiumWars, KanesWrath }

    internal sealed class GameProfile
    {
        internal GameKind Kind;
        internal string DisplayName;
        internal string ProcessStem;
        internal int UnitHpOffset;
        internal int UnitOwnerOffset;
        internal int UnitNameOffset;
        internal int UnitMarkerOffset;
        internal int ShieldMaxOffset;
        internal string PlayerPattern;
        internal string DamagePattern;
        internal string UnitPattern;
        internal string ShieldPattern;
        internal string QuickPattern;
        internal string GlobalPattern;
        internal string FanaticPattern;
        internal string GrenadePattern;

        internal static readonly HashSet<string> SupportedHashes = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            // Tiberium Wars 1.09 / EA 2025 update 1.10
            "8EE145C5F6DF2A8C853E073D8F43294F09EC9669150AFDF3E9644C830A19D15A",
            "AF568A89B6D0D4F69EC690CF1D443539CB15AFE197B96AC3FC5BF0EC0A56D141",
            // Kane's Wrath 1.02 / EA 2025 update 1.03
            "ED685B85CF2646FE79CEE57543A992B0165065F1FD2B59C31B1A200C6C7A0E9A",
            "1716C954AB80CF05752F4A4A467D34313A95A55A408718270F96382E330572F3"
        };

        internal static GameProfile ForProcessName(string name)
        {
            name = name.ToLowerInvariant();
            if (name.Contains("cnc3ep1")) return Kane();
            if (name.Contains("cnc3game")) return Tiberium();
            return null;
        }

        static GameProfile Tiberium()
        {
            return new GameProfile
            {
                Kind = GameKind.TiberiumWars,
                DisplayName = "泰伯利亚战争",
                ProcessStem = "cnc3game",
                UnitHpOffset = 0x2C0,
                UnitOwnerOffset = 0x33C,
                UnitNameOffset = 0x340,
                UnitMarkerOffset = 0x438,
                ShieldMaxOffset = 0x6C,
                PlayerPattern = "8B 47 60 8B 48 10 03 48 04 8B 16 51 8B CE FF 52 0C 6A 01 ?? ??",
                DamagePattern = "F3 0F 10 5D 08 0F 57 C9 56 8B F1 F3 0F 10 46 08 F3 0F 10 56 10",
                UnitPattern = "8B 8E C0 02 00 00 85 C9 ?? ?? 8B 01 57 FF 10 F6 86 CD 03 00 00 01",
                ShieldPattern = "8D BE 14 01 00 00 F3 0F 10 07 F3 0F 5C 45 FC 83 C4 0C 8B CB F3 0F 11 07",
                QuickPattern = "F3 0F 58 4B 1C F3 0F 10 05 ?? ?? ?? ?? 0F 2F C1 F3 0F 11 4D 08",
                FanaticPattern = "5F 5E C9 C2 04 00 55 8B EC 81 EC 98 00 00 00 8B 45 08 85 C0 53",
                GrenadePattern = "5E 83 C5 6C C9 C2 0C 00 55 8B EC 81 EC B0 00 00 00 53 56 57 6A 45"
            };
        }

        static GameProfile Kane()
        {
            return new GameProfile
            {
                Kind = GameKind.KanesWrath,
                DisplayName = "凯恩之怒",
                ProcessStem = "cnc3ep1",
                UnitHpOffset = 0x2CC,
                UnitOwnerOffset = 0x348,
                UnitNameOffset = 0x34C,
                UnitMarkerOffset = 0x444,
                ShieldMaxOffset = 0x7C,
                PlayerPattern = "8B 47 60 8B 48 10 03 48 04 8B 16 51 8B CE FF 52 0C 6A 01 ?? ??",
                DamagePattern = "F3 0F 10 5D 08 0F 57 C9 56 8B F1 F3 0F 10 46 08 F3 0F 10 56 10",
                UnitPattern = "8B 8E CC 02 00 00 85 C9 ?? ?? 8B 01 57 FF 10 F6 86 D9 03 00 00 01",
                ShieldPattern = "8D BE 14 01 00 00 F3 0F 10 07 F3 0F 5C 45 FC 83 C4 0C 8B CB F3 0F 11 07",
                QuickPattern = "F3 0F 58 4B 1C F3 0F 10 05 ?? ?? ?? ?? 0F 2F C1 F3 0F 11 4D 08",
                GlobalPattern = "8B 40 08 8B 78 74 8B 0D ?? ?? ?? ?? 8D 45 E4 50 E8 ?? ?? ?? ?? 8B 48 08",
                FanaticPattern = "5F 5E C9 C2 04 00 55 8D 6C 24 98 81 EC C4 00 00 00 A1 ?? ?? ??",
                GrenadePattern = "5E 83 C5 6C C9 C2 0C 00 55 8D 6C 24 8C 81 EC 1C 01 00 00 A1 ??"
            };
        }
    }
}
