"""Die Oberfläche: eine Kartenseite und eine Seite je Ort."""

import numpy as np
import sounddevice as sd
import soundfile as sf
from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QIcon, QImageReader, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

import services

PHOTO_HEIGHT = 340
PHOTO_WIDTH = 850

# Startseite: Breite der Textspalte links und Maße der Galerie rechts.
TEXT_WIDTH = 400
GALLERY_WIDTH = 410
PREVIEW_HEIGHT = 340
THUMB_SIZE = 76

# Welche Dateien im Galerieordner als Foto gelten.
PHOTO_SUFFIXES = (".jpg", ".jpeg", ".png")

# Durchmesser der Punkte auf der Karte in Pixeln.
MARKER_SIZE = 18

# So oft wird während der Aufnahme nachgesehen, ob sie schon fertig ist.
RECORD_POLL_MS = 100

STYLESHEET = """
QWidget { background: #1c1f26; color: #e8eaf0; font-size: 14px; }
QPushButton { background: #ff8a3d; color: #14161c; border: none;
              border-radius: 5px; padding: 7px 14px; font-weight: bold; }
QPushButton:disabled { background: #3a3f4b; color: #767d8c; }
QPushButton#marker { background: #ff8a3d; border: 2px solid #14161c;
                     border-radius: 9px; padding: 0; }
QPushButton#marker:hover { background: #ffd0a8; }
QToolTip { background: #14161c; color: #e8eaf0; border: 1px solid #ff8a3d;
           padding: 4px 7px; }
QPushButton#thumb { background: #262a33; border: 2px solid #262a33;
                    border-radius: 4px; padding: 0; }
QPushButton#thumb:hover { border-color: #ff8a3d; }
QLabel#preview { background: #14161c; border-radius: 6px; }
QLabel#lead { color: #ff8a3d; font-size: 16px; }
"""


def load_scaled(path, width, height):
    """Lädt ein Bild und verkleinert es schon beim Einlesen.

    Die Galeriefotos sind bis zu 4000 x 4000 Pixel groß. Voll geladen
    bräuchte jedes davon rund 64 MB Arbeitsspeicher. setScaledSize lässt
    den JPEG-Decoder stattdessen direkt in der gewünschten Größe arbeiten.

    Args:
        path: Pfad zur Bilddatei.
        width: Höchstbreite in Pixeln.
        height: Höchsthöhe in Pixeln.

    Returns:
        Ein QPixmap oder None, wenn die Datei nicht lesbar ist.
    """
    reader = QImageReader(str(path))

    # Fotos aus Kameras tragen ihre Drehung oft nur als EXIF-Feld und nicht
    # im Bild selbst. Ohne autoTransform lägen sie hier auf der Seite.
    reader.setAutoTransform(True)

    size = reader.size()
    if size.isValid():
        # scale rechnet die Zielgröße unter Beibehaltung des Seitenverhält-
        # nisses aus. Die Fotos sind teils quadratisch, teils 16:9.
        size.scale(width, height, Qt.AspectRatioMode.KeepAspectRatio)
        reader.setScaledSize(size)

    image = reader.read()
    if image.isNull():
        return None

    return QPixmap.fromImage(image)


