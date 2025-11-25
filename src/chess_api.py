import chessdotcom as chess_api
from chessdotcom import Client
import chess.pgn
import io
import random
import logging
from datetime import datetime
from config import USER_AGENT

# Configure User-Agent
Client.request_config["headers"]["User-Agent"] = USER_AGENT

logger = logging.getLogger(__name__)

def get_latest_game(username, max_moves=90):
    """
    Fetches the most recent game for the given username.
    Returns the PGN string or None if no games found.
    Skips games with more than max_moves to keep videos under 3 minutes.
    """
    try:
        # Get archives to find the latest month
        archives = chess_api.get_player_game_archives(username).json
        if not archives['archives']:
            logger.info(f"No archives found for user {username}")
            return None

        latest_archive_url = archives['archives'][-1]
        # URL format: https://api.chess.com/pub/player/{username}/games/{YYYY}/{MM}
        parts = latest_archive_url.split('/')
        year = parts[-2]
        month = parts[-1]

        games = chess_api.get_player_games_by_month(username, year=year, month=month).json

        if not games['games']:
            logger.info(f"No games found in the latest archive for {username}")
            return None

        # Get the very last game and check move count
        for game in reversed(games['games']):
            pgn_str = game.get('pgn')
            if pgn_str and _count_moves(pgn_str) <= max_moves:
                return pgn_str

        logger.info(f"No games found with {max_moves} moves or less")
        return None

    except Exception as e:
        logger.error(f"Error fetching latest game for {username}: {e}")
        return None

def get_random_old_game(username, max_moves=100):
    """
    Fetches a random game from the user's archives.
    Skips games with more than max_moves.
    """
    try:
        archives = chess_api.get_player_game_archives(username).json
        if not archives['archives']:
            return None

        # Pick a random archive
        random_archive_url = random.choice(archives['archives'])
        parts = random_archive_url.split('/')
        year = parts[-2]
        month = parts[-1]

        games = chess_api.get_player_games_by_month(username, year=year, month=month).json

        if not games['games']:
            return None

        # Filter games by move count
        valid_games = [g for g in games['games'] if _count_moves(g.get('pgn', '')) <= max_moves]

        if not valid_games:
            logger.info(f"No games found with {max_moves} moves or less in this archive")
            return None

        # Pick a random valid game
        random_game = random.choice(valid_games)
        return random_game.get('pgn')

    except Exception as e:
        logger.error(f"Error fetching random game for {username}: {e}")
        return None

def _count_moves(pgn_string):
    """
    Counts the number of moves in a PGN string.
    """
    if not pgn_string:
        return 0

    try:
        pgn = io.StringIO(pgn_string)
        game = chess.pgn.read_game(pgn)
        if not game:
            return 0
        return sum(1 for _ in game.mainline_moves())
    except:
        return 0

