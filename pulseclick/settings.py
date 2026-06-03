import json
import os

from .constants import SETTINGS_FILE


class SettingsStore:
    def __init__(self, base_dir):
        self.path = os.path.join(base_dir, SETTINGS_FILE)

    def load(self):
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def save(self, data):
        try:
            with open(self.path, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
        except OSError:
            pass