class StartView(QWidget):
    """Die Startseite: links die Erklärung, rechts eine kleine Fotogalerie.

    Ein Klick auf ein Vorschaubild zeigt das Foto darüber groß an.
    """

    def __init__(self, gallery_dir, window):
        super().__init__()
        self.window = window

        layout = QHBoxLayout(self)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(25)
        layout.addLayout(self.build_text())
        layout.addLayout(self.build_gallery(gallery_dir))

    def build_text(self):
        """Baut die linke Spalte mit der Erklärung und dem Knopf zur Karte."""
        title = QLabel("Hallburg")
        title.setStyleSheet("font-size: 26px; font-weight: bold;")

        lead = QLabel("Deine Stimme im Alten Elbtunnel")
        lead.setObjectName("lead")

        body = QLabel(
            "An verschiedenen Orten in Hamburg lief ein Sinus-Sweep über "
            "einen Lautsprecher, aufgenommen wurde, was der Raum daraus "
            "macht. Aus dieser Aufnahme lässt sich die Impulsantwort des "
            "Raums zurückrechnen: sie enthält, wie der Raum auf ein Geräusch "
            "reagiert, also jede Reflexion an jeder Wand.\n\n"
            "Faltet man eine Sprachaufnahme mit dieser Impulsantwort, klingt "
            "sie, als wäre sie an diesem Ort entstanden. Das Verfahren heißt "
            "Faltungshall.\n\n"
            "Einen Ort auf der Karte anklicken, das Foto ansehen und fünf "
            "Sekunden ins Mikrofon sprechen: die eigene Stimme kommt mit dem "
            "Nachhall dieses Raums zurück. Der Regler Hallanteil mischt "
            "zwischen Original und Hall."
        )
        body.setWordWrap(True)

        # Feste Breite statt einer Mindestbreite: so steht der Umbruch des
        # Textes fest und hängt nicht davon ab, wie breit die Galerie
        # daneben gerade ausfällt.
        column = QVBoxLayout()
        column.setSpacing(12)
        for widget in (title, lead, body):
            widget.setFixedWidth(TEXT_WIDTH)
            column.addWidget(widget)

        button = QPushButton("Zur Karte")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(self.window.show_map)

        column.addStretch()
        column.addWidget(button, alignment=Qt.AlignmentFlag.AlignLeft)

        return column

    def build_gallery(self, gallery_dir):
        """Baut die rechte Spalte: oben die Vorschau, darunter die Thumbnails."""
        self.preview = QLabel()
        self.preview.setObjectName("preview")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setWordWrap(True)
        self.preview.setFixedSize(GALLERY_WIDTH, PREVIEW_HEIGHT)

        thumbnails = QHBoxLayout()
        thumbnails.setSpacing(8)

        column = QVBoxLayout()
        column.setSpacing(10)
        column.addWidget(self.preview)
        column.addLayout(thumbnails)
        column.addStretch()

        # sorted() gibt der Galerie eine feste Reihenfolge. Ohne das hinge
        # sie davon ab, wie das Dateisystem die Einträge zurückgibt.
        paths = sorted(path for path in gallery_dir.glob("*")
                       if path.suffix.lower() in PHOTO_SUFFIXES)

        # Geladen wird einmal in Vorschaugröße. Die Thumbnails entstehen
        # daraus, statt die Dateien ein zweites Mal zu lesen.
        photos = []
        for path in paths:
            pixmap = load_scaled(path, GALLERY_WIDTH, PREVIEW_HEIGHT)
            if pixmap is not None:
                photos.append(pixmap)
                self.add_thumbnail(thumbnails, pixmap)

        thumbnails.addStretch()

        # Ein fehlender oder leerer Ordner ist kein Fehler, sondern nur ein
        # anderer Zustand – wie beim Kartenbild reicht hier eine if-Abfrage.
        if photos:
            self.preview.setPixmap(photos[0])
        else:
            self.preview.setText("Keine Fotos in " + str(gallery_dir))

        return column

    def add_thumbnail(self, row, pixmap):
        """Hängt ein Vorschaubild an die Reihe.

        Eine eigene Methode aus demselben Grund wie bei add_marker: so
        bekommt jeder Knopf sein eigenes Foto. In einer Schleife würden
        sich sonst alle Knöpfe das letzte merken.
        """
        thumb = pixmap.scaled(
            THUMB_SIZE - 8, THUMB_SIZE - 8,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)

        button = QPushButton()
        button.setObjectName("thumb")
        button.setFixedSize(THUMB_SIZE, THUMB_SIZE)
        button.setIcon(QIcon(thumb))
        button.setIconSize(QSize(thumb.width(), thumb.height()))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda: self.preview.setPixmap(pixmap))

        row.addWidget(button)


class MapView(QWidget):
    """Die Karte mit einem Knopf für jeden Ort."""

    def __init__(self, locations, map_path, window):
        super().__init__()
        self.window = window

        self.background = QLabel(self)
        pixmap = QPixmap(str(map_path))

        # Ein fehlendes Bild ist kein Fehler, sondern nur ein anderer
        # Zustand. Deshalb reicht hier eine if-Abfrage.
        if pixmap.isNull():
            self.background.setText("Kartenbild nicht gefunden:\n" + str(map_path))
            self.background.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.background.resize(900, 675)
        else:
            self.background.setPixmap(pixmap)
            self.background.resize(pixmap.size())

        self.setFixedSize(self.background.size())

        for location in locations:
            self.add_marker(location)

    def add_marker(self, location):
        """Setzt einen Punkt an die Position eines Ortes.

        Das steht in einer eigenen Methode, damit jeder Knopf sein eigenes
        location bekommt. In einer Schleife würden sich sonst alle Knöpfe
        den letzten Ort merken.
        """
        button = QPushButton(self)
        button.setObjectName("marker")
        button.setFixedSize(MARKER_SIZE, MARKER_SIZE)

        # Der Name steht nicht auf der Karte, sondern erscheint erst, wenn
        # die Maus auf dem Punkt steht. So verdecken die Beschriftungen die
        # Karte nicht.
        button.setToolTip(location.name)
        button.setCursor(Qt.CursorShape.PointingHandCursor)

        # move setzt die linke obere Ecke. Damit map_x und map_y den Ort
        # selbst meinen, wird der Knopf um seine halbe Größe verschoben.
        button.move(
            location.map_x - MARKER_SIZE // 2,
            location.map_y - MARKER_SIZE // 2,
        )
        button.clicked.connect(lambda: self.window.show_location(location))

    def mousePressEvent(self, event):
        """Gibt beim Klick auf die Karte die Koordinaten aus.

        Praktisch, um die Werte für neue Orte in locations.json zu finden.
        """
        position = event.position()
        print(f'"map_x": {int(position.x())}, "map_y": {int(position.y())}')


