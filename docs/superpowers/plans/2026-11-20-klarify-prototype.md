# Klarify Review-2 Prototype Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A synthetic-sound generator, an on-ESP32 sound classifier and a phone-facing alert portal, shipped as a no-install zip for a friend's Windows laptop that holds the board.

**Architecture:** Python synthesises sounds and streams raw 8 kHz PCM over USB serial. Portable header-only C++ (`firmware/include/core/`) does windowing, features, a decision tree exported from Python, a two-in-a-row alert engine and a state store. The same core is compiled natively (g++) for tests and as a board-less `sim_device`, and wrapped by a thin Arduino `main.cpp` that also hosts the portal on a SoftAP.

**Tech Stack:** Python 3.13 (numpy, scikit-learn, pyserial, pytest, PyInstaller), C++17 header-only core, PlatformIO (espressif32, Arduino, board `esp32dev`), esptool, vanilla HTML/JS portal, g++ (MSYS2 ucrt64, already installed).

**Spec:** `docs/superpowers/specs/2026-11-20-klarify-prototype-design.md`

**Commits:** the folder is not a git repo and nobody asked for commits, so there are no commit steps.

## Global Constraints
- Board: ESP32-WROOM-32 38-pin NodeMCU (`esp32dev`), USB serial **921600 baud**, onboard LED **GPIO2**; no other hardware. Board is NOT available here: firmware is compile-only; everything else is tested here.
- Audio: **8 kHz, 16-bit mono**, **1 s window (8000 samples)**, **hop 0.5 s (4000)**, 512-point FFT, frame step 256, stream blocks of 400 samples (50 ms).
- Classes (index order everywhere): `background, cooker_whistle, doorbell, baby_cry, smoke_alarm, microwave_beep`.
- Levels: urgent/red = smoke_alarm, cooker_whistle; important/amber = baby_cry; info/blue = doorbell, microwave_beep; background = no alert.
- Alert needs **two consecutive windows** with the same non-background label.
- LED: urgent fast continuous blink, important two blinks, info one blink.
- Portal: ESP32 SoftAP SSID `Klarify-Demo`, no internet, polls `/api/state` every ~300 ms, always shows a "simulated input" badge, per-sound mute, history log.
- Accuracy is measured on synthetic sounds only and must be labelled as such everywhere it is printed.
- Delivery is a zip needing no installs on a Windows machine with the CP210x driver; Python source stays in `tools/` as fallback.

## Review Focus
1. Garbage bytes, half frames and a bad checksum mid-stream (boot noise from the ESP32, unplug/replug) must resync, not wedge the parser. Pinned in Task 4.
2. All-zero (silence) and full-scale clipped windows must give finite features and class `background`, never NaN or a crash. Pinned in Tasks 2 and 3.
3. Feeder stopped or cable pulled mid-demo: portal must say input is idle instead of freezing on the last alert. Pinned in Task 5.
4. A muted sound must never flash or buzz but should still appear in the history marked muted. Pinned in Task 4.
5. A short sound that starts mid-window, or noise at the worst setting (3 dB), must not crash; accuracy is reported, not assumed. Pinned in Tasks 1, 2 and 8.

---

### Task 1: Environment and synthetic sound generator

**Files:**
- Create: `requirements.txt`, `pytest.ini` (`testpaths = tests`, `pythonpath = tools`), `tools/sounds.py`, `tests/test_sounds.py`

**Interfaces:**
- Produces: `SOUNDS: list[str]` (class order above); `LEVELS: dict[str, str]` mapping sound -> `"none"|"info"|"important"|"urgent"`; `SAMPLE_RATE = 8000`; `render(sound: str, duration_s: float, snr_db: float, rng: np.random.Generator) -> np.ndarray` (int16, mono, length `round(duration_s*8000)`, never clipping).

