import sys
from PySide6.QtWidgets import QApplication
from .ui import Window
from .logging_setup import configure_logging


def main():
    configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("Flux")
    window = Window()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
