# backend/scanner.py
"""
Library scanner: gathers games from Steam, Epic and Riot (when available),
enriches each GameEntry with metadata (covers) and returns or pushes the
result into a multiprocessing.Queue when provided.

This version:
 - Calls enrich_game_metadata(...) which sets game.cover_path / game.cover_url / game.image_path
 - Is robust to failures (continues on exceptions)
 - Accepts an optional queue (for mp.Process usage)
"""

from typing import List, Optional
from pathlib import Path
import sys

from common.utils import log_info, log_error
from backend.models import GameEntry
from backend.steam_parser import get_steam_games
from backend.epic_parser import get_epic_games
from backend.metadata import enrich_game_metadata
from common.settings import get_default_paths, load_config
import json


def scan_riot() -> list[GameEntry]:
    """
    Scan RiotClientInstalls.json (Windows/macOS only) to detect Riot games.
    Provides better logging and respects user override in config.json -> libraries.riot (first entry).
    """
    games = []

    # Riot not supported on Linux by design (Vanguard)
    if not (sys.platform.startswith("win") or sys.platform == "darwin"):
        log_info("scan_riot: skipping on non-supported OS")
        return games

    # Prefer user-overrides (settings) if present
    cfg = load_config()
    riot_paths = cfg.get("libraries", {}).get("riot") or []
    riot_default = get_default_paths().get("riot")
    if riot_paths:
        # user provided paths (accept only first for file)
        riot_file = Path(riot_paths[0])
    else:
        riot_file = Path(riot_default) if riot_default else None

    if not riot_file or not riot_file.exists():
        log_info(f"scan_riot: Riot installs JSON not found (tried: {riot_file})")
        return games

    try:
        raw = riot_file.read_text(encoding="utf-8")
        data = json.loads(raw)
        log_info(f"scan_riot: parsed Riot installs file with {len(data)} entries")
        for key, path in data.items():
            p = str(path)
            # Basic heuristics:
            if "LeagueClient" in p or "LeagueOfLegends" in p:
                games.append(GameEntry(
                    id="league",
                    name="League of Legends",
                    platform="riot",
                    installed=True,
                    install_path=Path(p).parent,
                    executable=p
                ))
            elif "VALORANT" in p.upper():
                games.append(GameEntry(
                    id="valorant",
                    name="VALORANT",
                    platform="riot",
                    installed=True,
                    install_path=Path(p).parent,
                    executable=p
                ))
            elif "Runeterra" in p or "LegendsOfRuneterra" in p:
                games.append(GameEntry(
                    id="lor",
                    name="Legends of Runeterra",
                    platform="riot",
                    installed=True,
                    install_path=Path(p).parent,
                    executable=p
                ))
            else:
                # unknown path — log for debugging
                log_info(f"scan_riot: ignored unknown install entry: {p}")
    except Exception as e:
        log_error(f"scan_riot: failed to parse {riot_file}: {e}")
    return games


def _platform_for_metadata(platform) -> Optional[str]:
    """
    Convert platform object/enum to a simple lowercase string for metadata use.
    Returns None if not provided.
    """
    if not platform:
        return None
    # If Enum-like with .value use that, otherwise coerce to str
    plat_val = getattr(platform, "value", None) or str(platform)
    try:
        return str(plat_val).lower()
    except Exception:
        return None


def scan_libraries(queue: Optional[object] = None) -> List[GameEntry]:
    """
    Scan all supported libraries (Steam, Epic, Riot), enrich with metadata and
    either return the list or put it into the provided multiprocessing.Queue.

    Signature supports being used as mp.Process(target=scan_libraries, args=(queue,))
    """
    results: List[GameEntry] = []

    # Gather raw results
    try:
        steam_games = get_steam_games()
        log_info(f"Steam scan returned {len(steam_games)} entries")
        results.extend(steam_games)
    except Exception as e:
        log_error(f"get_steam_games failed: {e}")

    try:
        epic_games = get_epic_games()
        log_info(f"Epic scan returned {len(epic_games)} entries")
        results.extend(epic_games)
    except Exception as e:
        log_error(f"get_epic_games failed: {e}")

    try:
        riot_games = scan_riot()
        if riot_games:
            log_info(f"Riot scan returned {len(riot_games)} entries")
        results.extend(riot_games)
    except Exception as e:
        # non-fatal
        log_error(f"scan_riot failed: {e}")

    # Enrich metadata (covers, image_path, cover_url, etc.)
    enriched: List[GameEntry] = []
    for game in results:
        try:
            # If the metadata module expects platform as a string, pass a string
            plat = _platform_for_metadata(getattr(game, "platform", None))
            # Call enrich_game_metadata which will set cover_path / cover_url / image_path
            # We pass the full GameEntry to let the helper set multiple attributes safely.
            enriched_game = enrich_game_metadata(game)
            # Fallback: if enrich_game_metadata didn't set image_path but fetch_cover available,
            # you could call fetch_cover here (but enrich_game_metadata already handles it).
            enriched.append(enriched_game)
        except Exception as e:
            log_error(f"Failed to enrich metadata for '{getattr(game, 'name', '<unknown>')}': {e}")
            enriched.append(game)

    # Put result into queue if requested (mp usage)
    if queue is not None:
        try:
            queue.put(enriched)
        except Exception as e:
            # If queueing fails, still return results to caller
            log_error(f"Failed to put scan results into queue: {e}")
            return enriched

        # When running in a child process, return empty collector to avoid accidental reuse
        return []

    return enriched
