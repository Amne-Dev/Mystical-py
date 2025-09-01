# launcher.py
"""
Robust launcher helpers for Steam, Epic and Riot games (cross-platform).

Behavior summary:
 - Steam: try protocol (steam://), steam.exe -applaunch, then generic open fallback.
 - Epic (Windows): try manifest->executable; if no executable, open strict protocol URI via ShellExecuteW
    (uses ShellExecuteW only for the final protocol open — no os.startfile or cmd fallback for Epic protocol).
 - Epic (non-Windows): use generic URI opener (may use system handlers).
 - Riot: try direct exe path if provided, else try to locate RiotClientServices via registry (Windows).
 - Generic launch_game(...) accepts dict or object with fields the UI provides.
"""

from __future__ import annotations
import os
import platform
import subprocess
import shutil
import ctypes
import json
import webbrowser
from pathlib import Path
from typing import Any, Optional, Dict

# Project settings helper (to find manifests / steam path). Provide fallback if import fails.
try:
    from common.settings import get_default_paths
except Exception:
    def get_default_paths() -> Dict[str, Path]:
        return {
            "epic": Path("C:/ProgramData/Epic/EpicGamesLauncher/Data/Manifests"),
            "steam": Path("C:/Program Files (x86)/Steam"),
            "riot": None
        }

# Optional Windows registry helper
try:
    import winreg  # type: ignore
except Exception:
    winreg = None


# -------------------------
# Debug helpers
# -------------------------
def _debug(msg: str):
    """Printable debug helper used throughout the module."""
    try:
        print(f"[launcher.debug] {msg}")
    except Exception:
        # avoid crashing if printing fails
        pass


def _diag(msg: str):
    """Short diagnostic messages used for manifest/executable steps."""
    try:
        print(f"[launcher.diag] {msg}")
    except Exception:
        pass


# -------------------------
# Generic URI opener
# -------------------------
def _open_uri_generic(uri: str) -> bool:
    """
    Generic opener that attempts to open a URI using the best available method
    for the current platform. This is used for non-strict Epic cases.
    """
    system = platform.system().lower()
    _debug(f"_open_uri_generic: trying to open URI: {uri} (platform={system})")
    try:
        if system == "windows":
            # try ShellExecuteW first (wide char)
            try:
                res = ctypes.windll.shell32.ShellExecuteW(None, "open", uri, None, None, 1)
                _debug(f"_open_uri_generic: ShellExecuteW returned {res}")
                try:
                    if int(res) > 32:
                        return True
                except Exception:
                    pass
            except Exception as e:
                _debug(f"_open_uri_generic: ShellExecuteW failed: {e}")

            # fallback to os.startfile
            try:
                os.startfile(uri)
                _debug("_open_uri_generic: os.startfile succeeded")
                return True
            except Exception as e:
                _debug(f"_open_uri_generic: os.startfile failed: {e}")

            # fallback to "cmd start" as last resort
            try:
                subprocess.Popen(["cmd", "/c", "start", "", uri], shell=False)
                _debug("_open_uri_generic: cmd start invoked")
                return True
            except Exception as e:
                _debug(f"_open_uri_generic: cmd start failed: {e}")

            # use webbrowser as final fallback
            try:
                webbrowser.open(uri)
                _debug("_open_uri_generic: webbrowser.open called")
                return True
            except Exception as e:
                _debug(f"_open_uri_generic: webbrowser.open failed: {e}")
                return False

        elif system == "darwin":
            try:
                subprocess.Popen(["open", uri])
                _debug("_open_uri_generic: open succeeded on macOS")
                return True
            except Exception as e:
                _debug(f"_open_uri_generic: open failed: {e}")
                return False

        else:
            opener = shutil.which("xdg-open") or shutil.which("gio") or shutil.which("gnome-open")
            if opener:
                try:
                    subprocess.Popen([opener, uri])
                    _debug(f"_open_uri_generic: used {opener}")
                    return True
                except Exception as e:
                    _debug(f"_open_uri_generic: {opener} failed: {e}")
            try:
                webbrowser.open(uri)
                _debug("_open_uri_generic: webbrowser open called on linux")
                return True
            except Exception as e:
                _debug(f"_open_uri_generic: webbrowser.open failed: {e}")
                return False
    except Exception as e:
        _debug(f"_open_uri_generic: unexpected error: {e}")
        return False


