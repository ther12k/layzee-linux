import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('WebKit2', '4.0')
try:
    gi.require_version('AyatanaAppIndicator3', '0.1')
    from gi.repository import AyatanaAppIndicator3 as AppIndicator
except Exception:
    AppIndicator = None

from gi.repository import Gtk, Gdk, WebKit2, GLib, GdkPixbuf
import cairo
import json
import os
import subprocess
import threading
import time
from Xlib import display, X, XK

TAURI_POLYFILL_TEMPLATE = """
(function() {
    window.__tauri_callbacks = {};
    window.__tauri_cb_id = 1;
    window.__tauri_listeners = {};

    window.__TAURI_INTERNALS__ = {
        metadata: {
            currentWindow: { label: "%(window_label)s" },
            currentWebview: { label: "%(window_label)s" }
        },
        transformCallback: function(cb, once) {
            const id = window.__tauri_cb_id++;
            window.__tauri_callbacks[id] = (data) => {
                if (once) delete window.__tauri_callbacks[id];
                cb(data);
            };
            return id;
        },
        unregisterCallback: function(id) {
            delete window.__tauri_callbacks[id];
        },
        runCallback: function(id, data) {
            if (window.__tauri_callbacks[id]) {
                window.__tauri_callbacks[id](data);
            }
        },
        invoke: function(cmd, payload = {}, options = {}) {
            return new Promise((resolve, reject) => {
                const cbId = window.__tauri_cb_id++;
                const errId = window.__tauri_cb_id++;
                window.__tauri_callbacks[cbId] = (res) => {
                    delete window.__tauri_callbacks[cbId];
                    delete window.__tauri_callbacks[errId];
                    resolve(res);
                };
                window.__tauri_callbacks[errId] = (err) => {
                    delete window.__tauri_callbacks[cbId];
                    delete window.__tauri_callbacks[errId];
                    reject(err);
                };
                window.webkit.messageHandlers.invoke.postMessage(JSON.stringify({
                    cmd: cmd,
                    payload: payload,
                    callback: cbId,
                    error: errId
                }));
            });
        }
    };

    window.__TAURI_EVENT_PLUGIN_INTERNALS__ = {
        unregisterListener: function(e, id) {
            delete window.__tauri_callbacks[id];
        }
    };
})();
"""

