# main.py
import sys
import os
from pathlib import Path

from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Qt

from ui.main_window import MainWindow
from common.theme import apply_theme
from common.settings import load_config
from common.autostart import is_autostart_enabled

def _assets_icon(path):
    p = Path(path)
    if p.exists():
        return str(p)
    return str(Path("assets") / "icons" / path)

def main():
    # set high-dpi policy early if desired (already warned earlier)
    # from PySide6.QtCore import Qt
    # QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)

    app = QApplication(sys.argv)

    # set application icon (favicon)
    icon_path = _assets_icon("mystical.png")
    if Path(icon_path).exists():
        app.setWindowIcon(QIcon(icon_path))

    # Apply theme immediately
    apply_theme(app)

    window = MainWindow()
    window.show()

    # --- System tray ---
    tray_icon_path = _assets_icon("mystical.ico") if os.name == "nt" else _assets_icon("mystical.png")
    tray_icon = QSystemTrayIcon(QIcon(tray_icon_path), parent=app)

    tray_menu = QMenu()
    show_action = QAction("Show Mystical")
    def on_show():
        if window.isMinimized() or not window.isVisible():
            window.showNormal()
        window.activateWindow()
        window.raise_()
    show_action.triggered.connect(on_show)
    tray_menu.addAction(show_action)

    settings_action = QAction("Settings")
    settings_action.triggered.connect(lambda: window.open_settings_dialog())
    tray_menu.addAction(settings_action)

    refresh_action = QAction("Refresh Libraries")
    refresh_action.triggered.connect(lambda: window.start_scan())
    tray_menu.addAction(refresh_action)

    tray_menu.addSeparator()
    quit_action = QAction("Quit")
    def on_quit():
        tray_icon.hide()
        QApplication.quit()
    quit_action.triggered.connect(on_quit)
    tray_menu.addAction(quit_action)

    tray_icon.setContextMenu(tray_menu)

    # clicking the tray icon toggles show/hide
    def on_tray_activated(reason):
        if reason == QSystemTrayIcon.Trigger:
            if window.isVisible():
                window.hide()
            else:
                on_show()
    tray_icon.activated.connect(on_tray_activated)

    tray_icon.show()

    # optional: show balloon at start if autostart enabled
    try:
        if is_autostart_enabled():
            tray_icon.showMessage("Mystical", "Autostart is enabled.", QSystemTrayIcon.Information, 3000)
    except Exception:
        pass

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
