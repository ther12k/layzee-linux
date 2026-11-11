import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, GLib
import cairo
import math
import random
import os

GTK_CSS = b"""
#notch-window {
    background-color: transparent;
}

#notch-pill {
    background-color: rgba(10, 10, 10, 0.95);
    border-radius: 0px 0px 20px 20px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.12);
    border-left: 1px solid rgba(255, 255, 255, 0.08);
    border-right: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 0px 4px 16px rgba(0, 0, 0, 0.5);
    padding: 6px 14px;
    transition: all 250ms cubic-bezier(0.4, 0, 0.2, 1);
}

#notch-pill:hover, #notch-pill.expanded {
    background-color: rgba(18, 18, 18, 0.98);
    border-radius: 22px;
    margin-top: 8px;
    border: 1px solid rgba(255, 255, 255, 0.15);
}

.title-label {
    color: #ffffff;
    font-weight: 600;
    font-size: 13px;
}

.artist-label {
    color: #a1a1aa;
    font-size: 11px;
}

.icon-badge {
    background-color: #2563eb;
    color: #ffffff;
    border-radius: 12px;
    font-weight: bold;
    font-size: 11px;
    min-width: 22px;
    min-height: 22px;
}

.ctrl-btn {
    background-color: rgba(255, 255, 255, 0.06);
    color: #f4f4f5;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 4px 10px;
    font-size: 12px;
}

.ctrl-btn:hover {
    background-color: rgba(255, 255, 255, 0.15);
}

.accent-btn {
    background-color: #2563eb;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 4px 12px;
    font-weight: 600;
    font-size: 12px;
}

.accent-btn:hover {
    background-color: #1d4ed8;
}
"""

