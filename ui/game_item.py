from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QHBoxLayout
from common.settings import toggle_favorite, get_favorites

class GameItemWidget(QWidget):
    def __init__(self, game, parent=None):
        super().__init__(parent)
        self.game = game
        layout = QHBoxLayout(self)

        self.label = QLabel(game.name)
        self.star_btn = QPushButton("★" if game.name in get_favorites() else "☆")
        self.star_btn.setFixedWidth(30)
        self.star_btn.clicked.connect(self.toggle_fav)

        layout.addWidget(self.label)
        layout.addWidget(self.star_btn)

    def toggle_fav(self):
        toggle_favorite(self.game.name)
        # Refresh star
        self.star_btn.setText("★" if self.game.name in get_favorites() else "☆")
