using System;
using System.Collections.Generic;

namespace Cnc3Trainer
{
    internal sealed class X86Builder
    {
        sealed class Fixup
        {
            internal int Position;
            internal string Label;
            internal int AbsoluteTarget;
            internal bool UsesLabel;
        }

        readonly int baseAddress;
        readonly List<byte> bytes = new List<byte>();
        readonly Dictionary<string, int> labels = new Dictionary<string, int>();
        readonly List<Fixup> fixups = new List<Fixup>();

        internal X86Builder(int baseAddress) { this.baseAddress = baseAddress; }
        internal int Position { get { return bytes.Count; } }

        internal void Emit(params byte[] values) { bytes.AddRange(values); }
        internal void EmitInt32(int value) { bytes.AddRange(BitConverter.GetBytes(value)); }
        internal void Label(string name) { labels[name] = bytes.Count; }

        internal void Jmp(string label)
        {
            Emit(0xE9); AddLabelFixup(label);
        }

        internal void JmpAbsolute(int target)
        {
            Emit(0xE9); AddAbsoluteFixup(target);
        }

        internal void Jcc(byte condition, string label)
        {
            Emit(0x0F, condition); AddLabelFixup(label);
        }

        void AddLabelFixup(string label)
        {
            fixups.Add(new Fixup { Position = bytes.Count, Label = label, UsesLabel = true });
            EmitInt32(0);
        }

        void AddAbsoluteFixup(int target)
        {
            fixups.Add(new Fixup { Position = bytes.Count, AbsoluteTarget = target, UsesLabel = false });
            EmitInt32(0);
        }

        internal byte[] ToArray()
        {
            byte[] result = bytes.ToArray();
            foreach (Fixup fixup in fixups)
            {
                int target;
                if (fixup.UsesLabel)
                {
                    int labelPosition;
                    if (!labels.TryGetValue(fixup.Label, out labelPosition)) throw new InvalidOperationException("未知代码标签: " + fixup.Label);
                    target = baseAddress + labelPosition;
                }
                else target = fixup.AbsoluteTarget;
                int nextInstruction = baseAddress + fixup.Position + 4;
                byte[] relative = BitConverter.GetBytes(target - nextInstruction);
                Buffer.BlockCopy(relative, 0, result, fixup.Position, 4);
            }
            return result;
        }
    }
}