- [ ] **Step 1: Create the venv and install.** `python -m venv .venv`, then `.venv\Scripts\python -m pip install numpy scikit-learn pyserial pytest pyinstaller esptool platformio`; pin the installed versions into `requirements.txt`. Expected: `.venv\Scripts\python -c "import numpy, sklearn, serial, PyInstaller"` exits 0.
- [ ] **Step 2: Write failing tests** in `tests/test_sounds.py`: `test_sound_list_and_levels` (exact list/levels from Global Constraints); `test_render_shape_dtype` (`render("doorbell",2.0,20,rng).shape == (16000,)`, dtype int16); `test_render_is_deterministic_for_same_seed`; `test_no_clipping_any_sound_any_snr` (all sounds, snr 3 and 30, `abs(max) < 32767`); `test_dominant_frequency_ranges` at snr 30 using the loudest 0.1 s: cooker_whistle 2500–3500 Hz, smoke_alarm 2900–3300, microwave_beep 2000–2400, doorbell within ±20 Hz of 523 or 659.
- [ ] **Step 3: Run** `.venv\Scripts\python -m pytest tests/test_sounds.py` → FAIL (module missing).
- [ ] **Step 4: Implement `tools/sounds.py`.** Signatures above. Sound signatures (random pitch/phase per call, noise added last to the requested SNR over the whole clip, then scaled to ~0.6 full scale):
  - cooker_whistle: tone 2500–3500 Hz, ±4 % pitch wobble at 5–8 Hz, 15 % breathy noise, 1.5 s on / 0.5 s off.
  - smoke_alarm: pure 2900–3300 Hz tone, 0.2 s on / 0.2 s off, 3 beeps then 1 s pause.
  - microwave_beep: 2000–2400 Hz, 0.25 s on / 0.25 s off, 3 beeps then 1.5 s pause.
  - doorbell: 659 Hz then 523 Hz, 0.4 s each with exponential decay and a 2nd harmonic, repeated every 2 s.
  - baby_cry: f0 350–550 Hz, 6–8 harmonics with falling amplitude, 5–6 Hz vibrato ±5 %, falling pitch contour, 0.8 s on / 0.3 s off.
  - background: low-level pink-ish noise plus occasional short clicks and an optional 50 Hz hum with harmonics.
- [ ] **Step 5: Run the tests** → PASS.

### Task 2: Reference features, dataset, trained decision tree

**Files:**
- Create: `tools/features.py`, `tools/dataset.py`, `tools/train.py`, `tests/test_features.py`, `tests/test_train.py`
- Generated: `firmware/include/model.h`

**Interfaces:**
- Consumes: Task 1 `render`, `SOUNDS`.
- Produces: `FEATURE_NAMES: list[str]` (order below); `extract(window: np.ndarray) -> np.ndarray` (int16 shape (8000,) in, float32 shape (10,) out); `make_dataset(n_per_class: int, seed: int, snr_range=(3.0, 30.0)) -> tuple[np.ndarray, np.ndarray]` (X (N,10), y (N,)): renders 4 s clips, takes a 1 s window at a random offset; `train(out_header: Path, seed: int = 0) -> TrainResult` with `.tree` (fitted `DecisionTreeClassifier`, `max_depth=8`) and `.metrics` (`accuracy`, `recall` per class, `confusion`; computed on a held-out set at snr 10–30, printed with the words "synthetic data"); writes `model.h` exposing `static inline int model_predict(const float* f)` (nested if/else).

Feature definition (x = samples/32768; this is the algorithm both Python and C++ must follow exactly):
frames i = 0..29, start `i*256`, length 512; `rms_i` of raw frame; spectrum `mag_i[k]`, k = 1..255, from a periodic Hann window `0.5*(1-cos(2πn/512))`; `peak_i` = argmax k; `max_rms` = max rms_i; frame i is *active* if `rms_i >= 0.5*max_rms`; if `max_rms < 1e-4` return zeros except flatness = 1. Over active frames A, bins × 15.625 Hz:
`0 dom_freq` = lower median of peak_i·15.625; `1 centroid` = mean of Σk·mag/Σmag·15.625; `2 flatness` = mean of exp(mean(log(mag+1e-9)))/(mean(mag)+1e-9); `3 bandwidth` = mean of sqrt(Σ(k−c)²mag/Σmag)·15.625; `4 duty` = |A|/30; `5 pulses` = count of active frames whose predecessor is not active (frame 0 counts if active); `6 freq_std` = population std of peak_i·15.625; `7 peak_ratio` = mean of mag[peak]/Σmag; `8 rms_cv` = std(rms)/(mean(rms)+1e-9) over all 30 frames; `9 harm2` = mean of max(mag[2p−1..2p+1] clipped to ≤255)/(mag[p]+1e-9).

