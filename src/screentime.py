import threading
import time
import json
import os
from Xlib import display, X

from .config import SCREENTIME_FILE

class ScreenTimeTracker:
    def __init__(self, emit_callback):
        self.emit = emit_callback
        self.running = True
        self.records = self._load_records()
        self.today = time.strftime("%Y-%m-%d")
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _load_records(self):
        if os.path.exists(SCREENTIME_FILE):
            try:
                with open(SCREENTIME_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_records(self):
        try:
            with open(SCREENTIME_FILE, "w", encoding="utf-8") as f:
                json.dump(self.records, f, indent=2)
        except Exception as e:
            print(f"[ScreenTime] Error saving: {e}")

    def _get_active_app(self, d, root, net_active_window):
        try:
            prop = root.get_full_property(net_active_window, X.AnyPropertyType)
            if not prop or not prop.value:
                return None
            win_id = prop.value[0]
            if win_id == 0:
                return None
            win = d.create_resource_object('window', win_id)
            wm_class = win.get_wm_class()
            if wm_class and len(wm_class) > 1:
                return wm_class[1]
            elif wm_class and len(wm_class) > 0:
                return wm_class[0]
        except Exception:
            pass
        return None

    def _run(self):
        try:
            d = display.Display()
            root = d.screen().root
            net_active_window = d.intern_atom('_NET_ACTIVE_WINDOW')
        except Exception as e:
            print(f"[ScreenTime] Display open error: {e}")
            return

        last_save = time.time()
        while self.running:
            today_str = time.strftime("%Y-%m-%d")
            hour_idx = int(time.strftime("%H"))

            if today_str not in self.records:
                self.records[today_str] = {
                    "date": today_str,
                    "total": 0,
                    "hours": [0] * 24,
                    "apps": {}
                }

            day_data = self.records[today_str]

            app_name = self._get_active_app(d, root, net_active_window)
            if app_name and app_name.lower() not in ["layzee", "desktop"]:
                day_data["total"] += 1
                day_data["hours"][hour_idx] += 1
                if app_name not in day_data["apps"]:
                    day_data["apps"][app_name] = 0
                day_data["apps"][app_name] += 1

                # Emit periodic update every 3 seconds
                if int(time.time()) % 3 == 0:
                    summary = self.get_summary()
                    self.emit("screentime", summary)

            if time.time() - last_save > 15:
                self._save_records()
                last_save = time.time()

            time.sleep(1.0)

    def get_summary(self):
        today_str = time.strftime("%Y-%m-%d")
        day_data = self.records.get(today_str, {"total": 0, "apps": {}})
        total_secs = day_data.get("total", 0)
        apps = day_data.get("apps", {})
        top_apps = []
        for app, secs in sorted(apps.items(), key=lambda x: x[1], reverse=True)[:10]:
            pct = round((secs / total_secs * 100)) if total_secs > 0 else 0
            top_apps.append({
                "app": app,
                "secs": secs,
                "percent": pct
            })

        return {
            "hours": round(total_secs / 3600.0, 1),
            "secs": total_secs,
            "top": top_apps
        }

    def get_days(self, num_days=7):
        dates = sorted(self.records.keys())[-num_days:]
        res = []
        for dt in dates:
            d_data = self.records[dt]
            total_secs = d_data.get("total", 0)
            apps = d_data.get("apps", {})
            sorted_apps = []
            for app, secs in sorted(apps.items(), key=lambda x: x[1], reverse=True)[:8]:
                pct = round((secs / total_secs * 100)) if total_secs > 0 else 0
                sorted_apps.append({
                    "name": app,
                    "secs": secs,
                    "pct": pct
                })
            res.append({
                "date": dt,
                "total": total_secs,
                "hours": d_data.get("hours", [0] * 24),
                "apps": sorted_apps
            })
        return res

    def clear(self):
        self.records = {}
        self._save_records()
        self.emit("screentime", self.get_summary())
