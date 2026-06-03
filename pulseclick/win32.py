import ctypes
from ctypes import wintypes


user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_NOREPEAT = 0x4000

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040

BUTTON_FLAGS = {
    "左键": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
    "右键": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
    "中键": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
}

RECORD_BUTTONS = {
    "left": {"vk": 0x01, "name": "左键", "down": MOUSEEVENTF_LEFTDOWN, "up": MOUSEEVENTF_LEFTUP},
    "right": {"vk": 0x02, "name": "右键", "down": MOUSEEVENTF_RIGHTDOWN, "up": MOUSEEVENTF_RIGHTUP},
    "middle": {"vk": 0x04, "name": "中键", "down": MOUSEEVENTF_MIDDLEDOWN, "up": MOUSEEVENTF_MIDDLEUP},
}

KEY_NAMES = {
    0x08: "Backspace", 0x09: "Tab", 0x0D: "Enter", 0x10: "Shift", 0x11: "Ctrl", 0x12: "Alt",
    0x1B: "Esc", 0x20: "Space", 0x21: "PageUp", 0x22: "PageDown", 0x23: "End", 0x24: "Home",
    0x25: "Left", 0x26: "Up", 0x27: "Right", 0x28: "Down", 0x2D: "Insert", 0x2E: "Delete",
    0xBA: ";", 0xBB: "=", 0xBC: ",", 0xBD: "-", 0xBE: ".", 0xBF: "/",
    0xC0: "`", 0xDB: "[", 0xDC: "\\", 0xDD: "]", 0xDE: "'",
}
for code in range(0x30, 0x3A):
    KEY_NAMES[code] = chr(code)
for code in range(0x41, 0x5B):
    KEY_NAMES[code] = chr(code)
for offset in range(12):
    KEY_NAMES[0x70 + offset] = f"F{offset + 1}"


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", INPUT_UNION)]


def last_error_message():
    error = ctypes.get_last_error()
    if not error:
        return "未知错误"
    buffer = ctypes.create_unicode_buffer(512)
    kernel32.FormatMessageW(0x00001000, None, error, 0, buffer, len(buffer), None)
    return buffer.value.strip() or f"Win32 error {error}"


def get_cursor_pos():
    point = POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def set_cursor_pos(x, y):
    user32.SetCursorPos(int(x), int(y))


def send_mouse_flag(flag):
    item = INPUT(type=INPUT_MOUSE, union=INPUT_UNION(mi=MOUSEINPUT(0, 0, 0, flag, 0, None)))
    user32.SendInput(1, ctypes.byref(item), ctypes.sizeof(INPUT))


def click(button_name):
    down, up = BUTTON_FLAGS[button_name]
    send_mouse_flag(down)
    send_mouse_flag(up)


def send_key(vk, is_down):
    flag = 0 if is_down else KEYEVENTF_KEYUP
    user32.keybd_event(int(vk), 0, flag, 0)


def send_unicode_text(text):
    for char in text:
        code = ord(char)
        down = INPUT(type=INPUT_KEYBOARD, union=INPUT_UNION(ki=KEYBDINPUT(0, code, KEYEVENTF_UNICODE, 0, None)))
        up = INPUT(type=INPUT_KEYBOARD, union=INPUT_UNION(ki=KEYBDINPUT(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, None)))
        user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT))
        user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT))


def is_key_down(vk):
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def vk_to_char(vk):
    if is_key_down(0x11) or is_key_down(0x12):
        return ""
    keyboard_state = (ctypes.c_ubyte * 256)()
    if not user32.GetKeyboardState(ctypes.byref(keyboard_state)):
        return ""
    buffer = ctypes.create_unicode_buffer(8)
    scan_code = user32.MapVirtualKeyW(vk, 0)
    result = user32.ToUnicode(vk, scan_code, keyboard_state, buffer, len(buffer), 0)
    if result <= 0:
        return ""
    char = buffer.value[:result]
    return char if char.isprintable() else ""
