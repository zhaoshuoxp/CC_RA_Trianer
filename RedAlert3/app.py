"""Red Alert 3 1.13 trainer with a dependency-free native Windows UI."""
import ctypes as C
import ctypes.wintypes as W
import json
import os
import sys
from pathlib import Path

from engine import FEATURES, Trainer, asm
from winmem import processes


user32 = C.WinDLL("user32", use_last_error=True)
gdi32 = C.WinDLL("gdi32", use_last_error=True)
kernel32 = C.WinDLL("kernel32", use_last_error=True)

LRESULT = C.c_ssize_t
WNDPROC = C.WINFUNCTYPE(LRESULT, W.HWND, W.UINT, W.WPARAM, W.LPARAM)


class WNDCLASSEXW(C.Structure):
    _fields_ = [
        ("cbSize", W.UINT), ("style", W.UINT), ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", C.c_int), ("cbWndExtra", C.c_int), ("hInstance", W.HINSTANCE),
        ("hIcon", W.HICON), ("hCursor", W.HANDLE), ("hbrBackground", W.HBRUSH),
        ("lpszMenuName", W.LPCWSTR), ("lpszClassName", W.LPCWSTR), ("hIconSm", W.HICON),
    ]


kernel32.GetModuleHandleW.argtypes = [W.LPCWSTR]
kernel32.GetModuleHandleW.restype = W.HMODULE
user32.DefWindowProcW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.CreateWindowExW.argtypes = [
    W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD,
    C.c_int, C.c_int, C.c_int, C.c_int,
    W.HWND, W.HMENU, W.HINSTANCE, W.LPVOID,
]
user32.CreateWindowExW.restype = W.HWND
user32.RegisterClassExW.argtypes = [C.POINTER(WNDCLASSEXW)]
user32.RegisterClassExW.restype = W.ATOM
user32.LoadCursorW.argtypes = [W.HINSTANCE, W.LPCWSTR]
user32.LoadCursorW.restype = W.HANDLE
user32.GetForegroundWindow.restype = W.HWND
user32.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
user32.SendMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
user32.SendMessageW.restype = LRESULT
user32.SetWindowTextW.argtypes = [W.HWND, W.LPCWSTR]
user32.GetWindowTextLengthW.argtypes = [W.HWND]
user32.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
user32.DestroyWindow.argtypes = [W.HWND]
user32.SetTimer.argtypes = [W.HWND, C.c_size_t, W.UINT, W.LPVOID]
user32.KillTimer.argtypes = [W.HWND, C.c_size_t]
user32.ShowWindow.argtypes = [W.HWND, C.c_int]
user32.UpdateWindow.argtypes = [W.HWND]
user32.GetMessageW.argtypes = [C.POINTER(W.MSG), W.HWND, W.UINT, W.UINT]
user32.TranslateMessage.argtypes = [C.POINTER(W.MSG)]
user32.DispatchMessageW.argtypes = [C.POINTER(W.MSG)]
gdi32.CreateFontW.restype = W.HANDLE

WM_DESTROY, WM_CLOSE, WM_COMMAND, WM_TIMER = 0x0002, 0x0010, 0x0111, 0x0113
WM_SETFONT, BM_GETCHECK, BM_SETCHECK = 0x0030, 0x00F0, 0x00F1
BN_CLICKED, BST_CHECKED = 0, 1
WS_OVERLAPPEDWINDOW, WS_VISIBLE, WS_CHILD, WS_TABSTOP = 0x00CF0000, 0x10000000, 0x40000000, 0x00010000
BS_PUSHBUTTON, BS_AUTOCHECKBOX = 0x00000000, 0x00000003
ES_NUMBER, WS_EX_CLIENTEDGE = 0x2000, 0x00000200
SW_SHOW, SWP_NOMOVE, SWP_NOSIZE, HWND_TOPMOST, HWND_NOTOPMOST = 5, 0x0002, 0x0001, -1, -2

