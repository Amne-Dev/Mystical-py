from pathlib import Path
from typing import List
import vdf

from backend.models import GameEntry, Platform
from common.settings import get_library_paths
from common.utils import log_info, log_error


def _parse_libraryfolders(vdf_path: Path) -> list[Path]:
    """Parse Steam's libraryfolders.vdf to get all Steam library paths."""
    libs = []
    try:
        data = vdf.load(open(vdf_path, encoding="utf-8"))
        if "libraryfolders" in data:
            for _, entry in data["libraryfolders"].items():
                path = Path(entry["path"])
                libs.append(path)
    except Exception as e:
        log_error(f"Error parsing {vdf_path}: {e}")
    return libs


def get_steam_games() -> List[GameEntry]:
    libs = []
    defaults = get_library_paths().get("steam", [])

    # Find libraryfolders.vdf in defaults
    for base in defaults:
        vdf_path = Path(base) / "steamapps" / "libraryfolders.vdf"
        if vdf_path.exists():
            libs.extend(_parse_libraryfolders(vdf_path))
        else:
            libs.append(base)  # fallback to default

    games: List[GameEntry] = []

    for lib_path in libs:
        steamapps = Path(lib_path) / "steamapps"
        if not steamapps.exists():
            continue

        for manifest in steamapps.glob("appmanifest_*.acf"):
            try:
                data = vdf.load(open(manifest, encoding="utf-8"))
                appid = data.get("AppState", {}).get("appid", "")
                name = data.get("AppState", {}).get("name", "Unknown")
                installdir = data.get("AppState", {}).get("installdir", "")
                install_path = steamapps / "common" / installdir

                game = GameEntry(
                    id=str(appid),
                    name=name,
                    platform=Platform.STEAM,
                    install_path=install_path,
                    installed=install_path.exists()
                )
                games.append(game)
            except Exception as e:
                log_error(f"Error parsing manifest {manifest}: {e}")

    log_info(f"Found {len(games)} Steam games")
    return games