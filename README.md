# Klarify prototype

Sound-alert demo: a laptop plays **synthetic** home sounds into an ESP32 over USB; the board classifies them and serves alerts to a phone page (colour flash, vibration, history).

## Just want to run it?
Download `klarify-demo.zip` from the **Releases** page, unzip it, and follow the `README.txt` inside.
Then do the 10-minute trial in [docs/trial-checklist.md](docs/trial-checklist.md).

## Build from source
Python 3.13, PlatformIO, MSYS2 g++ (for native tests).
```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt scikit-learn pyserial pytest pyinstaller
.venv\Scripts\python -m pytest
.venv\Scripts\python tools\build_release.py
```
Accuracy figures are measured on synthetic sounds only. The firmware has been compiled but not yet run on a real board.
