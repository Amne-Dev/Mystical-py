# common/settings.py
import json
import platform
from pathlib import Path
from typing import Dict, List, Optional, Any

CONFIG_DIR = Path.home() / ".mystical"
CONFIG_FILE = CONFIG_DIR / "config.json"
CACHE_DIR = CONFIG_DIR / "cache" / "images"

DEFAULT_CONFIG: Dict[str, Any] = {
    "libraries": {
        "steam": [],
        "epic": [],
        "riot": []
    },
    "theme": "system",   # supported: system, light, dark, steam, epic
    "autostart": False,
    "favorites": [],
    "igdb": {            # used by metadata.py for IGDB OAuth
        "client_id": "",
        "client_secret": "",
        "access_token": "",
        "expires_at": 0
    }
}


def get_default_paths() -> Dict[str, Optional[Path]]:
    """
    Return default Steam, Epic, and Riot paths depending on OS.
    Riot is only supported on Windows/macOS.
    """
    system = platform.system().lower()
    paths: Dict[str, Optional[Path]] = {}

    if system == "windows":
        paths["steam"] = Path("C:/Program Files (x86)/Steam")
        paths["epic"] = Path("C:/ProgramData/Epic/EpicGamesLauncher/Data/Manifests")
        paths["riot"] = Path("C:/ProgramData/Riot Games/RiotClientInstalls.json")

    elif system == "linux":
        paths["steam"] = Path.home() / ".steam/steam"
        paths["epic"] = Path.home() / ".local/share/legendary"
        paths["riot"] = None  # Riot Vanguard blocks Linux

    elif system == "darwin":  # macOS
        paths["steam"] = Path.home() / "Library/Application Support/Steam"
        paths["epic"] = Path.home() / "Library/Application Support/Epic"
        paths["riot"] = Path("/Users/Shared/Riot Games/RiotClientInstalls.json")

    else:
        # Unknown platform — return empty placeholders
        paths["steam"] = None
        paths["epic"] = None
        paths["riot"] = None

    return paths


