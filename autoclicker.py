import ctypes
import json
import math
import os
import random
import threading
import time
import tkinter as tk
from ctypes import wintypes
from tkinter import filedialog, messagebox

try:
    import customtkinter as ctk
except ImportError:
    messagebox.showerror("缺少依赖", "请先运行：python -m pip install customtkinter")
    raise


APP_TITLE = "PulseClick"
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pulseclick_settings.json")

VK_F6 = 0x75
VK_F7 = 0x76
VK_F8 = 0x77
VK_F9 = 0x78
VK_F10 = 0x79
WM_HOTKEY = 0x0312
MOD_NOREPEAT = 0x4000
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
INPUT_KEYBOARD = 1

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
RECORD_KEY_CODES = [code for code in KEY_NAMES if code not in (VK_F6, VK_F7, VK_F8, VK_F9, VK_F10)]

UI = {
    "app_bg": ("#f6f7fb", "#10131a"),
    "sidebar": ("#ffffff", "#151922"),
    "panel": ("#ffffff", "#1b202b"),
    "panel_soft": ("#eef2f7", "#252b38"),
    "field": ("#f8fafc", "#111722"),
    "text": ("#111827", "#f8fafc"),
    "text_muted": ("#647084", "#a3adbd"),
    "border": ("#d9e2ec", "#303847"),
    "accent": ("#2563eb", "#14b8a6"),
    "accent_hover": ("#1d4ed8", "#0d9488"),
    "accent_soft": ("#e7efff", "#132f2f"),
    "danger": ("#dc2626", "#f43f5e"),
    "danger_hover": ("#b91c1c", "#e11d48"),
    "neutral": ("#e4e9f2", "#26313f"),
    "neutral_hover": ("#cfd8e5", "#334155"),
}

FLAT_THEME = {
    "深色": {
        "overlay": "#10131a",
        "overlay_text": "#f8fafc",
    },
    "浅色": {
        "overlay": "#f6f7fb",
        "overlay_text": "#111827",
    },
}

user32 = ctypes.windll.user32


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", INPUT_UNION)]


class HotkeyThread(threading.Thread):
    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app
        self.thread_id = None
        self.running = True

    def run(self):
        self.thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        for hotkey_id, vk in ((1, VK_F6), (2, VK_F7), (3, VK_F8), (4, VK_F9), (5, VK_F10)):
            user32.RegisterHotKey(None, hotkey_id, MOD_NOREPEAT, vk)

        msg = wintypes.MSG()
        while self.running and user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == WM_HOTKEY:
                self.app.after(0, self.app.handle_hotkey, int(msg.wParam))
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        for hotkey_id in (1, 2, 3, 4, 5):
            user32.UnregisterHotKey(None, hotkey_id)

    def stop(self):
        self.running = False
        if self.thread_id:
            user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)


