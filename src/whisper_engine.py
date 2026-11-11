import os
import subprocess
import threading
import urllib.request
import re
from .config import MODELS_DIR

AVAILABLE_MODELS = {
    "turbo": {
        "id": "turbo",
        "name": "Large v3 Turbo",
        "file": "ggml-large-v3-turbo-q5_0.bin",
        "size_mb": 547,
        "sha256": "394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2"
    },
    "turbo_q8": {
        "id": "turbo_q8",
        "name": "Large v3 Turbo (Q8)",
        "file": "ggml-large-v3-turbo-q8_0.bin",
        "size_mb": 834,
        "sha256": "317eb69c11673c9de1e1f0d459b253999804ec71ac4c23c17ecf5fbe24e259a1"
    },
    "turbo_full": {
        "id": "turbo_full",
        "name": "Large v3 Turbo (FP16)",
        "file": "ggml-large-v3-turbo.bin",
        "size_mb": 1600,
        "sha256": "1fc70f774d38eb169993ac391eea357ef47c88757ef72ee5943879b7e8e2bc69"
    },
    "small": {
        "id": "small",
        "name": "Small (Q5_1)",
        "file": "ggml-small-q5_1.bin",
        "size_mb": 336,
        "sha256": "ae85e4a935d7a567bd102fe55afc16bb595bdb618e11b2fc7591bc08120411bb"
    },
    "tiny": {
        "id": "tiny",
        "name": "Tiny (Fastest)",
        "file": "ggml-tiny.bin",
        "size_mb": 75,
        "sha256": ""
    }
}

class WhisperEngine:
    def __init__(self, emit_callback):
        self.emit = emit_callback
        self.bin_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin")
        self.cli_path = os.path.join(self.bin_dir, "whisper-cli")
        self.downloading = {}

    def get_status(self, current_model="turbo"):
        installed = self.is_installed(current_model)
        if not installed:
            # Check if any model is installed
            any_installed = [m for m in AVAILABLE_MODELS if self.is_installed(m)]
            if not any_installed:
                return {
                    "engine": "no_model",
                    "backend": "cpu",
                    "model": current_model,
                    "message": "No model downloaded yet"
                }
        return {
            "engine": "ready",
            "backend": "cpu",
            "model": current_model,
            "message": None
        }

    def is_installed(self, model_id):
        info = AVAILABLE_MODELS.get(model_id)
        if not info:
            return False
        model_path = os.path.join(MODELS_DIR, info["file"])
        return os.path.exists(model_path) and os.path.getsize(model_path) > 1000000

    def list_models(self):
        result = []
        for mid, info in AVAILABLE_MODELS.items():
            model_path = os.path.join(MODELS_DIR, info["file"])
            installed = os.path.exists(model_path) and os.path.getsize(model_path) > 1000000
            current_size = os.path.getsize(model_path) // (1024 * 1024) if os.path.exists(model_path) else 0
            result.append({
                "id": mid,
                "name": info["name"],
                "size_mb": info["size_mb"],
                "installed": installed,
                "downloaded": current_size if installed else 0,
                "total": info["size_mb"]
            })
        return result

    def download_model(self, model_id):
        if model_id in self.downloading:
            return
        info = AVAILABLE_MODELS.get(model_id)
        if not info:
            return

        def _do_download():
            self.downloading[model_id] = True
            url = f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/{info['file']}"
            target_path = os.path.join(MODELS_DIR, info["file"])
            part_path = target_path + ".part"

            try:
                self.emit("model-progress", {"id": model_id, "percent": 0, "stage": "downloading"})
                req = urllib.request.Request(url, headers={"User-Agent": "layzee/2.1.5"})
                with urllib.request.urlopen(req) as resp, open(part_path, "wb") as out_f:
                    total_len = int(resp.headers.get("content-length", info["size_mb"] * 1024 * 1024))
                    downloaded = 0
                    chunk_size = 1024 * 512
                    last_pct = 0

                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        out_f.write(chunk)
                        downloaded += len(chunk)
                        pct = int((downloaded / total_len) * 100)
                        if pct != last_pct and pct % 2 == 0:
                            last_pct = pct
                            self.emit("model-progress", {"id": model_id, "percent": pct, "stage": "downloading"})

                os.rename(part_path, target_path)
                self.emit("model-progress", {"id": model_id, "percent": 100, "stage": "done"})
                self.emit("status", self.get_status(model_id))
            except Exception as e:
                print(f"[WhisperEngine] Download error: {e}")
                if os.path.exists(part_path):
                    os.remove(part_path)
                self.emit("model-progress", {"id": model_id, "percent": 0, "stage": "error"})
            finally:
                self.downloading.pop(model_id, None)

        threading.Thread(target=_do_download, daemon=True).start()

    def delete_model(self, model_id):
        info = AVAILABLE_MODELS.get(model_id)
        if not info:
            return
        path = os.path.join(MODELS_DIR, info["file"])
        if os.path.exists(path):
            os.remove(path)

    def transcribe(self, wav_path, model_id="turbo", lang="auto", settings=None):
        info = AVAILABLE_MODELS.get(model_id)
        if not info or not self.is_installed(model_id):
            # Fallback to any installed model
            installed_list = [m for m in AVAILABLE_MODELS if self.is_installed(m)]
            if installed_list:
                info = AVAILABLE_MODELS[installed_list[0]]
            else:
                return "Belum ada model Whisper yang di-download."

        model_path = os.path.join(MODELS_DIR, info["file"])
        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = self.bin_dir + ":" + env.get("LD_LIBRARY_PATH", "")

        cmd = [
            self.cli_path,
            "-m", model_path,
            "-f", wav_path,
            "-t", "6",
            "--no-timestamps"
        ]
        if lang and lang != "auto":
            cmd.extend(["-l", lang])

        try:
            res = subprocess.check_output(cmd, env=env, stderr=subprocess.DEVNULL).decode("utf-8")
            text = res.strip()
            # Post-process
            if settings:
                text = self._post_process(text, settings)
            return text
        except Exception as e:
            print(f"[WhisperEngine] Transcription error: {e}")
            return ""

    def _post_process(self, text, settings):
        if not text:
            return ""

        # Remove fillers if enabled
        if settings.get("remove_fillers"):
            fillers = [
                r"\b(?:uh|um|er|ah|eh|anu|kayak|gitu|hmm)\b",
                r"\b(?:like|you know|i mean)\b"
            ]
            for pattern in fillers:
                text = re.sub(pattern, "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s+", " ", text).strip()

        # Capitalization
        cap = settings.get("capitalization", "first_only")
        if cap == "first_only" and len(text) > 0:
            text = text[0].upper() + text[1:]
        elif cap == "lower":
            text = text.lower()

        # End punctuation
        if not settings.get("end_punct"):
            text = text.rstrip(".!?")

        # Trailing space
        if settings.get("trailing_space") and not text.endswith(" "):
            text += " "

        return text
