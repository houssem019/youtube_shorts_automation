import os

# Chess.com Configuration
CHESS_USERNAME = "houssem999"  # Placeholder, will be updated by user
USER_AGENT = "ChessShortsBot/1.0 (contact: your_email@example.com)"

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
TEMP_DIR = os.path.join(DATA_DIR, "temp")

# YouTube Configuration
YOUTUBE_CLIENT_SECRETS_FILE = os.path.join(BASE_DIR, "client_secrets.json")
YOUTUBE_TOKEN_FILE = os.path.join(DATA_DIR, "token.json")
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# Background Music Configuration
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
BACKGROUND_MUSIC_DIR = os.path.join(ASSETS_DIR, "music")
MUSIC_HISTORY_FILE = os.path.join(DATA_DIR, "music_history.json")
BACKGROUND_MUSIC_VOLUME = 0.05