class WindowManager:
    def __init__(self, server_url, config, stats_mgr, media_mgr, mixer, clips_mgr, screentime_mgr, whisper_engine, speech_mgr, shot_mgr):
        self.server_url = server_url
        self.config = config
        self.stats = stats_mgr
        self.media = media_mgr
        self.mixer = mixer
        self.clips = clips_mgr
        self.screentime = screentime_mgr
        self.whisper = whisper_engine
        self.speech = speech_mgr
        self.shot = shot_mgr

        self.settings = self.config.load_settings()
        self.notch_data = self.config.load_notch()

        # Listeners registry: { event_name: { (window_label, handler_id) } }
        self.listeners = {}

        # Windows
        self.notch_win = None
        self.main_win = None
        self.shot_win = None
        self.tray = None

        self._init_ui()

    def _init_ui(self):
        # Configure global WebKit context for minimal memory usage
        try:
            ctx = WebKit2.WebContext.get_default()
            ctx.set_cache_model(WebKit2.CacheModel.DOCUMENT_VIEWER)
        except Exception:
            pass

        # Create Notch Window (always running)
        self.notch_win = NotchWindow(self, self.server_url + "/notch.html")
        
        # Lazy-loaded windows to save memory
        self.main_win = None
        self.shot_win = None

        # Tray indicator
        self._init_tray()

        # Start Global Hotkey thread
        threading.Thread(target=self._hotkey_listener, daemon=True).start()

    def _init_tray(self):
        if not AppIndicator:
            return
        self.tray = AppIndicator.Indicator.new(
            "layzee-indicator",
            "accessories-character-map",
            AppIndicator.IndicatorCategory.APPLICATION_STATUS
        )
        self.tray.set_status(AppIndicator.IndicatorStatus.ACTIVE)

        menu = Gtk.Menu()

        item_notch = Gtk.MenuItem(label="Toggle Notch")
        item_notch.connect("activate", lambda _: self.toggle_notch())
        menu.append(item_notch)

        item_dictate = Gtk.MenuItem(label="Dictate (Speech-to-Text)")
        item_dictate.connect("activate", lambda _: self.speech.toggle_dictate())
        menu.append(item_dictate)

        item_shot = Gtk.MenuItem(label="Lazyshot (Screen Capture)")
        item_shot.connect("activate", lambda _: self.open_shot())
        menu.append(item_shot)

        menu.append(Gtk.SeparatorMenuItem())

        item_settings = Gtk.MenuItem(label="Settings")
        item_settings.connect("activate", lambda _: self.open_settings())
        menu.append(item_settings)

        item_quit = Gtk.MenuItem(label="Quit Layzee")
        item_quit.connect("activate", lambda _: Gtk.main_quit())
        menu.append(item_quit)

        menu.show_all()
        self.tray.set_menu(menu)

    def toggle_notch(self):
        if self.notch_win.is_visible():
            self.notch_win.hide()
        else:
            self.notch_win.show_all()

    def open_settings(self):
        if not self.main_win:
            self.main_win = MainWindow(self, self.server_url + "/index.html")
        self.main_win.show_all()
        self.main_win.present()

    def open_shot(self):
        self.shot.capture_screen()
        if not self.shot_win:
            self.shot_win = ShotWindow(self, self.server_url + "/shot.html")
        self.shot_win.show_all()
        self.shot_win.fullscreen()
        self.shot_win.present()

    def emit(self, event_name, payload):
        GLib.idle_add(self._do_emit, event_name, payload)

    def _do_emit(self, event_name, payload):
        target_handlers = self.listeners.get(event_name, set()).copy()
        if not target_handlers:
            return False

        json_data = json.dumps({
            "event": event_name,
            "id": 0,
            "payload": payload
        })

        for win_label, handler_id in target_handlers:
            script = f"window.__TAURI_INTERNALS__.runCallback({handler_id}, {json_data});"
            if win_label == "notch" and self.notch_win:
                self.notch_win.eval_js(script)
            elif win_label == "main" and self.main_win:
                self.main_win.eval_js(script)
            elif win_label == "shot" and self.shot_win:
                self.shot_win.eval_js(script)
        return False

    def handle_invoke(self, win_label, cmd, payload, cb_id, err_id):
        # Handle command routing
        res = None
        is_error = False

        try:
            if cmd == "get_settings":
                res = self.settings
            elif cmd == "save_settings":
                new_s = payload.get("settings", {})
                self.settings.update(new_s)
                self.config.save_settings(self.settings)
                self.emit("settings", self.settings)
                res = None
            elif cmd == "get_status":
                res = self.whisper.get_status(self.settings.get("model", "turbo"))
            elif cmd == "get_stats":
                res = self.stats.get_stats()
            elif cmd == "hardware":
                res = {
                    "cpu": "13th Gen Intel Core",
                    "gpus": ["Intel Graphics"],
                    "has_gpu": False,
                    "recommended_model": "turbo"
                }
            elif cmd == "list_models":
                res = self.whisper.list_models()
            elif cmd == "download_model" or cmd == "repair_model":
                self.whisper.download_model(payload.get("id"))
                res = None
            elif cmd == "delete_model":
                self.whisper.delete_model(payload.get("id"))
                res = None
            elif cmd == "list_mics":
                res = self.speech.list_mics()
            elif cmd == "default_mic":
                res = self.speech.default_mic()
            elif cmd == "mic_test":
                self.speech.set_mic_test(payload.get("on", False))
                res = None
            elif cmd == "open_models_dir":
                from .config import MODELS_DIR
                subprocess.Popen(["xdg-open", MODELS_DIR])
                res = None
            elif cmd == "open_logs_dir":
                from .config import DATA_DIR
                subprocess.Popen(["xdg-open", DATA_DIR])
                res = None
            elif cmd == "capture_hotkey":
                res = self.settings.get("hotkey", "CapsLock")
            elif cmd == "check_update":
                res = {"latest": True, "url": None, "sha256": None}
            elif cmd == "install_update" or cmd == "open_update":
                res = None
            elif cmd == "dictate_toggle":
                self.speech.toggle_dictate()
                res = None
            elif cmd == "notch_load":
                res = self.notch_data
            elif cmd == "notch_save":
                self.notch_data = payload.get("data", {})
                self.config.save_notch(self.notch_data)
                res = None
            elif cmd == "notch_drag":
                res = None
            elif cmd == "notch_focus":
                res = None
            elif cmd == "notch_region":
                region = payload.get("region")
                if region and self.notch_win:
                    GLib.idle_add(self.notch_win.update_input_region, region)
                res = None
            elif cmd == "locate":
                res = None
            elif cmd == "list_monitors":
                res = [[0, "Built-in Display (1920x1080)"]]
            elif cmd == "screentime_days":
                res = self.screentime.get_days(payload.get("days", 7))
            elif cmd == "screentime_summary":
                res = self.screentime.get_summary()
            elif cmd == "screentime_clear":
                self.screentime.clear()
                res = None
            elif cmd == "media_control":
                action = payload.get("action")
                pos = payload.get("pos")
                self.media.control(action, pos)
                res = None
            elif cmd == "set_lyrics":
                res = None
            elif cmd == "clips_list":
                res = self.clips.get_clips()
            elif cmd == "clip_add":
                self.clips.add_paths(payload.get("paths", []))
                res = None
            elif cmd == "clip_copy":
                self.clips.copy_clip(payload.get("items", []))
                res = None
            elif cmd == "clip_delete":
                self.clips.delete_clip(payload.get("items", []))
                res = None
            elif cmd == "clip_clear":
                self.clips.clear_clips()
                res = None
            elif cmd == "mixer_list":
                res = self.mixer.get_mixer_list()
            elif cmd == "mixer_set":
                self.mixer.set_mixer(payload.get("target"), payload.get("vol"), payload.get("mute"))
                res = None
            elif cmd == "show_settings":
                GLib.idle_add(self.open_settings)
                res = None
            elif cmd == "take_page":
                res = "home"
            elif cmd == "shot_size":
                res = self.shot.get_size()
            elif cmd == "shot_frame":
                res = self.shot.get_frame()
            elif cmd == "shot_ocr":
                x = payload.get("x", 0)
                y = payload.get("y", 0)
                w = payload.get("w", 0)
                h = payload.get("h", 0)
                res = self.shot.do_ocr(x, y, w, h)
            elif cmd == "shot_copy":
                self.shot.copy_image(payload, 0, 0)
                res = None
            elif cmd == "shot_done":
                if self.shot_win:
                    GLib.idle_add(self.shot_win.hide)
                res = None
            elif cmd == "plugin:app|version":
                res = "2.1.5"
            elif cmd == "plugin:event|listen":
                event_name = payload.get("event")
                handler_id = payload.get("handler")
                if event_name not in self.listeners:
                    self.listeners[event_name] = set()
                self.listeners[event_name].add((win_label, handler_id))
                res = handler_id
            elif cmd == "plugin:event|unlisten":
                event_name = payload.get("event")
                event_id = payload.get("eventId")
                if event_name in self.listeners:
                    self.listeners[event_name].discard((win_label, event_id))
                res = None
            elif cmd == "plugin:window|close":
                if win_label == "main":
                    GLib.idle_add(self.main_win.hide)
                res = None
            elif cmd == "plugin:window|minimize":
                if win_label == "main":
                    GLib.idle_add(self.main_win.iconify)
                res = None
            elif cmd == "plugin:window|toggle_maximize":
                if win_label == "main":
                    GLib.idle_add(lambda: self.main_win.unmaximize() if self.main_win.is_maximized() else self.main_win.maximize())
                res = None
            elif cmd == "plugin:window|start_dragging":
                res = None
            else:
                res = None
        except Exception as e:
            print(f"[IPC] Error handling {cmd}: {e}")
            res = str(e)
            is_error = True

        target_id = err_id if is_error else cb_id
        script = f"window.__TAURI_INTERNALS__.runCallback({target_id}, {json.dumps(res)});"

        if win_label == "notch" and self.notch_win:
            self.notch_win.eval_js(script)
        elif win_label == "main" and self.main_win:
            self.main_win.eval_js(script)
        elif win_label == "shot" and self.shot_win:
            self.shot_win.eval_js(script)

    def _hotkey_listener(self):
        try:
            d = display.Display()
            root = d.screen().root

            # Grab Caps_Lock (keycode 66)
            caps_code = d.keysym_to_keycode(XK.string_to_keysym('Caps_Lock'))
            if caps_code:
                root.grab_key(caps_code, X.AnyModifier, True, X.GrabModeAsync, X.GrabModeAsync)

            # Grab PrintScreen or Ctrl+Shift+S
            s_code = d.keysym_to_keycode(XK.string_to_keysym('s'))
            if s_code:
                root.grab_key(s_code, X.ControlMask | X.ShiftMask, True, X.GrabModeAsync, X.GrabModeAsync)

            while True:
                ev = d.next_event()
                if ev.type == X.KeyPress:
                    if ev.detail == caps_code:
                        GLib.idle_add(self.speech.start_dictate)
                    elif ev.detail == s_code and (ev.state & X.ControlMask) and (ev.state & X.ShiftMask):
                        GLib.idle_add(self.open_shot)
                elif ev.type == X.KeyRelease:
                    if ev.detail == caps_code:
                        GLib.idle_add(self.speech.stop_dictate)
        except Exception as e:
            print(f"[Hotkey] Listener exception: {e}")


