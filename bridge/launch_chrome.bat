@echo off
:: ============================================================
:: launch_chrome.bat  —  Start Chrome with remote debugging
:: ============================================================
:: Configure via environment variables or edit the defaults below.
::
::   CHROME_EXE          Full path to chrome.exe
::                       Default: standard Program Files location
::   CHROME_PROFILE_DIR  Where Chrome stores this session's profile
::                       Default: %USERPROFILE%\ArgonChromeProfile
::   CHROME_DEBUG_PORT   CDP port the bridge connects to
::                       Default: 9222
::
:: Usage:
::   Double-click this file, OR
::   set CHROME_PROFILE_DIR=D:\MyProfile && launch_chrome.bat
:: ============================================================

if not defined CHROME_EXE (
    set CHROME_EXE=C:\Program Files\Google\Chrome\Application\chrome.exe
)
if not defined CHROME_PROFILE_DIR (
    set CHROME_PROFILE_DIR=%USERPROFILE%\ArgonChromeProfile
)
if not defined CHROME_DEBUG_PORT (
    set CHROME_DEBUG_PORT=9222
)

echo Starting Chrome...
echo   Profile : %CHROME_PROFILE_DIR%
echo   CDP port: %CHROME_DEBUG_PORT%
echo.
echo Log in to the web AI (e.g. gemini.google.com) in this browser window.
echo Then switch back to your terminal and run argon_bridge.py.
echo.

start "" "%CHROME_EXE%" ^
    --remote-debugging-port=%CHROME_DEBUG_PORT% ^
    --user-data-dir="%CHROME_PROFILE_DIR%" ^
    --no-first-run ^
    --no-default-browser-check
