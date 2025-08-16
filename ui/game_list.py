from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QPushButton, QHBoxLayout
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
from pathlib import Path
from backend.models import GameEntry
from common.favorites import is_favorite, add_favorite, remove_favorite


class GameItemWidget(QWidget):
    def __init__(self, game: GameEntry):
        super().__init__()
        self.game = game

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        # --- Cover image ---
        self.image_label = QLabel()
        self.image_label.setFixedSize(200, 90)

        if game.image_path and Path(game.image_path).exists():
            pixmap = QPixmap(str(game.image_path))
            self.image_label.setPixmap(
                pixmap.scaled(200, 90, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            self.image_label.setText("No Image")
            self.image_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.image_label)

        # --- Game title ---
        title_text = game.name
        if game.release_year:
            title_text += f" ({game.release_year})"

        self.title_label = QLabel(title_text)
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)

        # --- Button row (Play + Favorite) ---
        btn_row = QHBoxLayout()

        if game.installed:
            self.play_button = QPushButton("Play")
            self.play_button.clicked.connect(self.play_clicked)
            btn_row.addWidget(self.play_button)

        self.fav_button = QPushButton()
        self.update_fav_button()
        self.fav_button.clicked.connect(self.toggle_favorite)
        btn_row.addWidget(self.fav_button)

        layout.addLayout(btn_row)

        # --- Tooltip with description ---
        if game.description:
            self.setToolTip(game.description)

    def play_clicked(self):
        main_window = self.window()
        if hasattr(main_window, "launch_game"):
            main_window.launch_game(self.game)

    def update_fav_button(self):
        """Update favorite button text based on current state."""
        if is_favorite(self.game.id):
            self.fav_button.setText("★ Unfavorite")
        else:
            self.fav_button.setText("☆ Favorite")

    def toggle_favorite(self):
        """Toggle favorite status and update UI."""
        if is_favorite(self.game.id):
            remove_favorite(self.game.id)
        else:
            add_favorite(self.game.id)

        self.update_fav_button()

        # Refresh the filter in main window if needed
        main_window = self.window()
        if hasattr(main_window, "apply_filter"):
            main_window.apply_filter()
