import time
from .config import load_stats, save_stats

class StatsManager:
    def __init__(self, emit_callback):
        self.emit = emit_callback
        self.stats = load_stats()

    def get_stats(self):
        return self.stats

    def record_words(self, count):
        self.stats["total_words"] = self.stats.get("total_words", 0) + count
        self.stats["week_words"] = self.stats.get("week_words", 0) + count
        save_stats(self.stats)
        self.emit("stats", self.stats)
