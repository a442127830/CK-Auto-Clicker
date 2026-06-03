import ctypes
import threading
from ctypes import wintypes

from .constants import HOTKEYS
from .win32 import MOD_NOREPEAT, WM_HOTKEY, WM_QUIT, last_error_message, user32, kernel32


class HotkeyThread(threading.Thread):
    def __init__(self, on_hotkey, on_error):
        super().__init__(daemon=True)
        self.on_hotkey = on_hotkey
        self.on_error = on_error
        self.thread_id = None
        self.running = True
        self.registered_ids = []

    def run(self):
        self.thread_id = kernel32.GetCurrentThreadId()
        for hotkey_id, vk, key_name, _label in HOTKEYS:
            if user32.RegisterHotKey(None, hotkey_id, MOD_NOREPEAT, vk):
                self.registered_ids.append(hotkey_id)
            else:
                self.on_error(f"{key_name} registration failed: {last_error_message()}")

        msg = wintypes.MSG()
        while self.running and user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == WM_HOTKEY:
                self.on_hotkey(int(msg.wParam))
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        for hotkey_id in self.registered_ids:
            user32.UnregisterHotKey(None, hotkey_id)

    def stop(self):
        self.running = False
        if self.thread_id:
            user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)
