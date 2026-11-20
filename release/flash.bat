@echo off
setlocal
cd /d "%~dp0"
echo.
echo ==============================================
echo   Klarify - flashing the ESP32
echo ==============================================
echo Make sure the board is plugged in with a DATA USB cable,
echo and that no other program (Arduino serial monitor) is using it.
echo.
esptool.exe --chip esp32 --baud 460800 write-flash 0x0 firmware.bin
if errorlevel 1 (
  echo.
  echo FLASHING FAILED.
  echo  1. Try another USB cable or port.
  echo  2. Hold the BOOT button on the board while this window says "Connecting....", then release.
  echo  3. Check Device Manager - Ports: a "Silicon Labs CP210x" entry must appear.
  pause
  exit /b 1
)
echo.
echo DONE. Next:  klarify-feeder.exe --selftest
pause
