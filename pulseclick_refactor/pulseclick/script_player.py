import threading
import time

from . import win32
from .win32 import RECORD_BUTTONS


class ScriptPlayerService:
    def __init__(self, on_step, on_done):
        self.on_step = on_step
        self.on_done = on_done
        self.stop_event = threading.Event()
        self.worker = None

    def is_running(self):
        return bool(self.worker and self.worker.is_alive())

    def start(self, events, repeat, speed):
        if self.is_running():
            return False
        self.stop_event.clear()
        self.worker = threading.Thread(target=self._run, args=(list(events), repeat, speed), daemon=True)
        self.worker.start()
        return True

    def stop(self):
        self.stop_event.set()

    def _run(self, events, repeat, speed):
        for _ in range(repeat):
            for event in events:
                delay = max(0, event.get("delay", 0) / speed)
                if self.stop_event.wait(delay):
                    self.on_done("STOPPED")
                    return
                self._perform(event)
                self.on_step()
        self.on_done("DONE")

    def _perform(self, event):
        event_type = event.get("type")
        if event_type == "move":
            win32.set_cursor_pos(event["x"], event["y"])
            return
        if event_type == "mouse":
            info = RECORD_BUTTONS[event["button"]]
            win32.set_cursor_pos(event["x"], event["y"])
            flag = info["down"] if event["action"] == "down" else info["up"]
            win32.send_mouse_flag(flag)
            return
        if event_type == "key":
            win32.send_key(event["vk"], event["action"] == "down")
            return
        if event_type == "text":
            win32.send_unicode_text(event.get("text", ""))
            time.sleep(0.01)
