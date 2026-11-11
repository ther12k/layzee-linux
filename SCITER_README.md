# Layzee - Sciter & Native GTK3 Lightweight Branch

This branch provides ultra-lightweight alternatives to the standard WebKit webview stack:

## 1. Native GTK3 + CSS Engine (`layzee_native.py`)
- **Memory Usage:** **~35 – 70 MB total** (over **80% less memory** than full browser engines).
- **Startup:** Instantaneous (< 50ms).
- **CPU:** 0.0% idle.
- **Features:**
  - Floating dynamic notch with hover expansion to music player controls, offline whisper dictation button, and screenshot tool.
  - Native GTK3 CSS styling with dark translucent background, rounded borders, and smooth transitions.
  - X11 Cairo shaped input mask (`input_shape_combine_region`) for background click-through.
  - DBus MPRIS2 media integration with animated audio frequency visualizer.
  - CapsLock hold-to-talk voice typing via `whisper.cpp`.
  - Lazyshot screen capture (`Ctrl+Shift+S`).
  - System tray icon via Ayatana AppIndicator.

### How to Run Native GTK3:
```bash
python3 layzee_native.py
```

---

## 2. Sciter (QuickJS + HTML/CSS) Engine
- **Memory Usage:** **~55 MB total**.
- Uses Sciter.JS (powered by Fabrice Bellard's **QuickJS** engine) combined with Sciter's lightweight HTML/CSS layout engine.
- Replaces heavy Chromium/WebKit runtimes with pure HTML/CSS and QuickJS scripts.
- Template located in `sciter_frontend/notch.html`.

### How to Run Sciter + QuickJS:
```bash
python3 layzee_native.py --sciter
```
Or directly with the Sciter GTK runtime:
```bash
./bin/sciter/usciter sciter_frontend/notch.html
```

---

## Switching Branches
- **`main`**: Full React + Vite + WebKit2GTK recreation (uses the original Windows UI assets and animations).
- **`sciter`**: Ultra-lightweight Native GTK3 & Sciter (QuickJS + HTML/CSS) engine (< 60 MB RAM).
