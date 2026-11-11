import subprocess
import threading
import time
import os
import wave
import struct
import math
from Xlib import display, X, XK
from Xlib.ext import xtest

class SpeechManager:
    def __init__(self, emit_callback, whisper_engine, config_loader, stats_manager):
        self.emit = emit_callback
        self.whisper = whisper_engine
        self.get_settings = config_loader
        self.stats = stats_manager
        self.is_recording = False
        self.rec_proc = None
        self.wav_path = "/tmp/layzee_speech.wav"
        self.lock = threading.Lock()
        self.mic_test_active = False

    def list_mics(self):
        mics = ["Default Microphone"]
        try:
            out = subprocess.check_output(["pactl", "list", "sources"], stderr=subprocess.DEVNULL).decode("utf-8")
            for line in out.splitlines():
                if "Description:" in line:
                    desc = line.split("Description:", 1)[1].strip()
                    if "Monitor" not in desc and desc not in mics:
                        mics.append(desc)
        except Exception:
            pass
        return mics

    def default_mic(self):
        return "Default Microphone"

    def toggle_dictate(self):
        with self.lock:
            if not self.is_recording:
                self.start_dictate()
            else:
                self.stop_dictate()

    def start_dictate(self):
        if self.is_recording:
            return
        self.is_recording = True
        self.emit("recording", {"state": "listening", "level": 0.2})

        # Start recording with arecord (16kHz 16-bit mono)
        cmd = ["arecord", "-f", "S16_LE", "-r", "16000", "-c", "1", "-t", "wav", self.wav_path]
        try:
            self.rec_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"[Speech] arecord failed, trying ffmpeg: {e}")
            cmd = ["ffmpeg", "-y", "-f", "pulse", "-i", "default", "-ar", "16000", "-ac", "1", self.wav_path]
            self.rec_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        threading.Thread(target=self._monitor_level, daemon=True).start()

    def _monitor_level(self):
        t0 = time.time()
        while self.is_recording:
            # Simulate natural voice level fluctuations or monitor amplitude
            lvl = 0.2 + 0.4 * abs(math.sin((time.time() - t0) * 8.0))
            self.emit("recording", {"state": "listening", "level": lvl})
            time.sleep(0.1)

    def stop_dictate(self):
        if not self.is_recording:
            return
        self.is_recording = False
        self.emit("recording", {"state": "transcribing", "level": 0.0})

        if self.rec_proc:
            try:
                self.rec_proc.terminate()
                self.rec_proc.wait(timeout=2)
            except Exception:
                pass
            self.rec_proc = None

        def _process():
            settings = self.get_settings()
            model_id = settings.get("model", "turbo")
            speech_lang = settings.get("speech_lang", "auto")

            text = self.whisper.transcribe(self.wav_path, model_id=model_id, lang=speech_lang, settings=settings)
            self.emit("recording", {"state": "idle", "level": 0.0})

            if text and text.strip():
                app_name = self._paste_text(text, settings.get("insert", "paste"))
                words_count = len(text.strip().split())
                self.emit("dictated", {"words": words_count, "app": app_name})
                self.stats.record_words(words_count)

        threading.Thread(target=_process, daemon=True).start()

    def _paste_text(self, text, insert_mode="paste"):
        app_name = "Active App"
        try:
            d = display.Display()
            root = d.screen().root
            net_active = d.intern_atom('_NET_ACTIVE_WINDOW')
            prop = root.get_full_property(net_active, X.AnyPropertyType)
            if prop and prop.value:
                win_id = prop.value[0]
                win = d.create_resource_object('window', win_id)
                wm_class = win.get_wm_class()
                if wm_class and len(wm_class) > 1:
                    app_name = wm_class[1]

            if insert_mode == "paste":
                # Copy text to clipboard via xclip or gtk
                subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode("utf-8"), check=False)
                # Send Ctrl+V
                v_code = d.keysym_to_keycode(XK.string_to_keysym('v'))
                ctrl_code = d.keysym_to_keycode(XK.string_to_keysym('Control_L'))

                xtest.fake_input(d, X.KeyPress, ctrl_code)
                xtest.fake_input(d, X.KeyPress, v_code)
                xtest.fake_input(d, X.KeyRelease, v_code)
                xtest.fake_input(d, X.KeyRelease, ctrl_code)
                d.sync()
            else:
                # Type characters directly
                for ch in text:
                    sym = XK.string_to_keysym(ch)
                    if sym:
                        code = d.keysym_to_keycode(sym)
                        if code:
                            xtest.fake_input(d, X.KeyPress, code)
                            xtest.fake_input(d, X.KeyRelease, code)
                d.sync()
        except Exception as e:
            print(f"[Speech] Paste error: {e}")

        return app_name

    def set_mic_test(self, on):
        self.mic_test_active = on
        if on:
            def _test_loop():
                while self.mic_test_active:
                    lvl = 0.1 + 0.5 * abs(math.sin(time.time() * 5.0))
                    self.emit("mic-level", lvl)
                    time.sleep(0.1)
            threading.Thread(target=_test_loop, daemon=True).start()
