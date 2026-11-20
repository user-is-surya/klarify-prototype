# Klarify trial run (10 minutes, do it well before the review)

The ESP32 firmware has only been compiled so far, never run on a real board. This trial is its first real test.
Do it on the friend's laptop with the board, using the unzipped `klarify-demo` folder.

| # | Do this | You should see | If not |
|---|---------|----------------|--------|
| 1 | Plug in the board. Device Manager > Ports | "Silicon Labs CP210x" with a COM number | other USB cable / port |
| 2 | Double-click `flash.bat` | ends with "Hash of data verified" and DONE | hold BOOT during "Connecting...." |
| 3 | `klarify-feeder.exe --selftest` | `OK klarify-fw 1.0` | wait 3 s after flashing and retry; close any serial monitor |
| 4 | Phone: join Wi-Fi `Klarify-Demo`, open `http://192.168.4.1` | dark "Listening..." page, **grey** dot, "Simulated input" badge, banner "Input idle" (no feeder yet; the dot turns green once the feeder runs) | rejoin Wi-Fi; disable the mobile-data switch; if the page never loads, turn mobile data off |
| 5 | `klarify-feeder.exe` (or `klarify-feeder.exe --port COMx` if it says No ESP32 found), press `1` | within about 2 s phone turns RED "Cooker whistle", dot turns green, banner "Input idle" disappears, onboard LED blinks fast (if your board has one on GPIO2) | see README troubleshooting |
| 6 | Press `2`, `3`, `4`, `5` in turn (wait for each to finish) | blue Doorbell, amber Baby crying, red Smoke alarm, blue Microwave beep, history list fills | note which sound is wrong |
| 7 | Press `+` four times (noisiest setting), then each of `1`-`5` | each sound should still be detected. A wrong extra alert for another sound can happen at this setting - that is expected on synthetic data; **write down how often** | note it |
| 8 | Tick "Mute" for Doorbell on the phone, press `2` | no colour flash, history shows "Doorbell (muted)" struck through | |
| 9 | Android only: tap "Tap to enable vibration", press `4` | phone vibrates | iPhone cannot vibrate from a web page |
| 10a | Press `4`, then quit the feeder with `q` while the alarm plays (board still powered) | within about 6 s the red clears; banner "Input idle" within about 3 s | |
| 10b | Start the feeder again right away | **no** red "Smoke alarm" appears from the old sound; the portal stays quiet until you press a key | tell us - this is the stale-audio bug we fixed |
| 10c | Press `4`, then pull the USB cable (this also switches the board off - it has no other power) | feeder says "Lost the connection"; within about 1-2 s the phone shows banner "Reconnecting..." and a grey "No signal" panel - **not** a stuck red screen | |
| 12 | Portal footer | shows "Firmware 1.2" and an Update link | tell us |
| 13 | Phone on Klarify-Demo: open `http://192.168.4.1/update`, wrong password, any file | "Wrong password." and nothing changes | |
| 14 | Same page, right password (`klarify`), choose `firmware.bin` (the USB file) | "That file is not an update image. Use klarify-ota.bin" and the board keeps working | |
| 15 | Same page, password `klarify`, choose `klarify-ota.bin` | progress bar, "Installed...", board restarts, portal comes back showing the same version; alerts still work | write down how long the restart took |
| 11 | Leave the feeder idle 2 minutes in `0` (background) | no alerts at all | count and note any false alerts |

Please send back: a photo of the phone for each colour, and anything in the "if not" column that happened.

Bring to the review: the laptop, the board, a USB cable, the phone. Everything works without internet.

## Things only the real board can answer (please report each)
- Does the board have a small blue LED, and does it blink on alerts? (GPIO2; some boards have none.)
- Does the portal ever flash "Reconnecting..." while idle? (Chrome can hold the board's single web connection for a few seconds.)
- Does the phone keep the Klarify-Demo Wi-Fi without internet, and reach 192.168.4.1 with mobile data on?
- Does the board stay up (no random reboots) while Wi-Fi is serving the phone and audio is streaming, on the laptop's USB port?
- Does opening the feeder reboot the board? (It should not; if it does, the first second after start is quiet.)
