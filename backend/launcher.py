# launcher.py
import os
import platform
import subprocess
import webbrowser
import shutil
import json
from pathlib import Path
from typing import Any, Optional

# optional: read defaults from your settings module if available
try:
    from common.settings import get_default_paths
except Exception:
    # fallback: common location used by Epic on Windows
    def get_default_paths():
        return {"epic": Path("C:/ProgramData/Epic/EpicGamesLauncher/Data/Manifests")}


def _open_uri(uri: str) -> bool:
    """
    Open a protocol URI using the OS handler (steam://, com.epicgames.launcher://, etc).
    """
    system = platform.system().lower()
    try:
        if system == "windows":
            os.startfile(uri)
            return True
        elif system == "darwin":
            subprocess.Popen(["open", uri])
            return True
        else:
            opener = shutil.which("xdg-open") or shutil.which("gio") or shutil.which("gnome-open")
            if opener:
                subprocess.Popen([opener, uri])
                return True
            webbrowser.open(uri)
            return True
    except Exception as e:
        print(f"[launcher] Failed to open URI '{uri}': {e}")
        return False


def _try_launch_executable(path: Path) -> bool:
    """
    Launch an executable path (best-effort). Returns True on success.
    """
    try:
        if not path:
            return False
        p = Path(path)
        if not p.exists():
            print(f"[launcher] Executable not found: {p}")
            return False

        # On Windows prefer using ShellExecute via startfile for things with registered associations,
        # but direct Popen is fine for exe files.
        if platform.system().lower() == "windows":
            # Use Popen without shell for direct exe
            subprocess.Popen([str(p)])
        elif platform.system().lower() == "darwin":
            subprocess.Popen(["open", str(p)])
        else:
            opener = shutil.which("xdg-open") or shutil.which("gio") or shutil.which("gnome-open")
            if opener:
                subprocess.Popen([opener, str(p)])
            else:
                subprocess.Popen([str(p)])
        return True
    except Exception as e:
        print(f"[launcher] Failed to launch executable {path}: {e}")
        return False


def _find_epic_manifest_by_identifier(manifests_dir: Path, identifier: str) -> Optional[dict]:
    """
    Search the Epic manifests folder for a manifest matching `identifier`.
    identifier may be an app name, catalog id or part of display name.
    Returns the parsed manifest dict or None.
    """
    if not manifests_dir or not manifests_dir.exists():
        return None

    identifier = str(identifier).lower()

    # Epic manifest files sometimes have .item extension or .manifest or plain json.
    for p in manifests_dir.glob("*"):
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            # skip files that are not JSON
            continue

        # Typical keys that contain identity/paths:
        # "InstallLocation", "LaunchExecutable", "AppName", "DisplayName", "CatalogItemId"
        keys_to_check = ["AppName", "DisplayName", "CatalogItemId", "CatalogNamespace", "AppId", "InstallLocation"]
        for k in keys_to_check:
            v = data.get(k)
            if not v:
                continue
            # Some manifest fields are nested dicts or lists; stringify safely
            try:
                vs = str(v).lower()
            except Exception:
                continue
            if identifier in vs or vs in identifier:
                return data

        # Extra: check embedded launch info
        # e.g. data may contain "LaunchExecutable" or "Executables"
        # No explicit match — but consider "AppName" substring match already done
    return None


