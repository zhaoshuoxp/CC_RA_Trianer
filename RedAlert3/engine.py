"""Red Alert 3 1.13 and Uprising 1.01 single-player trainer engine."""
import hashlib
import json
import struct
from pathlib import Path

from keystone import Ks, KS_ARCH_X86, KS_MODE_32
from winmem import Mem, modules, processes

ROOT = Path(__file__).resolve().parent
PROFILES = {
    "ra3_1.13.game": {
        "label": "Red Alert 3 1.13",
        "root": 0xCF214C, "manager_vt": 0xC650D0, "player_vt": 0xC65440,
        "object_vt": 0xC57340, "body_vt": 0xC418F8, "power_vt": 0xC65120,
        "protocol_vt": 0xC65180, "account_vt": 0xC65010,
        "owner": 0x418, "body": 0x33C, "vision": 0x258, "shroud": 0x260,
        "building_total": 0x3C, "power_ui": 0x3B0,
        "sites": {
            "power": (0xA698DD, "8B 40 04 8B 8E B0 03 00 00", 0xA698E6),
            "points": (0xA69A3C, "8B 78 34 8B 4E 3C", 0xA69A42),
            "fast1": (0x7386CE, "F3 0F 2C 46 1C", 0x7386D3),
            "fast2": (0x73862C, "D9 46 1C 89 46 5C", 0x738632),
            "fast3": (0x71FEDF, "D9 86 BC 01 00 00", 0x71FEE5),
            "charge": (0x714D19, "8B 98 18 04 00 00", 0x714D1F),
            "fraction": (0x867FB0, "51 8B 44 24 08", 0x867FB5),
            "ready": (0x868020, "8B 44 24 04 8B 50 08", 0x868027),
            "god": (0x78CB4E, "F3 0F 11 46 04", 0x78CB53),
        },
    },
    "ra3ep1_1.1.game": {
        "label": "Red Alert 3: Uprising 1.01",
        "root": 0xD05DD4, "manager_vt": 0xC75B70, "player_vt": 0xC75EF0,
        "object_vt": 0xC68258, "body_vt": 0xC51580, "power_vt": 0xC75BC0,
        "protocol_vt": 0xC75C20, "account_vt": 0xC75AB8,
        "owner": 0x428, "body": 0x34C, "vision": 0x25C, "shroud": 0x264,
        "building_total": 0x34, "power_ui": 0x3E0,
        "sites": {
            "power": (0xA64938, "8B 40 04 8B 8E E0 03 00 00", 0xA64941),
            "points": (0xA64AA8, "8B 78 34 8B 4E 3C", 0xA64AAE),
            "fast1": (0x74889E, "F3 0F 2C 46 1C", 0x7488A3),
            "fast2": (0x7487FC, "D9 46 1C 89 46 5C", 0x748802),
            "fast3": (0x72A36F, "D9 86 BC 01 00 00", 0x72A375),
            "charge": (0x723C59, "8B 98 28 04 00 00", 0x723C5F),
            "fraction": (0x873E50, "51 8B 44 24 08", 0x873E55),
            "ready": (0x873EC0, "8B 44 24 04 8B 50 08", 0x873EC7),
            "god": (0x7A048E, "F3 0F 11 46 04", 0x7A0493),
        },
    },
}

FLAGS = 0x00
FEATURES = {
    "power": 1,
    "points": 2,
    "build": 4,
    "cooldown": 8,
    "god": 16,
}


def asm(code, address):
    try:
        return bytes(Ks(KS_ARCH_X86, KS_MODE_32).asm(code, address)[0])
    except Exception as exc:
        raise RuntimeError(
            f"汇编失败，语句位置 {getattr(exc, 'stat_count', None)}：{exc}"
        ) from exc


def jump(source, target, size=5):
    if size < 5:
        raise ValueError("跳转覆盖长度不足")
    return b"\xE9" + struct.pack("<I", (target - source - 5) & 0xFFFFFFFF) + b"\x90" * (size - 5)


