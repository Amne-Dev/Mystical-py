# ui/main_window.py
import shutil
import subprocess
import multiprocessing as mp
import os
import sys
from pathlib import Path
from shutil import rmtree
import webbrowser

from PySide6.QtCore import QTimer, Qt, QSize
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QComboBox, QHBoxLayout, QMessageBox, QMenu,
    QPushButton, QScrollArea, QGridLayout, QFrame, QApplication, QSpacerItem, QSizePolicy
)
from PySide6.QtGui import QAction, QIcon, QPalette

from backend.scanner import scan_libraries
from backend.models import GameEntry
from ui.game_item import GameItemWidget, CACHE_DIR, get_cached_cover_path
from ui.settings_dialog import SettingsDialog
from common.favorites import get_favorites, add_favorite, remove_favorite, is_favorite


def open_install_folder(path):
    """Open folder using platform-appropriate method. Accepts Path or str."""
    try:
        if not path:
            return
        p = str(path)
        if sys.platform.startswith("win"):
            os.startfile(p)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", p])
        else:
            opener = shutil.which("xdg-open") or shutil.which("gio") or shutil.which("xdg-open")
            if opener:
                subprocess.Popen([opener, p])
            else:
                subprocess.Popen(["xdg-open", p])
    except Exception:
        # ignore failures to avoid breaking UI
        pass


def _open_uri(uri: str) -> bool:
    """
    Open a protocol URI in a platform-friendly way.
    Returns True on success-ish, False on failure.
    """
    try:
        if sys.platform.startswith("win"):
            # os.startfile works for protocol handlers (steam://, com.epicgames.launcher://)
            os.startfile(uri)
            return True
        elif sys.platform == "darwin":
            subprocess.Popen(["open", uri])
            return True
        else:
            opener = shutil.which("xdg-open") or shutil.which("gio") or shutil.which("xdg-open")
            if opener:
                subprocess.Popen([opener, uri])
                return True
            # fallback to webbrowser which handles protocol URIs in many systems
            webbrowser.open(uri)
            return True
    except Exception:
        try:
            webbrowser.open(uri)
            return True
        except Exception:
            return False


