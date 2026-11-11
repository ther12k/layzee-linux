#!/usr/bin/env python3
import os
import sys
import signal
import subprocess
import threading
import argparse

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

try:
    gi.require_version('AyatanaAppIndicator3', '0.1')
    from gi.repository import AyatanaAppIndicator3 as AppIndicator
except Exception:
    AppIndicator = None

from src import config
from src.server import StaticServer
from src.media import MediaManager
from src.audio_mixer import AudioMixer
from src.visualizer import VisualizerManager
from src.clipboard import ClipboardManager
from src.screentime import ScreenTimeTracker
from src.whisper_engine import WhisperEngine
from src.stats import StatsManager
from src.speech import SpeechManager
from src.shot import ShotManager
from src.ui import MainWindow, ShotWindow
from src.native_notch import NativeNotchWindow

def main():
    parser = argparse.ArgumentParser(description="Layzee (Lightweight Native GTK3 + Sciter/QuickJS)")
    parser.add_argument("--sciter", action="store_true", help="Launch using Sciter (QuickJS + HTML/CSS)")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.join(base_dir, "frontend")

    print("[Layzee Native] Starting server for settings/shot views...")
    server = StaticServer(frontend_dir)
    server.start()

    # Shared instances
    main_win = [None]
    shot_win = [None]
    notch_win = [None]

    def emit_callback(event, payload):
        if notch_win[0]:
            if event == "media":
                GLib.idle_add(notch_win[0].update_media, payload)
            elif event == "recording":
                GLib.idle_add(notch_win[0].update_speech_state, payload.get("state"), payload.get("level"))
        if main_win[0] and main_win[0].is_visible():
            json_data = f'{{"event": "{event}", "payload": {payload}}}'
            # notify main window if needed

    stats_mgr = StatsManager(emit_callback)
    whisper_engine = WhisperEngine(emit_callback)
    speech_mgr = SpeechManager(emit_callback, whisper_engine, config.load_settings, stats_mgr)
    media_mgr = MediaManager(emit_callback)
    mixer = AudioMixer()
    visualizer = VisualizerManager(emit_callback, media_mgr)
    clips_mgr = ClipboardManager(emit_callback)
    screentime_mgr = ScreenTimeTracker(emit_callback)
    shot_mgr = ShotManager()

    def open_settings():
        if not main_win[0]:
            from src.ui import WindowManager
            # Mock manager for main window
            class MockWM:
                def __init__(self):
                    self.listeners = {}
                def handle_invoke(self, label, cmd, payload, cb_id, err_id):
                    # Route to standard config/status
                    res = None
                    if cmd == "get_settings": res = config.load_settings()
                    elif cmd == "get_status": res = whisper_engine.get_status()
                    elif cmd == "get_stats": res = stats_mgr.get_stats()
                    elif cmd == "hardware": res = {"cpu": "Intel", "gpus": [], "has_gpu": False, "recommended_model": "turbo"}
                    elif cmd == "list_models": res = whisper_engine.list_models()
                    elif cmd == "list_mics": res = speech_mgr.list_mics()
                    elif cmd == "default_mic": res = speech_mgr.default_mic()
                    elif cmd == "take_page": res = "home"
                    elif cmd == "screentime_days": res = screentime_mgr.get_days()
                    elif cmd == "screentime_summary": res = screentime_mgr.get_summary()
                    elif cmd == "plugin:app|version": res = "2.1.5"
                    script = f"window.__TAURI_INTERNALS__.runCallback({cb_id}, {json.dumps(res)});"
                    if main_win[0]: main_win[0].eval_js(script)
            mock = MockWM()
            import json
            main_win[0] = MainWindow(mock, server.get_url("index.html"))
        main_win[0].show_all()
        main_win[0].present()

    def open_shot():
        shot_mgr.capture_screen()
        if not shot_win[0]:
            class MockShotWM:
                def handle_invoke(self, label, cmd, payload, cb_id, err_id):
                    import json
                    res = None
                    if cmd == "shot_size": res = shot_mgr.get_size()
                    elif cmd == "shot_frame": res = shot_mgr.get_frame()
                    elif cmd == "shot_done":
                        if shot_win[0]: GLib.idle_add(shot_win[0].hide)
                    script = f"window.__TAURI_INTERNALS__.runCallback({cb_id}, {json.dumps(res)});"
                    if shot_win[0]: shot_win[0].eval_js(script)
            mock_s = MockShotWM()
            shot_win[0] = ShotWindow(mock_s, server.get_url("shot.html"))
        shot_win[0].show_all()
        shot_win[0].fullscreen()
        shot_win[0].present()

    # System Tray
    if AppIndicator:
        tray = AppIndicator.Indicator.new(
            "layzee-native",
            "accessories-character-map",
            AppIndicator.IndicatorCategory.APPLICATION_STATUS
        )
        tray.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        menu = Gtk.Menu()

        item_notch = Gtk.MenuItem(label="Toggle Notch")
        item_notch.connect("activate", lambda _: notch_win[0].hide() if notch_win[0].is_visible() else notch_win[0].show_all())
        menu.append(item_notch)

        item_dictate = Gtk.MenuItem(label="Dictate (Hold CapsLock)")
        item_dictate.connect("activate", lambda _: speech_mgr.toggle_dictate())
        menu.append(item_dictate)

        item_shot = Gtk.MenuItem(label="Lazyshot (Ctrl+Shift+S)")
        item_shot.connect("activate", lambda _: open_shot())
        menu.append(item_shot)

        menu.append(Gtk.SeparatorMenuItem())
        item_settings = Gtk.MenuItem(label="Settings")
        item_settings.connect("activate", lambda _: open_settings())
        menu.append(item_settings)

        item_quit = Gtk.MenuItem(label="Quit Layzee")
        item_quit.connect("activate", lambda _: Gtk.main_quit())
        menu.append(item_quit)
        menu.show_all()
        tray.set_menu(menu)

    if args.sciter:
        print("[Layzee] Launching Sciter (QuickJS + HTML/CSS) engine...")
        sciter_bin = os.path.join(base_dir, "bin", "sciter", "usciter")
        sciter_html = os.path.join(base_dir, "sciter_frontend", "notch.html")
        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = os.path.join(base_dir, "bin", "sciter") + ":" + env.get("LD_LIBRARY_PATH", "")
        sciter_proc = subprocess.Popen([sciter_bin, sciter_html], env=env)
    else:
        print("[Layzee Native] Initializing Native GTK3 Notch (~25MB RAM)...")
        notch_win[0] = NativeNotchWindow(media_mgr, speech_mgr, shot_mgr, open_settings)
        notch_win[0].show_all()

    # Global Hotkey listener for CapsLock and Ctrl+Shift+S
    def _hotkey_thread():
        from Xlib import display, X, XK
        try:
            d = display.Display()
            root = d.screen().root
            caps_code = d.keysym_to_keycode(XK.string_to_keysym('Caps_Lock'))
            if caps_code:
                root.grab_key(caps_code, X.AnyModifier, True, X.GrabModeAsync, X.GrabModeAsync)
            s_code = d.keysym_to_keycode(XK.string_to_keysym('s'))
            if s_code:
                root.grab_key(s_code, X.ControlMask | X.ShiftMask, True, X.GrabModeAsync, X.GrabModeAsync)

            while True:
                ev = d.next_event()
                if ev.type == X.KeyPress:
                    if ev.detail == caps_code:
                        GLib.idle_add(speech_mgr.start_dictate)
                    elif ev.detail == s_code and (ev.state & X.ControlMask) and (ev.state & X.ShiftMask):
                        GLib.idle_add(open_shot)
                elif ev.type == X.KeyRelease:
                    if ev.detail == caps_code:
                        GLib.idle_add(speech_mgr.stop_dictate)
        except Exception as e:
            print(f"[Hotkey] Error: {e}")

    threading.Thread(target=_hotkey_thread, daemon=True).start()

    print("[Layzee Native] Running! Press Ctrl+C or quit from tray to exit.")
    try:
        Gtk.main()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()

if __name__ == "__main__":
    main()
