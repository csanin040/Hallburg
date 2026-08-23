# Hallburg

Sprich ins Mikrofon und höre deine Stimme so, als stündest du im Alten Elbtunnel.

## Beschreibung und Ziel

An verschiedenen Orten in Hamburg läuft über einen Lautsprecher ein
exponentieller Sinus-Sweep von 20 Hz bis 20 kHz, aufgenommen wird, was der Raum
daraus macht. Rechnet man die Aufnahme mit dem Inversfilter des Sweeps zurück,
erhält man die **Impulsantwort** des Raums: jede Reflexion an jeder Wand.

Ein zerplatzter Ballon täte es auch, der Sweep ist aber sauberer: die
Verzerrungen des Lautsprechers landen in der Entfaltung *vor* der Impulsantwort
und lassen sich dort abschneiden, beim Ballonknall stecken sie untrennbar im
Ergebnis.

Faltet man eine Sprachaufnahme mit dieser Impulsantwort, klingt sie, als wäre
sie an diesem Ort entstanden. Das Verfahren heißt **Faltungshall**; die Faltung
rechnet `scipy.signal.fftconvolve`.

## Verwendete Python-Version

Python 3.13

## Benötigte Bibliotheken

| Paket | Zweck |
|---|---|
| `PyQt6` | Grafische Oberfläche (Karte und Ortsseite) |
| `numpy` | Rechnen mit Arrays |
| `scipy` | Faltung über die FFT (`signal.fftconvolve`) |
| `sounddevice` | Aufnahme über das Mikrofon, Wiedergabe |
| `soundfile` | Lesen der WAV-Dateien mit den Impulsantworten |

## Installation

Im Projektordner:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Unter macOS muss der Mikrofonzugriff einmal in den Systemeinstellungen unter
*Datenschutz & Sicherheit → Mikrofon* erlaubt werden, sonst liefert die Aufnahme
nur Stille statt einer Fehlermeldung. Stille kommt auch von einem Eingang, der
nichts liefert – etwa Bluetooth-Kopfhörer. Dafür gibt es die Auswahlliste
*Mikrofon*; sie wird beim Start einmal gelesen, ein später angeschlossenes Gerät
erscheint erst nach einem Neustart.

## Starten

```bash
python main.py
```

## Bedienung

| Aktion | Wirkung |
|---|---|
| Klick auf ein Thumbnail (Startseite) | zeigt das Foto darüber in der Vorschau |
| *Zur Karte* | öffnet die Karte |
| Klick auf einen Marker | öffnet den Ort mit Foto |
| Auswahlliste *Mikrofon* | wählt das Eingabegerät für die Aufnahme |
| *Aufnahme starten* | nimmt 5 Sekunden auf und spielt sie verhallt ab |
| Regler *Hallanteil* | 0 % nur Originalstimme, 100 % nur Hall |
| *Abspielen* | wiederholt die Wiedergabe mit dem aktuellen Reglerwert |
| **ESC** | eine Seite zurück: Ort → Karte → Startseite |

Die **Startseite** ist zweigeteilt: links die Erklärung, rechts eine Galerie mit
den Fotos aus `galery_fotos/`, die beim Start gelesen werden. Ein Klick auf ein
Thumbnail zeigt das Foto darüber groß.

Während der Aufnahme bleibt das Fenster bedienbar: statt zu warten, sieht ein
`QTimer` alle 100 ms nach, ob sie fertig ist, und dazwischen kann Qt zeichnen und
auf Eingaben reagieren. Aufnahme, Wiedergabe und Mikrofonauswahl sind so lange
gesperrt, weil sie dasselbe Gerät belegen würden; ESC verwirft die Aufnahme.

## Die wichtigsten Funktionen

**`utils.fft_convolve(signal, ir)`** – das Kernstück. Eine Faltung im Zeitbereich
ist dasselbe wie eine Multiplikation im Frequenzbereich, über die FFT aber viel
schneller: direkt gerechnet bräuchten fünf Sekunden Aufnahme und fünf Sekunden
Impulsantwort rund 10¹⁰ Multiplikationen, über die FFT sind es Millisekunden.
`scipy.signal.fftconvolve` verlängert beide Signale vorher mit Nullen, weil die
FFT sonst im Kreis faltet und das Ende in den Anfang zurückrutschen würde.

