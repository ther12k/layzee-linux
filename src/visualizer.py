import threading
import time
import random
import math

class VisualizerManager:
    def __init__(self, emit_callback, media_manager):
        self.emit = emit_callback
        self.media = media_manager
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        t = 0.0
        while self.running:
            is_playing = False
            if self.media and self.media.current_media and self.media.current_media.get("playing"):
                is_playing = True

            if is_playing:
                # 4 frequency bands for the notch music visualizer
                b1 = max(0.1, min(1.0, 0.5 + 0.4 * math.sin(t * 3.5) + random.uniform(-0.1, 0.1)))
                b2 = max(0.1, min(1.0, 0.6 + 0.35 * math.sin(t * 4.2 + 1.2) + random.uniform(-0.1, 0.1)))
                b3 = max(0.1, min(1.0, 0.55 + 0.38 * math.sin(t * 5.1 + 2.4) + random.uniform(-0.1, 0.1)))
                b4 = max(0.1, min(1.0, 0.45 + 0.42 * math.sin(t * 2.8 + 0.5) + random.uniform(-0.1, 0.1)))
                self.emit("viz", [b1, b2, b3, b4])
            else:
                pass

            t += 0.08
            time.sleep(0.08)
