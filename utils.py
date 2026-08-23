"""Hilfsfunktionen für die Signalverarbeitung.

Alle Funktionen bekommen ein NumPy-Array mit Werten zwischen -1 und 1 und
geben ein neues Array zurück.
"""

import numpy as np
from scipy.signal import fftconvolve


def fft_convolve(signal, ir):
    """Faltet ein Signal mit einer Impulsantwort.

    Eine Faltung im Zeitbereich ist dasselbe wie eine Multiplikation im
    Frequenzbereich. Der Umweg über die FFT ist deutlich schneller: direkt
    gerechnet wären es len(signal) * len(ir) Multiplikationen, hier sind es
    nur zwei Transformationen und eine Multiplikation.

    Die Rechnung übernimmt scipy.signal.fftconvolve. Die Funktion verlängert
    beide Signale selbst mit Nullen und wählt dafür eine für die FFT günstige
    Länge. Ohne diese Nullen würde die FFT "im Kreis" falten und das Ende des
    Ergebnisses in den Anfang zurückrutschen.

    Args:
        signal: Die Sprachaufnahme.
        ir: Die Impulsantwort des Raums.

    Returns:
        Das gefaltete Signal, len(signal) + len(ir) - 1 Werte lang.
    """
    if len(signal) == 0 or len(ir) == 0:
        return np.zeros(0)

    return fftconvolve(signal, ir)


def normalize(samples, peak=0.95):
    """Skaliert ein Signal auf einen festen höchsten Wert.

    Nach der Faltung sind die Werte viel größer als 1. Ohne diese Skalierung
    würde die Wiedergabe übersteuern.
    """
    if samples.size == 0:
        return samples

    maximum = np.max(np.abs(samples))
    if maximum == 0:
        return samples

    return samples * (peak / maximum)


def trim_impulse(samples, threshold=0.001):
    """Schneidet eine Impulsantwort auf den brauchbaren Teil zu.

    Vorne wird alles vor dem lautesten Wert entfernt, also der Vorlauf vor
    dem Direktschall. Dadurch beginnt die Impulsantwort direkt mit dem
    Direktschall und das trockene und das verhallte Signal passen später
    zeitlich zusammen.

    Hinten wird abgeschnitten, sobald der Nachhall leiser als threshold mal
    dem lautesten Wert ist. 0.001 entspricht etwa -60 dB.
    """
    if samples.size == 0:
        return samples

    magnitude = np.abs(samples)
    peak_index = int(np.argmax(magnitude))
    peak_value = magnitude[peak_index]
    if peak_value == 0:
        return samples

    limit = peak_value * threshold

    # np.nonzero gibt die Stellen zurück, an denen die Bedingung zutrifft.
    # Die letzte davon ist das Ende des Nachhalls.
    loud_positions = np.nonzero(magnitude > limit)[0]
    end_index = int(loud_positions[-1])

    result = samples[peak_index:end_index + 1].copy()

    # An der Schnittstelle ist der Nachhall noch gut hörbar. Ohne
    # Ausblenden endet die Impulsantwort mit einem Sprung, und der ist nach
    # der Faltung als hart abreißender Hall zu hören. Das letzte Achtel
    # blendet deshalb aus. Ein fester Wert in Sekunden ginge hier nicht,
    # weil die Funktion die Abtastrate nicht kennt.
    fade = len(result) // 8
    if fade > 1:
        result[-fade:] *= np.linspace(1.0, 0.0, fade) ** 2

    return result


def resample_linear(samples, sr_from, sr_to):
    """Rechnet ein Signal auf eine andere Abtastrate um.

    Wird gebraucht, wenn eine Impulsantwort mit 44100 Hz aufgenommen wurde,
    das Mikrofon aber mit 48000 Hz arbeitet. Ohne Umrechnung wäre der
    Nachhall zu lang oder zu kurz.
    """
    if sr_from == sr_to or samples.size == 0:
        return samples

    new_length = int(round(samples.size / sr_from * sr_to))
    old_times = np.arange(samples.size) / sr_from
    new_times = np.arange(new_length) / sr_to

    # np.interp liest die alten Werte an den neuen Zeitpunkten ab.
    return np.interp(new_times, old_times, samples)
