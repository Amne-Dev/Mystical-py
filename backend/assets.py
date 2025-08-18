from pathlib import Path
import requests

from backend.models import GameEntry, Platform
from common.settings import CACHE_DIR
from common.utils import log_info, log_error

def fetch_assets(game: GameEntry) -> Path | None:
    """
    Fetch or return cached cover image for a game.
    Currently supports Steam covers via Steam CDN.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    img_path = CACHE_DIR / f"{game.platform.value}_{game.id}.jpg" # type: ignore

    if img_path.exists():
        return img_path

    try:
        if game.platform == Platform.STEAM and game.id.isdigit():
            url = f"https://steamcdn-a.akamaihd.net/steam/apps/{game.id}/header.jpg"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                img_path.write_bytes(resp.content)
                log_info(f"Downloaded Steam cover for {game.name}")
                return img_path

        # TODO: Epic support (SteamGridDB API or Legendary metadata)
        # For now, just return None → UI will show placeholder

    except Exception as e:
        log_error(f"Failed to fetch cover for {game.name}: {e}")

    return None