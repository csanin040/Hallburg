"""Die Klassen des Programms: Impulsantwort und Ort."""

import numpy as np
import soundfile as sf

import utils


class ImpulseResponse:
    """Die Impulsantwort eines Raums, aus einem Sinus-Sweep gewonnen.

    Eine Impulsantwort beschreibt, wie ein Raum auf einen einzelnen kurzen
    Impuls reagiert. Faltet man eine Sprachaufnahme damit, klingt sie so, als
    wäre sie in diesem Raum entstanden.

    Attribute:
        samples: Die aufbereitete Impulsantwort als NumPy-Array.
        samplerate: Die Abtastrate in Hertz.
        duration: Die Länge in Sekunden.
    """

    def __init__(self, path, samplerate):
        """Lädt eine WAV-Datei und bereitet sie als Impulsantwort auf.

        Raises:
            soundfile.LibsndfileError: Die Datei fehlt oder ist beschädigt.
        """
        # always_2d sorgt dafür, dass das Array immer die Form
        # (Anzahl Werte, Anzahl Kanäle) hat. Dadurch funktioniert der
        # Mittelwert über die Kanäle bei Mono und bei Stereo gleich.
        samples, file_samplerate = sf.read(str(path), dtype="float64", always_2d=True)
        samples = samples.mean(axis=1)

        samples = utils.resample_linear(samples, file_samplerate, samplerate)
        samples = utils.trim_impulse(samples)

        self.samples = utils.normalize(samples, 1.0)
        self.samplerate = samplerate
        self.duration = len(self.samples) / samplerate

    def apply_to(self, voice, mix):
        """Legt den Hall dieses Raums auf eine Sprachaufnahme.

        Args:
            voice: Die Mikrofonaufnahme.
            mix: Hallanteil von 0.0 (nur Original) bis 1.0 (nur Hall).

        Returns:
            Das gemischte Signal.
        """
        wet = utils.fft_convolve(voice, self.samples)
        if len(wet) == 0:
            return wet

        # Das verhallte Signal ist um die Länge der Impulsantwort länger.
        # Das Original wird deshalb hinten mit Stille aufgefüllt, damit
        # beide Arrays gleich lang sind und addiert werden können.
        dry = np.zeros(len(wet))
        dry[:len(voice)] = voice

        # Die Faltung addiert sehr viele Werte und macht das Signal dadurch
        # viel lauter. Ohne diesen Ausgleich hätte der Regler kaum Wirkung,
        # weil schon ein kleiner Hallanteil alles übertönen würde.
        dry_peak = np.max(np.abs(dry))
        if dry_peak > 0:
            wet = utils.normalize(wet, dry_peak)

        mixed = (1 - mix) * dry + mix * wet

        return utils.normalize(mixed)


class Location:
    """Ein Ort in Hamburg mit Foto und Impulsantwort.

    Attribute:
        name: Der Anzeigename, zum Beispiel "Alter Elbtunnel".
        description: Ein kurzer Satz zum Ort.
        map_x, map_y: Die Position des Markers auf der Karte in Pixeln.
        photo_path: Der Pfad zum Foto.
        ir_path: Der Pfad zur WAV-Datei mit der Impulsantwort.
    """

    def __init__(self, name, description, map_x, map_y, photo_path, ir_path):
        self.name = name
        self.description = description
        self.map_x = map_x
        self.map_y = map_y
        self.photo_path = photo_path
        self.ir_path = ir_path

    def load_ir(self, samplerate):
        """Lädt die Impulsantwort dieses Ortes.

        Raises:
            soundfile.LibsndfileError: Die WAV-Datei ist nicht lesbar.
        """
        return ImpulseResponse(self.ir_path, samplerate)
