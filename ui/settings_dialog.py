# ui/settings_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QHBoxLayout, QComboBox, QCheckBox, QMessageBox
)
from PySide6.QtCore import Qt
from common.settings import get_settings, update_setting, load_config, save_config
from common.autostart import enable_autostart, disable_autostart, is_autostart_enabled
from common.theme import apply_theme
from PySide6.QtWidgets import QApplication

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mystical Settings")
        self.setFixedSize(520, 340)

        layout = QVBoxLayout(self)

        # --- Steam ---
        self.steam_input = QLineEdit(get_settings("steam_path"))
        steam_row = QHBoxLayout()
        steam_row.addWidget(QLabel("Steam Path:"))
        steam_row.addWidget(self.steam_input)
        browse_steam = QPushButton("Browse")
        browse_steam.clicked.connect(lambda: self.browse_path(self.steam_input))
        steam_row.addWidget(browse_steam)
        layout.addLayout(steam_row)

        # --- Epic ---
        self.epic_input = QLineEdit(get_settings("epic_path"))
        epic_row = QHBoxLayout()
        epic_row.addWidget(QLabel("Epic Path:"))
        epic_row.addWidget(self.epic_input)
        browse_epic = QPushButton("Browse")
        browse_epic.clicked.connect(lambda: self.browse_path(self.epic_input))
        epic_row.addWidget(browse_epic)
        layout.addLayout(epic_row)

        # --- Riot (optional) ---
        riot_path = get_settings("riot_path")
        self.riot_input = None
        if riot_path:
            riot_path_str = str(riot_path) if not isinstance(riot_path, str) else riot_path
            self.riot_input = QLineEdit(riot_path_str)
            riot_row = QHBoxLayout()
            riot_row.addWidget(QLabel("Riot Path:"))
            riot_row.addWidget(self.riot_input)
            browse_riot = QPushButton("Browse")
            browse_riot.clicked.connect(lambda: self.browse_path(self.riot_input))
            riot_row.addWidget(browse_riot)
            layout.addLayout(riot_row)

        # --- Theme Selector ---
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Theme:"))
        self.theme_box = QComboBox()
        self.theme_map = {"System": "system", "Light": "light", "Dark": "dark", "Steam": "steam", "Epic": "epic"}
        self.theme_box.addItems(self.theme_map.keys())
        current_theme = load_config().get("theme", "system").lower()
        for display, internal in self.theme_map.items():
            if current_theme == internal:
                self.theme_box.setCurrentText(display)
                break
        theme_row.addWidget(self.theme_box)
        layout.addLayout(theme_row)

        # --- Autostart checkbox ---
        self.autostart_cb = QCheckBox("Start Mystical at login (autostart)")
        autostart_current = load_config().get("autostart", False)
        self.autostart_cb.setChecked(bool(autostart_current))
        # disable on platforms where not supported? we still attempt linux desktop file
        if not (QApplication.instance().platformName().lower().startswith("windows") or QApplication.instance().platformName().lower().startswith("linux")):
            # show but disable on unknown platforms (macOS not implemented here)
            self.autostart_cb.setEnabled(False)
            self.autostart_cb.setToolTip("Autostart currently implemented for Windows and Linux only.")
        layout.addWidget(self.autostart_cb)

        # --- Save Button ---
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save)
        layout.addWidget(save_btn, alignment=Qt.AlignRight)

    def browse_path(self, target_input: QLineEdit):
        path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if path:
            target_input.setText(path)

    def save(self):
        # write library overrides
        update_setting("steam_path", self.steam_input.text().strip())
        update_setting("epic_path", self.epic_input.text().strip())
        if self.riot_input:
            update_setting("riot_path", self.riot_input.text().strip())

        # theme
        chosen_display = self.theme_box.currentText()
        chosen_internal = self.theme_map[chosen_display]
        update_setting("theme", chosen_internal)

        # autostart
        autostart_val = bool(self.autostart_cb.isChecked())
        update_setting("autostart", autostart_val)

        # apply autostart immediately
        try:
            if autostart_val:
                ok = enable_autostart()
                if not ok:
                    QMessageBox.warning(self, "Autostart", "Failed to enable autostart. You may need to run as a normal user.")
            else:
                disable_autostart()
        except Exception:
            # ignore but warn
            QMessageBox.information(self, "Autostart", "Autostart toggle failed (platform may be unsupported).")

        # Apply theme immediately
        app = QApplication.instance()
        if app:
            apply_theme(app)

        self.accept()