class LocationView(QWidget):
    """Die Seite eines Ortes mit Foto, Aufnahme und Wiedergabe."""

    def __init__(self):
        super().__init__()
        self.location = None
        self.impulse_response = None
        self.voice = None
        self.recording = None

        # Das Programm darf während der Aufnahme nicht warten, sonst friert
        # das Fenster für fünf Sekunden ein. Der Timer sieht stattdessen
        # regelmäßig nach, ob die Aufnahme fertig ist. Dazwischen bleibt
        # Zeit, das Fenster zu zeichnen und auf Klicks zu reagieren.
        self.record_timer = QTimer(self)
        self.record_timer.setInterval(RECORD_POLL_MS)
        self.record_timer.timeout.connect(self.check_recording)

        self.photo = QLabel()
        self.photo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.photo.setFixedHeight(PHOTO_HEIGHT)

        self.title = QLabel()
        self.title.setStyleSheet("font-size: 24px; font-weight: bold;")

        self.device_box = QComboBox()
        self.fill_device_box()

        self.record_button = QPushButton("Aufnahme starten (5 s)")
        self.record_button.clicked.connect(self.record_and_play)

        self.play_button = QPushButton("Abspielen")
        self.play_button.setEnabled(False)
        self.play_button.clicked.connect(self.play_voice)

        self.mix_label = QLabel()
        self.mix_slider = QSlider(Qt.Orientation.Horizontal)
        self.mix_slider.setRange(0, 100)
        self.mix_slider.setValue(70)
        self.mix_slider.setFixedWidth(200)
        self.mix_slider.valueChanged.connect(self.update_mix_label)
        self.update_mix_label()

        self.status = QLabel("Bereit.")

        devices = QHBoxLayout()
        devices.addWidget(QLabel("Mikrofon"))
        devices.addWidget(self.device_box)
        devices.addStretch()

        buttons = QHBoxLayout()
        buttons.addWidget(self.record_button)
        buttons.addWidget(self.play_button)
        buttons.addSpacing(20)
        buttons.addWidget(self.mix_label)
        buttons.addWidget(self.mix_slider)
        buttons.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.addWidget(self.photo)
        layout.addWidget(self.title)
        layout.addStretch()
        layout.addLayout(devices)
        layout.addLayout(buttons)
        layout.addWidget(self.status)
        layout.addWidget(QLabel("ESC führt zurück zur Karte."))

    def fill_device_box(self):
        """Trägt die Mikrofone in die Auswahlliste ein.

        Der Index des Geräts wird als Datum am Eintrag mitgeführt, weil die
        Namen doppelt vorkommen können, die Indizes aber nicht.
        """
        for index, name in services.list_input_devices():
            self.device_box.addItem(name, index)

        # sd.default.device ist das Paar (Eingabe, Ausgabe). Vorausgewählt
        # wird das Mikrofon, das im System eingestellt ist.
        position = self.device_box.findData(sd.default.device[0])
        if position >= 0:
            self.device_box.setCurrentIndex(position)

    def update_mix_label(self):
        self.mix_label.setText(f"Hallanteil {self.mix_slider.value()} %")

    def show_location(self, location):
        """Zeigt einen Ort an und lädt seine Impulsantwort."""
        self.location = location
        self.voice = None
        self.play_button.setEnabled(False)
        self.title.setText(location.name)

        # load_scaled statt QPixmap: die Ortsfotos sind bis zu 4032 x 3024
        # Pixel groß. Voll geladen belegten sie rund 48 MB je Foto, nur um
        # danach auf PHOTO_HEIGHT verkleinert zu werden.
        pixmap = load_scaled(location.photo_path, PHOTO_WIDTH, PHOTO_HEIGHT)
        if pixmap is None:
            self.photo.setText("Kein Foto unter " + str(location.photo_path))
        else:
            self.photo.setPixmap(pixmap)

        try:
            self.impulse_response = location.load_ir(services.SAMPLERATE)
        except sf.LibsndfileError:
            # Die WAV-Datei fehlt oder ist kaputt. Der Ort bleibt sichtbar,
            # nur die Aufnahme wird gesperrt.
            self.impulse_response = None
            self.record_button.setEnabled(False)
            self.status.setText("Impulsantwort nicht lesbar: " + str(location.ir_path))
            return

        self.record_button.setEnabled(True)
        self.status.setText(
            f"Impulsantwort {self.impulse_response.duration:.2f} s. "
            "Aufnahme starten und sprechen."
        )

    def record_and_play(self):
        """Startet die Aufnahme. Das Fenster bleibt dabei bedienbar."""
        try:
            self.recording = services.start_record(
                device=self.device_box.currentData())
        except sd.PortAudioError as error:
            self.status.setText(f"Aufnahme nicht möglich: {error}")
            return

        # Während der Aufnahme darf weder ein zweites Mal aufgenommen noch
        # abgespielt werden, weil beides dasselbe Gerät belegt.
        self.voice = None
        self.record_button.setEnabled(False)
        self.play_button.setEnabled(False)
        self.device_box.setEnabled(False)

        self.status.setText("Aufnahme läuft ...")
        self.record_timer.start()

    def check_recording(self):
        """Sieht nach, ob die Aufnahme fertig ist, und spielt sie dann ab."""
        if services.is_recording():
            return

        self.record_timer.stop()
        self.record_button.setEnabled(True)
        self.device_box.setEnabled(True)

        voice = self.recording
        self.recording = None

        # Ein stummes Mikrofon meldet unter macOS keinen Fehler, sondern
        # liefert nur Nullen. Ohne diesen Hinweis sieht die Aufnahme
        # erfolgreich aus und man sucht den Fehler im Programm.
        if np.max(np.abs(voice)) < 1e-6:
            self.status.setText(
                f"Kein Signal von \"{self.device_box.currentText()}\". Ein anderes "
                "Mikrofon wählen oder den Zugriff in den Systemeinstellungen "
                "unter Datenschutz & Sicherheit erlauben."
            )
            return

        self.voice = voice
        self.play_button.setEnabled(True)
        self.play_voice()

    def cancel_recording(self):
        """Verwirft eine laufende Aufnahme, wenn die Seite verlassen wird."""
        if self.recording is None:
            return

        self.record_timer.stop()
        self.recording = None
        self.record_button.setEnabled(True)
        self.device_box.setEnabled(True)
        self.status.setText("Aufnahme abgebrochen.")

    def play_voice(self):
        """Faltet die Aufnahme mit dem Raum und spielt sie ab."""
        if self.voice is None or self.impulse_response is None:
            return

        mix = self.mix_slider.value() / 100
        mixed = self.impulse_response.apply_to(self.voice, mix)

        try:
            services.play(mixed)
        except sd.PortAudioError as error:
            self.status.setText(f"Wiedergabe nicht möglich: {error}")
            return

        self.status.setText("Wiedergabe: " + self.location.name)