def load_config() -> Dict[str, Any]:
    """
    Load config.json if present, else return a copy of DEFAULT_CONFIG.
    Merges missing fields from defaults to preserve backward compatibility.
    """
    # Ensure config dir exists
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            # Merge defaults (shallow) so missing keys are present
            merged = DEFAULT_CONFIG.copy()
            # For nested dicts, merge reasonably
            merged_libs = merged.get("libraries", {}).copy()
            loaded_libs = data.get("libraries", {})
            merged_libs.update(loaded_libs)
            merged["libraries"] = merged_libs

            # merge igdb block
            merged_igdb = merged.get("igdb", {}).copy()
            merged_igdb.update(data.get("igdb", {}))
            merged["igdb"] = merged_igdb

            # other top-level keys — take from loaded config when present
            for k in ("theme", "autostart", "favorites"):
                if k in data:
                    merged[k] = data[k]

            # Include any additional keys present in user's file (keep-forward compatibility)
            for k, v in data.items():
                if k not in merged:
                    merged[k] = v

            return merged
        except Exception:
            # If parsing fails, return defaults (safe fallback)
            return DEFAULT_CONFIG.copy()
    # No config file — return default copy
    return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]) -> None:
    """
    Save the given config to config.json (creates CONFIG_DIR if missing).
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")


def get_library_paths() -> Dict[str, List[Path]]:
    """
    Get combined library paths:
    - Defaults (per OS)
    - Plus user overrides in config.json

    Always returns lists of Path for the keys: 'steam', 'epic', 'riot'
    """
    defaults = get_default_paths()
    config = load_config()

    def wrap(p):
        return [Path(p)] if p and not isinstance(p, list) else ( [Path(x) for x in p] if p else [] )

    libs: Dict[str, List[Path]] = {
        "steam": [],
        "epic": [],
        "riot": []
    }

    # start with defaults (if present)
    if defaults.get("steam"):
        libs["steam"].append(defaults["steam"])
    if defaults.get("epic"):
        libs["epic"].append(defaults["epic"])
    if defaults.get("riot"):
        libs["riot"].append(defaults["riot"])

    # then append user configured libraries
    for platform_name, paths in config.get("libraries", {}).items():
        if isinstance(paths, list):
            for p in paths:
                try:
                    libs.setdefault(platform_name, []).append(Path(p))
                except Exception:
                    pass
        elif paths:
            try:
                libs.setdefault(platform_name, []).append(Path(paths))
            except Exception:
                pass

    # Deduplicate while preserving order
    for k in list(libs.keys()):
        seen = set()
        out = []
        for p in libs[k]:
            try:
                rp = str(p.resolve())
            except Exception:
                rp = str(p)
            if rp not in seen:
                seen.add(rp)
                out.append(Path(rp))
        libs[k] = out

    return libs


# --- Extra helpers for UI / other modules ---


def get_settings(key: Optional[str] = None) -> Any:
    """
    Get a single setting (like 'steam_path', 'epic_path', 'riot_path') or the full config.
    """
    config = load_config()
    defaults = get_default_paths()

    if key == "steam_path":
        # return a string path (first entry)
        steam_list = config.get("libraries", {}).get("steam") or ([str(defaults["steam"])] if defaults.get("steam") else [])
        return steam_list[0] if steam_list else ""
    if key == "epic_path":
        epic_list = config.get("libraries", {}).get("epic") or ([str(defaults["epic"])] if defaults.get("epic") else [])
        return epic_list[0] if epic_list else ""
    if key == "riot_path":
        # return empty string on linux if not supported
        if defaults.get("riot"):
            riot_list = config.get("libraries", {}).get("riot") or [str(defaults["riot"])]
            return riot_list[0] if riot_list else ""
        return ""

    # return whole config dict
    return config


def update_setting(key: str, value: Any) -> None:
    """
    Update a single setting in the config and persist it.
    Supported keys:
      - steam_path, epic_path, riot_path  -> stored under config['libraries']
      - theme -> stored at top-level (value like 'system'/'light'/'dark'/'steam'/'epic')
      - autostart -> bool
      - favorites -> list[str] (replaces)
      - igdb_client_id / igdb_client_secret / igdb_access_token / igdb_expires_at
    """
    config = load_config()
    if "libraries" not in config:
        config["libraries"] = {}

    if key == "steam_path":
        config["libraries"]["steam"] = [value]
    elif key == "epic_path":
        config["libraries"]["epic"] = [value]
    elif key == "riot_path":
        config["libraries"]["riot"] = [value]
    elif key == "theme":
        config["theme"] = value
    elif key == "autostart":
        config["autostart"] = bool(value)
    elif key == "favorites":
        # expect iterable
        config["favorites"] = list(value) if value is not None else []
    elif key == "igdb_client_id":
        config.setdefault("igdb", {})["client_id"] = str(value)
    elif key == "igdb_client_secret":
        config.setdefault("igdb", {})["client_secret"] = str(value)
    elif key == "igdb_access_token":
        config.setdefault("igdb", {})["access_token"] = str(value)
    elif key == "igdb_expires_at":
        # store as int timestamp
        try:
            config.setdefault("igdb", {})["expires_at"] = int(value)
        except Exception:
            config.setdefault("igdb", {})["expires_at"] = 0
    else:
        # Generic fallback: write top-level key
        config[key] = value

    save_config(config)


# Ensure cache dir exists
CACHE_DIR.mkdir(parents=True, exist_ok=True)


# Favorites helpers
def get_favorites() -> List[str]:
    config = load_config()
    return list(config.get("favorites", []))


def add_favorite(game_key: str) -> None:
    config = load_config()
    favs = list(dict.fromkeys(config.get("favorites", []) or []))
    if game_key not in favs:
        favs.append(game_key)
    config["favorites"] = favs
    save_config(config)


def remove_favorite(game_key: str) -> None:
    config = load_config()
    favs = list(dict.fromkeys(config.get("favorites", []) or []))
    if game_key in favs:
        favs.remove(game_key)
    config["favorites"] = favs
    save_config(config)


def toggle_favorite(game_key: str) -> None:
    config = load_config()
    favs = set(config.get("favorites", []) or [])
    if game_key in favs:
        favs.remove(game_key)
    else:
        favs.add(game_key)
    config["favorites"] = list(favs)
    save_config(config)


# Autostart read helper (actual enable/disable should call common.autostart)
def is_autostart_enabled() -> bool:
    config = load_config()
    return bool(config.get("autostart", False))
