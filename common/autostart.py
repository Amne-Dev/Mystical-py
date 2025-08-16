# common/autostart.py
import os
import sys
import shutil
from pathlib import Path
from typing import Optional

def _is_windows() -> bool:
    return sys.platform.startswith("win")

def _is_linux() -> bool:
    return sys.platform.startswith("linux")

# --- Windows implementation (HKCU\Software\Microsoft\Windows\CurrentVersion\Run) ---
if _is_windows():
    try:
        import winreg
    except Exception:
        winreg = None


def _get_run_key_name() -> str:
    """Name used in registry / desktop file to identify Mystical autostart entry."""
    return "Mystical"


def _get_startup_command() -> str:
    """
    Build the command that will start the app on login.
    If frozen (packaged), sys.executable is the exe.
    If running from source, use: "<python-exe> <path/to/main.py>"
    """
    exe = sys.executable
    # if running as a frozen bundle (PyInstaller), sys.executable is the app exe
    if getattr(sys, "frozen", False):
        return f'"{exe}"'
    # otherwise use python + script
    # try to find the main script (assume main.py at repo root)
    script = Path(sys.argv[0]).resolve()
    # if script is a module spinner like '-m', fallback to package root
    return f'"{exe}" "{script}"'


def enable_autostart() -> bool:
    """
    Enable autostart for the current user.
    On Windows: write registry HKCU\...\Run
    On Linux: create ~/.config/autostart/mystical.desktop
    Returns True on success.
    """
    name = _get_run_key_name()
    cmd = _get_startup_command()

    if _is_windows():
        if not winreg:
            return False
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Run",
                                 0, winreg.KEY_WRITE)
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, cmd)
            winreg.CloseKey(key)
            return True
        except Exception:
            # try CreateKey if OpenKey failed
            try:
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                       r"Software\Microsoft\Windows\CurrentVersion\Run")
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, cmd)
                winreg.CloseKey(key)
                return True
            except Exception:
                return False

    if _is_linux():
        try:
            autostart_dir = Path.home() / ".config" / "autostart"
            autostart_dir.mkdir(parents=True, exist_ok=True)
            desktop_file = autostart_dir / "mystical.desktop"
            # Exec should be the filled command
            content = f"""[Desktop Entry]
Type=Application
Exec={cmd}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name=Mystical
Comment=Start Mystical on login
"""
            desktop_file.write_text(content)
            return True
        except Exception:
            return False

    # macOS / others: not implemented — return False
    return False


def disable_autostart() -> bool:
    """Remove autostart entry."""
    name = _get_run_key_name()
    if _is_windows():
        if not winreg:
            return False
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Run",
                                 0, winreg.KEY_ALL_ACCESS)
            try:
                winreg.DeleteValue(key, name)
            except OSError:
                # already not present
                pass
            winreg.CloseKey(key)
            return True
        except Exception:
            return False

    if _is_linux():
        try:
            desktop_file = Path.home() / ".config" / "autostart" / "mystical.desktop"
            if desktop_file.exists():
                desktop_file.unlink()
            return True
        except Exception:
            return False

    return False


def is_autostart_enabled() -> bool:
    """Return True if autostart is currently enabled for this user."""
    name = _get_run_key_name()
    if _is_windows():
        if not winreg:
            return False
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Run",
                                 0, winreg.KEY_READ)
            try:
                val, _type = winreg.QueryValueEx(key, name)
                winreg.CloseKey(key)
                return bool(val)
            except Exception:
                winreg.CloseKey(key)
                return False
        except Exception:
            return False

    if _is_linux():
        desktop_file = Path.home() / ".config" / "autostart" / "mystical.desktop"
        return desktop_file.exists()

    return False
