import chessdotcom as chess_api
from chessdotcom import Client
import chess.pgn
import io
import random
import re
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

def get_random_unedited_game(username, history, max_plies=100, min_plies=0, time_class=None, max_months=12):
    """
    A random game of the user's that isn't in `history` (a list of game links or IDs).
    Looks through archive months in random order; only games with min_plies..max_plies half-moves,
    of the given time class ("rapid", "blitz", ...; None = any) and not abandoned count.
    Returns the PGN string or None if no month had a match.
    """
    done = {parse_game_id(h) or h for h in history}
    try:
        archives = chess_api.get_player_game_archives(username).json['archives']
        months = random.sample(archives, len(archives))
        for archive_url in months[:max_months]:
            parts = archive_url.split('/')
            games = chess_api.get_player_games_by_month(username, year=parts[-2], month=parts[-1]).json['games']
            valid = []
            for g in games:
                pgn_str = g.get('pgn')
                game_id = parse_game_id(g.get('url', ''))
                if not pgn_str or not game_id or game_id in done:
                    continue
                if time_class and g.get('time_class') != time_class:
                    continue
                if "abandoned" in (g.get('white', {}).get('result'), g.get('black', {}).get('result')):
                    continue
                if min_plies <= _count_moves(pgn_str) <= max_plies:
                    valid.append(pgn_str)
            if valid:
                return random.choice(valid)
            logger.info(f"No unedited games that fit in {parts[-2]}/{parts[-1]}; trying another month.")
        logger.info(f"No unedited games that fit in {min(max_months, len(months))} months.")
        return None
    except Exception as e:
        logger.error(f"Error picking a random game for {username}: {e}")
        return None


def get_recent_good_game(username, history, max_plies=200, min_plies=0, time_class=None, months=6, rating_margin=100):
    """
    A random unedited game from the user's last `months` archive months, played while the user's rating was
    good: at most `rating_margin` below the user's best rating in those games. Same filters as
    get_random_unedited_game. Returns the PGN string or None if no game fits.
    """
    done = {parse_game_id(h) or h for h in history}
    me = username.lower()
    try:
        archives = chess_api.get_player_game_archives(username).json['archives']
        pool = []  # (user rating, pgn)
        for archive_url in reversed(archives[-months:]):
            parts = archive_url.split('/')
            games = chess_api.get_player_games_by_month(username, year=parts[-2], month=parts[-1]).json['games']
            for g in games:
                pgn_str = g.get('pgn')
                game_id = parse_game_id(g.get('url', ''))
                if not pgn_str or not game_id or game_id in done:
                    continue
                if time_class and g.get('time_class') != time_class:
                    continue
                white, black = g.get('white', {}), g.get('black', {})
                if "abandoned" in (white.get('result'), black.get('result')):
                    continue
                mine = white if white.get('username', '').lower() == me else black
                if not mine.get('rating') or not min_plies <= _count_moves(pgn_str) <= max_plies:
                    continue
                pool.append((mine['rating'], pgn_str))
        if not pool:
            logger.info(f"No unedited games that fit in the last {months} months.")
            return None
        best = max(r for r, _ in pool)
        good = [p for r, p in pool if r >= best - rating_margin]
        logger.info(f"{len(good)} unedited games from the last {months} months played at {best - rating_margin}+ "
                    f"(best rating there: {best}).")
        return random.choice(good)
    except Exception as e:
        logger.error(f"Error picking a recent game for {username}: {e}")
        return None


def parse_game_id(game_ref):
    """'185153537828', 'https://www.chess.com/game/live/185153537828?move=3' -> '185153537828' (None if no ID)."""
    match = re.search(r"(\d{5,})(?!.*\d{5,})", game_ref or "")
    return match.group(1) if match else None


def get_game_by_id(username, game_ref):
    """
    Finds one of the user's games by its chess.com link or ID, searching the archives from the newest month back.
    Returns the PGN string or None if it isn't found.
    """
    game_id = parse_game_id(game_ref)
    if not game_id:
        logger.error(f"'{game_ref}' doesn't look like a chess.com game link or ID.")
        return None
    try:
        archives = chess_api.get_player_game_archives(username).json
        for archive_url in reversed(archives['archives']):
            parts = archive_url.split('/')
            games = chess_api.get_player_games_by_month(username, year=parts[-2], month=parts[-1]).json
            for game in games['games']:
                if game.get('url', '').rstrip('/').split('/')[-1] == game_id and game.get('pgn'):
                    return game['pgn']
        logger.error(f"Game {game_id} was not found in {username}'s games.")
        return None
    except Exception as e:
        logger.error(f"Error fetching game {game_id} for {username}: {e}")
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

