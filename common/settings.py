import json
import platform
from pathlib import Path

CONFIG_DIR = Path.home() / ".mystical"
CONFIG_FILE = CONFIG_DIR / "config.json"
CACHE_DIR = CONFIG_DIR / "cache" / "images"

DEFAULT_CONFIG = {
    "libraries": {
        "steam": [],
        "epic": [],
        "riot": []
    },
    "theme": "system"  # NEW: system, dark, light
}


def get_default_paths() -> dict[str, Path | None]:
    """
    Return default Steam, Epic, and Riot paths depending on OS.
    Riot is only supported on Windows/macOS.
    """
    system = platform.system().lower()
    paths: dict[str, Path | None] = {}

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

    return paths


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


def get_library_paths() -> dict[str, list[Path]]:
    """
    Merge defaults with user config overrides.
    """
    defaults = get_default_paths()
    config = load_config()

    libs = {
        "steam": [defaults["steam"]] if defaults["steam"] else [],
        "epic": [defaults["epic"]] if defaults["epic"] else [],
        "riot": [defaults["riot"]] if defaults["riot"] else []
    }

    for platform_name, paths in config.get("libraries", {}).items():
        for p in paths:
            libs.setdefault(platform_name, []).append(Path(p))

    return libs


# --- Extra helpers for UI ---

def get_settings(key: str | None = None):

    config = load_config()
    defaults = get_default_paths()

    if key == "steam_path":
        return (config.get("libraries", {}).get("steam") or [str(defaults["steam"])])[0]
    if key == "epic_path":
        return (config.get("libraries", {}).get("epic") or [str(defaults["epic"])])[0]
    if key == "riot_path":
        if defaults["riot"]:  # only supported on Windows/macOS
            return (config.get("libraries", {}).get("riot") or [str(defaults["riot"])])[0]
        return ""  # Linux → return empty string

    return config



def update_setting(key: str, value):
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
        config["theme"] = value  # <-- save theme

    save_config(config)


# Ensure cache dir exists
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_favorites() -> list[str]:
    config = load_config()
    return config.get("favorites", [])


def toggle_favorite(game_name: str):
    config = load_config()
    favs = set(config.get("favorites", []))
    if game_name in favs:
        favs.remove(game_name)
    else:
        favs.add(game_name)
    config["favorites"] = list(favs)
    save_config(config)

