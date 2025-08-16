from dataclasses import dataclass
from pathlib import Path
import platform as py_platform
from enum import Enum
import sys

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
    platform: str | Platform
    installed: bool
    install_path: Path | None = None
    image_path: Path | None = None
    image_url: str | None = None
    description: str | None = None
    release_year: int | None = None

    def _find_riot_client(self) -> Path | None:
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

    def launch_command(self) -> list[str] | None:
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
            return ["epicgames://launch", self.id]

        # ---- Riot ----
        if platform_value == "riot":
            if system == "windows":
                riot_client = self._find_riot_client()
                if riot_client:
                    exe = str(riot_client)
                    game_id = self.id.lower()
                    if "league" in game_id:
                        return [exe, "--launch-product=league_of_legends", "--launch-patchline=live"]
                    elif "valorant" in game_id:
                        return [exe, "--launch-product=valorant", "--launch-patchline=live"]
                    elif "lor" in game_id or "runeterra" in game_id:
                        return [exe, "--launch-product=bacon", "--launch-patchline=live"]

            # On Linux/macOS fallback: try direct install_path
            if self.install_path and Path(self.install_path).exists():
                return [str(self.install_path)]

        return None