- [ ] **Step 1: Failing feature tests** (`test_features.py`): `test_silence_gives_zeros_and_flatness_one_no_nan`; `test_pure_3khz_tone` (dom_freq within 3000±16, duty == 1.0, pulses == 1, peak_ratio > 0.3); `test_pulsed_tone_has_multiple_pulses` (0.2 s on/off → pulses ≥ 2); `test_white_noise_is_flat` (flatness > 0.5); `test_full_scale_square_wave_is_finite`; `test_output_dtype_and_len` (float32, 10).
- [ ] **Step 2: Failing train tests** (`test_train.py`): `test_train_meets_accuracy_on_synthetic` (accuracy ≥ 0.90, every class recall ≥ 0.80 with `n_per_class=300`); `test_header_written_and_contains_model_predict`; `test_training_is_deterministic_for_seed`.
- [ ] **Step 3: Run** both files → FAIL.
- [ ] **Step 4: Implement** `features.py`, `dataset.py`, `train.py` as above; also add `if __name__ == "__main__"` in `train.py` running `train(Path("firmware/include/model.h"))` with `n_per_class=1500`. If recall misses the bar, tune the synth ranges/tree depth, not the thresholds in the tests.
- [ ] **Step 5: Run tests** → PASS, then `.venv\Scripts\python tools/train.py` → writes `firmware/include/model.h` and prints metrics labelled synthetic.

### Task 3: C++ core, part A: config, FFT, features, classifier (parity with Python)

**Files:**
- Create: `firmware/include/core/config.h`, `fft.h`, `features.h`, `classifier.h`; `tests/native/test_features_model.cpp`; `tests/native_fixtures.py`; `tests/test_core_native.py`

**Interfaces:**
- Consumes: Task 2 feature definition and generated `model.h`.
- Produces: in `config.h`: constants `kSampleRate, kWindow, kHop, kFrame, kFrameStep, kNumFeatures=10, kNumClasses=6, kBlockSamples`; `enum Level {LEVEL_NONE=0, LEVEL_INFO, LEVEL_IMPORTANT, LEVEL_URGENT}`; `inline const char* const kClassNames[6]`; `inline const Level kClassLevel[6]`; `inline const char* const kClassLabels[6]` (display names, e.g. "Cooker whistle"). `features.h`: `void extract_features(const int16_t* window, float* out)` (own radix-2 FFT, no libs). `classifier.h`: `int classify(const float* features)` (calls `model_predict`). Python: `write_feature_fixtures(dir: Path, n: int = 60, seed: int = 1)` writes `clips.bin` (n×8000 int16), `features.bin` (n×10 float32 from `extract`), `pred.bin` (n int32 from `TrainResult.tree.predict`), mixing all sounds, snr 3–30, plus one silent and one full-scale clip.

- [ ] **Step 1: Failing test** `test_core_native.py::test_features_and_model_parity`: writes fixtures to `tmp_path`, compiles `tests/native/test_features_model.cpp` with `g++ -std=c++17 -O1 -I firmware/include` (path to g++ from `shutil.which` or `C:\msys64\ucrt64\bin\g++.exe`), runs it with the fixture dir, asserts exit 0. The C++ asserts: ≥ 95 % of (clip, feature) pairs within `max(1e-3, 0.02*|expected|)`; predicted class equal for ≥ 98 % of clips; no NaN/inf for the silent and clipped clips and their class is `background` (0).
- [ ] **Step 2: Run** → FAIL (headers missing).
- [ ] **Step 3: Implement** the four headers (header-only, `static inline`/`inline`, no Arduino includes, `float` math).
- [ ] **Step 4: Run** → PASS.

### Task 4: C++ core, part B: serial protocol, alert engine, pipeline

**Files:**
- Create: `firmware/include/core/protocol.h`, `alert.h`, `pipeline.h`; `tools/protocol.py`; `tests/native/test_protocol_alert_pipeline.cpp`; `tests/test_protocol.py`
- Modify: `tests/test_core_native.py` (add test)

