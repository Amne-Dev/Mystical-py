from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
from pathlib import Path
from backend.models import GameEntry


class GameItemWidget(QWidget):
    def __init__(self, game: GameEntry):
        super().__init__()

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

        # --- Tooltip with description ---
        if game.description:
            self.setToolTip(game.description)