class MainWindow(QMainWindow):
    GRID_COLS = 4
    GRID_CELL_W = 220
    GRID_CELL_H = 300

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mystical")
        self.setGeometry(160, 120, 1200, 900)

        self.all_games: list[GameEntry] = []
        self.view_mode = "grid"
        self._scan_process = None
        self._scan_queue = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar (dark, fixed) — buttons here MUST use default icons (no _dark)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(84)
        sidebar.setStyleSheet("QFrame#sidebar { background-color: #171717; color: white; }")
        sidebar_l = QVBoxLayout(sidebar)
        sidebar_l.setContentsMargins(8, 8, 8, 8)
        sidebar_l.setSpacing(10)

        lbl = QLabel("Mystical")
        lbl.setAlignment(Qt.AlignCenter) # type: ignore
        lbl.setStyleSheet("font-weight:700; color: white;")
        sidebar_l.addWidget(lbl)

        self.sidebar_status = QLabel("Scanning...")
        self.sidebar_status.setStyleSheet("color:#cfcfcf; font-size:12px;")
        self.sidebar_status.setAlignment(Qt.AlignCenter) # type: ignore
        sidebar_l.addWidget(self.sidebar_status)

        sidebar_l.addSpacerItem(QSpacerItem(10, 10, QSizePolicy.Minimum, QSizePolicy.Expanding)) # type: ignore

        # View toggle (sidebar button) — ALWAYS use default icons (no _dark)
        self.view_toggle = QPushButton()
        self.view_toggle.setIcon(self._get_sidebar_icon("grid"))
        self.view_toggle.setIconSize(QSize(28, 28))
        self.view_toggle.setFlat(True)
        self.view_toggle.clicked.connect(self._toggle_view)
        sidebar_l.addWidget(self.view_toggle, alignment=Qt.AlignHCenter) # type: ignore

        # Refresh covers button (sidebar) — default icon
        self.refresh_btn = QPushButton()
        self.refresh_btn.setIcon(self._get_sidebar_icon("refresh"))
        self.refresh_btn.setIconSize(QSize(24, 24))
        self.refresh_btn.setFlat(True)
        self.refresh_btn.setToolTip("Refresh covers (clears cache)")
        self.refresh_btn.clicked.connect(self._on_refresh_covers)
        sidebar_l.addWidget(self.refresh_btn, alignment=Qt.AlignHCenter) # type: ignore

        # Settings (gear) — sidebar, default icon
        self.settings_btn = QPushButton()
        self.settings_btn.setIcon(self._get_sidebar_icon("gear"))
        self.settings_btn.setIconSize(QSize(28, 28))
        self.settings_btn.setFlat(True)
        self.settings_btn.clicked.connect(self.open_settings_dialog)
        sidebar_l.addWidget(self.settings_btn, alignment=Qt.AlignHCenter) # type: ignore

        sidebar_l.addSpacerItem(QSpacerItem(10, 10, QSizePolicy.Minimum, QSizePolicy.Expanding)) # type: ignore

        root.addWidget(sidebar)

        # Main content area
        content = QWidget()
        content_l = QVBoxLayout(content)
        content_l.setContentsMargins(12, 12, 12, 12)
        content_l.setSpacing(8)

        top = QHBoxLayout()
        self.status_label = QLabel("Scanning libraries...")
        top.addWidget(self.status_label)
        top.addStretch()

        self.filter_box = QComboBox()
        self.filter_box.addItems(["All Games", "Installed Only", "Steam", "Epic", "Riot", "Favorites"])
        self.filter_box.currentTextChanged.connect(self.apply_filter)
        top.addWidget(QLabel("Filter:"))
        top.addWidget(self.filter_box)
        content_l.addLayout(top)

        # list view
        self.list_widget = QListWidget()
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu) # type: ignore
        self.list_widget.customContextMenuRequested.connect(self.open_context_menu)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double)
        content_l.addWidget(self.list_widget)

        # grid view (scrollable)
        self.scroll = QScrollArea() # type: ignore
        self.scroll.setWidgetResizable(True) # type: ignore
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        # tighter spacing
        self.grid_layout.setContentsMargins(6, 6, 6, 6)
        self.grid_layout.setSpacing(8)
        self.scroll.setWidget(self.grid_container) # type: ignore
        content_l.addWidget(self.scroll) # type: ignore

        root.addWidget(content, stretch=1)

        # start with grid visible
        self._show_grid(True)
        self.start_scan()

    # ----------------------------
    # icon helpers
    # ----------------------------
    def _is_light_theme(self) -> bool:
        app = QApplication.instance()
        if not app:
            return False
        pal: QPalette = app.palette() # type: ignore
        return pal.color(QPalette.Window).lightness() > pal.color(QPalette.WindowText).lightness() # type: ignore

    def _get_sidebar_icon(self, name: str) -> QIcon:
        """
        Sidebar MUST use the default variant (no `_dark`).
        Expecting assets/icons/<name>.png
        """
        base = Path("assets") / "icons"
        p = base / f"{name}.png"
        if p.exists():
            return QIcon(str(p))
        return QIcon()

    def _get_icon_theme_aware(self, name: str) -> QIcon:
        """
        For non-sidebar uses you may want theme-aware icons.
        (Not used for sidebar buttons in this version.)
        """
        light = self._is_light_theme()
        base = Path("assets") / "icons"
        mapping = {
            "heart": base / ("heart_dark.png" if light else "heart.png"),
            "grid": base / ("grid_dark.png" if light else "grid.png"),
            "list": base / ("list_dark.png" if light else "list.png"),
        }
        p = mapping.get(name)
        if p and p.exists():
            return QIcon(str(p))
        return QIcon()

    # ----------------------------
    # scanning
    # ----------------------------
    def start_scan(self):
        try:
            if self._scan_process and self._scan_process.is_alive():
                self._scan_process.terminate()
        except Exception:
            pass

        self._scan_queue = mp.Queue()
        # scan_libraries must accept the queue and put a list of GameEntry objects into it
        self._scan_process = mp.Process(target=scan_libraries, args=(self._scan_queue,))
        self._scan_process.start()

        self._timer = QTimer()
        self._timer.timeout.connect(self._poll_scan)
        self._timer.start(400)

    def _poll_scan(self):
        try:
            if self._scan_queue and not self._scan_queue.empty():
                games = self._scan_queue.get()
                self.all_games = games or []
                self.apply_filter()
                self.status_label.setText(f"Found {len(self.all_games)} games")
                self.sidebar_status.setText(f"{len(self.all_games)} games")
                self._timer.stop()
                try:
                    self._scan_process.terminate() # type: ignore
                except Exception:
                    pass
        except Exception:
            pass

    # ----------------------------
    # view helpers
    # ----------------------------
    def _show_grid(self, yes: bool):
        if yes:
            self.list_widget.hide()
            self.scroll.show() # type: ignore
        else:
            self.scroll.hide() # type: ignore
            self.list_widget.show()

    def _toggle_view(self):
        # toggles between grid & list; sidebar icon uses default variants
        # compute new mode first, then choose icon to reflect action (switch-to)
        new_mode = "list" if self.view_mode == "grid" else "grid"
        # set the toolbar icon to indicate the other view (pressing will switch)
        icon_name = "list" if new_mode == "list" else "grid"
        # actually flip mode
        self.view_mode = new_mode
        self.view_toggle.setIcon(self._get_sidebar_icon(icon_name))
        self._show_grid(self.view_mode == "grid")
        self.apply_filter()

    # ----------------------------
    # refresh covers
    # ----------------------------
    def _on_refresh_covers(self):
        reply = QMessageBox.question(self, "Refresh Covers",
                                     "This will clear the cover cache and re-download covers. Continue?",
                                     QMessageBox.Yes | QMessageBox.No) # type: ignore
        if reply != QMessageBox.Yes: # type: ignore
            return

        try:
            cache = CACHE_DIR
            if cache.exists():
                rmtree(cache)
            cache.mkdir(parents=True, exist_ok=True)
            self.sidebar_status.setText("Refreshing covers...")
            # re-run scan to repopulate metadata (or just re-apply filter so UI updates placeholders)
            self.apply_filter()
        except Exception as e:
            QMessageBox.warning(self, "Refresh failed", f"Could not clear cache: {e}")

    # ----------------------------
    # populate UI
    # ----------------------------
    def apply_filter(self):
        selected = self.filter_box.currentText()
        favs = get_favorites()

        # clear visible widgets for the current mode
        if self.view_mode == "list":
            self.list_widget.clear()
        else:
            # clear grid container
            for i in reversed(range(self.grid_layout.count())):
                item = self.grid_layout.itemAt(i)
                w = item.widget() if item else None
                if w:
                    w.setParent(None)

        row = 0
        col = 0

        for game in self.all_games:
            visible = True
            if selected == "Installed Only":
                visible = getattr(game, "installed", False)
            elif selected in ["Steam", "Epic", "Riot"]:
                plat = getattr(game, "platform", None)
                plat_str = getattr(plat, "value", str(plat)).lower() if plat is not None else ""
                visible = plat_str == selected.lower()
            elif selected == "Favorites":
                visible = getattr(game, "id", None) in favs

            if not visible:
                continue

            # LIST ROW (only create when list view active)
            if self.view_mode == "list":
                row_widget = GameItemWidget(game, grid_mode=False)
                if hasattr(row_widget, "play_button"):
                    # bind button to launch; use default arg-binding to capture game
                    row_widget.play_button.clicked.connect(lambda _=None, g=game: self.launch_game(g))
                item = QListWidgetItem(self.list_widget)
                item.setSizeHint(row_widget.sizeHint())
                item.setData(Qt.UserRole, game) # type: ignore
                self.list_widget.addItem(item)
                self.list_widget.setItemWidget(item, row_widget)

            # GRID TILE (only create when grid view active)
            if self.view_mode == "grid":
                grid_widget = GameItemWidget(game, grid_mode=True)
                if hasattr(grid_widget, "play_button"):
                    grid_widget.play_button.clicked.connect(lambda _=None, g=game: self.launch_game(g))
                # add to grid layout
                self.grid_layout.addWidget(grid_widget, row, col)
                col += 1
                if col >= self.GRID_COLS:
                    col = 0
                    row += 1

        self._show_grid(self.view_mode == "grid")
        self.sidebar_status.setText(f"{len(self.all_games)} games")

    # ----------------------------
    # actions & utilities
    # ----------------------------
    def open_context_menu(self, position):
        item = None
        if self.list_widget.isVisible():
            item = self.list_widget.itemAt(position)
        if not item:
            return
        game: GameEntry = item.data(Qt.UserRole) # type: ignore

        menu = QMenu(self)
        play_action = QAction("Play", self)
        play_action.triggered.connect(lambda: self.launch_game(game))
        menu.addAction(play_action)

        if is_favorite(getattr(game, "id", None) or getattr(game, "name", "")):
            fav_action = QAction("Remove from Favorites", self)
            fav_action.triggered.connect(lambda: self.remove_from_favorites(game))
        else:
            fav_action = QAction("Add to Favorites", self)
            fav_action.triggered.connect(lambda: self.add_to_favorites(game))
        menu.addAction(fav_action)

        open_folder = QAction("Open Install Folder", self)
        open_folder.triggered.connect(lambda: open_install_folder(getattr(game, "install_path", "")))
        menu.addAction(open_folder)

        menu.exec(self.list_widget.viewport().mapToGlobal(position))

    def _on_item_double(self, item: QListWidgetItem):
        game: GameEntry = item.data(Qt.UserRole) # type: ignore
        self.launch_game(game)

    def launch_game(self, game: GameEntry):
        """
        Use GameEntry.launch_command() when available, but handle common URI protocols properly
        so we don't rely on a local 'steam' executable being on PATH (Windows).
        """
        try:
            cmd = game.launch_command()
        except Exception:
            cmd = None

        if not cmd:
            QMessageBox.warning(self, "Launch Error", f"Cannot launch {getattr(game, 'name', 'Unknown')}")
            return

        # If cmd is a list/tuple and contains a URI (steam:// or com.epicgames.launcher://), open via OS handler
        try:
            if isinstance(cmd, (list, tuple)):
                # if any arg contains '://' treat as a protocol launch
                joined = " ".join(str(c) for c in cmd)
                protocol_arg = None
                for part in cmd:
                    ps = str(part)
                    if "://" in ps:
                        protocol_arg = ps
                        break

                if protocol_arg:
                    ok = _open_uri(protocol_arg)
                    if not ok:
                        QMessageBox.critical(self, "Launch Failed", f"Failed to open protocol URI for {getattr(game, 'name', 'Unknown')}")
                    return

                # otherwise try running the provided executable command directly
                try:
                    subprocess.Popen([str(x) for x in cmd])
                    return
                except FileNotFoundError:
                    # Try first element as executable path
                    exe = cmd[0] if cmd else None
                    if exe:
                        try:
                            subprocess.Popen([str(exe)])
                            return
                        except Exception as e:
                            QMessageBox.critical(self, "Launch Failed", f"Error launching {getattr(game, 'name', 'Unknown')}:\n{e}")
                            return
                    else:
                        QMessageBox.critical(self, "Launch Failed", f"Unable to run launch command for {getattr(game, 'name', 'Unknown')}")
                        return

            # If cmd is a plain string and looks like a URI use _open_uri
            if isinstance(cmd, str):
                if "://" in cmd:
                    if not _open_uri(cmd):
                        QMessageBox.critical(self, "Launch Failed", f"Failed to open protocol URI for {getattr(game, 'name', 'Unknown')}")
                    return
                else:
                    subprocess.Popen(cmd, shell=True)
                    return

            QMessageBox.critical(self, "Launch Failed", f"Unsupported launch command for {getattr(game, 'name', 'Unknown')}")
        except Exception as e:
            QMessageBox.critical(self, "Launch Failed", f"Error launching {getattr(game, 'name', 'Unknown')}:\n{e}")

    def add_to_favorites(self, game: GameEntry):
        add_favorite(getattr(game, "id", getattr(game, "name", "")))
        self.apply_filter()

    def remove_from_favorites(self, game: GameEntry):
        remove_favorite(getattr(game, "id", getattr(game, "name", "")))
        self.apply_filter()

    def open_settings_dialog(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self.sidebar_status.setText("Rescanning...")
            self.start_scan()
