#!/usr/bin/env python3
"""Sprite Drawer -- entry point.

Run with:  .venv/bin/python main.py
"""
import sys

from PySide6.QtWidgets import QApplication

from sprite_drawer.app import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Sprite Drawer")
    app.setOrganizationName("InHouseTools")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
