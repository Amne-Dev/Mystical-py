# launcher.py
"""
Robust launcher helpers for Steam, Epic and Riot games (cross-platform).
Drop this file into your project to replace the previous launcher.py.

Behavior summary:
 - Steam: try protocol (steam://), then steam.exe -applaunch <appid>, then cmd start fallback on Windows.
 - Epic: try to resolve manifest -> executable, then protocol (com.epicgames.launcher://...), then EpicGamesLauncher.exe.
 - Riot: try direct executable path if provided, else try to locate RiotClientServices via registry (Windows).
 - Generic `launch_game(...)` accepts dict-like or object and will pick platform-specific launchers.
Returns True when a launch attempt was made successfully, False otherwise.
"""

from __future__ import annotations
import os
import platform
import subprocess
import webbrowser
import shutil
import json
from pathlib import Path
from typing import Any, Optional, Dict

# optional settings helper to get manifest default paths; keep fallback values if import fails
try:
    from common.settings import get_default_paths
except Exception:
    def get_default_paths() -> Dict[str, Path]:
        return {"epic": Path("C:/ProgramData/Epic/EpicGamesLauncher/Data/Manifests"),
                "steam": Path("C:/Program Files (x86)/Steam")}

# optional winreg (Windows only)
try:
    import winreg  # type: ignore
except Exception:
    winreg = None


def _open_uri(uri: str) -> bool:
    """Open a protocol/uri using OS handler (Windows: os.startfile is preferred)."""
    system = platform.system().lower()
    try:
        if system == "windows":
            # os.startfile uses the registered handler for the URI
            os.startfile(uri)
            return True
        if system == "darwin":
            subprocess.Popen(["open", uri])
            return True
        opener = shutil.which("xdg-open") or shutil.which("gio") or shutil.which("gnome-open")
        if opener:
            subprocess.Popen([opener, uri])
            return True
        webbrowser.open(uri)
        return True
    except Exception as e:
        print(f"[launcher] _open_uri failed for {uri}: {e}")
        return False


def _try_launch_executable(path: Path) -> bool:
    """Launch an executable path (best-effort). Returns True on success."""
    try:
        if not path:
            return False
        p = Path(path)
        if not p.exists():
            print(f"[launcher] Executable not found: {p}")
            return False

        system = platform.system().lower()
        if system == "windows":
            try:
                os.startfile(str(p))
                return True
            except Exception:
                subprocess.Popen([str(p)])
                return True
        elif system == "darwin":
            subprocess.Popen(["open", str(p)])
            return True
        else:
            opener = shutil.which("xdg-open") or shutil.which("gio") or shutil.which("gnome-open")
            if opener:
                subprocess.Popen([opener, str(p)])
            else:
                subprocess.Popen([str(p)])
            return True
    except Exception as e:
        print(f"[launcher] _try_launch_executable failed for {path}: {e}")
        return False


# -------------------------
# Steam helpers
# -------------------------
def _find_steam_exe() -> Optional[Path]:
    """Locate steam executable on the current system (Windows tries registry + common folders)."""
    system = platform.system().lower()
    if system != "windows":
        bin_path = shutil.which("steam")
        return Path(bin_path) if bin_path else None

    # Windows: try registry entries
    if winreg:
        try:
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    key = winreg.OpenKey(hive, r"SOFTWARE\Valve\Steam")
                    try:
                        val, _ = winreg.QueryValueEx(key, "SteamExe")
                    except Exception:
                        try:
                            val, _ = winreg.QueryValueEx(key, "SteamPath")
                        except Exception:
                            val = None
                    winreg.CloseKey(key)
                    if val:
                        p = Path(val)
                        if p.exists():
                            if p.is_dir():
                                candidate = p / "steam.exe"
                                if candidate.exists():
                                    return candidate
                            return p
                except FileNotFoundError:
                    continue
                except Exception:
                    continue
        except Exception:
            pass

    # Common possible locations
    for base in (os.environ.get("PROGRAMFILES(X86)"), os.environ.get("PROGRAMFILES")):
        if base:
            candidate = Path(base) / "Steam" / "steam.exe"
            if candidate.exists():
                return candidate
    return None


