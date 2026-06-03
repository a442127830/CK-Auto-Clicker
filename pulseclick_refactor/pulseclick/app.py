import json
import os
import time
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    import customtkinter as ctk
except ImportError:
    messagebox.showerror("缺少依赖", "请先运行：python -m pip install customtkinter")
    raise

from .clicker import ClickSettings, ClickerService
from .constants import APP_TITLE, BUTTON_NAMES, CLICK_MODES, HOTKEYS, POSITION_MODES, REPEAT_MODES
from .hotkeys import HotkeyThread
from .recorder import RecorderService
from .script_player import ScriptPlayerService
from .settings import SettingsStore
from .theme import appearance, normalize_theme, token
from .win32 import get_cursor_pos


RADIUS = 14


class PulseClickApp(ctk.CTk):
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.settings_store = SettingsStore(self.base_dir)
        self.settings = self.settings_store.load()
        saved_theme = normalize_theme(self.settings.get("theme", "棕色"))
        ctk.set_appearance_mode(appearance(saved_theme))
        ctk.set_default_color_theme("blue")

        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1120x740")
        self.minsize(1020, 680)

        self.theme_name = tk.StringVar(value=saved_theme)
        self.always_on_top = tk.BooleanVar(value=bool(self.settings.get("always_on_top", False)))
        self.hide_when_running = tk.BooleanVar(value=bool(self.settings.get("hide_when_running", False)))
        self.record_moves = tk.BooleanVar(value=False)

        self.interval_ms = tk.StringVar(value="100")
        self.jitter_ms = tk.StringVar(value="0")
        self.start_delay = tk.StringVar(value="0")
        self.repeat_count = tk.StringVar(value="100")
        self.mouse_button = tk.StringVar(value="左键")
        self.click_mode = tk.StringVar(value="单击")
        self.repeat_mode = tk.StringVar(value="一直点击")
        self.position_mode = tk.StringVar(value="当前位置")
        self.fixed_x = tk.StringVar(value="-")
        self.fixed_y = tk.StringVar(value="-")

        self.status_text = tk.StringVar(value="READY")
        self.click_count_text = tk.StringVar(value="0")
        self.speed_text = tk.StringVar(value="0.0/s")
        self.script_summary = tk.StringVar(value="0 个事件")
        self.script_repeat = tk.StringVar(value="1")
        self.script_speed = tk.StringVar(value="1.0")
        self.script_text = tk.StringVar(value="")
        self.hotkey_status = tk.StringVar(value="热键已启用")
        self.page_name = tk.StringVar(value="连点")

        self.fixed_position = None
        self.clicks_done = 0
        self.started_at = None
        self.script_events = []
        self.picking_after_delay = False
        self.recording = False
        self.theme_overlay = None
        self.theme_jobs = []

        self.roles = []
        self.pages = {}

        self.clicker = ClickerService(self._thread_click, self._thread_done)
        self.player = ScriptPlayerService(self._thread_click, self._thread_done)
        self.recorder = RecorderService(self._thread_record_event)
        self.hotkeys = HotkeyThread(self._thread_hotkey, self._thread_hotkey_error)

        self._build_ui()
        self.apply_theme(animated=False)
        self.attributes("-topmost", self.always_on_top.get())
        self.hotkeys.start()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(250, self.update_cursor_preview)

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.shell = self.role(
            ctk.CTkScrollableFrame(
                self,
                corner_radius=0,
                fg_color="transparent",
                scrollbar_button_color=token(self.mode(), "surface_3"),
                scrollbar_button_hover_color=token(self.mode(), "muted"),
            ),
            "global_scroll",
        )
        self.shell.grid(row=0, column=0, sticky="nsew")
        self.shell.grid_columnconfigure(1, weight=1)

        self.sidebar = self.role(ctk.CTkFrame(self.shell, width=238, corner_radius=0), "sidebar")
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, padx=20, pady=(22, 18), sticky="ew")
        brand.grid_columnconfigure(1, weight=1)
        self.logo = self.role(ctk.CTkLabel(brand, text="P", width=42, height=42, corner_radius=12, font=ctk.CTkFont(size=20, weight="bold")), "brand_badge")
        self.logo.grid(row=0, column=0, rowspan=2, padx=(0, 12), sticky="w")
        self.role(ctk.CTkLabel(brand, text="PulseClick", font=ctk.CTkFont(size=21, weight="bold")), "title").grid(row=0, column=1, sticky="w")
        self.role(ctk.CTkLabel(brand, text="自动点击工具", font=ctk.CTkFont(size=12)), "muted").grid(row=1, column=1, sticky="w", pady=(2, 0))

        self.status_card = self.role(ctk.CTkFrame(self.sidebar, corner_radius=18), "primary_soft_panel")
        self.status_card.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="ew")
        self.status_card.grid_columnconfigure(0, weight=1)
        self.role(ctk.CTkLabel(self.status_card, text="当前状态", font=ctk.CTkFont(size=12)), "muted").grid(row=0, column=0, padx=16, pady=(14, 2), sticky="w")
        self.status_badge = self.role(ctk.CTkLabel(self.status_card, textvariable=self.status_text, font=ctk.CTkFont(size=26, weight="bold")), "primary_text_label")
        self.status_badge.grid(row=1, column=0, padx=16, pady=(0, 14), sticky="w")

        controls = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        controls.grid(row=2, column=0, padx=16, pady=(0, 12), sticky="ew")
        controls.grid_columnconfigure(0, weight=1)
        self.start_button = self.button(controls, "开始  F6", self.start, "primary")
        self.start_button.grid(row=0, column=0, pady=(0, 10), sticky="ew")
        self.stop_button = self.button(controls, "停止  F8", self.stop, "danger")
        self.stop_button.grid(row=1, column=0, sticky="ew")

        nav = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        nav.grid(row=3, column=0, padx=16, pady=(4, 16), sticky="ew")
        nav.grid_columnconfigure(0, weight=1)
        self.nav_buttons = {}
        for row, name in enumerate(("连点", "脚本", "状态")):
            button = self.button(nav, name, lambda page=name: self.show_page(page), "nav")
            button.grid(row=row, column=0, pady=4, sticky="ew")
            self.nav_buttons[name] = button

        keys = self.role(ctk.CTkFrame(self.sidebar, corner_radius=RADIUS), "surface_2")
        keys.grid(row=4, column=0, padx=16, pady=(0, 16), sticky="ew")
        keys.grid_columnconfigure(1, weight=1)
        self.role(ctk.CTkLabel(keys, text="全局热键", font=ctk.CTkFont(size=13, weight="bold")), "text").grid(row=0, column=0, columnspan=2, padx=14, pady=(14, 8), sticky="w")
        for row, (_hid, _vk, key, label) in enumerate(HOTKEYS, start=1):
            self.role(ctk.CTkLabel(keys, text=key, width=42, height=24, corner_radius=8, font=ctk.CTkFont(size=11, weight="bold")), "keycap").grid(row=row, column=0, padx=(14, 10), pady=3, sticky="w")
            self.role(ctk.CTkLabel(keys, text=label, anchor="w", font=ctk.CTkFont(size=12)), "muted").grid(row=row, column=1, padx=(0, 14), pady=3, sticky="ew")
        self.role(ctk.CTkLabel(keys, textvariable=self.hotkey_status, wraplength=190, anchor="w", justify="left", font=ctk.CTkFont(size=12)), "subtle").grid(row=6, column=0, columnspan=2, padx=14, pady=(8, 14), sticky="ew")

        bottom = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom.grid(row=6, column=0, padx=16, pady=(0, 18), sticky="ew")
        bottom.grid_columnconfigure(0, weight=1)
        self.theme_switch = self.segment(bottom, ["棕色", "白色"], self.theme_name, self.switch_theme)
        self.theme_switch.grid(row=0, column=0, pady=(0, 12), sticky="ew")
        self.top_switch = self.role(ctk.CTkSwitch(bottom, text="窗口置顶", variable=self.always_on_top, command=self.toggle_topmost), "switch")
        self.top_switch.grid(row=1, column=0, pady=(0, 8), sticky="w")
        self.hide_switch = self.role(ctk.CTkSwitch(bottom, text="开始后隐藏", variable=self.hide_when_running, command=self.save_settings), "switch")
        self.hide_switch.grid(row=2, column=0, sticky="w")

        self.main = ctk.CTkFrame(self.shell, fg_color="transparent")
        self.main.grid(row=0, column=1, sticky="nsew", padx=26, pady=24)
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(1, weight=1)

        self.hero = self.role(ctk.CTkFrame(self.main, corner_radius=24), "hero")
        self.hero.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        self.hero.grid_columnconfigure(0, weight=1)
        self.role(ctk.CTkLabel(self.hero, text="连点器", font=ctk.CTkFont(size=30, weight="bold")), "title").grid(row=0, column=0, padx=24, pady=(22, 4), sticky="w")
        self.role(ctk.CTkLabel(self.hero, text="设置点击间隔、按键和坐标，支持热键启动与脚本回放", font=ctk.CTkFont(size=13)), "muted").grid(row=1, column=0, padx=24, pady=(0, 22), sticky="w")
        self.live_chip = self.role(ctk.CTkLabel(self.hero, textvariable=self.page_name, height=34, corner_radius=17, font=ctk.CTkFont(size=13, weight="bold")), "chip")
        self.live_chip.grid(row=0, column=1, rowspan=2, padx=24, sticky="e")

        self.content = ctk.CTkFrame(self.main, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)
        self.pages["连点"] = self._build_click_page()
        self.pages["脚本"] = self._build_script_page()
        self.pages["状态"] = self._build_stats_page()
        self.show_page("连点")

    def _build_click_page(self):
        page = ctk.CTkFrame(self.content, fg_color="transparent")
        page.grid_columnconfigure((0, 1), weight=1)
        self.input_card(page, "点击间隔", self.interval_ms, "ms").grid(row=0, column=0, padx=(0, 10), pady=(0, 12), sticky="ew")
        self.input_card(page, "随机浮动", self.jitter_ms, "ms").grid(row=0, column=1, padx=(10, 0), pady=(0, 12), sticky="ew")
        self.input_card(page, "启动延迟", self.start_delay, "s").grid(row=1, column=0, padx=(0, 10), pady=12, sticky="ew")
        self.input_card(page, "固定次数", self.repeat_count, "次").grid(row=1, column=1, padx=(10, 0), pady=12, sticky="ew")
        self.segment_card(page, "鼠标按键", self.mouse_button, BUTTON_NAMES).grid(row=2, column=0, padx=(0, 10), pady=12, sticky="ew")
        self.segment_card(page, "点击方式", self.click_mode, CLICK_MODES).grid(row=2, column=1, padx=(10, 0), pady=12, sticky="ew")
        self.segment_card(page, "重复模式", self.repeat_mode, REPEAT_MODES).grid(row=3, column=0, padx=(0, 10), pady=12, sticky="ew")
        self.segment_card(page, "点击位置", self.position_mode, POSITION_MODES).grid(row=3, column=1, padx=(10, 0), pady=12, sticky="ew")

        presets = self.role(ctk.CTkFrame(page, corner_radius=RADIUS), "surface")
        presets.grid(row=4, column=0, columnspan=2, pady=(12, 0), sticky="ew")
        presets.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self.role(ctk.CTkLabel(presets, text="速度预设", font=ctk.CTkFont(size=16, weight="bold")), "text").grid(row=0, column=0, columnspan=4, padx=18, pady=(18, 10), sticky="w")
        for col, (name, interval, jitter) in enumerate((("稳一点", 250, 20), ("常用", 100, 0), ("快速", 25, 5), ("极快", 5, 0))):
            self.button(presets, name, lambda i=interval, j=jitter: self.apply_preset(i, j), "soft").grid(row=1, column=col, padx=8, pady=(0, 18), sticky="ew")
        return page

    def _build_script_page(self):
        page = ctk.CTkFrame(self.content, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)
        summary = self.role(ctk.CTkFrame(page, corner_radius=RADIUS), "surface")
        summary.grid(row=0, column=0, pady=(0, 12), sticky="ew")
        summary.grid_columnconfigure(0, weight=1)
        self.role(ctk.CTkLabel(summary, text="脚本录制", font=ctk.CTkFont(size=20, weight="bold")), "title").grid(row=0, column=0, padx=18, pady=(18, 4), sticky="w")
        self.role(ctk.CTkLabel(summary, textvariable=self.script_summary), "muted").grid(row=1, column=0, padx=18, pady=(0, 18), sticky="w")

        controls = self.role(ctk.CTkFrame(page, corner_radius=RADIUS), "surface")
        controls.grid(row=1, column=0, pady=12, sticky="ew")
        controls.grid_columnconfigure((0, 1, 2), weight=1)
        self.small_entry(controls, "循环次数", self.script_repeat).grid(row=0, column=0, padx=(18, 8), pady=18, sticky="ew")
        self.small_entry(controls, "速度倍率", self.script_speed).grid(row=0, column=1, padx=8, pady=18, sticky="ew")
        self.record_moves_check = self.role(ctk.CTkCheckBox(controls, text="记录鼠标移动轨迹", variable=self.record_moves), "check")
        self.record_moves_check.grid(row=0, column=2, padx=18, pady=18, sticky="w")

        text_panel = self.role(ctk.CTkFrame(page, corner_radius=RADIUS), "surface")
        text_panel.grid(row=2, column=0, pady=12, sticky="ew")
        text_panel.grid_columnconfigure(0, weight=1)
        self.role(ctk.CTkLabel(text_panel, text="文本输入事件", font=ctk.CTkFont(size=16, weight="bold")), "text").grid(row=0, column=0, columnspan=2, padx=18, pady=(18, 8), sticky="w")
        self.role(ctk.CTkEntry(text_panel, textvariable=self.script_text, height=42, placeholder_text="输入要回放的文本，支持中文和符号"), "entry").grid(row=1, column=0, padx=(18, 8), pady=(0, 18), sticky="ew")
        self.button(text_panel, "添加文本输入", self.add_text_event, "soft").grid(row=1, column=1, padx=(8, 18), pady=(0, 18), sticky="e")

        actions = self.role(ctk.CTkFrame(page, corner_radius=RADIUS), "surface")
        actions.grid(row=3, column=0, pady=(12, 0), sticky="ew")
        actions.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        self.record_button = self.button(actions, "录制 F9", self.toggle_recording, "primary")
        self.record_button.grid(row=0, column=0, padx=(18, 8), pady=18, sticky="ew")
        self.button(actions, "播放 F10", self.play_script, "soft").grid(row=0, column=1, padx=8, pady=18, sticky="ew")
        self.button(actions, "保存", self.save_script, "soft").grid(row=0, column=2, padx=8, pady=18, sticky="ew")
        self.button(actions, "加载", self.load_script, "soft").grid(row=0, column=3, padx=8, pady=18, sticky="ew")
        self.button(actions, "清空", self.clear_script, "danger_soft").grid(row=0, column=4, padx=(8, 18), pady=18, sticky="ew")
        return page

    def _build_stats_page(self):
        page = ctk.CTkFrame(self.content, fg_color="transparent")
        page.grid_columnconfigure((0, 1), weight=1)
        self.metric_card(page, "点击次数", self.click_count_text).grid(row=0, column=0, padx=(0, 10), pady=(0, 12), sticky="ew")
        self.metric_card(page, "当前速度", self.speed_text).grid(row=0, column=1, padx=(10, 0), pady=(0, 12), sticky="ew")
        self.metric_card(page, "坐标 X", self.fixed_x).grid(row=1, column=0, padx=(0, 10), pady=12, sticky="ew")
        self.metric_card(page, "坐标 Y", self.fixed_y).grid(row=1, column=1, padx=(10, 0), pady=12, sticky="ew")
        actions = self.role(ctk.CTkFrame(page, corner_radius=RADIUS), "surface")
        actions.grid(row=2, column=0, columnspan=2, pady=(12, 0), sticky="ew")
        actions.grid_columnconfigure((0, 1), weight=1)
        self.button(actions, "记录当前位置 F7", self.capture_position, "primary").grid(row=0, column=0, padx=(18, 8), pady=18, sticky="ew")
        self.button(actions, "3 秒后取点", self.capture_position_after_delay, "soft").grid(row=0, column=1, padx=(8, 18), pady=18, sticky="ew")
        return page

    def show_page(self, name):
        self.page_name.set(name)
        for page_name, page in self.pages.items():
            if page_name == name:
                page.grid(row=0, column=0, sticky="nsew")
            else:
                page.grid_remove()
        self.apply_nav_theme()

    def input_card(self, master, title, variable, suffix):
        frame = self.role(ctk.CTkFrame(master, corner_radius=RADIUS), "surface")
        frame.grid_columnconfigure(0, weight=1)
        self.role(ctk.CTkLabel(frame, text=title), "muted").grid(row=0, column=0, padx=18, pady=(18, 6), sticky="w")
        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.grid(row=1, column=0, padx=18, pady=(0, 18), sticky="ew")
        row.grid_columnconfigure(0, weight=1)
        self.role(ctk.CTkEntry(row, textvariable=variable, height=44, justify="right", font=ctk.CTkFont(size=20, weight="bold")), "entry").grid(row=0, column=0, sticky="ew")
        self.role(ctk.CTkLabel(row, text=suffix), "subtle").grid(row=0, column=1, padx=(10, 0))
        return frame

    def segment_card(self, master, title, variable, values):
        frame = self.role(ctk.CTkFrame(master, corner_radius=RADIUS), "surface")
        frame.grid_columnconfigure(0, weight=1)
        self.role(ctk.CTkLabel(frame, text=title), "muted").grid(row=0, column=0, padx=18, pady=(18, 10), sticky="w")
        self.segment(frame, list(values), variable).grid(row=1, column=0, padx=18, pady=(0, 18), sticky="ew")
        return frame

    def small_entry(self, master, title, variable):
        frame = ctk.CTkFrame(master, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)
        self.role(ctk.CTkLabel(frame, text=title), "muted").grid(row=0, column=0, sticky="w")
        self.role(ctk.CTkEntry(frame, textvariable=variable, height=40), "entry").grid(row=1, column=0, pady=(6, 0), sticky="ew")
        return frame

    def metric_card(self, master, title, variable):
        frame = self.role(ctk.CTkFrame(master, corner_radius=RADIUS), "surface")
        self.role(ctk.CTkLabel(frame, text=title), "muted").grid(row=0, column=0, padx=18, pady=(18, 4), sticky="w")
        self.role(ctk.CTkLabel(frame, textvariable=variable, font=ctk.CTkFont(size=28, weight="bold")), "title").grid(row=1, column=0, padx=18, pady=(0, 18), sticky="w")
        return frame

    def button(self, master, text, command, role):
        return self.role(ctk.CTkButton(master, text=text, height=42, corner_radius=12, command=command), f"button:{role}")

    def segment(self, master, values, variable, command=None):
        segment = self.role(ctk.CTkSegmentedButton(master, values=values, variable=variable, command=command), "segment")
        self.bind_segment_refresh(segment)
        return segment

    def bind_segment_refresh(self, segment):
        for button in getattr(segment, "_buttons_dict", {}).values():
            button.bind("<ButtonRelease-1>", lambda _event, item=segment: self.after(1, lambda: self.refresh_segment_text(item, self.mode())), add="+")

    def role(self, widget, role_name):
        self.roles.append((widget, role_name))
        return widget

    def mode(self):
        return self.theme_name.get()

    def apply_theme(self, animated=True):
        if animated:
            self.show_theme_overlay()
            self.after(35, self.commit_theme)
            return
        self.commit_theme()

    def commit_theme(self):
        mode = self.mode()
        ctk.set_appearance_mode(appearance(mode))
        self.configure(fg_color=token(mode, "window"))
        for widget, role_name in list(self.roles):
            if not widget.winfo_exists():
                continue
            self.apply_widget_theme(widget, role_name, mode)
        self.apply_nav_theme()
        self.save_settings()
        self.update_idletasks()
        self.fade_theme_overlay()

    def apply_widget_theme(self, widget, role_name, mode):
        try:
            if role_name == "sidebar":
                widget.configure(fg_color=token(mode, "sidebar"))
            elif role_name == "global_scroll":
                widget.configure(
                    fg_color="transparent",
                    scrollbar_button_color=token(mode, "surface_3"),
                    scrollbar_button_hover_color=token(mode, "muted"),
                )
            elif role_name == "surface":
                widget.configure(fg_color=token(mode, "surface"), border_width=1, border_color=token(mode, "line"))
            elif role_name == "surface_2":
                widget.configure(fg_color=token(mode, "surface_2"), border_width=1, border_color=token(mode, "line"))
            elif role_name == "hero":
                widget.configure(fg_color=token(mode, "surface"), border_width=1, border_color=token(mode, "line"))
            elif role_name == "primary_soft_panel":
                widget.configure(fg_color=token(mode, "primary_soft"), border_width=0)
            elif role_name == "brand_badge":
                widget.configure(fg_color=token(mode, "primary"), text_color=token(mode, "primary_text"))
            elif role_name == "chip":
                widget.configure(fg_color=token(mode, "primary_soft"), text_color=token(mode, "primary"))
            elif role_name == "keycap":
                widget.configure(fg_color=token(mode, "surface_3"), text_color=token(mode, "text"))
            elif role_name == "title":
                widget.configure(text_color=token(mode, "text"))
            elif role_name == "text":
                widget.configure(text_color=token(mode, "text"))
            elif role_name == "muted":
                widget.configure(text_color=token(mode, "muted"))
            elif role_name == "subtle":
                widget.configure(text_color=token(mode, "subtle"))
            elif role_name == "primary_text_label":
                widget.configure(text_color=token(mode, "primary"))
            elif role_name == "entry":
                widget.configure(fg_color=token(mode, "surface_2"), border_color=token(mode, "line"), text_color=token(mode, "text"), placeholder_text_color=token(mode, "subtle"))
            elif role_name == "segment":
                widget.configure(
                    fg_color=token(mode, "surface_3"),
                    selected_color=token(mode, "primary"),
                    selected_hover_color=token(mode, "primary_hover"),
                    unselected_color=token(mode, "surface_3"),
                    unselected_hover_color=token(mode, "surface_2"),
                    text_color=token(mode, "text"),
                )
                self.refresh_segment_text(widget, mode)
            elif role_name == "switch":
                widget.configure(progress_color=token(mode, "primary"), button_hover_color=token(mode, "primary_hover"), text_color=token(mode, "text"))
            elif role_name == "check":
                widget.configure(fg_color=token(mode, "primary"), hover_color=token(mode, "primary_hover"), border_color=token(mode, "line"), text_color=token(mode, "text"))
            elif role_name.startswith("button:"):
                self.apply_button_theme(widget, role_name.split(":", 1)[1], mode)
        except (tk.TclError, ValueError):
            pass

    def refresh_segment_text(self, segment, mode):
        selected = segment.get()
        buttons = getattr(segment, "_buttons_dict", {})
        for value, button in buttons.items():
            if not button.winfo_exists():
                continue
            if value == selected:
                button.configure(text_color=token(mode, "primary_text"))
            else:
                button.configure(text_color=token(mode, "text"))

    def apply_button_theme(self, widget, kind, mode):
        if kind == "primary":
            widget.configure(fg_color=token(mode, "primary"), hover_color=token(mode, "primary_hover"), text_color=token(mode, "primary_text"), border_width=0)
        elif kind == "danger":
            widget.configure(fg_color=token(mode, "danger"), hover_color=token(mode, "danger_hover"), text_color=token(mode, "primary_text"), border_width=0)
        elif kind == "danger_soft":
            widget.configure(fg_color=token(mode, "surface_2"), hover_color=token(mode, "surface_3"), text_color=token(mode, "danger"), border_width=1, border_color=token(mode, "line"))
        elif kind == "nav":
            widget.configure(fg_color="transparent", hover_color=token(mode, "surface_2"), text_color=token(mode, "muted"), border_width=0, anchor="w")
        else:
            widget.configure(fg_color=token(mode, "surface_2"), hover_color=token(mode, "surface_3"), text_color=token(mode, "text"), border_width=1, border_color=token(mode, "line"))

    def apply_nav_theme(self):
        mode = self.mode()
        active = self.page_name.get()
        for name, button in getattr(self, "nav_buttons", {}).items():
            if not button.winfo_exists():
                continue
            if name == active:
                button.configure(fg_color=token(mode, "primary_soft"), hover_color=token(mode, "primary_soft"), text_color=token(mode, "primary"))
            else:
                button.configure(fg_color="transparent", hover_color=token(mode, "surface_2"), text_color=token(mode, "muted"))

    def switch_theme(self, _value=None):
        self.apply_theme(animated=True)

    def show_theme_overlay(self):
        self.cancel_theme_jobs()
        if self.theme_overlay and self.theme_overlay.winfo_exists():
            self.theme_overlay.destroy()
        self.update_idletasks()
        overlay = tk.Toplevel(self)
        overlay.overrideredirect(True)
        overlay.configure(bg=self.cget("fg_color"))
        overlay.geometry(f"{max(1, self.winfo_width())}x{max(1, self.winfo_height())}+{self.winfo_rootx()}+{self.winfo_rooty()}")
        overlay.attributes("-alpha", 0.18)
        overlay.attributes("-topmost", True)
        overlay.lift()
        self.theme_overlay = overlay
        for index, alpha in enumerate((0.22, 0.26, 0.30)):
            self.theme_jobs.append(self.after(index * 18, lambda value=alpha: self.set_overlay_alpha(value)))

    def fade_theme_overlay(self):
        if not self.theme_overlay:
            return
        for index, alpha in enumerate((0.24, 0.18, 0.12, 0.07, 0.03, 0.0)):
            self.theme_jobs.append(self.after(index * 32, lambda value=alpha: self.set_overlay_alpha(value)))
        self.theme_jobs.append(self.after(210, self.destroy_theme_overlay))

    def set_overlay_alpha(self, alpha):
        if self.theme_overlay and self.theme_overlay.winfo_exists():
            self.theme_overlay.attributes("-alpha", alpha)

    def destroy_theme_overlay(self):
        if self.theme_overlay and self.theme_overlay.winfo_exists():
            self.theme_overlay.destroy()
        self.theme_overlay = None
        self.theme_jobs = []

    def cancel_theme_jobs(self):
        for job in self.theme_jobs:
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass
        self.theme_jobs = []

    def toggle_topmost(self):
        self.attributes("-topmost", self.always_on_top.get())
        self.save_settings()

    def save_settings(self):
        self.settings_store.save({
            "theme": self.theme_name.get(),
            "always_on_top": bool(self.always_on_top.get()),
            "hide_when_running": bool(self.hide_when_running.get()),
        })

    def validate_click_settings(self):
        try:
            interval = max(1, int(float(self.interval_ms.get())))
            jitter = max(0, int(float(self.jitter_ms.get())))
            delay = max(0, float(self.start_delay.get()))
            repeat_count = max(1, int(float(self.repeat_count.get())))
        except ValueError:
            messagebox.showerror("设置错误", "点击间隔、随机浮动、启动延迟和次数都需要填写数字。")
            return None
        if self.position_mode.get() == "固定坐标" and self.fixed_position is None:
            messagebox.showerror("设置错误", "固定坐标模式需要先记录鼠标位置。")
            return None
        return ClickSettings(
            interval=interval / 1000,
            jitter=jitter / 1000,
            delay=delay,
            button=self.mouse_button.get(),
            clicks_per_cycle=2 if self.click_mode.get() == "双击" else 1,
            repeat_forever=self.repeat_mode.get() == "一直点击",
            repeat_count=repeat_count,
            position=self.fixed_position if self.position_mode.get() == "固定坐标" else None,
        )

    def start(self):
        if self.is_busy():
            return
        if self.recording:
            self.stop_recording()
        settings = self.validate_click_settings()
        if not settings:
            return
        self.clicks_done = 0
        self.started_at = time.time()
        self.set_running_ui("RUNNING")
        if self.hide_when_running.get():
            self.iconify()
        self.clicker.start(settings)

    def stop(self):
        self.clicker.stop()
        self.player.stop()
        if self.recording:
            self.stop_recording()
        self.set_ready_ui("STOPPED")
        self.deiconify()

    def is_busy(self):
        return self.clicker.is_running() or self.player.is_running()

    def set_running_ui(self, status):
        self.status_text.set(status)
        self.start_button.configure(state="disabled")
        self.record_button.configure(state="disabled")

    def set_ready_ui(self, status):
        self.status_text.set(status)
        self.start_button.configure(state="normal")
        self.record_button.configure(state="normal")
        self.refresh_counter()

    def _thread_click(self):
        self.after(0, self._record_click_step)

    def _record_click_step(self):
        self.clicks_done += 1
        self.refresh_counter()

    def _thread_done(self, status):
        self.after(0, lambda: self.set_ready_ui(status))

    def refresh_counter(self):
        elapsed = 0 if not self.started_at else max(0.001, time.time() - self.started_at)
        speed = self.clicks_done / elapsed if self.clicks_done else 0
        self.click_count_text.set(str(self.clicks_done))
        self.speed_text.set(f"{speed:.1f}/s")

    def capture_position(self):
        self.fixed_position = get_cursor_pos()
        self.fixed_x.set(str(self.fixed_position[0]))
        self.fixed_y.set(str(self.fixed_position[1]))
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
        if self.position_mode.get() == "当前位置" and not self.is_busy():
            x, y = get_cursor_pos()
            self.fixed_x.set(str(x))
            self.fixed_y.set(str(y))
        self.after(250, self.update_cursor_preview)

    def apply_preset(self, interval, jitter):
        self.interval_ms.set(str(interval))
        self.jitter_ms.set(str(jitter))

    def toggle_recording(self):
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        if self.is_busy():
            messagebox.showerror("正在运行", "请先停止连点或脚本回放，再开始录制。")
            return
        self.script_events = []
        self.recording = True
        self.record_button.configure(text="停止录制 F9")
        self.status_text.set("RECORDING")
        self.refresh_script_summary()
        self.recorder.start(lambda: self.record_moves.get())

    def stop_recording(self):
        self.recorder.stop()
        self.recording = False
        self.record_button.configure(text="录制 F9")
        self.status_text.set("RECORDED")
        self.refresh_script_summary()

    def _thread_record_event(self, event):
        self.after(0, lambda: self.add_script_event(event))

    def add_script_event(self, event):
        if event.get("type") == "text" and self.script_events and self.script_events[-1].get("type") == "text" and event.get("delay", 0) < 1:
            self.script_events[-1]["text"] += event.get("text", "")
        else:
            self.script_events.append(event)
        self.refresh_script_summary()

    def add_text_event(self):
        text = self.script_text.get()
        if not text:
            return
        self.script_events.append({"type": "text", "delay": 0.1, "text": text})
        self.script_text.set("")
        self.status_text.set("TEXT ADDED")
        self.refresh_script_summary()

    def refresh_script_summary(self):
        moves = sum(1 for event in self.script_events if event.get("type") == "move")
        clicks = sum(1 for event in self.script_events if event.get("type") == "mouse")
        keys = sum(1 for event in self.script_events if event.get("type") == "key")
        texts = sum(len(event.get("text", "")) for event in self.script_events if event.get("type") == "text")
        duration = sum(float(event.get("delay", 0)) for event in self.script_events)
        self.script_summary.set(f"{len(self.script_events)} 个事件 · {duration:.1f}s · 鼠标{clicks} 键盘{keys} 文本{texts} 移动{moves}")

    def play_script(self):
        if self.recording:
            self.stop_recording()
        if self.is_busy():
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
        self.clicks_done = 0
        self.started_at = time.time()
        self.set_running_ui("SCRIPT")
        self.player.start(list(self.script_events), repeat, speed)

    def save_script(self):
        if not self.script_events:
            messagebox.showerror("没有脚本", "当前没有可保存的脚本。")
            return
        path = filedialog.asksaveasfilename(title="保存脚本", defaultextension=".json", filetypes=[("PulseClick 脚本", "*.json"), ("所有文件", "*.*")])
        if not path:
            return
        data = {"app": APP_TITLE, "version": 2, "created_at": time.strftime("%Y-%m-%d %H:%M:%S"), "events": self.script_events}
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        self.status_text.set("SAVED")

    def load_script(self):
        path = filedialog.askopenfilename(title="加载脚本", filetypes=[("PulseClick 脚本", "*.json"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            messagebox.showerror("脚本错误", "脚本文件读取失败。")
            return
        events = data.get("events", data if isinstance(data, list) else [])
        if not isinstance(events, list):
            messagebox.showerror("脚本错误", "脚本文件格式不正确。")
            return
        self.script_events = events
        self.status_text.set("LOADED")
        self.refresh_script_summary()

    def clear_script(self):
        self.script_events = []
        self.status_text.set("CLEARED")
        self.refresh_script_summary()

    def _thread_hotkey(self, hotkey_id):
        self.after(0, lambda: self.handle_hotkey(hotkey_id))

    def _thread_hotkey_error(self, message):
        self.after(0, lambda: self.hotkey_status.set(message))

    def handle_hotkey(self, hotkey_id):
        self.hotkey_status.set("热键已启用")
        if hotkey_id == 1:
            self.stop() if self.is_busy() else self.start()
        elif hotkey_id == 2:
            self.capture_position()
        elif hotkey_id == 3:
            self.stop()
        elif hotkey_id == 4:
            self.toggle_recording()
        elif hotkey_id == 5:
            self.play_script()

    def on_close(self):
        self.clicker.stop()
        self.player.stop()
        self.recorder.stop()
        self.hotkeys.stop()
        self.cancel_theme_jobs()
        if self.theme_overlay and self.theme_overlay.winfo_exists():
            self.theme_overlay.destroy()
        self.save_settings()
        self.destroy()
