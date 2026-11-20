# Klarify trial run (10 minutes, do it well before the review)

The ESP32 firmware has only been compiled so far, never run on a real board. This trial is its first real test.
Do it on the friend's laptop with the board, using the unzipped `klarify-demo` folder.

| # | Do this | You should see | If not |
|---|---------|----------------|--------|
| 1 | Plug in the board. Device Manager > Ports | "Silicon Labs CP210x" with a COM number | other USB cable / port |
| 2 | Double-click `flash.bat` | ends with "Hash of data verified" and DONE | hold BOOT during "Connecting...." |
| 3 | `klarify-feeder.exe --selftest` | `OK klarify-fw 1.0` | wait 3 s after flashing and retry; close any serial monitor |
| 4 | Phone: join Wi-Fi `Klarify-Demo`, open `http://192.168.4.1` | dark "Listening..." page, green dot, "Simulated input" badge, banner "Input idle" | rejoin Wi-Fi; disable mobile-data switch |
| 5 | `klarify-feeder.exe`, press `1` | within about 2 s phone turns RED "Cooker whistle", LED blinks fast, banner "Input idle" disappears | see README troubleshooting |
| 6 | Press `2`, `3`, `4`, `5` in turn (wait for each to finish) | blue Doorbell, amber Baby crying, red Smoke alarm, blue Microwave beep, history list fills | note which sound is wrong |
| 7 | Press `+` four times, repeat `1` | still detected (noisier) | note it |
| 8 | Tick "Mute" for Doorbell on the phone, press `2` | no colour flash, history shows "Doorbell (muted)" struck through | |
| 9 | Android only: tap "Tap to enable vibration", press `4` | phone vibrates | iPhone cannot vibrate from a web page |
| 10 | Pull the USB cable during a demo | feeder says "Lost the connection"; phone shows "Input idle" within 3 s | |
| 11 | Leave the feeder idle 2 minutes in `0` (background) | no alerts at all | count and note any false alerts |

Please send back: a photo of the phone for each colour, and anything in the "if not" column that happened.

Bring to the review: the laptop, the board, a USB cable, the phone. Everything works without internet.
