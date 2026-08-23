"""Startpunkt des Programms "Hallburg".

Starten mit:  python main.py
"""

import json
import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMessageBox

import services
from gui import STYLESHEET, MainWindow

PROJECT_DIR = Path(__file__).parent
LOCATIONS_FILE = PROJECT_DIR / "locations.json"
MAP_FILE = PROJECT_DIR / "assets" / "hamburg_map.png"
GALLERY_DIR = PROJECT_DIR / "galery_fotos"


def main():
    """Liest die Orte ein und öffnet das Fenster."""
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)

    # Ohne Orte gibt es nichts anzuzeigen. Deshalb wird hier abgebrochen,
    # statt ein leeres Fenster zu öffnen.
    try:
        locations = services.load_locations(LOCATIONS_FILE)
    except FileNotFoundError:
        QMessageBox.critical(None, "Datei fehlt",
                             f"Die Datei {LOCATIONS_FILE.name} wurde nicht gefunden.")
        return 1
    except json.JSONDecodeError as error:
        QMessageBox.critical(None, "Datei fehlerhaft",
                             f"{LOCATIONS_FILE.name} enthält kein gültiges JSON.\n"
                             f"Zeile {error.lineno}: {error.msg}")
        return 1

    if not locations:
        QMessageBox.critical(None, "Keine Orte",
                             f"{LOCATIONS_FILE.name} enthält keinen vollständigen Eintrag.")
        return 1

    window = MainWindow(locations, MAP_FILE, GALLERY_DIR)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
