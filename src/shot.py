import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, GdkPixbuf
import io
from PIL import Image

class ShotManager:
    def __init__(self, close_callback=None):
        self.close_cb = close_callback
        self.current_pixbuf = None
        self.w = 1920
        self.h = 1080

    def capture_screen(self):
        root = Gdk.get_default_root_window()
        self.w = root.get_width()
        self.h = root.get_height()
        self.current_pixbuf = Gdk.pixbuf_get_from_window(root, 0, 0, self.w, self.h)
        return self.w, self.h

    def get_size(self):
        return {"w": self.w, "h": self.h}

    def get_frame(self):
        if not self.current_pixbuf:
            self.capture_screen()
        # WebKit expects raw Uint8Array RGBA pixel bytes
        # Pixbuf get_pixels returns raw bytes
        pixels = self.current_pixbuf.get_pixels()
        n_channels = self.current_pixbuf.get_n_channels()
        rowstride = self.current_pixbuf.get_rowstride()

        # If 3 channels (RGB), convert to RGBA for canvas ImageData
        if n_channels == 3:
            img = Image.frombytes("RGB", (self.w, self.h), pixels, "raw", "RGB", rowstride, 1)
            rgba = img.convert("RGBA")
            return list(rgba.tobytes())
        return list(pixels)

    def do_ocr(self, x, y, w, h):
        # Crop region
        try:
            pixels = self.current_pixbuf.get_pixels()
            rowstride = self.current_pixbuf.get_rowstride()
            n_channels = self.current_pixbuf.get_n_channels()
            mode = "RGBA" if n_channels == 4 else "RGB"
            img = Image.frombytes(mode, (self.w, self.h), pixels, "raw", mode, rowstride, 1)
            crop_img = img.crop((x, y, x + w, y + h))

            # Try pytesseract if available
            try:
                import pytesseract
                text = pytesseract.image_to_string(crop_img)
                return text.strip()
            except Exception:
                pass
        except Exception as e:
            print(f"[Shot] OCR error: {e}")
        return ""

    def copy_image(self, img_bytes, w, h):
        try:
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            # Create pixbuf from PNG bytes or raw bytes
            loader = GdkPixbuf.PixbufLoader.new()
            loader.write(bytes(img_bytes))
            loader.close()
            pixbuf = loader.get_pixbuf()
            if pixbuf:
                clipboard.set_image(pixbuf)
        except Exception as e:
            print(f"[Shot] Copy error: {e}")
