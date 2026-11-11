import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib
import json
import os
import time
import base64
from io import BytesIO
from PIL import Image

from .config import CLIPS_FILE

class ClipboardManager:
    def __init__(self, emit_callback):
        self.emit = emit_callback
        self.clips = self._load_clips()
        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        self.last_text = ""
        self.clipboard.connect("owner-change", self._on_clipboard_change)

    def _load_clips(self):
        if os.path.exists(CLIPS_FILE):
            try:
                with open(CLIPS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save_clips(self):
        try:
            with open(CLIPS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.clips[:60], f, indent=2)
        except Exception as e:
            print(f"[Clipboard] Error saving clips: {e}")

    def _on_clipboard_change(self, clipboard, event):
        GLib.timeout_add(100, self._check_clipboard)

    def _check_clipboard(self):
        text = self.clipboard.wait_for_text()
        if text and text.strip() and text != self.last_text:
            self.last_text = text
            # Check if already at head
            if not self.clips or self.clips[0].get("text") != text:
                clip = {
                    "id": int(time.time() * 1000),
                    "kind": "text",
                    "text": text,
                    "at": int(time.time() * 1000)
                }
                self.clips.insert(0, clip)
                self.clips = self.clips[:60]
                self._save_clips()
                self.emit("clips", self.clips)
            return False

        # Check for image
        pixbuf = self.clipboard.wait_for_image()
        if pixbuf:
            w = pixbuf.get_width()
            h = pixbuf.get_height()
            thumb_pixbuf = pixbuf.scale_simple(min(w, 120), int(min(w, 120) * h / w), GdkPixbuf.InterpType.BILINEAR)
            success, buffer = thumb_pixbuf.save_to_bufferv("png", [], [])
            if success:
                b64 = base64.b64encode(buffer).decode("ascii")
                thumb_url = f"data:image/png;base64,{b64}"
                clip = {
                    "id": int(time.time() * 1000),
                    "kind": "image",
                    "thumb": thumb_url,
                    "at": int(time.time() * 1000)
                }
                self.clips.insert(0, clip)
                self.clips = self.clips[:60]
                self._save_clips()
                self.emit("clips", self.clips)
        return False

    def get_clips(self):
        return self.clips

    def copy_clip(self, items):
        if not items:
            return
        item_id = int(items[0])
        for c in self.clips:
            if c.get("id") == item_id:
                if c.get("kind") == "text":
                    self.last_text = c.get("text", "")
                    self.clipboard.set_text(self.last_text, -1)
                break

    def delete_clip(self, items):
        ids = [int(i) for i in items]
        self.clips = [c for c in self.clips if c.get("id") not in ids]
        self._save_clips()
        self.emit("clips", self.clips)

    def clear_clips(self):
        self.clips = []
        self._save_clips()
        self.emit("clips", self.clips)

    def add_paths(self, paths):
        for p in paths:
            if os.path.exists(p):
                clip = {
                    "id": int(time.time() * 1000),
                    "kind": "folder" if os.path.isdir(p) else "file",
                    "name": os.path.basename(p),
                    "path": p,
                    "at": int(time.time() * 1000)
                }
                self.clips.insert(0, clip)
        self.clips = self.clips[:60]
        self._save_clips()
        self.emit("clips", self.clips)
