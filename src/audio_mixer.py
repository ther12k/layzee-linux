import subprocess
import re

class AudioMixer:
    def __init__(self):
        pass

    def get_mixer_list(self):
        master_vol = 1.0
        master_muted = False
        apps = []

        # Get default sink volume
        try:
            out = subprocess.check_output(["pactl", "get-sink-volume", "@DEFAULT_SINK@"], stderr=subprocess.DEVNULL).decode("utf-8")
            m = re.search(r"(\d+)%", out)
            if m:
                master_vol = int(m.group(1)) / 100.0
            
            mute_out = subprocess.check_output(["pactl", "get-sink-mute", "@DEFAULT_SINK@"], stderr=subprocess.DEVNULL).decode("utf-8")
            if "yes" in mute_out.lower():
                master_muted = True
        except Exception:
            pass

        # Get sink inputs (running audio applications)
        try:
            out = subprocess.check_output(["pactl", "list", "sink-inputs"], stderr=subprocess.DEVNULL).decode("utf-8")
            chunks = out.split("Sink Input #")
            for chunk in chunks[1:]:
                app_name = None
                app_vol = 1.0
                app_muted = False

                for line in chunk.splitlines():
                    line = line.strip()
                    if line.startswith("application.name = "):
                        app_name = line.split("=", 1)[1].strip().strip('"')
                    elif line.startswith("Volume:") and not app_vol:
                        vm = re.search(r"(\d+)%", line)
                        if vm:
                            app_vol = int(vm.group(1)) / 100.0
                    elif line.startswith("Mute:"):
                        app_muted = "yes" in line.lower()

                if app_name:
                    apps.append({
                        "name": app_name,
                        "vol": app_vol,
                        "muted": app_muted
                    })
        except Exception:
            pass

        return {
            "master": master_vol,
            "muted": master_muted,
            "apps": apps
        }

    def set_mixer(self, target, vol=None, mute=None):
        try:
            if target == "master":
                if vol is not None:
                    pct = int(vol * 100)
                    subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{pct}%"], check=False)
                if mute is not None:
                    subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1" if mute else "0"], check=False)
            else:
                # Find sink input id for target application
                out = subprocess.check_output(["pactl", "list", "sink-inputs"], stderr=subprocess.DEVNULL).decode("utf-8")
                chunks = out.split("Sink Input #")
                for chunk in chunks[1:]:
                    lines = chunk.splitlines()
                    inp_id = lines[0].strip()
                    has_name = any(f'application.name = "{target}"' in l for l in lines)
                    if has_name:
                        if vol is not None:
                            pct = int(vol * 100)
                            subprocess.run(["pactl", "set-sink-input-volume", inp_id, f"{pct}%"], check=False)
                        if mute is not None:
                            subprocess.run(["pactl", "set-sink-input-mute", inp_id, "1" if mute else "0"], check=False)
        except Exception as e:
            print(f"[Mixer] set_mixer error: {e}")
