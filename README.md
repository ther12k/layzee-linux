# Layzee for Ubuntu (Linux Recreation)

Recreation of **Layzee 2.1.5** (originally a Windows Tauri 2.12 + whisper.cpp app) for **Ubuntu / Linux**.

## Features Recreated
1. **Dynanotch (Notch & Dynamic Island)**:
   - Borderless, transparent, always-on-top floating pill at top of screen with X11 shape clipping (`input_shape_combine_region`).
   - Background clicks and hovers pass through transparent areas to underlying applications.
   - Music player with album art, controls, and live synced lyrics (via MPRIS2 DBus + LRCLIB).
   - Audio spectrum visualizer (`viz`).
   - Ambient sound generator (Rain, Campfire, Forest, Waves, Kalimba, Handpan, Keyboard, Water).
   - Pomodoro focus timer & daily To-Do tasks.
   - Screen time indicator.
   - Clipboard history manager.
   - Volume / App audio mixer controls (PulseAudio / PipeWire).

2. **Lazytype (Voice Typing / Offline Speech-to-Text)**:
   - Global hotkey (default: **CapsLock** hold-to-talk).
   - Microphone recording with live audio level visualization.
   - Native transcription using compiled `whisper.cpp` (`whisper-cli`).
   - Automatic filler removal ("uh", "um", "kayak", "gitu", etc.), auto capitalization, and punctuation rules.
   - Pastes directly into the focused application via X11 synthetic input.

3. **Lazyshot (Screen Capture & OCR)**:
   - Fullscreen capture triggered via shortcut (default: **Ctrl+Shift+S**).
   - Interactive drawing canvas (pen, arrow, rectangle, ellipse, text).
   - Copy to clipboard or extract text via OCR.

4. **Settings & Statistics Window**:
   - Complete original UI with all tabs (Home, Dynanotch, Lazytype, Lazyshot, Screen Time, Reminders, General, Support).
   - Model manager to download and switch Whisper models (`turbo`, `small`, etc.).
   - Microphone selection and live testing.

## How to Run

```bash
./run.sh
```

Or execute directly:
```bash
python3 layzee.py
```

## System Tray
Layzee runs in the system tray (AppIndicator) where you can quickly toggle the Notch, open Settings, trigger Speech-to-Text, capture the screen, or quit.
