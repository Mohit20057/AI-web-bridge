@echo off
:: ============================================================
:: launch_chrome.bat  —  Start Chrome or Edge with remote debugging
:: ============================================================
:: Configure via environment variables or edit the defaults below.
::
::   BROWSER             chrome (default) or edge
::   BROWSER_EXE         Optional full path to the browser executable
::   BROWSER_PROFILE_DIR Dedicated browser profile directory
::   CHROME_PROFILE_DIR  Where Chrome stores this session's profile
::                       Default: %USERPROFILE%\ArgonChromeProfile
::   CDP_PORT            CDP port the bridge connects to
::   CHROME_DEBUG_PORT   Legacy CDP port setting
::                       Default: 9222
::
:: Usage:
::   Double-click this file, OR
::   set CHROME_PROFILE_DIR=D:\MyProfile && launch_chrome.bat
:: ============================================================

if not defined BROWSER (
    set BROWSER=chrome
)
if not defined BROWSER_EXE (
    if /I "%BROWSER%"=="edge" (
        set BROWSER_EXE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe
    ) else (
        set BROWSER_EXE=C:\Program Files\Google\Chrome\Application\chrome.exe
    )
)
if not defined BROWSER_PROFILE_DIR (
    if defined CHROME_PROFILE_DIR (
        set BROWSER_PROFILE_DIR=%CHROME_PROFILE_DIR%
    ) else if /I "%BROWSER%"=="edge" (
        set BROWSER_PROFILE_DIR=%USERPROFILE%\ArgonEdgeProfile
    ) else (
        set BROWSER_PROFILE_DIR=%USERPROFILE%\ArgonChromeProfile
    )
)
if not defined CDP_PORT (
    if defined CHROME_DEBUG_PORT (
        set CDP_PORT=%CHROME_DEBUG_PORT%
    ) else (
        set CDP_PORT=9222
    )
)

echo Starting %BROWSER%...
echo   Browser : %BROWSER%
echo   Profile : %BROWSER_PROFILE_DIR%
echo   CDP port: %CDP_PORT%
echo.
echo Log in to Gemini in this browser window.
echo Then switch back to your terminal and run argon_bridge.py.
echo.

start "" "%BROWSER_EXE%" ^
    --remote-debugging-address=127.0.0.1 ^
    --remote-debugging-port=%CDP_PORT% ^
    --remote-allow-origins=http://localhost:%CDP_PORT%,http://127.0.0.1:%CDP_PORT% ^
    --user-data-dir="%BROWSER_PROFILE_DIR%" ^
    --no-first-run ^
    --no-default-browser-check
