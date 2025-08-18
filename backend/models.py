# backend/models.py
from dataclasses import dataclass, field
from pathlib import Path
import platform as py_platform
from enum import Enum
import sys
from typing import Optional, Union, Dict, Any

# On Windows we’ll use winreg to detect Riot Client location
if sys.platform.startswith("win"):
    try:
        import winreg
    except ImportError:
        winreg = None


class Platform(Enum):
    STEAM = "Steam"
    EPIC = "Epic"
    RIOT = "Riot"


@dataclass
class GameEntry:
    id: str
    name: str
    platform: Union[str, Platform]
    installed: bool

    install_path: Optional[Union[Path, str]] = None

    # image_path and cover_path may be a Path or a str (downloaded path or raw string)
    image_path: Optional[Union[Path, str]] = None
    cover_path: Optional[Union[Path, str]] = None
    image_url: Optional[str] = None

    description: Optional[str] = None
    release_year: Optional[int] = None

    # flexible metadata container (IDs, app_name, other hints)
    extra: Dict[str, Any] = field(default_factory=dict)

    # optional executable (path to launcher, riot client, etc.)
    executable: Optional[Union[str, Path]] = None

    def _find_riot_client(self) -> Optional[Path]:
        """Try to locate RiotClientServices.exe (Windows)."""
        if not sys.platform.startswith("win") or not winreg:
            return None

        try:
            # Check both 64-bit and 32-bit registry hives
            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    key = winreg.OpenKey(
                        hive,
                        r"SOFTWARE\Riot Games, Inc\Riot Client",
                        0,
                        winreg.KEY_READ
                    )
                    value, _ = winreg.QueryValueEx(key, "Path")
                    winreg.CloseKey(key)
                    riot_path = Path(value) / "RiotClientServices.exe"
                    if riot_path.exists():
                        return riot_path
                except FileNotFoundError:
                    continue
        except Exception:
            pass

        # Fallback default path
        default_path = Path("C:/Riot Games/Riot Client/RiotClientServices.exe")
        return default_path if default_path.exists() else None

    def launch_command(self) -> Optional[list[str]]:
        """
        Returns the system command needed to launch this game.
        """
        system = py_platform.system().lower()

        if isinstance(self.platform, Platform):
            platform_value = self.platform.value.lower()
        else:
            platform_value = str(self.platform).lower()

        # ---- Steam ----
        if platform_value == "steam":
            return ["steam", f"steam://rungameid/{self.id}"]

        # ---- Epic ----
        if platform_value == "epic":
            # prefer using epic handler (platform-dependent)
            if system == "windows":
                # use cmd start to invoke URI on windows
                return ["cmd", "/c", f"start epicgames://launch/{self.id}"]
            return ["epicgames://launch", self.id]

        # ---- Riot ----
        if platform_value == "riot":
            exe = None
            if self.executable:
                exe = str(self.executable)
            elif self.extra.get("riot_client"):
                exe = str(self.extra["riot_client"])
            else:
                rc = self._find_riot_client()
                exe = str(rc) if rc else None

            if exe:
                gid = str(self.id).lower()
                if "league" in gid or "league_of_legends" in gid:
                    return [exe, "--launch-product=league_of_legends", "--launch-patchline=live"]
                elif "valorant" in gid:
                    return [exe, "--launch-product=valorant", "--launch-patchline=live"]
                elif "lor" in gid or "runeterra" in gid:
                    return [exe, "--launch-product=bacon", "--launch-patchline=live"]

            # fallback: try direct install path
            if self.install_path and Path(self.install_path).exists():
                return [str(self.install_path)]

        return None