def _open_uri_epic_strict_windows(uri: str) -> bool:
    """
    Strict opener for Epic protocol on Windows — uses ShellExecuteW only.
    Returns True if ShellExecuteW indicates success (>32), False otherwise.
    """
    system = platform.system().lower()
    _debug(f"_open_uri_epic_strict_windows: will attempt to open -> {uri}")
    if system != "windows":
        _debug("_open_uri_epic_strict_windows: platform is not Windows")
        return False

    try:
        res = ctypes.windll.shell32.ShellExecuteW(None, "open", str(uri), None, None, 1)
        _debug(f"_open_uri_epic_strict_windows: ShellExecuteW returned {res}")
        try:
            if int(res) > 32:
                _debug("_open_uri_epic_strict_windows: ShellExecuteW indicates success (>32)")
                return True
            else:
                _debug("_open_uri_epic_strict_windows: ShellExecuteW indicates failure (<=32)")
                return False
        except Exception:
            _debug(f"_open_uri_epic_strict_windows: ShellExecuteW returned non-int {res}")
            return False
    except Exception as e:
        _debug(f"_open_uri_epic_strict_windows: ShellExecuteW call failed: {e}")
        return False


# -------------------------
# Steam helpers
# -------------------------
def _find_steam_exe() -> Optional[Path]:
    """Attempt to find steam.exe on the system (Windows registry or common locations)."""
    system = platform.system().lower()
    if system != "windows":
        bin_path = shutil.which("steam")
        return Path(bin_path) if bin_path else None

    # Windows: try registry
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

    for base in (os.environ.get("PROGRAMFILES(X86)"), os.environ.get("PROGRAMFILES")):
        if base:
            candidate = Path(base) / "Steam" / "steam.exe"
            if candidate.exists():
                return candidate
    return None


def launch_steam_game(appid: str) -> bool:
    """Launch a Steam game by AppID."""
    if not appid:
        _debug("launch_steam_game: no appid provided")
        return False

    uri = f"steam://rungameid/{appid}"
    _debug(f"launch_steam_game: trying URI {uri}")

    # try ShellExecuteW on Windows
    if platform.system().lower() == "windows":
        try:
            res = ctypes.windll.shell32.ShellExecuteW(None, "open", uri, None, None, 1)
            _debug(f"launch_steam_game: ShellExecuteW returned {res}")
            if isinstance(res, int) and res > 32:
                _debug("launch_steam_game: protocol handler opened")
                return True
        except Exception as e:
            _debug(f"launch_steam_game: ShellExecuteW failed: {e}")

    # try steam.exe -applaunch
    steam_exe = _find_steam_exe()
    if steam_exe:
        try:
            _debug(f"launch_steam_game: attempting steam.exe -applaunch via {steam_exe}")
            subprocess.Popen([str(steam_exe), "-applaunch", str(appid)])
            return True
        except Exception as e:
            _debug(f"launch_steam_game: steam.exe launch failed: {e}")

    # fallback to generic opener
    _debug("launch_steam_game: falling back to generic URI open")
    return _open_uri_generic(uri)


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
    """Find and parse an Epic manifest that matches identifier (app id, display name, etc.)."""
    if not manifests_dir or not manifests_dir.exists():
        return None
    identifier = str(identifier).lower()
    for p in manifests_dir.glob("*"):
        if not p.is_file():
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
            data = json.loads(txt)
        except Exception:
            # not JSON => skip except raw search below
            data = None

        if data:
            keys_to_check = ["AppName", "DisplayName", "CatalogItemId", "CatalogNamespace", "AppId", "InstallationName", "InstallLocation"]
            for k in keys_to_check:
                v = data.get(k)
                if not v:
                    continue
                try:
                    vs = str(v).lower()
                except Exception:
                    continue
                if identifier in vs or vs in identifier:
                    data["_manifest_file"] = str(p)
                    return data

        # raw text fallback
        try:
            if identifier in p.read_text(encoding="utf-8", errors="ignore").lower():
                # attempt to parse, but if parsing fails return minimal info with file path
                try:
                    d2 = json.loads(txt) if txt else {}
                    d2["_manifest_file"] = str(p)
                    return d2
                except Exception:
                    return {"_manifest_file": str(p)}
        except Exception:
            continue
    return None