def launch_steam_game(appid: str) -> bool:
    """Launch a Steam game by appid. Tries protocol, steam.exe and cmd start fallback."""
    if not appid:
        print("[launcher] launch_steam_game: no appid provided")
        return False

    uri = f"steam://rungameid/{appid}"
    system = platform.system().lower()

    # 1) Try protocol handler first
    try:
        if _open_uri(uri):
            print(f"[launcher] opened steam protocol for {appid}")
            return True
    except Exception as e:
        print(f"[launcher] steam protocol open failed: {e}")

    # 2) Try steam.exe -applaunch
    steam_exe = _find_steam_exe()
    if steam_exe:
        try:
            subprocess.Popen([str(steam_exe), "-applaunch", str(appid)])
            print(f"[launcher] launched steam.exe -applaunch using: {steam_exe}")
            return True
        except FileNotFoundError as e:
            print(f"[launcher] steam exe not found while launching: {e}")
        except Exception as e:
            print(f"[launcher] error launching steam.exe: {e}")

    # 3) Windows final fallback: cmd start which should use the protocol handler
    if system == "windows":
        try:
            subprocess.Popen(["cmd", "/c", "start", "", uri], shell=False)
            print("[launcher] used cmd start fallback for steam")
            return True
        except Exception as e:
            print(f"[launcher] cmd start fallback failed: {e}")

    print(f"[launcher] Unable to launch Steam game {appid}")
    return False


# -------------------------
# Epic helpers
# -------------------------
def _find_epic_manifests_dir() -> Optional[Path]:
    defaults = get_default_paths()
    m = defaults.get("epic")
    try:
        return Path(m) if m else None
    except Exception:
        return None


def _find_epic_manifest_by_identifier(manifests_dir: Path, identifier: str) -> Optional[dict]:
    """
    Search the Epic manifests folder for a manifest matching the identifier
    (app id, catalog id, app name substring).
    Returns parsed manifest dict with an extra key "_manifest_file" (path) if found.
    """
    if not manifests_dir or not manifests_dir.exists():
        return None
    identifier = str(identifier).lower()
    for p in manifests_dir.glob("*"):
        if not p.is_file():
            continue
        try:
            txt = p.read_text(encoding="utf-8")
            data = json.loads(txt)
        except Exception:
            # skip non-json files
            continue

        # keys that commonly identify the game
        keys_to_check = ["AppName", "DisplayName", "CatalogItemId", "CatalogNamespace", "AppId", "InstallLocation", "InstallationName"]
        found = False
        for k in keys_to_check:
            v = data.get(k)
            if not v:
                continue
            try:
                vs = str(v).lower()
            except Exception:
                continue
            if identifier in vs or vs in identifier:
                found = True
                break
        if found:
            data["_manifest_file"] = str(p)
            return data

        # last-resort raw text search
        if identifier in txt.lower():
            try:
                data = json.loads(txt)
                data["_manifest_file"] = str(p)
                return data
            except Exception:
                # return minimal info
                return {"_manifest_file": str(p)}
    return None


