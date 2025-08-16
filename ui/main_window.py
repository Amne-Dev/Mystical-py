import subprocess
import multiprocessing as mp
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QListWidget,
    QListWidgetItem, QLabel, QComboBox, QHBoxLayout, QMessageBox, QMenu
)
from PySide6.QtGui import QAction

from backend.scanner import scan_libraries
from backend.models import GameEntry
from ui.game_list import GameItemWidget
from ui.settings_dialog import SettingsDialog
from common.favorites import get_favorites, add_favorite, remove_favorite, is_favorite
import os, sys

def open_install_folder(path):
    if sys.platform == "win32":
        os.startfile(path)  # Windows
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])  # macOS
    else:
        subprocess.Popen(["xdg-open", str(path)])  # Linux


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mystical")
        self.setGeometry(200, 200, 900, 600)

        self.all_games: list[GameEntry] = []
        self.current_filter = "All Games"

        # Menu
        menubar = self.menuBar()
        settings_menu = menubar.addMenu("Settings")
        open_settings = QAction("Preferences", self)
        open_settings.triggered.connect(self.open_settings_dialog)
        settings_menu.addAction(open_settings)

        # Central
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Top bar
        top_bar = QHBoxLayout()
        self.status_label = QLabel("Scanning libraries...", self)

        self.filter_box = QComboBox()
        self.filter_box.addItems([
            "All Games",
            "Installed Only",
            "Steam",
            "Epic",
            "Riot",
            "Favorites"
        ])
        self.filter_box.currentTextChanged.connect(self.apply_filter)

        top_bar.addWidget(self.status_label)
        top_bar.addStretch()
        top_bar.addWidget(QLabel("Filter:"))
        top_bar.addWidget(self.filter_box)
        layout.addLayout(top_bar)

        # Game list
        self.game_list = QListWidget()
        self.game_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.game_list.customContextMenuRequested.connect(self.open_context_menu)
        self.game_list.itemDoubleClicked.connect(self.launch_selected_game)
        layout.addWidget(self.game_list)

        # Start scan
        self.start_scan()

    def start_scan(self):
        self.queue = mp.Queue()
        self.process = mp.Process(target=scan_libraries, args=(self.queue,))
        self.process.start()

        self.timer = QTimer()
        self.timer.timeout.connect(self.check_results)
        self.timer.start(500)

    def check_results(self):
        if not self.queue.empty():
            games: list[GameEntry] = self.queue.get()
            self.all_games = games
            self.apply_filter()

            self.status_label.setText(f"Found {len(games)} games")
            self.timer.stop()
            self.process.terminate()

    def apply_filter(self):
        selected = self.filter_box.currentText()
        favs = get_favorites()

        self.game_list.clear()
        for game in self.all_games:
            visible = True

            if selected == "Installed Only":
                visible = game.installed
            elif selected in ["Steam", "Epic", "Riot"]:
                visible = game.platform.value.lower() == selected.lower()
            elif selected == "Favorites":
                visible = game.id in favs

            if visible:
                widget = GameItemWidget(game)
                item = QListWidgetItem(self.game_list)
                item.setSizeHint(widget.sizeHint())
                item.setData(Qt.UserRole, game)
                self.game_list.addItem(item)
                self.game_list.setItemWidget(item, widget)

    def open_context_menu(self, position):
        item = self.game_list.itemAt(position)
        if not item:
            return
        game: GameEntry = item.data(Qt.UserRole)

        menu = QMenu(self)

        play_action = QAction("Play", self)
        play_action.triggered.connect(lambda: self.launch_game(game))
        menu.addAction(play_action)

        if is_favorite(game.id):
            fav_action = QAction("Remove from Favorites", self)
            fav_action.triggered.connect(lambda: self.remove_from_favorites(game))
        else:
            fav_action = QAction("Add to Favorites", self)
            fav_action.triggered.connect(lambda: self.add_to_favorites(game))
        menu.addAction(fav_action)

        open_folder = QAction("Open Install Folder", self)
        open_folder.triggered.connect(lambda: open_install_folder(game.install_path))
        menu.addAction(open_folder)


        menu.exec(self.game_list.viewport().mapToGlobal(position))

    def launch_selected_game(self, item: QListWidgetItem):
        game: GameEntry = item.data(Qt.UserRole)
        self.launch_game(game)

    def launch_game(self, game: GameEntry):
        cmd = game.launch_command()
        if not cmd:
            QMessageBox.warning(self, "Launch Error", f"Cannot launch {game.name}")
            return
        try:
            subprocess.Popen(cmd)
        except Exception as e:
            QMessageBox.critical(self, "Launch Failed", f"Error launching {game.name}:\n{e}")

    def add_to_favorites(self, game: GameEntry):
        add_favorite(game.id)
        self.apply_filter()

    def remove_from_favorites(self, game: GameEntry):
        remove_favorite(game.id)
        self.apply_filter()

    def open_settings_dialog(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            # User saved settings → rescan libraries
            self.status_label.setText("Rescanning libraries...")
            self.start_scan()
