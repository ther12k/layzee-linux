#!/usr/bin/env python3
import os
import sys
import signal

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

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
from src.ui import WindowManager

def main():
    # Setup exit signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.join(base_dir, "frontend")

    print("[Layzee] Starting frontend asset server...")
    server = StaticServer(frontend_dir)
    server.start()
    print(f"[Layzee] Static server running on port {server.port}")

    # Forward emit callback
    def emit_callback(event, payload):
        if hasattr(main, "wm") and main.wm:
            main.wm.emit(event, payload)

    # Initialize subsystems
    stats_mgr = StatsManager(emit_callback)
    whisper_engine = WhisperEngine(emit_callback)
    speech_mgr = SpeechManager(emit_callback, whisper_engine, config.load_settings, stats_mgr)
    media_mgr = MediaManager(emit_callback)
    mixer = AudioMixer()
    visualizer = VisualizerManager(emit_callback, media_mgr)
    clips_mgr = ClipboardManager(emit_callback)
    screentime_mgr = ScreenTimeTracker(emit_callback)
    shot_mgr = ShotManager()

    # Initialize UI Window Manager
    print("[Layzee] Initializing desktop UI windows...")
    main.wm = WindowManager(
        server_url=f"http://127.0.0.1:{server.port}",
        config=config,
        stats_mgr=stats_mgr,
        media_mgr=media_mgr,
        mixer=mixer,
        clips_mgr=clips_mgr,
        screentime_mgr=screentime_mgr,
        whisper_engine=whisper_engine,
        speech_mgr=speech_mgr,
        shot_mgr=shot_mgr
    )

    # Show Notch on startup if notch_on is true
    settings = config.load_settings()
    if settings.get("notch_on", True):
        main.wm.notch_win.show_all()

    # If first run or welcomed is false, also open main window
    if not settings.get("welcomed", True):
        main.wm.main_win.show_all()

    print("[Layzee] Running on Ubuntu! Press Ctrl+C or quit from tray to exit.")
    try:
        Gtk.main()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()

if __name__ == "__main__":
    main()