def _resolve_executable_from_manifest(manifest: dict) -> Optional[Path]:
    """Try to resolve an executable path from an Epic manifest dict."""
    install = manifest.get("InstallLocation") or manifest.get("installationLocation") or manifest.get("InstallPath")
    launch_exe = manifest.get("LaunchExecutable") or manifest.get("LaunchCommand") or manifest.get("ExecutablePath") or manifest.get("Executable")
    executables = manifest.get("Executables") or manifest.get("executables")

    # Prefer InstallLocation + LaunchExecutable
    if install and launch_exe:
        try:
            candidate = Path(install) / Path(str(launch_exe))
            if candidate.exists():
                return candidate
            # maybe launch_exe is already an absolute path
            alt = Path(str(launch_exe))
            if alt.exists():
                return alt
        except Exception:
            pass

    # Check executables array
    if isinstance(executables, (list, tuple)):
        for e in executables:
            path_candidate = None
            if isinstance(e, dict):
                path_candidate = e.get("ExecutablePath") or e.get("executablePath") or e.get("Path") or e.get("path")
            else:
                path_candidate = e
            if not path_candidate:
                continue
            try:
                if install:
                    ep = Path(install) / Path(str(path_candidate))
                    if ep.exists():
                        return ep
                ep2 = Path(str(path_candidate))
                if ep2.exists():
                    return ep2
            except Exception:
                continue

    # last-resort keys that might include absolute path
    for k in ("LaunchExecutableFullPath", "Executable", "ExecutablePath"):
        v = manifest.get(k)
        if v:
            try:
                p = Path(v)
                if p.exists():
                    return p
            except Exception:
                pass

    return None


