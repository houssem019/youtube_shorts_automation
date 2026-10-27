import os

# Chess.com Configuration (the CHESS_USERNAME environment variable overrides this)
CHESS_USERNAME = os.environ.get("CHESS_USERNAME", "houssem999")
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


# Edited Short with commentary (video_editor/). Set EDITOR_ENABLED = False to go back to the plain render.
EDITOR_ENABLED = True
EDITOR_DIR = os.path.join(BASE_DIR, "video_editor")
EDITOR_PYTHON = os.path.join(EDITOR_DIR, ".venv", "Scripts", "python.exe")
# Stockfish engine (the STOCKFISH_PATH environment variable overrides this)
STOCKFISH_PATH = os.environ.get(
    "STOCKFISH_PATH", r"C:\Users\Cognira\Downloads\stockfish-windows-x86-64-avx2\stockfish\stockfish-windows-x86-64-avx2.exe")
EDITOR_VOICES = ["af_heart", "am_michael"]  # narrators, used in turn: one per uploaded video (female, male)
EDITOR_VOICE_FILE = os.path.join(DATA_DIR, "editor_voice.json")  # remembers the voice of the last upload
EDITOR_STYLE_FILE = os.path.join(DATA_DIR, "editor_style.json")  # storytelling styles + titles of the latest uploads
EDITOR_WRITER = "auto"         # "auto" = Claude writes the commentary if available, else the built-in writer
EDITOR_TIMEOUT_MIN = 45

# Long-form videos (video_editor/make_long.py): 16:9, 5-10 min, own history so a game can get a Short AND a long video.
LONG_HISTORY_FILE = os.path.join(DATA_DIR, "history_long.json")
LONG_STYLE_FILE = os.path.join(DATA_DIR, "editor_style_long.json")  # styles + titles of the latest long videos
LONG_VOICE = "am_michael"      # one fixed narrator for every long video
LONG_WORK_DIR = os.path.join(TEMP_DIR, "long")
LONG_TIMEOUT_MIN = 240         # a long render takes 1-2 hours
LONG_TIME_CLASS = "rapid"      # random long picks only use games of this time class (None = any)
LONG_MIN_PLIES, LONG_MAX_PLIES = 40, 200
LONG_RECENT_MONTHS = 6         # random long picks come from the last 6 months...
LONG_RATING_MARGIN = 100       # ...and from games played at most 100 points below my best rating in them
