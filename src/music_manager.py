import os
import json
import random
import logging
from config import BACKGROUND_MUSIC_DIR, MUSIC_HISTORY_FILE

logger = logging.getLogger(__name__)

class MusicManager:
    def __init__(self):
        self.music_dir = BACKGROUND_MUSIC_DIR
        self.history_file = MUSIC_HISTORY_FILE
        self._ensure_music_dir_exists()

    def _ensure_music_dir_exists(self):
        if not os.path.exists(self.music_dir):
            os.makedirs(self.music_dir)

    def _load_history(self):
        if not os.path.exists(self.history_file):
            return {}
        try:
            with open(self.history_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading music history: {e}")
            return {}

    def _save_history(self, history):
        try:
            with open(self.history_file, 'w') as f:
                json.dump(history, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving music history: {e}")

    def get_background_music(self):
        """
        Selects a background music file.
        Prioritizes files that haven't been used recently.
        """
        if not os.path.exists(self.music_dir):
            return None

        files = [f for f in os.listdir(self.music_dir) if f.lower().endswith(('.mp3', '.wav'))]
        if not files:
            logger.warning(f"No music files found in {self.music_dir}")
            return None

        history = self._load_history()

        # Sort files by usage count (ascending)
        # If count is same, random tie-break is good, but let's just use min
        # We want to find the file with minimum usage count

        file_stats = []
        for f in files:
            count = history.get(f, 0)
            file_stats.append((count, f))

        # Find minimum count
        min_count = min(s[0] for s in file_stats)

        # Get all files with that minimum count
        candidates = [s[1] for s in file_stats if s[0] == min_count]

        # Pick one randomly
        selected_file = random.choice(candidates)

        # Update history
        history[selected_file] = history.get(selected_file, 0) + 1
        self._save_history(history)

        full_path = os.path.join(self.music_dir, selected_file)
        logger.info(f"Selected background music: {selected_file} (Used {history[selected_file]} times)")

        return full_path