class NativeNotchWindow(Gtk.Window):
    def __init__(self, media_mgr, speech_mgr, shot_mgr, open_settings_cb):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.media = media_mgr
        self.speech = speech_mgr
        self.shot = shot_mgr
        self.open_settings = open_settings_cb

        self.set_title("layzee notch")
        self.set_name("notch-window")
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

        # Apply CSS
        style_provider = Gtk.CssProvider()
        style_provider.load_from_data(GTK_CSS)
        Gtk.StyleContext.add_provider_for_screen(
            screen,
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        screen_w = screen.get_width()
        self.screen_w = screen_w
        self.set_default_size(screen_w, 200)
        self.move(0, 0)

        # Build Widgets
        self.is_expanded = False
        self._build_ui()

        # Connect hover events
        self.connect("enter-notify-event", self._on_enter)
        self.connect("leave-notify-event", self._on_leave)

        # Input shape timer
        GLib.timeout_add(100, self._update_shape)
        # Visualizer animation timer
        self.viz_bars = [6, 8, 12, 7]
        GLib.timeout_add(80, self._animate_viz)

    def _build_ui(self):
        root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root_box.set_halign(Gtk.Align.CENTER)
        root_box.set_valign(Gtk.Align.START)
        self.add(root_box)

        self.pill = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.pill.set_name("notch-pill")
        root_box.pack_start(self.pill, False, False, 0)

        # 1. Compact View Header
        self.compact_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.pill.pack_start(self.compact_box, False, False, 0)

        badge = Gtk.Label(label="Z")
        badge.get_style_context().add_class("icon-badge")
        self.compact_box.pack_start(badge, False, False, 0)

        self.title_label = Gtk.Label(label="Zee · Ready")
        self.title_label.get_style_context().add_class("title-label")
        self.title_label.set_ellipsize(3) # PANGO_ELLIPSIZE_END
        self.title_label.set_max_width_chars(30)
        self.compact_box.pack_start(self.title_label, True, True, 0)

        # Visualizer area
        self.viz_area = Gtk.DrawingArea()
        self.viz_area.set_size_request(24, 16)
        self.viz_area.connect("draw", self._draw_viz)
        self.compact_box.pack_start(self.viz_area, False, False, 0)

        # 2. Expanded Details View (initially hidden)
        self.expanded_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.expanded_box.set_no_show_all(True)
        self.pill.pack_start(self.expanded_box, False, False, 0)

        # Subtitle / Artist
        self.artist_label = Gtk.Label(label="Hold CapsLock to speak · Offline Whisper")
        self.artist_label.get_style_context().add_class("artist-label")
        self.expanded_box.pack_start(self.artist_label, False, False, 0)

        # Control buttons row
        ctrl_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        ctrl_box.set_halign(Gtk.Align.CENTER)
        self.expanded_box.pack_start(ctrl_box, False, False, 0)

        btn_prev = Gtk.Button(label="⏮")
        btn_prev.get_style_context().add_class("ctrl-btn")
        btn_prev.connect("clicked", lambda _: self.media.control("prev"))
        ctrl_box.pack_start(btn_prev, False, False, 0)

        btn_play = Gtk.Button(label="⏯")
        btn_play.get_style_context().add_class("ctrl-btn")
        btn_play.connect("clicked", lambda _: self.media.control("toggle"))
        ctrl_box.pack_start(btn_play, False, False, 0)

        btn_next = Gtk.Button(label="⏭")
        btn_next.get_style_context().add_class("ctrl-btn")
        btn_next.connect("clicked", lambda _: self.media.control("next"))
        ctrl_box.pack_start(btn_next, False, False, 0)

        btn_dictate = Gtk.Button(label="🎙 Dictate")
        btn_dictate.get_style_context().add_class("accent-btn")
        btn_dictate.connect("clicked", lambda _: self.speech.toggle_dictate())
        ctrl_box.pack_start(btn_dictate, False, False, 0)

        btn_shot = Gtk.Button(label="📸 Shot")
        btn_shot.get_style_context().add_class("ctrl-btn")
        btn_shot.connect("clicked", lambda _: self.shot.capture_screen())
        ctrl_box.pack_start(btn_shot, False, False, 0)

        btn_settings = Gtk.Button(label="⚙ Settings")
        btn_settings.get_style_context().add_class("ctrl-btn")
        btn_settings.connect("clicked", lambda _: self.open_settings())
        ctrl_box.pack_start(btn_settings, False, False, 0)

    def _on_enter(self, widget, event):
        self.is_expanded = True
        self.pill.get_style_context().add_class("expanded")
        self.expanded_box.show_all()
        GLib.idle_add(self._update_shape)

    def _on_leave(self, widget, event):
        # Only collapse if mouse truly left the pill bounds
        alloc = self.pill.get_allocation()
        if event.y > alloc.height + 15 or event.x < alloc.x - 10 or event.x > alloc.x + alloc.width + 10:
            self.is_expanded = False
            self.pill.get_style_context().remove_class("expanded")
            self.expanded_box.hide()
            GLib.idle_add(self._update_shape)

    def _update_shape(self):
        alloc = self.pill.get_allocation()
        if alloc.width > 10 and alloc.height > 10:
            # Mask only the visible pill area so the rest of the screen is click-through
            rect = cairo.RectangleInt(alloc.x, alloc.y, alloc.width, alloc.height)
            reg = cairo.Region(rect)
            self.input_shape_combine_region(reg)
        return False

    def _animate_viz(self):
        is_playing = False
        if self.media and self.media.current_media and self.media.current_media.get("playing"):
            is_playing = True

        if is_playing:
            self.viz_bars = [
                random.randint(4, 15),
                random.randint(6, 16),
                random.randint(5, 14),
                random.randint(3, 13)
            ]
            self.viz_area.queue_draw()
        return True

    def _draw_viz(self, widget, cr):
        # Draw 4 green bars
        cr.set_source_rgb(0.13, 0.77, 0.37) # #22c55e
        w = 3
        gap = 2
        for i, h in enumerate(self.viz_bars):
            x = i * (w + gap) + 2
            y = 16 - h
            cr.rectangle(x, y, w, h)
            cr.fill()

    def update_media(self, media_info):
        if media_info and media_info.get("title"):
            title = media_info.get("title", "")
            artist = media_info.get("artist", "")
            self.title_label.set_text(title)
            self.artist_label.set_text(f"{artist} · Playing" if artist else "Playing")
        else:
            self.title_label.set_text("Zee · Ready")
            self.artist_label.set_text("Hold CapsLock to speak · Offline Whisper")
        GLib.idle_add(self._update_shape)

    def update_speech_state(self, state, level):
        if state == "listening":
            self.title_label.set_text("🎙 Listening…")
            self.artist_label.set_text("Release CapsLock to transcribe & paste")
        elif state == "transcribing":
            self.title_label.set_text("⚡ Transcribing…")
            self.artist_label.set_text("Processing with Whisper AI…")
        elif state == "idle":
            self.update_media(self.media.current_media if self.media else None)
        GLib.idle_add(self._update_shape)
