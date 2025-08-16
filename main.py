import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from common.theme import apply_theme


def main():
    app = QApplication(sys.argv)

    # Apply theme before showing main window
    apply_theme(app)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