ID_CONNECT, ID_DISABLE, ID_MONEY, ID_SET_MONEY, ID_TOPMOST = 100, 101, 102, 103, 104
FEATURE_IDS = {"power": 201, "points": 202, "build": 203, "cooldown": 204, "god": 205}


def loword(value):
    return value & 0xFFFF


def hiword(value):
    return (value >> 16) & 0xFFFF


class NativeApp:
    def __init__(self):
        self.trainer = Trainer()
        self.connected = False
        self.pid = 0
        self.closing = False
        self.hot_down = set()
        self.poll_ticks = 0
        self.controls = {}
        self.hinstance = kernel32.GetModuleHandleW(None)
        self.class_name = "RA3TrainerNativeWindow"
        self.wndproc_ref = WNDPROC(self.wndproc)
        self.register_class()
        self.hwnd = user32.CreateWindowExW(
            0, self.class_name, "Red Alert 3 / 起义时刻 · 单人修改器",
            WS_OVERLAPPEDWINDOW, 180, 100, 690, 610,
            None, None, self.hinstance, None,
        )
        if not self.hwnd:
            raise C.WinError(C.get_last_error())
        self.font = gdi32.CreateFontW(
            -17, 0, 0, 0, 400, 0, 0, 0, 134, 0, 0, 5, 0, "Microsoft YaHei UI"
        )
        self.build_controls()
        user32.SetTimer(self.hwnd, 1, 80, None)

    def register_class(self):
        wc = WNDCLASSEXW()
        wc.cbSize = C.sizeof(wc)
        wc.lpfnWndProc = self.wndproc_ref
        wc.hInstance = self.hinstance
        wc.hCursor = user32.LoadCursorW(None, C.cast(C.c_void_p(32512), W.LPCWSTR))
        wc.hbrBackground = C.c_void_p(6)
        wc.lpszClassName = self.class_name
        if not user32.RegisterClassExW(C.byref(wc)) and C.get_last_error() != 1410:
            raise C.WinError(C.get_last_error())

    def control(self, kind, text, style, x, y, width, height, control_id=0, exstyle=0):
        hwnd = user32.CreateWindowExW(
            exstyle, kind, text, WS_VISIBLE | WS_CHILD | style,
            x, y, width, height, self.hwnd, W.HMENU(control_id), self.hinstance, None,
        )
        if not hwnd:
            raise C.WinError(C.get_last_error())
        user32.SendMessageW(hwnd, WM_SETFONT, self.font, True)
        if control_id:
            self.controls[control_id] = hwnd
        return hwnd

    def build_controls(self):
        self.control("STATIC", "Red Alert 3", 0, 24, 18, 620, 38)
        self.control("STATIC", "原版 1.13 / 起义时刻 1.01 · Win11 · 单机战局", 0, 26, 56, 620, 24)
        self.control("BUTTON", "连接游戏  小键盘*", WS_TABSTOP | BS_PUSHBUTTON, 24, 91, 190, 38, ID_CONNECT)
        self.control("BUTTON", "关闭全部功能  小键盘0", WS_TABSTOP | BS_PUSHBUTTON, 226, 91, 220, 38, ID_DISABLE)
        self.control("BUTTON", "窗口置顶", WS_TABSTOP | BS_AUTOCHECKBOX, 510, 96, 125, 30, ID_TOPMOST)
        self.controls[300] = self.control("STATIC", "进入战局后连接；所有功能默认关闭。", 0, 25, 141, 625, 25)

        self.control("STATIC", "金钱", 0, 25, 183, 55, 28)
        self.control("EDIT", "100000", WS_TABSTOP | ES_NUMBER, 83, 178, 135, 32, ID_MONEY, WS_EX_CLIENTEDGE)
        self.control("BUTTON", "设置  小键盘1", WS_TABSTOP | BS_PUSHBUTTON, 230, 177, 160, 34, ID_SET_MONEY)

        labels = [
            ("power", "无限电力  小键盘2"),
            ("points", "无限支援协议点 999  小键盘3"),
            ("build", "瞬间建造（单位与建筑，通用阵营路径）  小键盘4"),
            ("cooldown", "超级武器 / 支援能力无冷却  小键盘5"),
            ("god", "我方步兵、车辆与建筑免普通攻击伤害  小键盘6"),
        ]
        for index, (name, label) in enumerate(labels):
            self.control(
                "BUTTON", label, WS_TABSTOP | BS_AUTOCHECKBOX,
                24, 224 + index * 38, 625, 32, FEATURE_IDS[name],
            )

        note = (
            "Num Lock 开启后，热键只在游戏前台响应。\r\n"
            "免伤覆盖步兵、车辆和建筑，并排除火焰、残骸等临时对象。\r\n"
            "瞬间建造覆盖通用生产路径；苏军已实测，盟军和帝国不受阵营限制。\r\n"
            "本版本未加入无法可靠显示阴影中敌军的全图可见功能。"
        )
        self.control("STATIC", note, 0, 25, 424, 625, 82)
        self.controls[301] = self.control("STATIC", "未连接", 0, 25, 525, 625, 30)

    def text(self, control_id, value):
        user32.SetWindowTextW(self.controls[control_id], str(value))

    def get_text(self, control_id):
        length = user32.GetWindowTextLengthW(self.controls[control_id])
        buffer = C.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(self.controls[control_id], buffer, len(buffer))
        return buffer.value

    def checked(self, control_id):
        return user32.SendMessageW(self.controls[control_id], BM_GETCHECK, 0, 0) == BST_CHECKED

    def set_checked(self, control_id, value):
        user32.SendMessageW(self.controls[control_id], BM_SETCHECK, BST_CHECKED if value else 0, 0)

    def connect(self):
        try:
            if self.connected:
                self.trainer.detach()
                self.connected, self.pid = False, 0
                self.text(ID_CONNECT, "连接游戏  小键盘*")
                self.text(301, "已恢复原始指令并断开。")
                self.clear_checks()
            else:
                self.text(301, "正在核对游戏版本与补丁位置…")
                snap = self.trainer.attach()
                self.connected, self.pid = True, snap["pid"]
                self.text(ID_CONNECT, "断开并恢复  小键盘*")
                self.text(301, "已连接；所有功能默认关闭。")
                self.update_snapshot(snap)
        except Exception as exc:
            self.connected, self.pid = False, 0
            try:
                self.trainer.detach()
            except Exception:
                pass
            self.text(ID_CONNECT, "连接游戏  小键盘*")
            self.text(301, str(exc))

    def set_money(self):
        if not self.ensure_connected():
            return
        try:
            value = int(self.get_text(ID_MONEY))
            self.trainer.set_money(value)
            self.text(301, "设置金钱：已完成")
            self.update_snapshot(self.trainer.snapshot())
        except Exception as exc:
            self.text(301, str(exc))

    def toggle(self, key):
        if not self.ensure_connected():
            self.update_checks(0)
            return
        try:
            enabled = self.checked(FEATURE_IDS[key])
            self.trainer.feature(key, enabled)
            self.text(301, ("开启" if enabled else "关闭") + "：已完成")
        except Exception as exc:
            self.text(301, str(exc))
            self.safe_snapshot()

    def disable_all(self):
        if not self.ensure_connected():
            return
        try:
            self.trainer.disable_all()
            self.update_checks(0)
            self.text(301, "关闭全部功能：已完成")
        except Exception as exc:
            self.text(301, str(exc))

    def ensure_connected(self):
        if self.connected:
            return True
        self.text(301, "请先连接已经进入战局的 ra3_1.13.game。")
        return False

    def update_checks(self, flags):
        for name, bit in FEATURES.items():
            self.set_checked(FEATURE_IDS[name], bool(flags & bit))

    def clear_checks(self):
        self.update_checks(0)
        self.text(300, "进入战局后连接；所有功能默认关闭。")

    def update_snapshot(self, snap):
        self.text(300, f"{snap['game']}    金钱 {snap['money']:,}    电力 {snap['power']:,} / {snap['drain']:,}    协议点 {snap['points']}")
        self.update_checks(snap["flags"])

    def safe_snapshot(self):
        if not self.connected:
            return
        try:
            self.update_snapshot(self.trainer.snapshot())
        except Exception as exc:
            self.connected, self.pid = False, 0
            self.text(ID_CONNECT, "连接游戏  小键盘*")
            self.text(301, str(exc))
            try:
                self.trainer.detach()
            except Exception:
                pass

    def foreground_pid(self):
        pid = W.DWORD()
        user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), C.byref(pid))
        return pid.value

    def hotkeys(self):
        keys = [*range(0x60, 0x67), 0x6A]
        down = {key for key in keys if user32.GetAsyncKeyState(key) & 0x8000}
        pressed = down - self.hot_down
        self.hot_down = down
        if not pressed or any(user32.GetAsyncKeyState(key) & 0x8000 for key in (0x10, 0x11, 0x12)):
            return
        foreground_pid = self.foreground_pid()
        if 0x6A in pressed:
            game_is_foreground = any(
                process_id == foreground_pid and name.lower() in ("ra3_1.13.game", "ra3ep1_1.1.game")
                for process_id, name in processes()
            )
            if foreground_pid in (self.pid, os.getpid()) or game_is_foreground:
                self.connect()
            return
        if not self.connected or foreground_pid != self.pid:
            return
        for key in sorted(pressed):
            number = key - 0x60
            if number == 0:
                self.disable_all()
            elif number == 1:
                self.set_money()
            elif 2 <= number <= 6:
                name = {2: "power", 3: "points", 4: "build", 5: "cooldown", 6: "god"}[number]
                control_id = FEATURE_IDS[name]
                self.set_checked(control_id, not self.checked(control_id))
                self.toggle(name)

    def close(self):
        if self.closing:
            return
        self.closing = True
        self.text(301, "正在关闭功能并恢复原始指令…")
        try:
            self.trainer.detach()
        finally:
            user32.DestroyWindow(self.hwnd)

    def wndproc(self, hwnd, message, wparam, lparam):
        if message == WM_COMMAND and hiword(wparam) == BN_CLICKED:
            control_id = loword(wparam)
            if control_id == ID_CONNECT:
                self.connect()
            elif control_id == ID_DISABLE:
                self.disable_all()
            elif control_id == ID_SET_MONEY:
                self.set_money()
            elif control_id == ID_TOPMOST:
                top = HWND_TOPMOST if self.checked(ID_TOPMOST) else HWND_NOTOPMOST
                user32.SetWindowPos(hwnd, C.c_void_p(top), 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
            else:
                name = next((key for key, value in FEATURE_IDS.items() if value == control_id), None)
                if name:
                    self.toggle(name)
            return 0
        if message == WM_TIMER:
            self.hotkeys()
            self.poll_ticks += 1
            if self.poll_ticks >= 10:
                self.poll_ticks = 0
                self.safe_snapshot()
            return 0
        if message == WM_CLOSE:
            self.close()
            return 0
        if message == WM_DESTROY:
            user32.KillTimer(hwnd, 1)
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, message, wparam, lparam)

    def run(self):
        user32.ShowWindow(self.hwnd, SW_SHOW)
        user32.UpdateWindow(self.hwnd)
        message = W.MSG()
        while user32.GetMessageW(C.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(C.byref(message))
            user32.DispatchMessageW(C.byref(message))


def self_check():
    assert asm("ret", 0x100000) == b"\xc3"
    data = json.loads((Path(__file__).parent / "fingerprints.json").read_text(encoding="utf-8-sig"))
    assert data[0]["Name"].lower() == "ra3_1.13.game"
    assert data[1]["Name"].lower() == "ra3ep1_1.1.game"


if __name__ == "__main__":
    if "--check" in sys.argv:
        self_check()
        raise SystemExit(0)
    user32.SetProcessDPIAware()
    if "--ui-check" in sys.argv:
        app = NativeApp()
        assert app.hwnd and len(app.controls) == 12
        user32.DestroyWindow(app.hwnd)
        raise SystemExit(0)
    NativeApp().run()