class Trainer:
    def __init__(self):
        self.mem = None
        self.base = 0
        self.patches = []
        self.path = ""
        self.profile = None

    def find(self):
        games = [p for p in processes() if p[1].lower() in PROFILES]
        if len(games) != 1:
            raise RuntimeError("请只启动一场 Red Alert 3 1.13 或《起义时刻》1.01 单机战局。")
        return games[0][0]

    def attach(self, pid=None):
        if self.mem:
            self.detach()
        pid = pid or self.find()
        game_modules = modules(pid)
        target = next((m for m in game_modules if m["name"].lower() in PROFILES), None)
        if not target:
            raise RuntimeError("没有找到受支持的游戏主模块。")
        name = target["name"].lower()
        fingerprints = json.loads((ROOT / "fingerprints.json").read_text(encoding="utf-8-sig"))
        fingerprint = next((item for item in fingerprints if item["Name"].lower() == name), None)
        if not fingerprint:
            raise RuntimeError("缺少该游戏版本的指纹。")
        actual = hashlib.sha256(Path(target["path"]).read_bytes()).hexdigest().upper()
        if actual != fingerprint["SHA256"]:
            raise RuntimeError("游戏版本指纹不同，停止写入。")
        if target["base"] != 0x400000:
            raise RuntimeError("不支持的游戏映像基址。")
        self.mem = Mem(pid)
        self.path = target["path"]
        self.profile = PROFILES[name]
        try:
            self.validate_session()
            self.install()
        except Exception:
            self.detach()
            raise
        return self.snapshot()

    def validate_session(self):
        if not self.mem:
            raise RuntimeError("尚未连接游戏。")
        m = self.mem
        p = self.profile
        manager = m.u32(p["root"])
        if manager < 0x10000 or m.u32(manager) != p["manager_vt"]:
            raise RuntimeError("尚未进入有效战局。")
        player = m.u32(manager + 0x28)
        if player < 0x10000 or m.u32(player) != p["player_vt"]:
            raise RuntimeError("没有有效的本地玩家。")
        player_id = m.u32(player + 0x20)
        if player_id > 17:
            raise RuntimeError("本地玩家数据异常。")
        return player

    def install(self):
        m = self.mem
        p = self.profile
        checks = {name: (site, bytes.fromhex(original), target)
                  for name, (site, original, target) in p["sites"].items()}
        for address, expected, _ in checks.values():
            if m.read(address, len(expected)) != expected:
                raise RuntimeError(f"补丁冲突或游戏未重启：{address:08X}")

        self.base = base = m.alloc(0x10000)
        m.write(base, bytes(0x1000))
        flags = hex(base + FLAGS)
        root = hex(p["root"])
        specs = []

        power = f"""
pushfd
push ecx
test dword ptr [{flags}],1
jz power_original
cmp dword ptr [eax],{hex(p['power_vt'])}
jne power_original
mov ecx,[{root}]
test ecx,ecx
jz power_original
mov ecx,[ecx+0x28]
cmp [eax+0x1c],ecx
jne power_original
mov dword ptr [eax+4],10000
mov dword ptr [eax+8],0
xor edx,edx
power_original:
pop ecx
popfd
mov eax,[eax+4]
mov ecx,[esi+{hex(p['power_ui'])}]
jmp {hex(checks['power'][2])}
"""
        points = f"""
pushfd
push ecx
test dword ptr [{flags}],2
jz points_original
cmp dword ptr [eax],{hex(p['protocol_vt'])}
jne points_original
mov ecx,[{root}]
test ecx,ecx
jz points_original
mov ecx,[ecx+0x28]
cmp [eax+0x28],ecx
jne points_original
mov dword ptr [eax+0x34],999
points_original:
pop ecx
popfd
mov edi,[eax+0x34]
mov ecx,[esi+0x3c]
jmp {hex(checks['points'][2])}
"""
        fast1 = f"""
pushfd
test dword ptr [{flags}],4
jz fast1_original
mov dword ptr [esi+0x1c],0x42c80000
fast1_original:
popfd
cvttss2si eax,[esi+0x1c]
jmp {hex(checks['fast1'][2])}
"""
        fast2 = f"""
pushfd
test dword ptr [{flags}],4
jz fast2_original
mov dword ptr [esi+0x1c],0x42c80000
fast2_original:
popfd
fld dword ptr [esi+0x1c]
mov [esi+0x5c],eax
jmp {hex(checks['fast2'][2])}
"""
        fast3 = f"""
pushfd
push eax
test dword ptr [{flags}],4
jz fast3_original
cmp ebp,1
jne fast3_original
mov eax,[edi+{hex(p['building_total'])}]
inc eax
mov [edi+0x14],eax
fast3_original:
pop eax
popfd
fld dword ptr [esi+0x1bc]
jmp {hex(checks['fast3'][2])}
"""
        charge = f"""
pushfd
push ecx
test dword ptr [{flags}],8
jz charge_original
cmp dword ptr [eax],{hex(p['object_vt'])}
jne charge_original
mov ecx,[{root}]
test ecx,ecx
jz charge_original
mov ecx,[ecx+0x28]
cmp [eax+{hex(p['owner'])}],ecx
jne charge_original
mov dword ptr [esi+0x20],1
charge_original:
pop ecx
popfd
mov ebx,[eax+{hex(p['owner'])}]
jmp {hex(checks['charge'][2])}
"""
        fraction = f"""
test dword ptr [{flags}],8
jz fraction_original
mov eax,[{root}]
test eax,eax
jz fraction_original
mov eax,[eax+0x28]
cmp ecx,eax
jne fraction_original
fld1
ret 4
fraction_original:
push ecx
mov eax,[esp+8]
jmp {hex(checks['fraction'][2])}
"""
        ready = f"""
test dword ptr [{flags}],8
jz ready_original
push edx
mov edx,[{root}]
test edx,edx
jz ready_not_local
mov edx,[edx+0x28]
cmp ecx,edx
jne ready_not_local
pop edx
mov eax,1
ret 4
ready_not_local:
pop edx
ready_original:
mov eax,[esp+4]
mov edx,[eax+8]
jmp {hex(checks['ready'][2])}
"""
        god = f"""
pushfd
push eax
push edx
test dword ptr [{flags}],16
jz god_original
test eax,eax
jz god_original
cmp dword ptr [esi],{hex(p['body_vt'])}
jne god_original
mov eax,[esi-8]
cmp eax,0x10000
jb god_original
cmp dword ptr [eax],{hex(p['object_vt'])}
jne god_original
cmp dword ptr [eax+{hex(p['vision'])}],0
jle god_original
cmp dword ptr [eax+{hex(p['vision'])}],0x7f800000
jae god_original
cmp dword ptr [eax+{hex(p['shroud'])}],0
jle god_original
cmp dword ptr [eax+{hex(p['shroud'])}],0x7f800000
jae god_original
cmp [eax+{hex(p['body'])}],esi
jne god_original
mov edx,[{root}]
test edx,edx
jz god_original
mov edx,[edx+0x28]
test edx,edx
jz god_original
cmp [eax+{hex(p['owner'])}],edx
jne god_original
cmp dword ptr [esi+4],0
jle god_original
comiss xmm0,[esi+4]
jae god_original
movss xmm0,[esi+4]
god_original:
pop edx
pop eax
popfd
movss [esi+4],xmm0
jmp {hex(checks['god'][2])}
"""

        sources = [
            (checks["power"][0], checks["power"][1], power),
            (checks["points"][0], checks["points"][1], points),
            (checks["fast1"][0], checks["fast1"][1], fast1),
            (checks["fast2"][0], checks["fast2"][1], fast2),
            (checks["fast3"][0], checks["fast3"][1], fast3),
            (checks["charge"][0], checks["charge"][1], charge),
            (checks["fraction"][0], checks["fraction"][1], fraction),
            (checks["ready"][0], checks["ready"][1], ready),
            (checks["god"][0], checks["god"][1], god),
        ]
        code_address = base + 0x2000
        for site, original, source in sources:
            binary = asm(source, code_address)
            m.write(code_address, binary)
            specs.append((site, original, jump(site, code_address, len(original))))
            code_address = (code_address + len(binary) + 15) & ~15

        self.patches = specs
        m.suspend()
        try:
            for site, original, patch in specs:
                if m.read(site, len(original)) != original:
                    raise RuntimeError(f"安装时检测到新的补丁冲突：{site:08X}")
            for site, original, patch in specs:
                m.write(site, patch)
        finally:
            m.resume()

    def feature(self, name, enabled):
        player = self.validate_session()
        p = self.profile
        if name not in FEATURES:
            raise ValueError(name)
        flag = FEATURES[name]
        bits = self.mem.u32(self.base + FLAGS)
        self.mem.put32(self.base + FLAGS, bits | flag if enabled else bits & ~flag)
        if enabled and name == "power":
            power = self.mem.u32(player + 0x74)
            if self.mem.u32(power) != p["power_vt"] or self.mem.u32(power + 0x1C) != player:
                raise RuntimeError("电力对象校验失败。")
            self.mem.put32(power + 4, 10000)
            self.mem.put32(power + 8, 0)
        if enabled and name == "points":
            protocol = self.mem.u32(player + 0x1320)
            if self.mem.u32(protocol) != p["protocol_vt"] or self.mem.u32(protocol + 0x28) != player:
                raise RuntimeError("协议点对象校验失败。")
            self.mem.put32(protocol + 0x34, 999)
        return enabled

    def set_money(self, value=100000):
        player = self.validate_session()
        p = self.profile
        if not 0 <= value <= 99999999:
            raise ValueError("金额范围为 0～99999999。")
        begin = self.mem.u32(player + 0xE4)
        end = self.mem.u32(player + 0xE8)
        if begin < 0x10000 or end - begin < 4:
            raise RuntimeError("当前玩家没有资源账户。")
        account = self.mem.u32(begin)
        if self.mem.u32(account) != p["account_vt"]:
            raise RuntimeError("资源账户校验失败。")
        self.mem.put32(account + 4, value)
        return value

    def disable_all(self):
        self.validate_session()
        self.mem.put32(self.base + FLAGS, 0)

    def snapshot(self):
        player = self.validate_session()
        m = self.mem
        p = self.profile
        account = m.u32(m.u32(player + 0xE4))
        power = m.u32(player + 0x74)
        protocol = m.u32(player + 0x1320)
        if m.u32(account) != p["account_vt"] or m.u32(power) != p["power_vt"] or m.u32(protocol) != p["protocol_vt"]:
            raise RuntimeError("战局对象已变化，请重新连接。")
        return {
            "pid": m.pid,
            "player": player,
            "money": m.i32(account + 4),
            "power": m.i32(power + 4),
            "drain": m.i32(power + 8),
            "points": m.i32(protocol + 0x34),
            "flags": m.u32(self.base + FLAGS) if self.base else 0,
            "game": p["label"],
        }

    def detach(self):
        m = self.mem
        if not m:
            return
        try:
            if self.base:
                m.put32(self.base + FLAGS, 0)
            m.suspend()
            try:
                for site, original, patch in reversed(self.patches):
                    if m.read(site, len(patch)) == patch:
                        m.write(site, original)
            finally:
                m.resume()
        except OSError:
            pass
        finally:
            m.close()
            self.mem = None
            self.base = 0
            self.patches = []
            self.profile = None
        # 代码页保留到游戏退出，避免线程仍在返回路径时释放。
