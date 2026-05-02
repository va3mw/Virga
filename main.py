"""Virga — SSB Voice Equaliser entry point."""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from virga.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Virga")
    app.setApplicationDisplayName("Virga — SSB Voice EQ")
    app.setOrganizationName("VA3MW")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
