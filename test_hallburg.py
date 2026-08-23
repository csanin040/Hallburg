"""Tests für die Signalverarbeitung und das Einlesen der Orte.

Starten mit:  python -m unittest test_hallburg.py

Die Tests erzeugen ihre Signale selbst und brauchen keine Aufnahmen.
"""

import json
import unittest
from pathlib import Path

import numpy as np

import services
from utils import fft_convolve, normalize, resample_linear, trim_impulse


class TestFftConvolve(unittest.TestCase):
    """Die Faltung ist das Kernstück des Programms."""

    def test_unit_impulse_returns_input(self):
        # Ein Signal mit einem einzelnen 1er verändert nichts.
        signal = np.array([0.1, -0.4, 0.7, 0.2])
        result = fft_convolve(signal, np.array([1.0]))
        np.testing.assert_allclose(result, signal, atol=1e-12)

    def test_length(self):
        result = fft_convolve(np.zeros(100), np.zeros(30))
        self.assertEqual(len(result), 129)

    def test_matches_numpy(self):
        # np.convolve rechnet direkt und dient hier als Vergleich.
        rng = np.random.default_rng(42)
        signal = rng.normal(size=500)
        ir = rng.normal(size=137)
        np.testing.assert_allclose(
            fft_convolve(signal, ir), np.convolve(signal, ir), atol=1e-9)


class TestNormalize(unittest.TestCase):

    def test_reaches_target(self):
        result = normalize(np.array([0.1, -0.2, 0.05]), peak=0.95)
        self.assertAlmostEqual(np.max(np.abs(result)), 0.95)

    def test_silence_stays_silent(self):
        # Ohne die Abfrage wäre das eine Division durch Null.
        np.testing.assert_array_equal(normalize(np.zeros(10)), np.zeros(10))


class TestTrimImpulse(unittest.TestCase):

    def test_peak_moves_to_front(self):
        samples = np.array([0.0, 0.0, 0.01, 1.0, 0.5, 0.2])
        result = trim_impulse(samples)
        self.assertAlmostEqual(result[0], 1.0)

    def test_quiet_tail_removed(self):
        samples = np.concatenate([[1.0, 0.5], np.full(1000, 1e-6)])
        self.assertEqual(len(trim_impulse(samples)), 2)


class TestResampleLinear(unittest.TestCase):

    def test_length_changes(self):
        self.assertEqual(len(resample_linear(np.zeros(44100), 44100, 48000)), 48000)


class TestLoadLocations(unittest.TestCase):
    """Prüft, was beim Einlesen von locations.json schiefgehen kann."""

    def write_temp(self, text):
        path = Path("test_temp.json")
        path.write_text(text, encoding="utf-8")
        self.addCleanup(path.unlink)
        return path

    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            services.load_locations(Path("gibt_es_nicht.json"))

    def test_broken_json(self):
        path = self.write_temp("{ das ist kein JSON")
        with self.assertRaises(json.JSONDecodeError):
            services.load_locations(path)

    def test_incomplete_entry_is_skipped(self):
        # Der unvollständige Eintrag fällt weg, der gültige bleibt.
        path = self.write_temp(json.dumps([
            {"name": "Kaputt"},
            {"name": "Heil", "description": "", "map_x": 1, "map_y": 2,
             "photo": "b.jpg", "ir": "b.wav"},
        ]))
        locations = services.load_locations(path)
        self.assertEqual(len(locations), 1)
        self.assertEqual(locations[0].name, "Heil")


if __name__ == "__main__":
    unittest.main()