class NotchWindow(Gtk.Window):
    def __init__(self, manager, url):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.mgr = manager
        self.label = "notch"

        self.set_title("layzee notch")
        self.set_app_paintable(True)
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.stick()

        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)

        # Full screen width at top
        screen_w = screen.get_width()
        self.screen_w = screen_w
        self.set_default_size(screen_w, 420)
        self.move(0, 0)

        # Setup WebKit
        ucm = WebKit2.UserContentManager()
        ucm.register_script_message_handler("invoke")
        ucm.connect("script-message-received::invoke", self._on_message)

        script_code = TAURI_POLYFILL_TEMPLATE % {"window_label": "notch"}
        script = WebKit2.UserScript(
            source=script_code,
            injected_frames=WebKit2.UserContentInjectedFrames.ALL_FRAMES,
            injection_time=WebKit2.UserScriptInjectionTime.START
        )
        ucm.add_script(script)

        self.webview = WebKit2.WebView.new_with_user_content_manager(ucm)
        self.webview.set_background_color(Gdk.RGBA(0, 0, 0, 0))

        settings = self.webview.get_settings()
        settings.set_enable_developer_extras(True)
        settings.set_allow_file_access_from_file_urls(True)
        settings.set_allow_universal_access_from_file_urls(True)

        self.add(self.webview)
        self.webview.load_uri(url)

        # Initial input shape (top-center pill)
        init_w = 200
        init_h = 36
        init_x = (screen_w - init_w) // 2
        self.update_input_region({"x": init_x, "y": 0, "w": init_w, "h": init_h})

    def update_input_region(self, r):
        try:
            x = int(r.get("x", 0))
            y = int(r.get("y", 0))
            w = int(r.get("w", 200))
            h = int(r.get("h", 40))
            rect = cairo.RectangleInt(x, y, w, h)
            reg = cairo.Region(rect)
            self.input_shape_combine_region(reg)
        except Exception as e:
            pass
        return False

    def eval_js(self, script):
        self.webview.evaluate_javascript(script, -1, None, None, None, None, None)

    def _on_message(self, ucm, js_result):
        data = json.loads(js_result.get_js_value().to_string())
        self.mgr.handle_invoke(
            self.label,
            data.get("cmd"),
            data.get("payload", {}),
            data.get("callback"),
            data.get("error")
        )


