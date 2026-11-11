import dbus
import urllib.request
import urllib.parse
import json
import base64
import os
import re
import threading
import time

class MediaManager:
    def __init__(self, emit_callback):
        self.emit = emit_callback
        self.current_media = None
        self.current_art = None
        self.lyrics_cache = {}
        self.running = True
        self.bus = None
        try:
            self.bus = dbus.SessionBus()
        except Exception as e:
            print(f"[Media] DBus session bus error: {e}")

        self.thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.thread.start()

    def _get_active_player(self):
        if not self.bus:
            return None
        try:
            names = [n for n in self.bus.list_names() if n.startswith("org.mpris.MediaPlayer2.") and "layzee" not in n.lower()]
            # Prefer active playing or known players
            for name in names:
                try:
                    obj = self.bus.get_object(name, "/org/mpris.MediaPlayer2")
                    props = dbus.Interface(obj, "org.freedesktop.DBus.Properties")
                    status = str(props.Get("org.mpris.MediaPlayer2.Player", "PlaybackStatus"))
                    if status == "Playing":
                        return name
                except Exception:
                    pass
            if names:
                return names[0]
        except Exception:
            pass
        return None

    def _poll_loop(self):
        last_track_id = None
        while self.running:
            try:
                player_name = self._get_active_player()
                if player_name:
                    obj = self.bus.get_object(player_name, "/org/mpris.MediaPlayer2")
                    props = dbus.Interface(obj, "org.freedesktop.DBus.Properties")
                    metadata = props.Get("org.mpris.MediaPlayer2.Player", "Metadata")
                    status = str(props.Get("org.mpris.MediaPlayer2.Player", "PlaybackStatus"))

                    title = ""
                    if "xesam:title" in metadata:
                        title = str(metadata["xesam:title"])

                    artist = ""
                    if "xesam:artist" in metadata:
                        artists = metadata["xesam:artist"]
                        if isinstance(artists, (list, dbus.Array)) and len(artists) > 0:
                            artist = str(artists[0])
                        else:
                            artist = str(artists)

                    album = ""
                    if "xesam:album" in metadata:
                        album = str(metadata["xesam:album"])

                    pos = 0
                    try:
                        pos = int(props.Get("org.mpris.MediaPlayer2.Player", "Position")) / 1000000.0
                    except Exception:
                        pass

                    duration = 0
                    if "mpris:length" in metadata:
                        try:
                            duration = int(metadata["mpris:length"]) / 1000000.0
                        except Exception:
                            pass

                    art_url = ""
                    if "mpris:artUrl" in metadata:
                        art_url = str(metadata["mpris:artUrl"])

                    media_info = {
                        "title": title or "Unknown Title",
                        "artist": artist or "Unknown Artist",
                        "album": album,
                        "playing": (status == "Playing"),
                        "pos": round(pos),
                        "duration": round(duration),
                    }

                    track_key = f"{title}_{artist}"
                    if track_key != last_track_id:
                        last_track_id = track_key
                        # Update art
                        art_data = self._load_art(art_url)
                        self.current_art = art_data
                        self.emit("media-art", art_data)
                        # Fetch lyrics in background
                        threading.Thread(target=self._fetch_lyrics, args=(title, artist), daemon=True).start()

                    self.current_media = media_info
                    self.emit("media", media_info)
                else:
                    if self.current_media is not None:
                        self.current_media = None
                        self.emit("media", None)
                        self.emit("media-art", None)
            except Exception as e:
                pass

            time.sleep(1.0)

    def _load_art(self, art_url):
        if not art_url:
            return None
        if art_url.startswith("file://"):
            local_path = art_url[7:]
            if os.path.exists(local_path):
                try:
                    with open(local_path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode("ascii")
                        return f"data:image/jpeg;base64,{b64}"
                except Exception:
                    pass
        elif art_url.startswith("data:"):
            return art_url
        return art_url

    def _fetch_lyrics(self, title, artist):
        if not title:
            return
        cache_key = f"{title} {artist}".strip()
        if cache_key in self.lyrics_cache:
            self.emit("lyrics", self.lyrics_cache[cache_key])
            return

        try:
            params = urllib.parse.urlencode({"track_name": title, "artist_name": artist})
            url = f"https://lrclib.net/api/get?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": "layzee/2.1.5"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                synced = data.get("syncedLyrics")
                if synced:
                    lines = self._parse_lrc(synced)
                    payload = {"key": cache_key, "lines": lines}
                    self.lyrics_cache[cache_key] = payload
                    self.emit("lyrics", payload)
        except Exception:
            pass

    def _parse_lrc(self, lrc_text):
        lines = []
        for line in lrc_text.splitlines():
            m = re.match(r"\[(\d+):(\d+(?:\.\d+)?)\](.*)", line)
            if m:
                mins = int(m.group(1))
                secs = float(m.group(2))
                text = m.group(3).strip()
                lines.append({"time": mins * 60 + secs, "text": text})
        return lines

    def control(self, action, pos=None):
        player_name = self._get_active_player()
        if not player_name or not self.bus:
            return
        try:
            obj = self.bus.get_object(player_name, "/org/mpris.MediaPlayer2")
            player = dbus.Interface(obj, "org.mpris.MediaPlayer2.Player")
            if action == "toggle" or action == "playpause":
                player.PlayPause()
            elif action == "play":
                player.Play()
            elif action == "pause":
                player.Pause()
            elif action == "next":
                player.Next()
            elif action == "prev" or action == "previous":
                player.Previous()
            elif action == "seek" and pos is not None:
                props = dbus.Interface(obj, "org.freedesktop.DBus.Properties")
                metadata = props.Get("org.mpris.MediaPlayer2.Player", "Metadata")
                track_id = metadata.get("mpris:trackid", "/org/mpris/MediaPlayer2/CurrentTrack")
                player.SetPosition(track_id, dbus.Int64(int(pos * 1000000)))
        except Exception as e:
            print(f"[Media] Control error: {e}")