**Interfaces:**
- Produces (Python `protocol.py`): `PCM = 0x01`, `PING = 0x02`; `encode_frame(ftype: int, payload: bytes) -> bytes` = `0x4B 0x4C, type, len_lo, len_hi, payload, checksum` (checksum = XOR of type, len bytes and payload); `encode_pcm(seq: int, samples: np.ndarray) -> bytes` (payload = `seq` u16 LE + int16 LE samples); `encode_ping() -> bytes`.
- Produces (C++): `struct Frame { uint8_t type; uint16_t len; uint8_t payload[820]; }`; `class FrameParser { bool feed(uint8_t byte, Frame& out); }` (true when a valid frame completes; resyncs on bad magic/length/checksum). `enum Outcome {OUT_NONE, OUT_ALERT, OUT_MUTED}`; `struct AlertEvent { int cls; Level level; uint32_t ms; }`; `class AlertEngine { Outcome update(int cls, uint32_t now_ms, AlertEvent& ev); void set_muted(int cls, bool m); bool is_muted(int cls) const; }`: fires on 2 consecutive same non-background windows, then again only if the label changes or ≥ 4000 ms since the last event; muted returns `OUT_MUTED` and no alert. `struct WindowResult { int cls; float features[10]; Outcome outcome; AlertEvent ev; }`; `class Pipeline { explicit Pipeline(AlertEngine&); bool push_samples(const int16_t* s, size_t n, uint32_t now_ms, WindowResult& r); }`: first window after 8000 samples, then one every 4000 samples (n ≤ 4000 per call).

- [ ] **Step 1: Failing tests.** Native (`test_protocol_alert_pipeline.cpp`): `parser_resyncs_after_garbage` (Python-written byte stream: random garbage, a truncated frame, a frame with bad checksum, then 3 good frames → exactly the 3 good frames parsed in order); `two_in_a_row_required`; `background_never_alerts`; `refire_same_label_only_after_4s`; `label_change_fires_immediately_after_confirmation`; `muted_returns_muted_not_alert`; `pipeline_first_window_after_8000_samples`; `pipeline_hop_is_4000_samples`. Python (`test_protocol.py`): `test_encode_pcm_length_and_checksum` (length = 5 + 2 + 2·n + 1), `test_ping_frame_bytes`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** headers and `protocol.py`.
- [ ] **Step 4: Run** → PASS.

### Task 5: C++ core, part C: state store, LED pattern, board-less simulator

**Files:**
- Create: `firmware/include/core/state.h`, `led.h`; `tests/native/sim_device.cpp`; `tests/native/test_state_led.cpp`
- Modify: `tests/test_core_native.py`

**Interfaces:**
- Consumes: Task 4 types.
- Produces: `class StateStore { void on_pcm(uint32_t now_ms); void on_window(const WindowResult& r, uint32_t now_ms); void set_muted(int cls, bool m); size_t to_json(char* buf, size_t cap, uint32_t now_ms) const; }`. JSON: `{"input":"synthetic","connected":bool,"uptime_ms":n,"seq":n,"current":null|{"sound","label","level","age_ms"},"history":[{"t_ms","sound","level","muted"}…],"muted":["doorbell",…]}`; `connected` = PCM seen within last 3000 ms; `current` = last ALERT within 6000 ms else null; `seq` increments on each alert; history newest-first, max 20, includes muted hits marked `"muted":true`. `bool led_state(Level level, uint32_t ms_since_event)`: urgent 100/100 ms blink for 5 s; important two 200 ms blinks; info one 300 ms blink; otherwise off. `sim_device.cpp`: reads protocol frames on stdin; PING → prints `PONG klarify-fw 1.0`; each completed window prints `CLS <class_name> <none|alert|muted> <t_ms>`; time derived from sample count (deterministic); exits at EOF.

- [ ] **Step 1: Failing tests** (`test_state_led.cpp`): `connected_false_after_3s_without_pcm` (Review Focus 3); `current_expires_after_6s`; `history_capped_at_20_newest_first`; `muted_hit_recorded_with_muted_true_and_no_seq_increment` (Review Focus 4); `json_fits_in_1024_bytes_when_history_full`; `led_urgent_blinks_continuously_then_stops_after_5s`; `led_important_two_blinks`; `led_info_one_blink`. Python wrapper test compiles and runs it, asserts exit 0.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** the headers and `sim_device.cpp`. **Step 4: Run** → PASS, and `g++ ... sim_device.cpp -o build/sim_device.exe` compiles.