def _find_epic_launcher_exe_windows() -> Optional[Path]:
    possible = [
        Path(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")) / "Epic Games" / "Launcher" / "Portal" / "Binaries" / "Win64" / "EpicGamesLauncher.exe",
        Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")) / "Epic Games" / "Launcher" / "Portal" / "Binaries" / "Win64" / "EpicGamesLauncher.exe",
    ]
    for p in possible:
        if p.exists():
            return p
    return None


def launch_epic_game_windows(app_name: Optional[str] = None, app_id: Optional[str] = None) -> bool:
    manifests_dir = _find_epic_manifests_dir() or Path("C:/ProgramData/Epic/EpicGamesLauncher/Data/Manifests")
    search_keys = []
    if app_id:
        search_keys.append(str(app_id))
    if app_name:
        search_keys.append(str(app_name))

    for key in search_keys:
        manifest = _find_epic_manifest_by_identifier(manifests_dir, key)
        if manifest:
            print(f"[launcher] matched Epic manifest: {manifest.get('_manifest_file')}")
            exe = _resolve_executable_from_manifest(manifest)
            if exe:
                print(f"[launcher] resolved executable from manifest: {exe}")
                if _try_launch_executable(exe):
                    return True
            else:
                print(f"[launcher] manifest has no resolved executable (manifest keys: {list(manifest.keys())})")

    # Try protocol URI (may bring Microsoft Store prompt if not registered)
    identifier = app_id or app_name
    if identifier:
        uri = f"com.epicgames.launcher://apps/{identifier}?action=launch"
        if _open_uri(uri):
            print(f"[launcher] opened epic protocol for {identifier}")
            return True

    # Try launching Epic launcher itself
    launcher_exe = _find_epic_launcher_exe_windows()
    if launcher_exe and _try_launch_executable(launcher_exe):
        print("[launcher] launched EpicGamesLauncher.exe as fallback")
        return True

    print("[launcher] Unable to launch Epic game (Windows): manifest/protocol/launcher not usable.")
    return False


def launch_epic_game(app_name: Optional[str] = None, app_id: Optional[str] = None) -> bool:
    system = platform.system().lower()
    if system == "linux":
        legendary = shutil.which("legendary")
        if legendary and (app_id or app_name):
            try:
                subprocess.Popen([legendary, "launch", str(app_id or app_name)])
                return True
            except Exception as e:
                print(f"[launcher] legendary failed: {e}")
        if app_id or app_name:
            uri = f"com.epicgames.launcher://apps/{app_id or app_name}?action=launch"
            return _open_uri(uri)
        return False

    if system == "darwin":
        if app_id or app_name:
            uri = f"com.epicgames.launcher://apps/{app_id or app_name}?action=launch"
            if _open_uri(uri):
                return True
        try:
            subprocess.Popen(["open", "-a", "Epic Games Launcher"])
            return True
        except Exception as e:
            print(f"[launcher] mac fallback failed: {e}")
            return False

    if system == "windows":
        return launch_epic_game_windows(app_name=app_name, app_id=app_id)

    if app_id or app_name:
        uri = f"com.epicgames.launcher://apps/{app_id or app_name}?action=launch"
        return _open_uri(uri)
    return False


# -------------------------
# Riot helpers
# -------------------------
def _find_riot_client_exe() -> Optional[Path]:
    """Try to locate RiotClientServices executable on Windows via registry or common paths."""
    if platform.system().lower() != "windows":
        # On macOS the location may be /Applications/... but most users are on Windows here.
        # try common mac default:
        possible_mac = [
            Path("/Applications/Riot Client.app/Contents/MacOS/RiotClientServices"),
            Path("/Applications/RiotClientServices.app/Contents/MacOS/RiotClientServices"),
        ]
        for p in possible_mac:
            if p.exists():
                return p
        return None

    if not winreg:
        return None

    try:
        # common Riot registry locations — try a few likely keys
        hives = (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER)
        for hive in hives:
            try:
                key = winreg.OpenKey(hive, r"SOFTWARE\Riot Games, Inc\Riot Client")
                try:
                    val, _ = winreg.QueryValueEx(key, "Path")
                except Exception:
                    val = None
                winreg.CloseKey(key)
                if val:
                    candidate = Path(val) / "RiotClientServices.exe"
                    if candidate.exists():
                        return candidate
            except FileNotFoundError:
                continue
            except Exception:
                continue
    except Exception:
        pass

    # fallback common install locations
    possible = [
        Path("C:/Riot Games/Riot Client/RiotClientServices.exe"),
        Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")) / "Riot Games" / "Riot Client" / "RiotClientServices.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")) / "Riot Games" / "Riot Client" / "RiotClientServices.exe",
    ]
    for p in possible:
        if p.exists():
            return p
    return None


def launch_riot_game(exe_path: Optional[str] = None) -> bool:
    """
    Launch a Riot title:
     - If exe_path provided, attempt direct launch
     - Else attempt to find RiotClientServices and use it (arguments differ per product)
    """
    if exe_path:
        try:
            return _try_launch_executable(Path(exe_path))
        except Exception:
            pass

    client = _find_riot_client_exe()
    if not client:
        print("[launcher] Riot client exe not found")
        return False

    # We can't reliably pass product launch args for every install; best-effort:
    # If the client is present, launching it normally will open the client.
    # For more deterministic product launching you'd need RiotClientServices command-line options per product.
    return _try_launch_executable(client)


# -------------------------
# Generic wrapper
# -------------------------
def launch_game(game: Any) -> bool:
    """
    Generic entrypoint used by the UI. Accepts dict or object attributes.
    Looks for fields: platform, id/appid/app_id, app_name/name, executable/exe_path, install_path.
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
        app_id = gget(game, "app_id", "id", "catalog_item_id")
        app_name = gget(game, "app_name", "name")
        return launch_epic_game(app_name=app_name, app_id=app_id)

    if platform_name == "steam":
        appid = gget(game, "appid", "id")
        if appid:
            return launch_steam_game(str(appid))
        # fallback try install_path/executable
        exe = gget(game, "executable", "exe_path", "launch_exe")
        if exe:
            return _try_launch_executable(Path(exe))
        return False

    if platform_name == "riot":
        exe = gget(game, "executable", "exe_path", "path")
        if exe:
            return _try_launch_executable(Path(exe))
        return launch_riot_game()

    # generic fallback: try executable or install path
    exe = gget(game, "executable", "exe_path")
    if exe:
        return _try_launch_executable(Path(exe))
    install = gget(game, "install_path")
    if install:
        return _try_launch_executable(Path(install))
    print(f"[launcher] Unknown platform or missing launch info for: {gget(game, 'name','id')}")
    return False


# Backwards-compatible helper
def launch_steam_game_uri(appid: str) -> bool:
    return launch_steam_game(appid)
