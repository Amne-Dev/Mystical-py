from PySide6.QtCore import QObject, Signal, Slot
from backend.steam_parser import get_steam_games
from backend.epic_parser import get_epic_games
from backend.riot_parser import scan_riot

class ScanWorker(QObject):
    progress = Signal(str)
    finished = Signal(list)

    @Slot()
    def run(self):
        all_games = []
        self.progress.emit("Scanning Steam...")
        all_games.extend(get_steam_games)
        self.progress.emit("Scanning Epic...")
        all_games.extend(get_epic_games)
        self.progress.emit("Scanning Riot...")
        all_games.extend(scan_riot)
        self.finished.emit(all_games)