def _resolve_executable_from_manifest(manifest: dict) -> Optional[Path]:
    """
    Given a parsed Epic manifest, try to resolve the actual game executable path.
    It checks InstallLocation + LaunchExecutable, Executables array, and several absolute keys.
    """
    install = manifest.get("InstallLocation") or manifest.get("installationLocation") or manifest.get("InstallPath") or manifest.get("installationPath")
    launch_exe = manifest.get("LaunchExecutable") or manifest.get("LaunchCommand") or manifest.get("ExecutablePath") or manifest.get("Executable")
    executables = manifest.get("Executables") or manifest.get("executables")

    if install and launch_exe:
        try:
            candidate = Path(install) / Path(str(launch_exe))
            _diag(f"_resolve_executable_from_manifest: checking candidate {candidate}")
            if candidate.exists():
                return candidate
            alt = Path(str(launch_exe))
            if alt.exists():
                return alt
        except Exception:
            pass

    if isinstance(executables, (list, tuple)):
        for e in executables:
            candidate_path = None
            if isinstance(e, dict):
                candidate_path = e.get("ExecutablePath") or e.get("executablePath") or e.get("Path") or e.get("path")
            else:
                candidate_path = e
            if candidate_path:
                try:
                    if install:
                        p = Path(install) / Path(str(candidate_path))
                        _diag(f"_resolve_executable_from_manifest: checking executables entry {p}")
                        if p.exists():
                            return p
                    p2 = Path(str(candidate_path))
                    if p2.exists():
                        return p2
                except Exception:
                    continue

    # last-resort absolute keys
    for k in ("LaunchExecutableFullPath", "Executable", "ExecutablePath"):
        v = manifest.get(k)
        if v:
            try:
                p = Path(v)
                _diag(f"_resolve_executable_from_manifest: checking absolute key {k} -> {p}")
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
    """
    Windows Epic launcher behavior (strict):
      1) Try to resolve game executable from manifests and run it (preferred)
      2) Else: open EXACT protocol URI using ShellExecuteW only:
         com.epicgames.launcher://apps/{AppID}?action=launch&silent=true
    """
    manifests_dir = _find_epic_manifests_dir() or Path("C:/ProgramData/Epic/EpicGamesLauncher/Data/Manifests")
    search_keys = []
    if app_id:
        search_keys.append(str(app_id))
    if app_name:
        search_keys.append(str(app_name))

    for key in search_keys:
        manifest = _find_epic_manifest_by_identifier(manifests_dir, key)
        if manifest:
            _debug(f"launch_epic_game_windows: matched manifest: {manifest.get('_manifest_file')}")
            exe = _resolve_executable_from_manifest(manifest)
            if exe:
                _debug(f"launch_epic_game_windows: resolved executable: {exe}")
                if _try_launch_executable(exe):
                    _debug("launch_epic_game_windows: game executable launched from manifest")
                    return True
                else:
                    _debug("launch_epic_game_windows: failed to launch executable from manifest")

    # Build exact protocol URI (do NOT percent-encode or modify the AppID)
    identifier = app_id or app_name
    if not identifier:
        _debug("launch_epic_game_windows: no identifier provided")
        return False

    uri = f"com.epicgames.launcher://apps/{identifier}?action=launch&silent=true"
    _debug(f"launch_epic_game_windows: attempting strict ShellExecuteW open of URI: {uri}")

    ok = _open_uri_epic_strict_windows(uri)
    _debug(f"launch_epic_game_windows: strict ShellExecuteW result = {ok}")
    return ok