class MainWindow(QMainWindow):
    """Das Hauptfenster mit den beiden Seiten."""

    def __init__(self, locations, map_path, gallery_dir):
        super().__init__()
        self.setWindowTitle("Hallburg")

        self.start_view = StartView(gallery_dir, self)
        self.map_view = MapView(locations, map_path, self)
        self.location_view = LocationView()

        # Der QStackedWidget zeigt immer nur eine der drei Seiten an.
        # Zuerst steht die Startseite oben.
        self.pages = QStackedWidget()
        self.pages.addWidget(self.start_view)
        self.pages.addWidget(self.map_view)
        self.pages.addWidget(self.location_view)
        self.setCentralWidget(self.pages)

        self.resize(self.map_view.width(), self.map_view.height())

    def show_map(self):
        self.pages.setCurrentWidget(self.map_view)

    def show_location(self, location):
        self.location_view.show_location(location)
        self.pages.setCurrentWidget(self.location_view)

    def keyPressEvent(self, event):
        """ESC führt eine Seite zurück: Ort -> Karte -> Startseite."""
        if event.key() == Qt.Key.Key_Escape:
            # sd.stop beendet Aufnahme und Wiedergabe. Seit die Oberfläche
            # während der Aufnahme bedienbar ist, kann ESC auch mitten in
            # eine Aufnahme fallen. Die wird dann verworfen.
            sd.stop()
            self.location_view.cancel_recording()

            if self.pages.currentWidget() is self.location_view:
                self.pages.setCurrentWidget(self.map_view)
            else:
                self.pages.setCurrentWidget(self.start_view)
        else:
            super().keyPressEvent(event)
