from backend.models import GameEntry
from backend.steam_parser import get_steam_games
from backend.epic_parser import get_epic_games
from common.settings import get_default_paths
from backend.metadata import fetch_cover
import json
import sys
from pathlib import Path


# ---------- Riot ----------
def scan_riot() -> list[GameEntry]:
    """
    Scan RiotClientInstalls.json (Windows/macOS only) to detect Riot games.
    """
    games = []

    # Riot Vanguard blocks Linux, skip
    if not (sys.platform.startswith("win") or sys.platform == "darwin"):
        return games

    default_paths = get_default_paths()
    riot_file = default_paths.get("riot")

    if not riot_file or not Path(riot_file).exists():
        return games

    try:
        data = json.loads(Path(riot_file).read_text())
        for key, path in data.items():
            path = str(path)
            if "LeagueClient" in path:
                games.append(GameEntry(
                    id="league",
                    name="League of Legends",
                    platform="riot",
                    installed=True,
                    install_path=Path(path).parent,
                    executable=path
                ))
            elif "VALORANT" in path:
                games.append(GameEntry(
                    id="valorant",
                    name="VALORANT",
                    platform="riot",
                    installed=True,
                    install_path=Path(path).parent,
                    executable=path
                ))
            elif "LoR" in path or "Runeterra" in path:
                games.append(GameEntry(
                    id="lor",
                    name="Legends of Runeterra",
                    platform="riot",
                    installed=True,
                    install_path=Path(path).parent,
                    executable=path
                ))
    except Exception:
        pass

    return games


# ---------- Main Scanner ----------
def scan_libraries(queue=None) -> list[GameEntry]:
    """
    Scan all supported libraries (Steam, Epic, Riot)
    and return combined game list.
    """
    results: list[GameEntry] = []
    results.extend(get_steam_games())
    results.extend(get_epic_games())
    results.extend(scan_riot())

    # Fetch covers/metadata
    for game in results:
        if not game.image_path:
            cover = fetch_cover(game.name, game.platform)
            if cover:
                game.image_path = cover

    if queue:
        queue.put(results)
    return results
