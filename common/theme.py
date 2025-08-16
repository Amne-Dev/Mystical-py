# common/theme.py
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette
from common.settings import load_config

def apply_theme(app: QApplication):
    config = load_config()
    theme = str(config.get("theme", "system") or "system").lower()

    def _is_light_palette() -> bool:
        try:
            pal = app.palette()
            window_light = pal.color(QPalette.Window).lightness()
            text_light = pal.color(QPalette.WindowText).lightness()
            return window_light > text_light
        except Exception:
            return True

    common_rules = """
    /* Make game cards transparent */
    QWidget#gameItem { background-color: transparent; border: none; }

    /* Sidebar always dark */
    QFrame#sidebar { background-color: #171717; color: #ffffff; }

    /* Sidebar direct labels (top header text) should be transparent so they inherit sidebar bg */
    QFrame#sidebar > QLabel { background-color: transparent; }

    /* Sidebar buttons always dark */
    QFrame#sidebar QPushButton {
        background-color: #1f1f1f;
        color: #ffffff;
        border: 1px solid #2a2a2a;
        padding: 8px;
        border-radius: 8px;
    }
    QFrame#sidebar QPushButton:hover { background-color: #2a2a2a; }
    QFrame#sidebar QPushButton:pressed { background-color: #333333; }
    """

    if theme == "system":
        app.setStyleSheet("")
        return

    # Light theme
    if theme == "light":
        app.setStyleSheet(
            common_rules
            + """
            QWidget { background-color: #f6f7f8; color: #111111; font-family: "Segoe UI", Roboto, Arial, sans-serif; }

            /* Play button styling for light theme */
            QPushButton#playButton, QPushButton[role="primary"] {
                background-color: #e8f0fe;
                color: #0b3a66;
                border: 1px solid #d0e3fc;
                padding: 6px;
                border-radius: 6px;
            }
            QPushButton#playButton:hover, QPushButton[role="primary"]:hover { background-color: #d2e3fc; }

            QPushButton { background-color: #ffffff; color: #111111; border: 1px solid #d0d4d8; padding: 6px; border-radius: 6px; }
            QPushButton:hover { background-color: #f0f4f7; }
            QListWidget, QScrollArea, QAbstractScrollArea { background-color: transparent; }
            QLineEdit, QTextEdit { background-color: #ffffff; border: 1px solid #d0d4d8; color: #111111; padding: 4px; border-radius: 4px; }
            QLabel { color: #111111; }
            """
        )
        return

    # Dark theme
    if theme == "dark":
        text_color = "#ffffff"
        app.setStyleSheet(
            common_rules
            + f"""
            QWidget {{ background-color: #0f1113; color: {text_color}; font-family: "Segoe UI", Roboto, Arial, sans-serif; }}

            /* Play button styling for dark theme */
            QPushButton#playButton, QPushButton[role="primary"] {{
                background-color: #1f78d1;
                color: white;
                border: 1px solid #1766a8;
                padding: 6px;
                border-radius: 6px;
            }}
            QPushButton#playButton:hover, QPushButton[role="primary"]:hover {{ background-color: #1766a8; }}

            QPushButton {{ background-color: #1c1f23; color: {text_color}; border: 1px solid #2d3136; padding: 6px; border-radius: 6px; }}
            QPushButton:hover {{ background-color: #262a30; }}
            QListWidget, QScrollArea, QAbstractScrollArea {{ background-color: transparent; }}
            QLineEdit, QTextEdit {{ background-color: #141617; border: 1px solid #2d3136; color: {text_color}; padding: 4px; border-radius: 4px; }}
            QLabel {{ color: {text_color}; }}
            """
        )
        return

    # Steam theme (dark, force white text)
    if theme == "steam":
        text_color = "#ffffff"
        primary_accent = "#66c0f4"
        app.setStyleSheet(
            common_rules
            + f"""
            QWidget {{ background-color: #07121a; color: {text_color}; font-family: "Segoe UI", Roboto, Arial, sans-serif; }}

            QPushButton#playButton, QPushButton[role="primary"] {{
                background-color: {primary_accent};
                color: #07202b;
                border: 1px solid #4eaee8;
                padding: 6px;
                border-radius: 6px;
            }}
            QPushButton#playButton:hover, QPushButton[role="primary"]:hover {{ background-color: #53b5ee; }}

            QPushButton {{ background-color: #0f2635; color: {text_color}; border: 1px solid #163246; padding: 6px; border-radius: 6px; }}
            QPushButton:hover {{ background-color: #163246; }}
            QListWidget, QScrollArea, QAbstractScrollArea {{ background-color: transparent; }}
            QLineEdit, QTextEdit {{ background-color: #0b1a24; border: 1px solid #163246; color: {text_color}; padding: 4px; border-radius: 4px; }}
            QLabel {{ color: {text_color}; }}
            """
        )
        return

    # Epic theme (dark, force white text)
    if theme == "epic":
        text_color = "#ffffff"
        primary_accent = "#7b61ff"
        app.setStyleSheet(
            common_rules
            + f"""
            QWidget {{ background-color: #0b0f16; color: {text_color}; font-family: "Segoe UI", Roboto, Arial, sans-serif; }}

            QPushButton#playButton, QPushButton[role="primary"] {{
                background-color: {primary_accent};
                color: #121018;
                border: 1px solid #6a4ff2;
                padding: 6px;
                border-radius: 6px;
            }}
            QPushButton#playButton:hover, QPushButton[role="primary"]:hover {{ background-color: #6a4ff2; }}

            QPushButton {{ background-color: #12141b; color: {text_color}; border: 1px solid #1f2130; padding: 6px; border-radius: 6px; }}
            QPushButton:hover {{ background-color: #171822; }}
            QListWidget, QScrollArea, QAbstractScrollArea {{ background-color: transparent; }}
            QLineEdit, QTextEdit {{ background-color: #0e1218; border: 1px solid #1f2130; color: {text_color}; padding: 4px; border-radius: 4px; }}
            QLabel {{ color: {text_color}; }}
            """
        )
        return

    app.setStyleSheet("")
