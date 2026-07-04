@echo off
setlocal EnableExtensions
REM ============================================================
REM  fix_dslr_time.bat  -  shift DSLR capture time + stamp zone
REM  Reusable per trip: edit the SET lines below, then run.
REM ------------------------------------------------------------
REM  WHAT IT DOES
REM    - Targets Make=%MATCH% NEF/JPG under %FOLDER% (recursive)
REM    - SKIPS any file that already has a timezone offset, so
REM      phone photos and already-fixed files are never touched
REM      and the script is safe to run more than once (idempotent)
REM    - PASS 1: adds %SHIFT% to every capture timestamp it finds
REM        EXIF  DateTimeOriginal / CreateDate / ModifyDate
REM        XMP   CreateDate / ModifyDate / DateCreated(photoshop) /
REM              DateTimeOriginal(exif) / DateTime(tiff)
REM        IPTC  DateCreated / TimeCreated
REM      and stamps %OFFSET% on OffsetTime/Original/Digitized,
REM      and sets XMP MetadataDate = now.
REM    - PASS 2: rewrites IPTC DateCreated/TimeCreated from the
REM      corrected, zone-aware time so the IPTC zone is right too,
REM      and refreshes IPTCDigest. (no extra backup is made)
REM    - Keeps a *_original backup of every file it changes.
REM    - Narrative .xmp sidecars hold no date fields (only a "good"
REM      rating flag), so there is nothing to shift in them.
REM ============================================================

REM ====== EDIT THESE FOR EACH TRIP ============================
set "FOLDER=C:\path\to\your\photos"
set "SHIFT=0:0:0 7:0:0"
set "OFFSET=+02:00"
set "MATCH=NIKON"
set "EXIFTOOL=exiftool"
set "BACKUP=1"
REM   BACKUP = 1 keep *_original backups (safe default); 0 = no backups
REM   SHIFT  = Y:M:D h:m:s   (here = +7 hours)
REM   OFFSET = the TRUE local zone of the shoot (here = Amsterdam CEST)
REM   MATCH  = camera Make to target (guards phone pics)
REM   EXIFTOOL = "exiftool" if on PATH, else full path to exiftool.exe
REM ============================================================

where %EXIFTOOL% >nul 2>&1
if errorlevel 1 (
  echo  ERROR: exiftool not found. Install from https://exiftool.org,
  echo  put exiftool.exe on PATH, or set EXIFTOOL to its full path.
  pause & exit /b 1
)

echo.
echo  Folder : %FOLDER%
echo  Action : shift Make=%MATCH% NEF/JPG by +%SHIFT%, stamp %OFFSET%
echo  Guard  : files that already have an offset are skipped.
echo.
echo  ---- PREVIEW (files that will change: current time -^> shift/zone) ----
%EXIFTOOL% -r -q -ext NEF -ext JPG ^
  -if "$Make=~/%MATCH%/i and not $OffsetTimeOriginal" ^
  -p "${FileName}:  now=${DateTimeOriginal}  ->  +%SHIFT%, zone %OFFSET%" ^
  "%FOLDER%" 2>nul
echo  ----------------------------------------------------------------------
echo.
set /p GO="  Proceed and write changes? (Y = yes) : "
if /i not "%GO%"=="Y" ( echo  Cancelled - nothing changed. & pause & exit /b 0 )

set "OWO="
if "%BACKUP%"=="0" set "OWO=-overwrite_original"
if "%BACKUP%"=="0" echo  NOTE: BACKUP=0 - no *_original backups will be kept.

echo.
echo  PASS 1/2 : shifting timestamps and stamping the zone...
%EXIFTOOL% -r -ext NEF -ext JPG %OWO% ^
  -if "$Make=~/%MATCH%/i and not $OffsetTimeOriginal" ^
  "-AllDates+=%SHIFT%" ^
  "-XMP-xmp:CreateDate+=%SHIFT%" "-XMP-xmp:ModifyDate+=%SHIFT%" ^
  "-XMP-photoshop:DateCreated+=%SHIFT%" ^
  "-XMP-exif:DateTimeOriginal+=%SHIFT%" ^
  "-XMP-tiff:DateTime+=%SHIFT%" ^
  "-IPTC:DateCreated+=%SHIFT%" "-IPTC:TimeCreated+=%SHIFT%" ^
  "-OffsetTime=%OFFSET%" "-OffsetTimeOriginal=%OFFSET%" "-OffsetTimeDigitized=%OFFSET%" ^
  "-XMP-xmp:MetadataDate=now" ^
  "%FOLDER%"

echo.
echo  PASS 2/2 : making the IPTC time-zone consistent...
%EXIFTOOL% -r -ext NEF -ext JPG -overwrite_original ^
  -if "$Make=~/%MATCH%/i and $IPTC:TimeCreated" ^
  "-IPTC:DateCreated<SubSecDateTimeOriginal" ^
  "-IPTC:TimeCreated<SubSecDateTimeOriginal" ^
  "-IPTCDigest=new" ^
  "%FOLDER%"

echo.
echo  ---- VERIFY (new values, a few files) --------------------------------
%EXIFTOOL% -r -q -ext NEF -ext JPG ^
  -if "$Make=~/%MATCH%/i" ^
  -p "${FileName}:  ${DateTimeOriginal} ${OffsetTimeOriginal}" ^
  "%FOLDER%" 2>nul | more
echo  ----------------------------------------------------------------------
echo.
echo  Done. Pristine backups saved as *_original next to each file.
echo  After you have confirmed everything looks right, you can remove them:
echo      %EXIFTOOL% -r -delete_original! "%FOLDER%"
echo.
pause
