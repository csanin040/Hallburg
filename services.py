"""Programmlogik: Orte einlesen, aufnehmen und abspielen."""

import json

import numpy as np
import sounddevice as sd

from models import Location

SAMPLERATE = 48000
RECORD_SECONDS = 5.0


def load_locations(path):
    """Liest die Orte aus der JSON-Datei.

    Ein Eintrag, bei dem ein Feld fehlt, wird übersprungen. So macht ein
    Tippfehler in einem Ort nicht das ganze Programm unbrauchbar.

    Args:
        path: Pfad zur locations.json.

    Returns:
        Eine Liste von Location-Objekten.

    Raises:
        FileNotFoundError: Die Datei gibt es nicht.
        json.JSONDecodeError: Die Datei enthält kein gültiges JSON.
    """
    with open(path, encoding="utf-8") as file:
        entries = json.load(file)

    # Die Pfade in der JSON-Datei gelten ab dem Projektordner. Sie werden
    # hier mit dem Ordner der JSON-Datei kombiniert, damit das Programm auch
    # aus einem anderen Verzeichnis gestartet werden kann.
    base_dir = path.parent

    locations = []
    for entry in entries:
        try:
            location = Location(
                entry["name"],
                entry["description"],
                entry["map_x"],
                entry["map_y"],
                base_dir / entry["photo"],
                base_dir / entry["ir"],
            )
            locations.append(location)
        except (KeyError, TypeError) as error:
            print("Ort übersprungen, Eintrag unvollständig:", error)

    return locations


def list_input_devices():
    """Sucht alle Geräte, die aufnehmen können.

    Returns:
        Eine Liste aus Paaren (Index, Name).
    """
    devices = []
    for index, device in enumerate(sd.query_devices()):
        if device["max_input_channels"] > 0:
            devices.append((index, device["name"]))

    return devices


def start_record(duration=RECORD_SECONDS, samplerate=SAMPLERATE, device=None):
    """Startet eine Aufnahme und kehrt sofort zurück.

    Es wird bewusst nicht auf das Ende gewartet. Sonst stünde das Programm
    fünf Sekunden still und das Fenster wäre in dieser Zeit eingefroren.
    Ob die Aufnahme fertig ist, beantwortet is_recording().

    Args:
        device: Index des Mikrofons. Bei None wird das Gerät benutzt, das im
            System eingestellt ist.

    Returns:
        Das Array, in das aufgenommen wird, als eindimensionales Array. Es
        füllt sich während der Aufnahme nach und nach mit Werten.

    Raises:
        sounddevice.PortAudioError: Kein Mikrofon vorhanden oder belegt.
    """
    frames = int(duration * samplerate)

    # sd.rec legt sein Array sonst ohne Startwerte an. Kommt die Aufnahme
    # nicht zustande, stünden dort zufällige Zahlen, die als sehr lautes
    # Rauschen hörbar wären. Ein Array aus Nullen ergibt in diesem Fall Stille.
    buffer = np.zeros((frames, 1))
    sd.rec(frames, samplerate=samplerate, channels=1, out=buffer, device=device)

    # Aus der Form (Anzahl Werte, 1) wird eine einfache Liste von Werten.
    # reshape kopiert dabei nichts, sondern zeigt auf denselben Speicher.
    # Deshalb landen die Werte der laufenden Aufnahme auch hier.
    return buffer.reshape(-1)


def is_recording():
    """Sagt, ob die zuletzt gestartete Aufnahme noch läuft."""
    return sd.get_stream().active


def play(samples, samplerate=SAMPLERATE):
    """Spielt ein Signal ab, ohne auf das Ende zu warten.

    Raises:
        sounddevice.PortAudioError: Kein Ausgabegerät vorhanden.
    """
    sd.play(samples, samplerate=samplerate)
