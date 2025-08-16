from pathlib import Path
import json

from common.settings import CONFIG_DIR

FAVORITES_FILE = CONFIG_DIR / "favorites.json"


def _load_favorites() -> list[str]:
    if FAVORITES_FILE.exists():
        try:
            return json.loads(FAVORITES_FILE.read_text())
        except Exception:
            return []
    return []


def _save_favorites(favs: list[str]) -> None:
    FAVORITES_FILE.parent.mkdir(parents=True, exist_ok=True)
    FAVORITES_FILE.write_text(json.dumps(favs, indent=2))


def get_favorites() -> list[str]:
    return _load_favorites()


def add_favorite(game_id: str) -> None:
    favs = _load_favorites()
    if game_id not in favs:
        favs.append(game_id)
        _save_favorites(favs)


def remove_favorite(game_id: str) -> None:
    favs = _load_favorites()
    if game_id in favs:
        favs.remove(game_id)
        _save_favorites(favs)


def is_favorite(game_id: str) -> bool:
    return game_id in _load_favorites()