### Task 6: Portal page, embed script, mock server

**Files:**
- Create: `firmware/portal/index.html`, `tools/embed_portal.py`, `tools/mock_portal_server.py`, `tests/test_portal.py`
- Generated: `firmware/include/portal.h`

**Interfaces:**
- Consumes: Task 5 JSON schema and `POST /api/mute?sound=<name>&on=<0|1>`.
- Produces: `embed_portal.py` writes `portal.h` with `static const char PORTAL_HTML[] PROGMEM = R"KL(...)KL";`; `mock_portal_server.py [--port 8080]` serves the page and a scripted `/api/state` that cycles every sound (with the real JSON shape) and accepts mute posts.

Portal behaviour: single file, no external requests, mobile first; polls every 300 ms; full-screen background by `current.level` (urgent red, important amber, info blue, idle dark with "Listening…"); big icon + label + time; history list; mute toggle per sound; always-visible "Simulated input" badge; "Input idle" banner when `connected` is false (Review Focus 3); "Reconnecting…" banner after 2 failed polls; "Tap to enable vibration" button, and vibrate only on a new `seq`, patterns urgent `[600,200,600,200,600]`, important `[300,150,300]`, info `[150]`.

- [ ] **Step 1: Failing tests** (`test_portal.py`): `test_embed_writes_header_with_portal_markers` (contains `PORTAL_HTML`, "Simulated input", "/api/state"); `test_html_has_no_external_urls` (no `http://`/`https://` besides inside comments); `test_mock_state_matches_schema` (start mock server in a thread, fetch `/api/state`, keys exactly as above); `test_mock_mute_roundtrip`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** the three files. **Step 4: Run** → PASS.
- [ ] **Step 5: Manual look.** Run `.venv\Scripts\python tools/mock_portal_server.py`, open `http://localhost:8080` in a phone-sized browser window: confirm red/amber/blue flashes, history fills, mute works, stopping the server shows "Reconnecting…". If a headless browser is easy to use (webapp-testing skill), take screenshots instead.

### Task 7: Firmware wrapper and board build

**Files:**
- Create: `firmware/platformio.ini`, `firmware/src/main.cpp`

**Interfaces:**
- Consumes: all `core/` headers, `model.h`, `portal.h`.
- Produces: a flashable firmware: USB serial 921600 (`Serial.setRxBufferSize(8192)` before `begin`), SoftAP `Klarify-Demo` (open), `WebServer` on 80 with `/` (portal), `/api/state`, `/api/mute`; loop reads serial bytes → `FrameParser` → on `PCM` call `StateStore::on_pcm` and `Pipeline::push_samples` → on window `StateStore::on_window` and print `CLS …`; on `PING` print `PONG klarify-fw 1.0`; drives GPIO2 via `led_state`; calls `server.handleClient()` every loop. `platformio.ini`: env `esp32dev`, `framework = arduino`, `monitor_speed = 921600`, `-std=gnu++17`.

- [ ] **Step 1: Write `platformio.ini` and `main.cpp`** (thin: no logic that is not in `core/`).
- [ ] **Step 2: Build** `.venv\Scripts\pio run -d firmware`. Expected: `SUCCESS`; note RAM/flash usage and record it (RAM must stay under about 60 %). Fix include/lint problems without moving logic out of `core/`. Needs internet on the first build to fetch the espressif32 platform.

### Task 8: Feeder CLI and board-less end-to-end test

**Files:**
- Create: `tools/feed.py`, `tests/test_feed_sim.py`

