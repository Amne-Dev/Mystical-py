"""
Metadata helper module for fetching game covers, descriptions, etc.
Currently a placeholder; extend with real API calls later.
"""

from pathlib import Path
from backend.models import GameEntry
from common.utils import log_info, log_error


def fetch_cover(game: GameEntry) -> str | None:
    """
    Dummy metadata fetcher: in the future connect to IGDB or SteamGridDB.
    For now, just return None so the app still works.
    """
    log_info(f"[metadata] Fetching cover for: {game.name}")
    return None


def enrich_game_metadata(game: GameEntry) -> GameEntry:
    """
    Stub: enrich the GameEntry with metadata.
    """
    try:
        cover = fetch_cover(game)
        if cover:
            game.image_path = Path(cover)
    except Exception as e:
        log_error(f"Metadata fetch failed for {game.name}: {e}")

    # Could also add description/release_year when API is ready
    return game
