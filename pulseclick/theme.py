THEMES = {
    "Brown": {
        "appearance": "Dark",
        "window": "#17120f",
        "sidebar": "#211913",
        "surface": "#2b221c",
        "surface_2": "#352a22",
        "surface_3": "#44362c",
        "line": "#56473c",
        "text": "#f7efe6",
        "muted": "#c4b4a5",
        "subtle": "#927f70",
        "primary": "#c58a5a",
        "primary_hover": "#d79b69",
        "primary_soft": "#3e2b20",
        "primary_text": "#ffffff",
        "danger": "#dc6f67",
        "danger_hover": "#ed8177",
        "success": "#8fbd75",
        "shadow": "#0d0907",
        "glass": "#2f251f",
        "overlay": "#211913",
    },
    "White": {
        "appearance": "Light",
        "window": "#f7f4ee",
        "sidebar": "#eee8df",
        "surface": "#fffdf9",
        "surface_2": "#f4efe8",
        "surface_3": "#e8dfd3",
        "line": "#ded3c5",
        "text": "#24201c",
        "muted": "#74685d",
        "subtle": "#9f9284",
        "primary": "#8d6747",
        "primary_hover": "#76563b",
        "primary_soft": "#efe4d8",
        "primary_text": "#ffffff",
        "danger": "#b85b55",
        "danger_hover": "#9f4a45",
        "success": "#6f9856",
        "shadow": "#ddd4c8",
        "glass": "#fffaf4",
        "overlay": "#f7f4ee",
    },
}


def token(mode, key):
    return THEMES[mode][key]


def normalize_theme(name):
    if name == "Brown":
        return "Brown"
    if name == "White":
        return "White"
    if name == "深色":
        return "Brown"
    if name == "浅色":
        return "White"
    if name == "棕色":
        return "Brown"
    if name == "白色":
        return "White"
    return "Brown"


def appearance(mode):
    return token(mode, "appearance")