**Interfaces:**
- Consumes: Tasks 1, 4, 5 (`render`, `encode_pcm`, `encode_ping`, `sim_device.exe`).
- Produces: `find_port() -> str | None` (first serial port whose description contains `CP210`); `class SoundSource` with `set_sound(name)`, `set_noise_level(i)` (levels → snr_db `[30,20,15,10,6,3]`, default index 2) and `next_block() -> np.ndarray` (400 int16, continuous, phase-continuous within a sound); CLI `python tools/feed.py [--port COMx | --sim PATH_TO_SIM_EXE] [--selftest] [--script "doorbell:8,background:4,..."] [--speed 1.0] [--auto]`. Interactive keys (msvcrt): `1`–`5` sounds in class order after background, `0` background, `+`/`-` noise level, `a` auto playlist, `q` quit. Self-test: ping every 0.5 s up to 5 s, expect `PONG klarify-fw …`, print `OK` and exit 0, else exit 1. Reader thread decodes device lines with `errors="ignore"` (boot garbage is expected) and shows the latest `CLS` line. `--speed 0` sends without pacing (tests). `--sim` runs the simulator as a subprocess and wires its stdin/stdout instead of a serial port.

- [ ] **Step 1: Failing tests** (`test_feed_sim.py`, builds `sim_device.exe` with g++ first): `test_selftest_against_sim_prints_ok`; `test_each_sound_detected_at_default_noise` (script each of the 5 sounds for 8 s with 4 s background between, level 2; sim output has an `alert` line for that sound's class during its segment); `test_no_false_alerts_in_30s_background_at_default_noise`; `test_worst_noise_level_does_not_crash` (script all sounds at level 5; process exits 0 and prints at least one `CLS` line; accuracy is not asserted); `test_find_port_returns_none_without_device_or_a_string`; `test_soundsource_block_is_400_int16`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement `feed.py`.** **Step 4: Run** → PASS. If detections are missing, retrain (Task 2 step 5) with wider variation before touching the engine.

### Task 9: Release bundle for the friend's laptop

**Files:**
- Create: `tools/build_release.py`, `release/flash.bat`, `release/README.txt`
- Output: `dist/klarify-demo/` and `dist/klarify-demo.zip`

**Interfaces:**
- Produces: `build_release.py` does, in order: `pio run`; merge bootloader, partitions, `boot_app0` and app into one `firmware.bin` (offsets `0x1000`, `0x8000`, `0xe000`, `0x10000`, flash mode dio, 4MB) with esptool's `merge_bin`; PyInstaller `--onefile` builds of `klarify-feeder.exe` (from `feed.py`) and `esptool.exe`; copies `flash.bat` and `README.txt`; zips. `flash.bat` runs `esptool.exe --chip esp32 --baud 460800 write_flash 0x0 firmware.bin` (esptool auto-finds the port), then prints the next steps. `README.txt` (one page, plain language): flash, run `klarify-feeder.exe --selftest`, run `klarify-feeder.exe`, join `Klarify-Demo` Wi-Fi on the phone, open `http://192.168.4.1`, key list, what the panel should see per sound, and troubleshooting: hold BOOT while flashing if it will not connect, antivirus may flag the exe (use the Python fallback), phone auto-leaves Wi-Fi with no internet (turn off "switch to mobile data"), iPhone has no vibration.

- [ ] **Step 1: Write the three files** and run `.venv\Scripts\python tools/build_release.py`. Expected: `dist/klarify-demo.zip` exists and contains `firmware.bin`, `esptool.exe`, `klarify-feeder.exe`, `flash.bat`, `README.txt`.
- [ ] **Step 2: Smoke test the packaged exe** (board-less): from an unzipped copy run `klarify-feeder.exe --sim <path to sim_device.exe> --selftest` → prints `OK`; and the same with `--script "cooker_whistle:8" --speed 0` → an `alert cooker_whistle` line.
- [ ] **Step 3: Write `docs/trial-checklist.md`**: the 10-minute trial for the friend (flash, self-test, each sound, phone portal, pull the cable → "Input idle" within 3 s), with expected results, to be done well before the review.

---

## Self-review
- **Spec coverage:** G1 Tasks 2–4/7; G2 Task 8; G3 Task 6/7; G4 Task 1/3; G5 Task 4; G6 Task 5/7; delivery Task 9; testing/evidence Tasks 2, 8; risks (untested hardware: self-test + trial checklist; AV: Python fallback) Tasks 8–9.
- **Types:** `Level`, `Outcome`, `AlertEvent`, `WindowResult`, `kClassNames` and the feature order are defined once (Tasks 2–4) and reused unchanged in 5–8.
- **Known limit:** the first real run on the ESP32 happens on the friend's setup; serial throughput and SoftAP behaviour under load are the least-tested parts.
