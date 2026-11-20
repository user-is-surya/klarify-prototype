@echo off
rem Klarify - install a new firmware over Wi-Fi (no USB needed).
rem Before running: download the new kit, then join the "Klarify-Demo" Wi-Fi on this laptop.
rem The new file must be called klarify-ota.bin and sit next to this script (or in the current folder).
setlocal
if "%KLARIFY_HOST%"=="" set KLARIFY_HOST=192.168.4.1
if "%KLARIFY_KEY%"=="" set KLARIFY_KEY=klarify
set "FILE=klarify-ota.bin"
if not exist "%FILE%" set "FILE=%~dp0klarify-ota.bin"
set "RESP=%TEMP%\klarify_ota_resp.txt"
set "CODEF=%TEMP%\klarify_ota_code.txt"
del "%RESP%" "%CODEF%" 2>nul

echo.
echo ==============================================
echo   Klarify - installing update over Wi-Fi
echo ==============================================
if not exist "%FILE%" (
  echo Cannot find klarify-ota.bin. Put it in the same folder as update.bat.
  goto fail
)
where curl.exe >nul 2>nul
if errorlevel 1 (
  echo This needs curl.exe, which comes with Windows 10 and 11. Use the update page instead:
  echo   join the Klarify-Demo Wi-Fi and open http://%KLARIFY_HOST%/update
  goto fail
)
echo Sending %FILE% to %KLARIFY_HOST% ... keep the board plugged in.
curl.exe -s -S --max-time 240 -o "%RESP%" -w "%%{http_code}" -F "file=@%FILE%" "http://%KLARIFY_HOST%/update?key=%KLARIFY_KEY%" > "%CODEF%"
set "CODE="
if exist "%CODEF%" set /p CODE=<"%CODEF%"
if "%CODE%"=="200" (
  echo.
  echo Update installed. The board is restarting; wait about 10 seconds, then reconnect.
  goto done
)
echo.
echo The update did not install.
if "%CODE%"=="403" echo Wrong password.
if "%CODE%"=="000" echo Could not reach the board. Is this laptop on the Klarify-Demo Wi-Fi?
if "%CODE%"=="" echo Could not reach the board. Is this laptop on the Klarify-Demo Wi-Fi?
if exist "%RESP%" type "%RESP%"
echo.
echo If the board says the magic byte is wrong, you used firmware.bin; use klarify-ota.bin.
goto fail

:done
if "%KLARIFY_NOPAUSE%"=="" pause
exit /b 0

:fail
if "%KLARIFY_NOPAUSE%"=="" pause
exit /b 1