def launch_epic_game_windows(app_name: Optional[str] = None, app_id: Optional[str] = None) -> bool:
    """
    Windows-specific Epic launcher:
     1) Try to find the game's manifest and launch its executable (InstallLocation + LaunchExecutable).
     2) Try the Epic protocol URI: com.epicgames.launcher://apps/<id>?action=launch
     3) Fallback: launch EpicGamesLauncher application.
    """
    manifests_dir = None
    try:
        defaults = get_default_paths()
        # get_default_paths may give Path or string; handle both
        m = defaults.get("epic")
        manifests_dir = Path(m) if m else Path("C:/ProgramData/Epic/EpicGamesLauncher/Data/Manifests")
    except Exception:
        manifests_dir = Path("C:/ProgramData/Epic/EpicGamesLauncher/Data/Manifests")

    # Prefer searching by explicit app_id first then app_name
    search_keys = []
    if app_id:
        search_keys.append(str(app_id))
    if app_name:
        search_keys.append(str(app_name))

    # Try manifest-based launch
    for key in search_keys:
        manifest = _find_epic_manifest_by_identifier(manifests_dir, key)
        if manifest:
            # Determine install location and launch executable
            install = manifest.get("InstallLocation") or manifest.get("installationLocation") or manifest.get("installLocation")
            # LaunchExecutable may be relative to InstallLocation
            launch_exe = manifest.get("LaunchExecutable") or manifest.get("launchExecutable") or manifest.get("ExecutablePath") or manifest.get("executable")
            if not install:
                # Some manifests include "AppName" with a path; try to skip if missing
                print(f"[launcher] Found manifest but InstallLocation missing for '{key}'. Manifest keys: {list(manifest.keys())}")
            else:
                # Some LaunchExecutable entries include placeholders or extra args; handle common cases:
                try:
                    exe_path = Path(install) / Path(launch_exe) if launch_exe else None
                except Exception:
                    exe_path = None

                # If exe_path exists, launch it
                if exe_path and exe_path.exists():
                    return _try_launch_executable(exe_path)

                # Some manifests include an "Executables" array with "ExecutablePath"
                executables = manifest.get("Executables") or manifest.get("executables")
                if isinstance(executables, (list, tuple)) and executables:
                    for e in executables:
                        # each entry may be dict with "ExecutablePath" or a simple string
                        path_candidate = None
                        if isinstance(e, dict):
                            path_candidate = e.get("ExecutablePath") or e.get("executablePath") or e.get("Path") or e.get("path")
                        else:
                            path_candidate = e
                        if path_candidate:
                            try:
                                ep = Path(install) / Path(path_candidate)
                                if ep.exists():
                                    return _try_launch_executable(ep)
                            except Exception:
                                continue

            # If we found a manifest but couldn't launch its exe, still attempt protocol fallback below

    # Protocol URI fallback
    identifier = app_id or app_name
    if identifier:
        uri = f"com.epicgames.launcher://apps/{identifier}?action=launch"
        if _open_uri(uri):
            return True

    # As last resort, try launching EpicGamesLauncher app itself
    try:
        # common install locations
        possible = [
            Path(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")) / "Epic Games" / "Launcher" / "Portal" / "Binaries" / "Win64" / "EpicGamesLauncher.exe",
            Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")) / "Epic Games" / "Launcher" / "Portal" / "Binaries" / "Win64" / "EpicGamesLauncher.exe",
        ]
        for p in possible:
            if p.exists():
                subprocess.Popen([str(p)])
                return True

        # fallback: try the App Protocol without app id (open launcher)
        if _open_uri("com.epicgames.launcher://"):
            return True
    except Exception as e:
        print(f"[launcher] fallback to EpicGamesLauncher exe failed: {e}")

    print("[launcher] Unable to launch Epic game (Windows).")
    return False


# Exported cross-platform wrapper
def launch_epic_game(app_name: Optional[str] = None, app_id: Optional[str] = None) -> bool:
    system = platform.system().lower()
    if system == "linux":
        # Linux handled elsewhere (legendary)
        legendary = shutil.which("legendary")
        if legendary and (app_id or app_name):
            try:
                target = app_id or app_name
                subprocess.Popen([legendary, "launch", str(target)])
                return True
            except Exception as e:
                print(f"[launcher] legendary launch failed: {e}")
                # fallthrough to other attempts
        # try protocol URI as last resort
        if app_name or app_id:
            uri = f"com.epicgames.launcher://apps/{app_id or app_name}?action=launch"
            return _open_uri(uri)
        return False

    if system == "darwin":
        # macOS: try protocol then app open fallback
        if app_id or app_name:
            uri = f"com.epicgames.launcher://apps/{app_id or app_name}?action=launch"
            if _open_uri(uri):
                return True
        try:
            subprocess.Popen(["open", "-a", "Epic Games Launcher"])
            return True
        except Exception as e:
            print(f"[launcher] macOS Epic fallback failed: {e}")
            return False

    if system == "windows":
        return launch_epic_game_windows(app_name=app_name, app_id=app_id)

    # unknown platform fallback
    if app_name or app_id:
        uri = f"com.epicgames.launcher://apps/{app_id or app_name}?action=launch"
        return _open_uri(uri)
    return False


# Example generic wrapper for your GameEntry/dict used by UI
def launch_game(game: Any) -> bool:
    """
    Generic entrypoint for your UI. Accepts dict or object attributes.
    """
    def gget(obj, *keys):
        if isinstance(obj, dict):
            for k in keys:
                if k in obj and obj[k]:
                    return obj[k]
            return None
        else:
            for k in keys:
                if hasattr(obj, k) and getattr(obj, k):
                    return getattr(obj, k)
            return None

    platform_name = (gget(game, "platform") or "").lower()

    if platform_name == "epic":
        # try app_id first then app_name
        app_id = gget(game, "app_id", "id", "catalog_item_id")
        app_name = gget(game, "app_name", "name")
        return launch_epic_game(app_name=app_name, app_id=app_id)

    # other platforms can call into your existing implementations
    if platform_name == "steam":
        appid = gget(game, "appid", "id")
        if appid:
            return launch_steam_game(appid=str(appid))
        return False

    if platform_name == "riot":
        exe = gget(game, "executable", "exe_path", "path")
        if exe:
            return _try_launch_executable(Path(exe))
        return False

    # fallback generic
    exe = gget(game, "executable", "exe_path")
    if exe:
        return _try_launch_executable(Path(exe))
    install = gget(game, "install_path")
    if install:
        return _try_launch_executable(Path(install))
    print(f"[launcher] Unknown platform or missing launch info for: {gget(game, 'name','id')}")
    return False


# keep backward-compat small helper if your code calls the old names
def launch_steam_game(appid: str) -> bool:
    uri = f"steam://rungameid/{appid}"
    return _open_uri(uri)
