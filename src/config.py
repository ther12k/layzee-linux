import os
import json
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODELS_DIR = os.path.join(BASE_DIR, "models")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
STATS_FILE = os.path.join(DATA_DIR, "stats.json")
NOTCH_FILE = os.path.join(DATA_DIR, "notch.json")
SCREENTIME_FILE = os.path.join(DATA_DIR, "screentime.json")
CLIPS_FILE = os.path.join(DATA_DIR, "clips.json")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

DEFAULT_SETTINGS = {
    "language": "en",
    "autostart": False,
    "beep": True,
    "motion": True,
    "hotkey": "CapsLock",
    "mode": "hold",
    "insert": "paste",
    "mic": "default",
    "model": "turbo",
    "processor": "cpu",
    "speech_lang": "auto",
    "high_accuracy": True,
    "vocabulary": "",
    "type_enabled": True,
    "welcomed": True,
    "onboarded": True,
    "end_punct": True,
    "capitalization": "first_only",
    "formality": "casual",
    "remove_fillers": True,
    "trailing_space": True,
    "notch_on": True,
    "notch_monitor": 0,
    "notch_style": "notch",
    "notch_w": 380,
    "notch_h": 38,
    "notch_hide": 0,
    "island_w": 200,
    "island_h": 36,
    "island_hide": 0,
    "island_pos": "tc",
    "island_sticky": True,
    "island_x": None,
    "island_y": None,
    "notch_hide_fullscreen": True,
    "remind_water": True,
    "remind_move": True,
    "page_sounds": True,
    "page_clipboard": True,
    "page_camera": False,
    "page_mixer": True,
    "page_screen": True,
    "lyrics_on": True,
    "prayer_on": False,
    "prayer_city": "Jakarta",
    "prayer_lat": -6.2088,
    "prayer_lng": 106.8456,
    "prayer_method": "MWL",
    "screen_time_on": True,
    "shot_on": True,
    "shot_hotkey": "Control+Shift+S"
}

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                res = DEFAULT_SETTINGS.copy()
                res.update(data)
                return res
        except Exception:
            pass
    return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        print(f"Error saving settings: {e}")

def load_stats():
    default_stats = {
        "total_words": 150,
        "week_words": 150,
        "streak_days": 1,
        "first_use": time.strftime("%Y-%m-%d")
    }
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_stats.update(data)
                return default_stats
        except Exception:
            pass
    return default_stats

def save_stats(stats):
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)
    except Exception as e:
        print(f"Error saving stats: {e}")

def load_notch():
    default_notch = {
        "todos": [],
        "sessions": 0,
        "day": time.strftime("%a %b %d %Y"),
        "len": {"focus": 25, "break": 5}
    }
    if os.path.exists(NOTCH_FILE):
        try:
            with open(NOTCH_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_notch.update(data)
                return default_notch
        except Exception:
            pass
    return default_notch

def save_notch(data):
    try:
        with open(NOTCH_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving notch: {e}")