**`utils.trim_impulse(samples)`** – schneidet die Impulsantwort zu: vorne bis zum
lautesten Wert, dem Direktschall, hinten ab einem Tausendstel des Spitzenwerts
(etwa −60 dB). Der Schnitt vorne sorgt dafür, dass Original und Hall beim Mischen
zeitlich zusammenpassen.

**`utils.normalize(samples, peak)`** – skaliert ein Signal auf einen festen
Höchstwert, damit die Wiedergabe nicht übersteuert.

**`gui.load_scaled(path, width, height)`** – lädt ein Foto und verkleinert es
schon beim Einlesen. Voll geladen bräuchten die bis zu 4000 × 4000 Pixel großen
Fotos rund 64 MB je Bild; `QImageReader.setScaledSize` lässt den JPEG-Decoder
direkt in der gebrauchten Größe arbeiten.

**`ImpulseResponse.apply_to(voice, mix)`** – faltet die Aufnahme mit dem Raum und
mischt Original und Hall. Da die Faltung viele Werte aufaddiert, wird das
Hallsignal vorher auf den Pegel des Originals gebracht; sonst hätte der Regler
kaum Wirkung.

## Projektstruktur

```
├── main.py             Startpunkt, fängt Fehler beim Programmstart ab
├── gui.py              MainWindow, StartView (Startseite), MapView (Karte),
│                       LocationView (Ortsseite)
├── models.py           Klassen ImpulseResponse und Location
├── services.py         Orte einlesen, Aufnahme, Wiedergabe
├── utils.py            Signalverarbeitung (Faltung, Zuschneiden, Skalieren)
├── locations.json      Orte mit Kartenposition, Foto und Impulsantwort
├── test_hallburg.py    Tests
├── assets/             Kartenbild, Fotos, Impulsantworten
└── galery_fotos/       Fotos für die Galerie auf der Startseite
```

## Objektorientierung

Zwei Klassen in `models.py`:

- **`ImpulseResponse`** lädt im Konstruktor eine WAV-Datei und bereitet sie auf.
  Attribute sind `samples`, `samplerate` und `duration`, die Methode `apply_to`
  legt den Hall auf eine Sprachaufnahme.
- **`Location`** beschreibt einen Ort mit Name, Kartenposition, Foto und
  Impulsantwort. Die Methode `load_ir` lädt die zugehörige Datei.

Auf Vererbung wurde bewusst verzichtet, weil die beiden Klassen nichts gemeinsam
haben, das eine Oberklasse rechtfertigen würde.

## Fehlerbehandlung

`try-except` steht dort, wo tatsächlich etwas schiefgehen kann:

| Stelle | Abgefangen |
|---|---|
| `main.py` | `FileNotFoundError` und `json.JSONDecodeError` beim Einlesen von `locations.json` |
| `services.load_locations` | `KeyError` und `TypeError` je Eintrag – ein unvollständiger Ort wird übersprungen, statt die ganze Karte zu verlieren |
| `gui.LocationView.show_location` | `soundfile.LibsndfileError` – deckt fehlende *und* beschädigte WAV-Dateien ab |
| `gui.LocationView.record_and_play` und `play_voice` | `sounddevice.PortAudioError` – kein Audiogerät oder Gerät belegt |

Ein **fehlendes Foto** wird dagegen mit einer if-Abfrage geprüft, weil das hier
besser passt als `try-except`. Beachtenswert: `soundfile` meldet eine fehlende
Datei nicht als `FileNotFoundError`, sondern ebenfalls als `LibsndfileError` –
ein `except FileNotFoundError` würde den Fall gar nicht erfassen.

## Tests

```bash
python -m unittest test_hallburg.py
```

11 Tests, die ohne Aufnahmen laufen. Geprüft werden unter anderem:

- Die Faltung mit einem Einheitsimpuls gibt das Signal unverändert zurück.
- Die Faltung stimmt mit `np.convolve` als unabhängigem Vergleich überein.
- `normalize` erreicht den Zielpegel und stürzt bei Stille nicht ab.
- `trim_impulse` legt den lautesten Wert an den Anfang.
- `locations.json` fehlt, ist kein gültiges JSON oder ein Eintrag ist
  unvollständig.

Zusätzlich von Hand geprüft: Aufnahme und Wiedergabe bei 0 %, 70 % und 100 %
Hallanteil, fehlende und beschädigte WAV-Dateien, fehlendes Foto, fehlendes
Kartenbild und ein nicht verfügbares Mikrofon.