class AutoClickerApp(ctk.CTk):
    def __init__(self):
        self.settings = self.load_settings()
        saved_theme = self.settings.get("theme", "深色")
        if saved_theme not in ("深色", "浅色"):
            saved_theme = "深色"
        ctk.set_appearance_mode("Dark" if saved_theme == "深色" else "Light")
        ctk.set_default_color_theme("blue")

        super().__init__()
        self.root = self
        self.title(APP_TITLE)
        self.geometry("1060x760")
        self.minsize(980, 700)
        self.configure(fg_color=UI["app_bg"])

        self.theme_name = tk.StringVar(value=saved_theme)
        self.always_on_top = tk.BooleanVar(value=bool(self.settings.get("always_on_top", False)))
        self.hide_when_running = tk.BooleanVar(value=bool(self.settings.get("hide_when_running", False)))
        self.record_moves = tk.BooleanVar(value=False)

        self.interval_ms = tk.StringVar(value="100")
        self.jitter_ms = tk.StringVar(value="0")
        self.start_delay = tk.StringVar(value="0")
        self.mouse_button = tk.StringVar(value="左键")
        self.click_mode = tk.StringVar(value="单击")
        self.repeat_mode = tk.StringVar(value="一直点击")
        self.repeat_count = tk.StringVar(value="100")
        self.position_mode = tk.StringVar(value="当前位置")
        self.fixed_x = tk.StringVar(value="-")
        self.fixed_y = tk.StringVar(value="-")
        self.status_text = tk.StringVar(value="READY")
        self.counter_text = tk.StringVar(value="0")
        self.speed_text = tk.StringVar(value="0.0/s")
        self.script_summary = tk.StringVar(value="0 个事件")
        self.script_repeat = tk.StringVar(value="1")
        self.script_speed = tk.StringVar(value="1.0")
        self.script_text_input = tk.StringVar(value="")

        self.stop_event = threading.Event()
        self.record_stop_event = threading.Event()
        self.worker = None
        self.recorder = None
        self.clicks_done = 0
        self.started_at = None
        self.fixed_position = None
        self.picking_after_delay = False
        self.script_events = []
        self.recording = False
        self.switching_theme = False
        self.pending_theme_job = None
        self.theme_overlay = None
        self.button_registry = []
        self.segment_registry = []
        self.switch_registry = []

        self.build_ui()
        self.register_button(self.start_button, "primary")
        self.register_button(self.stop_button, "danger")
        self.enhance_buttons()
        self.apply_interactive_theme()
        self.attributes("-topmost", self.always_on_top.get())
        self.hide_when_running.trace_add("write", lambda *_args: self.save_settings())

        self.hotkeys = HotkeyThread(self)
        self.hotkeys.start()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(250, self.update_cursor_preview)

    def build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=230, corner_radius=0, fg_color=UI["sidebar"])
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(8, weight=1)

        ctk.CTkLabel(self.sidebar, text=APP_TITLE, text_color=UI["text"], font=ctk.CTkFont(size=28, weight="bold")).grid(row=0, column=0, padx=24, pady=(28, 4), sticky="w")
        ctk.CTkLabel(self.sidebar, text="Auto clicker & macro", text_color=UI["text_muted"]).grid(row=1, column=0, padx=24, pady=(0, 20), sticky="w")

        self.status_badge = ctk.CTkLabel(self.sidebar, textvariable=self.status_text, height=44, corner_radius=14, fg_color=UI["accent_soft"], text_color=UI["accent"], font=ctk.CTkFont(size=18, weight="bold"))
        self.status_badge.grid(row=2, column=0, padx=20, pady=(0, 18), sticky="ew")

        self.start_button = ctk.CTkButton(self.sidebar, text="开始  F6", height=44, corner_radius=12, fg_color=UI["accent"], hover_color=UI["accent_hover"], command=self.start)
        self.start_button.grid(row=3, column=0, padx=20, pady=(0, 10), sticky="ew")
        self.stop_button = ctk.CTkButton(self.sidebar, text="停止  F8", height=44, corner_radius=12, fg_color=UI["danger"], hover_color=UI["danger_hover"], command=self.stop)
        self.stop_button.grid(row=4, column=0, padx=20, pady=(0, 18), sticky="ew")

        ctk.CTkLabel(self.sidebar, text="快捷键", text_color=UI["text_muted"], anchor="w").grid(row=5, column=0, padx=24, sticky="ew")
        shortcuts = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        shortcuts.grid(row=6, column=0, padx=20, pady=(10, 20), sticky="ew")
        shortcuts.grid_columnconfigure(1, weight=1)
        for row, (key, text) in enumerate((
            ("F6", "开始 / 停止"),
            ("F7", "记录坐标"),
            ("F8", "急停"),
            ("F9", "录制脚本"),
            ("F10", "播放脚本"),
        )):
            self.shortcut_row(shortcuts, row, key, text)

        ctk.CTkLabel(self.sidebar, text="外观", text_color=UI["text_muted"], anchor="w").grid(row=9, column=0, padx=24, pady=(0, 8), sticky="ew")
        self.theme_switch = ctk.CTkSegmentedButton(
            self.sidebar,
            values=["深色", "浅色"],
            variable=self.theme_name,
            fg_color=UI["panel_soft"],
            selected_color=UI["accent"],
            selected_hover_color=UI["accent_hover"],
            unselected_hover_color=UI["neutral_hover"],
            text_color=UI["text"],
            command=self.switch_theme,
        )
        self.theme_switch.grid(row=10, column=0, padx=20, pady=(0, 12), sticky="ew")
        self.segment_registry.append(self.theme_switch)
        self.top_switch = ctk.CTkSwitch(self.sidebar, text="窗口置顶", variable=self.always_on_top, progress_color=UI["accent"], button_hover_color=UI["accent_hover"], command=self.toggle_topmost)
        self.top_switch.grid(row=11, column=0, padx=24, pady=(0, 10), sticky="w")
        self.hide_switch = ctk.CTkSwitch(self.sidebar, text="开始后隐藏", variable=self.hide_when_running, progress_color=UI["accent"], button_hover_color=UI["accent_hover"], command=self.save_settings)
        self.hide_switch.grid(row=12, column=0, padx=24, pady=(0, 24), sticky="w")
        self.switch_registry.extend([self.top_switch, self.hide_switch])

        self.main = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main.grid(row=0, column=1, sticky="nsew", padx=24, pady=24)
        self.main.grid_rowconfigure(1, weight=1)
        self.main.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self.main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="自动点击与脚本录制", text_color=UI["text"], font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(header, text="参考 CustomTkinter / Fluent 风格重做的现代桌面工具界面", text_color=UI["text_muted"]).grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.tabs = ctk.CTkTabview(
            self.main,
            corner_radius=18,
            fg_color=UI["panel"],
            border_width=1,
            border_color=UI["border"],
            segmented_button_fg_color=UI["panel_soft"],
            segmented_button_selected_color=UI["accent"],
            segmented_button_selected_hover_color=UI["accent_hover"],
            segmented_button_unselected_hover_color=UI["neutral_hover"],
        )
        self.tabs.grid(row=1, column=0, sticky="nsew")
        self.click_tab = self.tabs.add("连点")
        self.script_tab = self.tabs.add("脚本")
        self.stats_tab = self.tabs.add("状态")
        self.tabs._segmented_button.configure(
            width=360,
            height=40,
            corner_radius=12,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.tabs._segmented_button.grid_configure(sticky="w", padx=22, pady=(18, 8))
        self.build_click_tab()
        self.build_script_tab()
        self.build_stats_tab()

    def build_click_tab(self):
        tab = self.click_tab
        tab.grid_columnconfigure((0, 1), weight=1)

        self.input_card(tab, "点击间隔", self.interval_ms, "ms").grid(row=0, column=0, padx=(10, 8), pady=(10, 10), sticky="ew")
        self.input_card(tab, "随机浮动", self.jitter_ms, "ms").grid(row=0, column=1, padx=(8, 10), pady=(10, 10), sticky="ew")
        self.input_card(tab, "启动延迟", self.start_delay, "s").grid(row=1, column=0, padx=(10, 8), pady=10, sticky="ew")
        self.input_card(tab, "固定次数", self.repeat_count, "次").grid(row=1, column=1, padx=(8, 10), pady=10, sticky="ew")

        self.segment_card(tab, "鼠标按键", self.mouse_button, ["左键", "右键", "中键"]).grid(row=2, column=0, padx=(10, 8), pady=10, sticky="ew")
        self.segment_card(tab, "点击方式", self.click_mode, ["单击", "双击"]).grid(row=2, column=1, padx=(8, 10), pady=10, sticky="ew")
        self.segment_card(tab, "重复模式", self.repeat_mode, ["一直点击", "固定次数"]).grid(row=3, column=0, padx=(10, 8), pady=10, sticky="ew")
        self.segment_card(tab, "点击位置", self.position_mode, ["当前位置", "固定坐标"]).grid(row=3, column=1, padx=(8, 10), pady=10, sticky="ew")

        preset = ctk.CTkFrame(tab, corner_radius=18, fg_color=UI["panel"])
        preset.grid(row=4, column=0, columnspan=2, padx=10, pady=(12, 10), sticky="ew")
        preset.grid_columnconfigure((0, 1, 2, 3), weight=1)
        ctk.CTkLabel(preset, text="速度预设", text_color=UI["text"], font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=0, columnspan=4, padx=18, pady=(16, 10), sticky="w")
        for col, (text, interval, jitter) in enumerate((("稳一点", 250, 20), ("常用", 100, 0), ("快速", 25, 5), ("极快", 5, 0))):
            self.styled_button(preset, text, lambda i=interval, j=jitter: self.apply_preset(i, j), kind="soft", height=36).grid(row=1, column=col, padx=8, pady=(0, 16), sticky="ew")

    def build_script_tab(self):
        tab = self.script_tab
        tab.grid_columnconfigure(0, weight=1)

        summary = ctk.CTkFrame(tab, corner_radius=18, fg_color=UI["panel"])
        summary.grid(row=0, column=0, padx=10, pady=(10, 10), sticky="ew")
        summary.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(summary, text="脚本录制", text_color=UI["text"], font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=18, pady=(16, 4), sticky="w")
        ctk.CTkLabel(summary, textvariable=self.script_summary, text_color=UI["text_muted"]).grid(row=1, column=0, padx=18, pady=(0, 16), sticky="w")

        controls = ctk.CTkFrame(tab, corner_radius=18, fg_color=UI["panel"])
        controls.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        controls.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self.small_entry(controls, "循环次数", self.script_repeat).grid(row=0, column=0, padx=(16, 8), pady=16, sticky="ew")
        self.small_entry(controls, "速度倍率", self.script_speed).grid(row=0, column=1, padx=8, pady=16, sticky="ew")
        ctk.CTkCheckBox(controls, text="记录鼠标移动轨迹", variable=self.record_moves).grid(row=0, column=2, columnspan=2, padx=16, pady=16, sticky="w")

        text_card = ctk.CTkFrame(tab, corner_radius=18, fg_color=UI["panel"])
        text_card.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        text_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(text_card, text="文本输入事件", text_color=UI["text"], font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=0, columnspan=2, padx=18, pady=(16, 8), sticky="w")
        ctk.CTkEntry(text_card, textvariable=self.script_text_input, height=42, placeholder_text="输入要回放的文本，支持中文和符号", fg_color=UI["field"], border_color=UI["border"], text_color=UI["text"], placeholder_text_color=UI["text_muted"]).grid(row=1, column=0, padx=(18, 8), pady=(0, 18), sticky="ew")
        self.styled_button(text_card, "添加文本输入", self.add_text_input_event, height=42).grid(row=1, column=1, padx=(8, 18), pady=(0, 18), sticky="e")

        actions = ctk.CTkFrame(tab, corner_radius=18, fg_color=UI["panel"])
        actions.grid(row=3, column=0, padx=10, pady=10, sticky="ew")
        actions.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        self.record_button = self.styled_button(actions, "录制 F9", self.toggle_recording, kind="danger", height=42)
        self.record_button.grid(row=0, column=0, padx=(16, 8), pady=16, sticky="ew")
        self.styled_button(actions, "播放 F10", self.play_script, height=42).grid(row=0, column=1, padx=8, pady=16, sticky="ew")
        self.styled_button(actions, "保存", self.save_script, kind="soft", height=42).grid(row=0, column=2, padx=8, pady=16, sticky="ew")
        self.styled_button(actions, "加载", self.load_script, kind="soft", height=42).grid(row=0, column=3, padx=8, pady=16, sticky="ew")
        self.styled_button(actions, "清空", self.clear_script, kind="neutral", height=42).grid(row=0, column=4, padx=(8, 16), pady=16, sticky="ew")

    def build_stats_tab(self):
        tab = self.stats_tab
        tab.grid_columnconfigure((0, 1), weight=1)

        self.metric_card(tab, "点击次数", self.counter_text).grid(row=0, column=0, padx=(10, 8), pady=(10, 10), sticky="ew")
        self.metric_card(tab, "当前速度", self.speed_text).grid(row=0, column=1, padx=(8, 10), pady=(10, 10), sticky="ew")
        self.metric_card(tab, "坐标 X", self.fixed_x).grid(row=1, column=0, padx=(10, 8), pady=10, sticky="ew")
        self.metric_card(tab, "坐标 Y", self.fixed_y).grid(row=1, column=1, padx=(8, 10), pady=10, sticky="ew")

        coord_actions = ctk.CTkFrame(tab, corner_radius=18, fg_color=UI["panel"])
        coord_actions.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        coord_actions.grid_columnconfigure((0, 1), weight=1)
        self.styled_button(coord_actions, "记录当前位置 F7", self.capture_position, height=44).grid(row=0, column=0, padx=(16, 8), pady=16, sticky="ew")
        self.styled_button(coord_actions, "3 秒后取点", self.capture_position_after_delay, kind="soft", height=44).grid(row=0, column=1, padx=(8, 16), pady=16, sticky="ew")

    def input_card(self, master, title, variable, suffix):
        frame = ctk.CTkFrame(master, corner_radius=18, fg_color=UI["panel"])
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(frame, text=title, text_color=UI["text_muted"]).grid(row=0, column=0, padx=18, pady=(16, 4), sticky="w")
        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.grid(row=1, column=0, padx=18, pady=(0, 16), sticky="ew")
        row.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(row, textvariable=variable, height=44, font=ctk.CTkFont(size=20, weight="bold"), justify="right", fg_color=UI["field"], border_color=UI["border"], text_color=UI["text"]).grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(row, text=suffix, text_color=UI["text_muted"]).grid(row=0, column=1, padx=(10, 0))
        return frame

    def segment_card(self, master, title, variable, values):
        frame = ctk.CTkFrame(master, corner_radius=18, fg_color=UI["panel"])
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(frame, text=title, text_color=UI["text_muted"]).grid(row=0, column=0, padx=18, pady=(16, 8), sticky="w")
        segment = ctk.CTkSegmentedButton(
            frame,
            values=values,
            variable=variable,
            fg_color=UI["panel_soft"],
            selected_color=UI["accent"],
            selected_hover_color=UI["accent_hover"],
            unselected_hover_color=UI["neutral_hover"],
            text_color=UI["text"],
        )
        segment.grid(row=1, column=0, padx=18, pady=(0, 16), sticky="ew")
        self.segment_registry.append(segment)
        return frame

    def small_entry(self, master, title, variable):
        frame = ctk.CTkFrame(master, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(frame, text=title, text_color=UI["text_muted"]).grid(row=0, column=0, sticky="w")
        ctk.CTkEntry(frame, textvariable=variable, height=38, fg_color=UI["field"], border_color=UI["border"], text_color=UI["text"]).grid(row=1, column=0, pady=(6, 0), sticky="ew")
        return frame

    def metric_card(self, master, title, variable):
        frame = ctk.CTkFrame(master, corner_radius=18, fg_color=UI["panel"])
        ctk.CTkLabel(frame, text=title, text_color=UI["text_muted"]).grid(row=0, column=0, padx=18, pady=(16, 4), sticky="w")
        ctk.CTkLabel(frame, textvariable=variable, text_color=UI["text"], font=ctk.CTkFont(size=28, weight="bold")).grid(row=1, column=0, padx=18, pady=(0, 18), sticky="w")
        return frame

    def shortcut_row(self, master, row, key, text):
        keycap = ctk.CTkLabel(
            master,
            text=key,
            width=44,
            height=26,
            corner_radius=8,
            fg_color=UI["panel_soft"],
            text_color=UI["text"],
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        keycap.grid(row=row, column=0, padx=(0, 10), pady=4, sticky="w")
        ctk.CTkLabel(
            master,
            text=text,
            text_color=UI["text_muted"],
            font=ctk.CTkFont(size=13),
            anchor="w",
        ).grid(row=row, column=1, pady=4, sticky="ew")

    def styled_button(self, master, text, command, kind="primary", height=40):
        if kind == "danger":
            fg_color, hover_color = UI["danger"], UI["danger_hover"]
        elif kind == "neutral":
            fg_color, hover_color = UI["neutral"], UI["neutral_hover"]
        elif kind == "soft":
            fg_color, hover_color = UI["panel_soft"], UI["neutral_hover"]
        else:
            fg_color, hover_color = UI["accent"], UI["accent_hover"]

        text_color = ("#0f172a", "#f8fafc") if kind in ("soft", "neutral") else "#ffffff"
        button = ctk.CTkButton(
            master,
            text=text,
            height=height,
            corner_radius=12,
            fg_color=fg_color,
            hover_color=hover_color,
            text_color=text_color,
            border_width=0,
            border_color=UI["accent"],
            command=command,
        )
        self.register_button(button, kind)
        return button

    def register_button(self, button, kind):
        button._pulse_kind = kind
        if not any(item[0] is button for item in self.button_registry):
            self.button_registry.append((button, kind))

    def ui_color(self, key):
        value = UI[key]
        if isinstance(value, tuple):
            return value[1] if self.theme_name.get() == "深色" else value[0]
        return value

    def button_colors(self, kind):
        if kind == "danger":
            return self.ui_color("danger"), self.ui_color("danger_hover"), "#ffffff"
        if kind == "neutral":
            return self.ui_color("neutral"), self.ui_color("neutral_hover"), self.ui_color("text")
        if kind == "soft":
            return self.ui_color("panel_soft"), self.ui_color("neutral_hover"), self.ui_color("text")
        return self.ui_color("accent"), self.ui_color("accent_hover"), "#ffffff"

    def apply_interactive_theme(self):
        for button, kind in list(self.button_registry):
            if not button.winfo_exists():
                continue
            fg_color, hover_color, text_color = self.button_colors(kind)
            button.configure(
                fg_color=fg_color,
                hover_color=hover_color,
                text_color=text_color,
                border_color=self.ui_color("accent"),
            )

        for segment in list(self.segment_registry):
            if not segment.winfo_exists():
                continue
            segment.configure(
                fg_color=self.ui_color("panel_soft"),
                selected_color=self.ui_color("accent"),
                selected_hover_color=self.ui_color("accent_hover"),
                unselected_hover_color=self.ui_color("neutral_hover"),
                text_color=self.ui_color("text"),
            )

        for switch in list(self.switch_registry):
            if not switch.winfo_exists():
                continue
            switch.configure(
                progress_color=self.ui_color("accent"),
                button_hover_color=self.ui_color("accent_hover"),
                text_color=self.ui_color("text"),
            )

        if hasattr(self, "status_badge") and self.status_badge.winfo_exists():
            self.status_badge.configure(
                fg_color=self.ui_color("accent_soft"),
                text_color=self.ui_color("accent"),
            )

    def enhance_buttons(self):
        def visit(widget):
            if isinstance(widget, ctk.CTkButton):
                widget.configure(cursor="hand2")

                def enter(_event, button=widget):
                    if str(button.cget("state")) != "disabled":
                        button.configure(border_width=2, border_color=self.ui_color("accent"))

                def leave(_event, button=widget):
                    if button.winfo_exists():
                        button.configure(border_width=0)

                widget.bind("<Enter>", enter, add="+")
                widget.bind("<Leave>", leave, add="+")

            for child in widget.winfo_children():
                visit(child)

        visit(self)

    def load_settings(self):
        if not os.path.exists(SETTINGS_FILE):
            return {}
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def save_settings(self):
        data = {
            "theme": self.theme_name.get(),
            "always_on_top": bool(self.always_on_top.get()),
            "hide_when_running": bool(self.hide_when_running.get()),
        }
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def switch_theme(self, _value=None):
        if self.pending_theme_job:
            self.after_cancel(self.pending_theme_job)
        if not self.switching_theme:
            self.switching_theme = True
            self.theme_switch.configure(state="disabled")
            self.show_theme_overlay()
            self.update_idletasks()
        self.pending_theme_job = self.after(60, self.apply_theme_switch)

    def apply_theme_switch(self):
        self.pending_theme_job = None
        ctk.set_appearance_mode("Dark" if self.theme_name.get() == "深色" else "Light")
        self.apply_interactive_theme()
        self.save_settings()
        self.after(80, lambda: self.fade_theme_overlay(0.92))
        self.after(120, lambda: self.fade_theme_overlay(0.75))
        self.after(160, lambda: self.fade_theme_overlay(0.45))
        self.after(200, lambda: self.fade_theme_overlay(0.18))
        self.after(240, self.finish_theme_switch)

    def show_theme_overlay(self):
        if self.theme_overlay and self.theme_overlay.winfo_exists():
            self.theme_overlay.destroy()

        palette = FLAT_THEME[self.theme_name.get()]
        self.update_idletasks()
        x = self.winfo_rootx()
        y = self.winfo_rooty()
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())

        overlay = tk.Toplevel(self)
        overlay.overrideredirect(True)
        overlay.configure(bg=palette["overlay"])
        overlay.geometry(f"{width}x{height}+{x}+{y}")
        overlay.attributes("-alpha", 0.98)
        overlay.attributes("-topmost", True)
        label = tk.Label(
            overlay,
            text="切换主题中...",
            bg=palette["overlay"],
            fg=palette["overlay_text"],
            font=("Microsoft YaHei UI", 18, "bold"),
        )
        label.place(relx=0.5, rely=0.5, anchor="center")
        overlay.lift()
        self.theme_overlay = overlay

    def fade_theme_overlay(self, alpha):
        if self.theme_overlay and self.theme_overlay.winfo_exists():
            self.theme_overlay.attributes("-alpha", alpha)

    def finish_theme_switch(self):
        if self.theme_overlay and self.theme_overlay.winfo_exists():
            self.theme_overlay.destroy()
        self.theme_overlay = None
        self.switching_theme = False
        self.theme_switch.configure(state="normal")
        self.apply_interactive_theme()

    def toggle_topmost(self):
        self.attributes("-topmost", self.always_on_top.get())
        self.save_settings()

    def apply_preset(self, interval, jitter):
        self.interval_ms.set(str(interval))
        self.jitter_ms.set(str(jitter))

    def validate_settings(self):
        try:
            interval = max(1, int(float(self.interval_ms.get())))
            jitter = max(0, int(float(self.jitter_ms.get())))
            delay = max(0, float(self.start_delay.get()))
            count = max(1, int(float(self.repeat_count.get())))
        except ValueError:
            messagebox.showerror("设置错误", "点击间隔、随机浮动、启动延迟和次数都需要填写数字。")
            return None

        if self.position_mode.get() == "固定坐标" and self.fixed_position is None:
            messagebox.showerror("设置错误", "固定坐标模式需要先记录鼠标位置。")
            return None

        return {
            "interval": interval / 1000,
            "jitter": jitter / 1000,
            "delay": delay,
            "button": self.mouse_button.get(),
            "clicks_per_cycle": 2 if self.click_mode.get() == "双击" else 1,
            "repeat_forever": self.repeat_mode.get() == "一直点击",
            "repeat_count": count,
            "position": self.fixed_position if self.position_mode.get() == "固定坐标" else None,
        }

    def start(self):
        if self.worker and self.worker.is_alive():
            return
        if self.recording:
            self.stop_recording()
        settings = self.validate_settings()
        if not settings:
            return
        self.stop_event.clear()
        self.clicks_done = 0
        self.started_at = time.time()
        self.set_running_ui(True)
        if self.hide_when_running.get():
            self.iconify()
        self.worker = threading.Thread(target=self.click_loop, args=(settings,), daemon=True)
        self.worker.start()

    def stop(self):
        if self.recording:
            self.stop_recording()
        self.stop_event.set()
        self.set_running_ui(False)
        self.status_text.set("STOPPED")

    def click_loop(self, settings):
        if settings["delay"] and self.stop_event.wait(settings["delay"]):
            self.after(0, self.finish_run, "STOPPED")
            return

        down, up = BUTTON_FLAGS[settings["button"]]
        cycles = 0
        while not self.stop_event.is_set():
            if not settings["repeat_forever"] and cycles >= settings["repeat_count"]:
                break
            if settings["position"] is not None:
                user32.SetCursorPos(settings["position"][0], settings["position"][1])

            for _ in range(settings["clicks_per_cycle"]):
                user32.mouse_event(down, 0, 0, 0, 0)
                time.sleep(0.015)
                user32.mouse_event(up, 0, 0, 0, 0)
                self.clicks_done += 1
                self.after(0, self.refresh_counter)
                if settings["clicks_per_cycle"] > 1:
                    time.sleep(0.06)

            cycles += 1
            wait_time = settings["interval"]
            if settings["jitter"]:
                wait_time = max(0.001, wait_time + random.uniform(-settings["jitter"], settings["jitter"]))
            if self.stop_event.wait(wait_time):
                break

        self.after(0, self.finish_run, "DONE" if not self.stop_event.is_set() else "STOPPED")

    def finish_run(self, status):
        self.stop_event.set()
        self.set_running_ui(False)
        self.status_text.set(status)
        self.refresh_counter()

    def set_running_ui(self, running):
        self.status_text.set("RUNNING" if running else "READY")
        self.start_button.configure(state="disabled" if running else "normal")
        self.stop_button.configure(state="normal")
        self.apply_interactive_theme()

    def refresh_counter(self):
        elapsed = 0 if not self.started_at else max(0.001, time.time() - self.started_at)
        cps = self.clicks_done / elapsed if self.clicks_done else 0
        self.counter_text.set(str(self.clicks_done))
        self.speed_text.set(f"{cps:.1f}/s")

    def capture_position(self):
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        self.fixed_position = (pt.x, pt.y)
        self.fixed_x.set(str(pt.x))
        self.fixed_y.set(str(pt.y))
        self.position_mode.set("固定坐标")
        self.status_text.set("POINT SET")

    def capture_position_after_delay(self):
        if self.picking_after_delay:
            return
        self.picking_after_delay = True
        self.status_text.set("PICKING")
        self.after(3000, self.finish_delayed_capture)

    def finish_delayed_capture(self):
        self.picking_after_delay = False
        self.capture_position()

    def update_cursor_preview(self):
        if self.position_mode.get() == "当前位置" and not (self.worker and self.worker.is_alive()):
            pt = POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            self.fixed_x.set(str(pt.x))
            self.fixed_y.set(str(pt.y))
        self.after(250, self.update_cursor_preview)

    def toggle_recording(self):
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        if self.worker and self.worker.is_alive():
            messagebox.showerror("正在运行", "请先停止连点或脚本回放，再开始录制。")
            return
        self.script_events = []
        self.record_stop_event.clear()
        self.recording = True
        self.record_button.configure(text="停止录制 F9")
        self.apply_interactive_theme()
        self.status_text.set("RECORDING")
        self.refresh_script_summary()
        self.recorder = threading.Thread(target=self.record_loop, daemon=True)
        self.recorder.start()

    def stop_recording(self):
        self.record_stop_event.set()
        self.recording = False
        self.record_button.configure(text="录制 F9")
        self.apply_interactive_theme()
        self.status_text.set("RECORDED")
        self.refresh_script_summary()

    def record_loop(self):
        last_time = time.time()
        last_move_time = last_time
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        last_pos = (pt.x, pt.y)
        mouse_state = {name: self.is_key_down(info["vk"]) for name, info in RECORD_BUTTONS.items()}
        key_state = {vk: self.is_key_down(vk) for vk in RECORD_KEY_CODES}

        while not self.record_stop_event.is_set():
            now = time.time()
            user32.GetCursorPos(ctypes.byref(pt))
            pos = (pt.x, pt.y)

            if self.record_moves.get() and now - last_move_time >= 0.05 and math.dist(pos, last_pos) >= 12:
                self.add_script_event({"type": "move", "delay": now - last_time, "x": pos[0], "y": pos[1]})
                last_time = now
                last_move_time = now
                last_pos = pos

            for name, info in RECORD_BUTTONS.items():
                down = self.is_key_down(info["vk"])
                if down != mouse_state[name]:
                    self.add_script_event({
                        "type": "mouse",
                        "delay": now - last_time,
                        "button": name,
                        "button_name": info["name"],
                        "action": "down" if down else "up",
                        "x": pos[0],
                        "y": pos[1],
                    })
                    mouse_state[name] = down
                    last_time = now
                    last_pos = pos

            for vk in RECORD_KEY_CODES:
                down = self.is_key_down(vk)
                if down != key_state[vk]:
                    char = self.vk_to_char(vk) if down else ""
                    if char:
                        self.add_text_record_event(char, now - last_time)
                    elif not self.is_printable_key(vk):
                        self.add_script_event({
                            "type": "key",
                            "delay": now - last_time,
                            "vk": vk,
                            "name": KEY_NAMES.get(vk, str(vk)),
                            "action": "down" if down else "up",
                        })
                    key_state[vk] = down
                    last_time = now

            time.sleep(0.01)

    def is_key_down(self, vk):
        return bool(user32.GetAsyncKeyState(vk) & 0x8000)

    def is_printable_key(self, vk):
        return 0x30 <= vk <= 0x5A or vk in (0x20, 0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF, 0xC0, 0xDB, 0xDC, 0xDD, 0xDE)

    def vk_to_char(self, vk):
        if self.is_key_down(0x11) or self.is_key_down(0x12):
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

    def add_script_event(self, event):
        self.script_events.append(event)
        self.after(0, self.refresh_script_summary)

    def add_text_record_event(self, text, delay):
        if not text:
            return
        if self.script_events and self.script_events[-1]["type"] == "text" and delay < 1:
            self.script_events[-1]["text"] += text
        else:
            self.script_events.append({"type": "text", "delay": delay, "text": text})
        self.after(0, self.refresh_script_summary)

    def add_text_input_event(self):
        text = self.script_text_input.get()
        if not text:
            return
        self.script_events.append({"type": "text", "delay": 0.1, "text": text})
        self.script_text_input.set("")
        self.refresh_script_summary()
        self.status_text.set("TEXT ADDED")

    def refresh_script_summary(self):
        moves = sum(1 for event in self.script_events if event["type"] == "move")
        clicks = sum(1 for event in self.script_events if event["type"] == "mouse")
        keys = sum(1 for event in self.script_events if event["type"] == "key")
        texts = sum(len(event.get("text", "")) for event in self.script_events if event["type"] == "text")
        duration = sum(event.get("delay", 0) for event in self.script_events)
        self.script_summary.set(f"{len(self.script_events)} 个事件 · {duration:.1f}s · 鼠标{clicks} 键盘{keys} 文本{texts} 移动{moves}")

    def play_script(self):
        if self.recording:
            self.stop_recording()
        if self.worker and self.worker.is_alive():
            return
        if not self.script_events:
            messagebox.showerror("没有脚本", "请先录制或加载一个脚本。")
            return
        try:
            repeat = max(1, int(float(self.script_repeat.get())))
            speed = max(0.1, float(self.script_speed.get()))
        except ValueError:
            messagebox.showerror("设置错误", "脚本循环和速度倍率需要填写数字。")
            return

        self.stop_event.clear()
        self.clicks_done = 0
        self.started_at = time.time()
        self.set_running_ui(True)
        self.status_text.set("SCRIPT")
        self.worker = threading.Thread(target=self.script_loop, args=(list(self.script_events), repeat, speed), daemon=True)
        self.worker.start()

    def script_loop(self, events, repeat, speed):
        for _ in range(repeat):
            for event in events:
                delay = max(0, event.get("delay", 0) / speed)
                if self.stop_event.wait(delay):
                    self.after(0, self.finish_run, "STOPPED")
                    return
                self.perform_script_event(event)
                self.clicks_done += 1
                self.after(0, self.refresh_counter)
        self.after(0, self.finish_run, "DONE")

    def perform_script_event(self, event):
        if event["type"] == "move":
            user32.SetCursorPos(int(event["x"]), int(event["y"]))
            return
        if event["type"] == "mouse":
            info = RECORD_BUTTONS[event["button"]]
            user32.SetCursorPos(int(event["x"]), int(event["y"]))
            flag = info["down"] if event["action"] == "down" else info["up"]
            user32.mouse_event(flag, 0, 0, 0, 0)
            return
        if event["type"] == "key":
            flag = 0 if event["action"] == "down" else KEYEVENTF_KEYUP
            user32.keybd_event(int(event["vk"]), 0, flag, 0)
            return
        if event["type"] == "text":
            self.send_unicode_text(event.get("text", ""))

    def send_unicode_text(self, text):
        for char in text:
            code = ord(char)
            down = INPUT(type=INPUT_KEYBOARD, union=INPUT_UNION(ki=KEYBDINPUT(0, code, KEYEVENTF_UNICODE, 0, None)))
            up = INPUT(type=INPUT_KEYBOARD, union=INPUT_UNION(ki=KEYBDINPUT(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, None)))
            user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT))
            user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT))
            time.sleep(0.01)

    def save_script(self):
        if not self.script_events:
            messagebox.showerror("没有脚本", "当前没有可保存的脚本。")
            return
        path = filedialog.asksaveasfilename(
            title="保存脚本",
            defaultextension=".json",
            filetypes=[("PulseClick 脚本", "*.json"), ("所有文件", "*.*")],
        )
        if not path:
            return
        data = {
            "app": APP_TITLE,
            "version": 1,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "events": self.script_events,
        }
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        self.status_text.set("SAVED")

    def load_script(self):
        path = filedialog.askopenfilename(
            title="加载脚本",
            filetypes=[("PulseClick 脚本", "*.json"), ("所有文件", "*.*")],
        )
        if not path:
            return
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        events = data.get("events", data if isinstance(data, list) else [])
        if not isinstance(events, list):
            messagebox.showerror("脚本错误", "脚本文件格式不正确。")
            return
        self.script_events = events
        self.refresh_script_summary()
        self.status_text.set("LOADED")

    def clear_script(self):
        self.script_events = []
        self.refresh_script_summary()
        self.status_text.set("CLEARED")

    def handle_hotkey(self, hotkey_id):
        if hotkey_id == 1:
            if self.worker and self.worker.is_alive():
                self.stop()
            else:
                self.start()
        elif hotkey_id == 2:
            self.capture_position()
        elif hotkey_id == 3:
            self.stop()
            self.deiconify()
        elif hotkey_id == 4:
            self.toggle_recording()
        elif hotkey_id == 5:
            self.play_script()

    def on_close(self):
        self.stop_event.set()
        self.record_stop_event.set()
        if self.pending_theme_job:
            self.after_cancel(self.pending_theme_job)
            self.pending_theme_job = None
        if self.theme_overlay and self.theme_overlay.winfo_exists():
            self.theme_overlay.destroy()
        self.hotkeys.stop()
        self.destroy()


if __name__ == "__main__":
    AutoClickerApp().mainloop()
