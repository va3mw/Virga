"""Virga — SSB Voice Equaliser entry point."""

import sys
import traceback
from PySide6.QtWidgets import QApplication, QMessageBox
from virga.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Virga")
    app.setApplicationDisplayName("Virga — SSB Voice EQ")
    app.setOrganizationName("VA3MW")

    try:
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception:
        error = traceback.format_exc()
        print(error)
        box = QMessageBox()
        box.setWindowTitle("Virga — Startup Error")
        box.setText("Virga failed to start. See details below.")
        box.setDetailedText(error)
        box.exec()
        sys.exit(1)


if __name__ == "__main__":
    main()
