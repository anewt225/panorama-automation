@echo off
setlocal EnableExtensions
REM ============================================================
REM  build_gpx_and_geotag.bat
REM   1) Builds phone_track.gpx from your phone photos' GPS.
REM   2) Geotags the (already time-corrected) Nikon NEF/JPG files
REM      by matching their +%OFFSET% local time to UTC track time.
REM
REM  PREREQUISITE: run fix_dslr_time.bat FIRST so the Nikon files
REM  carry the correct local time + OffsetTimeOriginal. Geotagging
REM  uses that offset to convert each photo's local time to UTC.
REM
REM  Reusable per trip: edit the SET lines below, then run.
REM  Keeps a *_original backup of every file it changes.
REM ============================================================

REM ====== EDIT THESE FOR EACH TRIP ============================
set "FOLDER=C:\path\to\your\photos"
set "PHONE_DIR=C:\Users\you\OneDrive\Pictures\Camera Roll"
set "GPX=%FOLDER%\phone_track.gpx"
set "FMT=%~dp0gpx.fmt"
set "MATCH=NIKON"
set "EXIFTOOL=exiftool"
REM  Optional extra/fallback track(s) for gaps (e.g. Google Timeline
REM  export). Leave EXTRA_GPX blank to use only the phone track.
REM  Example: set "EXTRA_GPX=%FOLDER%\google_timeline.gpx"
set "EXTRA_GPX="
REM  Max seconds a photo may sit outside the track and still be
REM  tagged (interpolation/extrapolation window). 1800 = 30 min.
set "MAXSECS=1800"
REM  FOLDER    = Nikon library to geotag (recursive)
REM  PHONE_DIR = folder of phone photos to read GPS from (recursive)
REM  MATCH     = camera Make to target (guards phone pics)
REM ============================================================

where %EXIFTOOL% >nul 2>&1
if errorlevel 1 ( echo  ERROR: exiftool not found on PATH. & pause & exit /b 1 )
if not exist "%FMT%" ( echo  ERROR: gpx.fmt not found next to this script. & pause & exit /b 1 )

echo.
echo  STEP 1 : building GPX track from phone GPS...
echo          source : %PHONE_DIR%
echo          output : %GPX%
%EXIFTOOL% -r -fileOrder gpsdatetime -p "%FMT%" -d "%%Y-%%m-%%dT%%H:%%M:%%SZ" "%PHONE_DIR%" > "%GPX%" 2>nul
for /f %%C in ('findstr /R /C:"<trkpt " "%GPX%" ^| find /c /v ""') do set "NPTS=%%C"
echo          wrote %NPTS% track points.
if "%NPTS%"=="0" ( echo  ERROR: no GPS points found - check PHONE_DIR. & pause & exit /b 1 )

set "GEOTAGS=-geotag "%GPX%""
if not "%EXTRA_GPX%"=="" if exist "%EXTRA_GPX%" set "GEOTAGS=-geotag "%GPX%" -geotag "%EXTRA_GPX%""

echo.
echo  STEP 2 : geotagging Make=%MATCH% NEF/JPG under %FOLDER% ...
echo          (matching each photo's local time + its OffsetTimeOriginal to UTC)
echo.
set /p GO="  Proceed and write GPS tags? (Y = yes) : "
if /i not "%GO%"=="Y" ( echo  Cancelled - GPX built, no photos changed. & pause & exit /b 0 )

%EXIFTOOL% -r -ext NEF -ext JPG ^
  -if "$Make=~/%MATCH%/i" ^
  -api GeoMaxIntSecs=%MAXSECS% -api GeoMaxExtSecs=%MAXSECS% ^
  %GEOTAGS% ^
  "-geotime<${DateTimeOriginal}${OffsetTimeOriginal}" ^
  "%FOLDER%"

echo.
echo  ---- VERIFY (newly tagged coordinates, a few files) ------------------
%EXIFTOOL% -r -q -ext NEF -ext JPG ^
  -if "$Make=~/%MATCH%/i and $GPSLatitude" ^
  -p "${FileName}:  ${GPSLatitude#},${GPSLongitude#}" ^
  "%FOLDER%" 2>nul | more
echo  ----------------------------------------------------------------------
echo.
echo  Done. Pristine backups saved as *_original next to each file.
echo.
pause