def launch_epic_game(app_name: Optional[str] = None, app_id: Optional[str] = None) -> bool:
    """Cross-platform wrapper for Epic launches."""
    system = platform.system().lower()
    if system == "linux":
        legendary = shutil.which("legendary")
        if legendary and (app_id or app_name):
            try:
                subprocess.Popen([legendary, "launch", str(app_id or app_name)])
                return True
            except Exception as e:
                _debug(f"launch_epic_game: legendary launch failed: {e}")
        if app_id or app_name:
            uri = f"com.epicgames.launcher://apps/{app_id or app_name}?action=launch&silent=true"
            return _open_uri_generic(uri)
        return False

    if system == "darwin":
        if app_id or app_name:
            uri = f"com.epicgames.launcher://apps/{app_id or app_name}?action=launch&silent=true"
            return _open_uri_generic(uri)
        return False

    if system == "windows":
        return launch_epic_game_windows(app_name=app_name, app_id=app_id)

    # fallback for unknown OS
    if app_id or app_name:
        uri = f"com.epicgames.launcher://apps/{app_id or app_name}?action=launch&silent=true"
        return _open_uri_generic(uri)
    return False


# -------------------------
# Executable helper
# -------------------------
def _try_launch_executable(path: Path) -> bool:
    """Try to launch an executable path. Use ShellExecuteW on Windows when possible."""
    try:
        if not path:
            return False
        p = Path(path)
        if not p.exists():
            _debug(f"_try_launch_executable: executable not found: {p}")
            return False

        system = platform.system().lower()
        _debug(f"_try_launch_executable: launching {p} on {system}")
        if system == "windows":
            try:
                res = ctypes.windll.shell32.ShellExecuteW(None, "open", str(p), None, None, 1)
                _debug(f"_try_launch_executable: ShellExecuteW returned {res}")
                try:
                    if isinstance(res, int) and res > 32:
                        return True
                except Exception:
                    pass
            except Exception as e:
                _debug(f"_try_launch_executable: ShellExecuteW failed: {e}")

            try:
                subprocess.Popen([str(p)])
                return True
            except Exception as e:
                _debug(f"_try_launch_executable: subprocess failed: {e}")
                return False

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
        _debug(f"_try_launch_executable: unexpected error {e}")
        return False


# -------------------------
# Riot helpers
# -------------------------
def _find_riot_client_exe() -> Optional[Path]:
    """Try to find RiotClientServices.exe on Windows, or common mac paths for macOS."""
    if platform.system().lower() != "windows":
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
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
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

    # fallback common locations
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
    if exe_path:
        return _try_launch_executable(Path(exe_path))
    client = _find_riot_client_exe()
    if client:
        return _try_launch_executable(client)
    _debug("launch_riot_game: riot client not found")
    return False


# -------------------------
# Generic wrapper
# -------------------------
def launch_game(game: Any) -> bool:
    """
    Generic UI-facing entrypoint.

    Accepts dict-like or object. Looks for keys/attrs:
      - platform (steam|epic|riot)
      - id, appid, app_id (Epic/Steam)
      - app_name, name
      - executable, exe_path, launch_exe, install_path
    """
    def gget(obj, *keys):
        if isinstance(obj, dict):
            for k in keys:
                v = obj.get(k)
                if v:
                    return v
            return None
        else:
            for k in keys:
                if hasattr(obj, k) and getattr(obj, k):
                    return getattr(obj, k)
            return None

    platform_name = (gget(game, "platform") or "").lower()
    _debug(f"launch_game: platform detected -> {platform_name}")

    if platform_name == "epic":
        app_id = gget(game, "app_id", "id", "catalog_item_id")
        app_name = gget(game, "app_name", "name")
        return launch_epic_game(app_name=app_name, app_id=app_id)

    if platform_name == "steam":
        appid = gget(game, "appid", "id")
        if appid:
            return launch_steam_game(str(appid))
        exe = gget(game, "executable", "exe_path", "launch_exe")
        if exe:
            return _try_launch_executable(Path(exe))
        install = gget(game, "install_path")
        if install:
            return _try_launch_executable(Path(install))
        return False

    if platform_name == "riot":
        exe = gget(game, "executable", "exe_path", "path")
        if exe:
            return _try_launch_executable(Path(exe))
        return launch_riot_game()

    # fallback generic
    exe = gget(game, "executable", "exe_path")
    if exe:
        return _try_launch_executable(Path(exe))
    install = gget(game, "install_path")
    if install:
        return _try_launch_executable(Path(install))

    _debug(f"launch_game: unknown platform or missing launch info for {gget(game, 'name','id')}")
    return False
