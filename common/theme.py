from PySide6.QtWidgets import QApplication
from common.settings import load_config


def apply_theme(app: QApplication):
    config = load_config()
    theme = config.get("theme", "System")

    if theme == "System":
        app.setStyleSheet("")  # Reset → follow system/Qt default
    elif theme == "Light":
        app.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                color: #000000;
            }
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #ccc;
                padding: 3px;
            }
        """)
    elif theme == "Dark":
        app.setStyleSheet("""
            QWidget {
                background-color: #121212;
                color: #eeeeee;
            }
            QPushButton {
                background-color: #1e1e1e;
                border: 1px solid #444;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #333333;
            }
            QLineEdit {
                background-color: #1e1e1e;
                border: 1px solid #444;
                padding: 3px;
                color: #eeeeee;
            }
        """)
