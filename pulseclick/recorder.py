import math
import threading
import time

from .constants import VK_F6, VK_F7, VK_F8, VK_F9, VK_F10
from .win32 import KEY_NAMES, RECORD_BUTTONS, get_cursor_pos, is_key_down, vk_to_char


RECORD_KEY_CODES = [code for code in KEY_NAMES if code not in (VK_F6, VK_F7, VK_F8, VK_F9, VK_F10)]


class RecorderService:
    def __init__(self, on_event):
        self.on_event = on_event
        self.stop_event = threading.Event()
        self.worker = None

    def is_running(self):
        return bool(self.worker and self.worker.is_alive())

    def start(self, record_moves):
        if self.is_running():
            return False
        self.stop_event.clear()
        self.worker = threading.Thread(target=self._run, args=(record_moves,), daemon=True)
        self.worker.start()
        return True

    def stop(self):
        self.stop_event.set()

    def _run(self, record_moves):
        last_time = time.time()
        last_move_time = last_time
        last_pos = get_cursor_pos()
        mouse_state = {name: is_key_down(info["vk"]) for name, info in RECORD_BUTTONS.items()}
        key_state = {vk: is_key_down(vk) for vk in RECORD_KEY_CODES}

        while not self.stop_event.is_set():
            now = time.time()
            pos = get_cursor_pos()

            if record_moves() and now - last_move_time >= 0.05 and math.dist(pos, last_pos) >= 12:
                self.on_event({"type": "move", "delay": now - last_time, "x": pos[0], "y": pos[1]})
                last_time = now
                last_move_time = now
                last_pos = pos

            for name, info in RECORD_BUTTONS.items():
                down = is_key_down(info["vk"])
                if down != mouse_state[name]:
                    self.on_event({
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
                down = is_key_down(vk)
                if down != key_state[vk]:
                    char = vk_to_char(vk) if down else ""
                    if char:
                        self.on_event({"type": "text", "delay": now - last_time, "text": char})
                    elif not _is_printable_key(vk):
                        self.on_event({
                            "type": "key",
                            "delay": now - last_time,
                            "vk": vk,
                            "name": KEY_NAMES.get(vk, str(vk)),
                            "action": "down" if down else "up",
                        })
                    key_state[vk] = down
                    last_time = now

            time.sleep(0.01)


def _is_printable_key(vk):
    return 0x30 <= vk <= 0x5A or vk in (0x20, 0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF, 0xC0, 0xDB, 0xDC, 0xDD, 0xDE)
