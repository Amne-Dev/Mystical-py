from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QHBoxLayout, QComboBox
)
from common.theme import apply_theme
from common.settings import get_settings, update_setting, load_config, save_config


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mystical Settings")
        self.setFixedSize(500, 300)

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
        # Show pretty names, but store lowercase
        self.theme_map = {
            "System": "system",
            "Light": "light",
            "Dark": "dark"
        }
        self.theme_box.addItems(self.theme_map.keys())

        current_theme = load_config().get("theme", "system").lower()
        # Reverse lookup to match UI name
        for display, internal in self.theme_map.items():
            if current_theme == internal:
                self.theme_box.setCurrentText(display)
                break

        theme_row.addWidget(self.theme_box)
        layout.addLayout(theme_row)

        # --- Save Button ---
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save)
        layout.addWidget(save_btn)

    def browse_path(self, target_input: QLineEdit):
        path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if path:
            target_input.setText(path)

    def save(self):
        update_setting("steam_path", self.steam_input.text().strip())
        update_setting("epic_path", self.epic_input.text().strip())
        if self.riot_input:
            update_setting("riot_path", self.riot_input.text().strip())

        # Save lowercase version of theme
        chosen_display = self.theme_box.currentText()
        chosen_internal = self.theme_map[chosen_display]

        config = load_config()
        config["theme"] = self.theme_box.currentText()
        save_config(config)

        # Apply immediately
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            apply_theme(app)

        self.accept()