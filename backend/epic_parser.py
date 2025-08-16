import json
from pathlib import Path
from typing import List

from backend.models import GameEntry, Platform
from common.settings import get_library_paths
from common.utils import log_info, log_error


def _parse_manifest_file(path: Path) -> GameEntry | None:
    """Parse a single Epic manifest .item file."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))

        game_id = data.get("CatalogItemId") or data.get("AppName") or path.stem
        name = data.get("DisplayName", "Unknown Epic Game")
        install_location = data.get("InstallLocation")
        install_path = Path(install_location) if install_location else None

        return GameEntry(
            id=str(game_id),
            name=name,
            platform=Platform.EPIC,
            install_path=install_path,
            installed=install_path.exists() if install_path else False,
        )
    except Exception as e:
        log_error(f"Failed to parse Epic manifest {path}: {e}")
        return None


def _parse_legendary_file(path: Path) -> List[GameEntry]:
    """Parse Legendary's installed.json file (Linux)."""
    games: List[GameEntry] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        for game_id, entry in data.items():
            name = entry.get("title") or entry.get("app_name", "Unknown")
            install_path = Path(entry.get("install_path", "")) if entry.get("install_path") else None
            games.append(
                GameEntry(
                    id=game_id,
                    name=name,
                    platform=Platform.EPIC,
                    install_path=install_path,
                    installed=install_path.exists() if install_path else False,
                )
            )
    except Exception as e:
        log_error(f"Failed to parse Legendary installed.json: {e}")
    return games


def get_epic_games() -> List[GameEntry]:
    libs = get_library_paths().get("epic", [])
    games: List[GameEntry] = []

    for lib_path in libs:
        if not Path(lib_path).exists():
            continue

        # Case 1: Epic Games Launcher manifests (.item files)
        for manifest in Path(lib_path).glob("*.item"):
            game = _parse_manifest_file(manifest)
            if game:
                games.append(game)

        # Case 2: Legendary installed.json
        installed_json = Path(lib_path) / "installed.json"
        if installed_json.exists():
            games.extend(_parse_legendary_file(installed_json))

    log_info(f"Found {len(games)} Epic games")
    return games