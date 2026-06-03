import random
import threading
import time
from dataclasses import dataclass

from . import win32


@dataclass(frozen=True)
class ClickSettings:
    interval: float
    jitter: float
    delay: float
    button: str
    clicks_per_cycle: int
    repeat_forever: bool
    repeat_count: int
    position: tuple[int, int] | None


class ClickerService:
    def __init__(self, on_click, on_done):
        self.on_click = on_click
        self.on_done = on_done
        self.stop_event = threading.Event()
        self.worker = None

    def is_running(self):
        return bool(self.worker and self.worker.is_alive())

    def start(self, settings):
        if self.is_running():
            return False
        self.stop_event.clear()
        self.worker = threading.Thread(target=self._run, args=(settings,), daemon=True)
        self.worker.start()
        return True

    def stop(self):
        self.stop_event.set()

    def _run(self, settings):
        if settings.delay and self.stop_event.wait(settings.delay):
            self.on_done("STOPPED")
            return

        cycles = 0
        while not self.stop_event.is_set():
            if not settings.repeat_forever and cycles >= settings.repeat_count:
                break
            if settings.position is not None:
                win32.set_cursor_pos(*settings.position)

            for index in range(settings.clicks_per_cycle):
                win32.click(settings.button)
                self.on_click()
                if index + 1 < settings.clicks_per_cycle:
                    time.sleep(0.06)

            cycles += 1
            wait_time = settings.interval
            if settings.jitter:
                wait_time = max(0.001, wait_time + random.uniform(-settings.jitter, settings.jitter))
            if self.stop_event.wait(wait_time):
                break

        self.on_done("DONE" if not self.stop_event.is_set() else "STOPPED")