class MainWindow(Gtk.Window):
    def __init__(self, manager, url):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.mgr = manager
        self.label = "main"

        self.set_title("layzee")
        self.set_default_size(960, 660)
        self.set_position(Gtk.WindowPosition.CENTER)

        # Handle close button (hide instead of exit)
        self.connect("delete-event", lambda w, e: self.hide_on_delete())

        ucm = WebKit2.UserContentManager()
        ucm.register_script_message_handler("invoke")
        ucm.connect("script-message-received::invoke", self._on_message)

        script_code = TAURI_POLYFILL_TEMPLATE % {"window_label": "main"}
        script = WebKit2.UserScript(
            source=script_code,
            injected_frames=WebKit2.UserContentInjectedFrames.ALL_FRAMES,
            injection_time=WebKit2.UserScriptInjectionTime.START
        )
        ucm.add_script(script)

        self.webview = WebKit2.WebView.new_with_user_content_manager(ucm)
        settings = self.webview.get_settings()
        settings.set_enable_developer_extras(True)

        self.add(self.webview)
        self.webview.load_uri(url)

    def eval_js(self, script):
        self.webview.evaluate_javascript(script, -1, None, None, None, None, None)

    def _on_message(self, ucm, js_result):
        data = json.loads(js_result.get_js_value().to_string())
        self.mgr.handle_invoke(
            self.label,
            data.get("cmd"),
            data.get("payload", {}),
            data.get("callback"),
            data.get("error")
        )


class ShotWindow(Gtk.Window):
    def __init__(self, manager, url):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.mgr = manager
        self.label = "shot"

        self.set_title("layzee shot")
        self.set_app_paintable(True)
        self.set_decorated(False)
        self.set_keep_above(True)

        ucm = WebKit2.UserContentManager()
        ucm.register_script_message_handler("invoke")
        ucm.connect("script-message-received::invoke", self._on_message)

        script_code = TAURI_POLYFILL_TEMPLATE % {"window_label": "shot"}
        script = WebKit2.UserScript(
            source=script_code,
            injected_frames=WebKit2.UserContentInjectedFrames.ALL_FRAMES,
            injection_time=WebKit2.UserScriptInjectionTime.START
        )
        ucm.add_script(script)

        self.webview = WebKit2.WebView.new_with_user_content_manager(ucm)
        settings = self.webview.get_settings()
        settings.set_enable_developer_extras(True)

        self.add(self.webview)
        self.webview.load_uri(url)

    def eval_js(self, script):
        self.webview.evaluate_javascript(script, -1, None, None, None, None, None)

    def _on_message(self, ucm, js_result):
        data = json.loads(js_result.get_js_value().to_string())
        self.mgr.handle_invoke(
            self.label,
            data.get("cmd"),
            data.get("payload", {}),
            data.get("callback"),
            data.get("error")
        )
