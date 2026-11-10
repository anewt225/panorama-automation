# DSLR Metadata Repair & Panorama Automation

Two weeks of travel photos came home with the wrong timezone on every file, no location data, and 38 hand-held panorama bursts still unstitched. I scoped the fix, directed an AI coding agent (Claude Code) to build it, and audited what it produced.

- **2,394 photo files** (1,197 raw + JPEG pairs) time-corrected and geotagged
- **38 panorama bursts** (320 raw frames) run through an automated develop-and-stitch batch; **35 delivered**
- **2 agent defects caught and corrected** before anything shipped
- Time fix checked against phone GPS to within about 40 seconds; geotags checked to about 11 m

> The photos are the test case. The subject is **how to work with an AI agent on a messy real problem**: what to hand off, what to verify, and when to overrule it.
> **[Case study](CASE_STUDY.md)** · **[Reflection: what I owned and what the agent owned](REFLECTION.md)**

![hero panorama](docs/hero.jpg)

---

## By the numbers
![metrics](docs/metrics.png)

## Who did what

| | |
|---|---|
| **The agent** | Wrote every line of code, ran the batch operations, handled the ExifTool, rawpy and Hugin mechanics |
| **Me** | Defined the problem and the constraints, made each quality and trade-off call, caught and corrected the agent's errors, checked the method against how photographers do this, verified the results |

The constraints I set up front shaped the whole design: never touch the phone photos, keep every step reversible, verify against ground truth, and make it re-runnable for the next trip.

## How it works
![pipeline](docs/pipeline_diagram.png)

| Stage | Tool | What happens |
|---|---|---|
| **1 · Time repair** | ExifTool | Shift every capture timestamp (EXIF, XMP and IPTC) and stamp the true timezone. Limited to one camera make, skips files that already carry an offset (so it is safe to re-run), shows a preview and asks before writing, keeps `*_original` backups. |
| **2 · Geotag** | ExifTool | Build a GPX track from the GPS in phone photos, then time-match it to the DSLR files (local time + offset → UTC). |
| **3 · Gap-fill** | ExifTool | Where the phone had no signal, fall back to a Google Timeline track. Where neither existed, I identified the place from the photo and stamped neighborhood-level coordinates. |
| **4 · Panoramas** | rawpy · OpenCV · Hugin | Per burst: develop from raw with highlight recovery and a luminance-only tone curve → stitch with Hugin using a projection chosen from the measured field of view → export a JPG carrying the first frame's GPS and capture date. |

## Two decisions I overruled the agent on

**Dynamic-range recovery.** Its first tone-map ran each RGB channel through the curve separately, which tinted bright skies. I had it switch to tone-mapping luminance only, which keeps hue intact:
![develop before/after](docs/develop_before_after.jpg)

**Projection.** Its default bowed the foreground shoreline. The projection is now picked per scene from the solved field of view: rectilinear under 100°, cylindrical from 100° to 140°, Panini from 140° to 170°, cylindrical again above that:
![projection](docs/projection.jpg)

## How I verified it

- **Time fix:** compared a corrected photo's UTC time with the matching phone GPS timestamp. The difference was 39 seconds.
- **Geotags:** checked tagged coordinates against the true location; they landed within about 11 m.
- **Measure before processing:** instead of draft-stitching 38 panoramas to find exposure problems, the triage scripts read exposure spread and sensor clipping straight from the raw files. That showed the scenes needed shadow recovery, not HDR bracketing.
- **Fail loudly:** a burst with too few control points, unconnected frames or an implausible field of view is logged for manual finishing in the Hugin GUI and no output is written for it.

## Results

**1,197 DSLR photos geotagged across two countries:**
![geotag map](docs/geotag_map.png)

**Selected panoramas** (developed from raw, adaptive projection):
![gallery](docs/gallery.jpg)

---

## Scripts

| File | What it does |
|---|---|
| `fix_dslr_time.bat` | Timestamp and timezone repair. Settings (`FOLDER`, `SHIFT`, `OFFSET`, `MATCH`, `BACKUP`) are `set` lines at the top of the file. |
| `build_gpx_and_geotag.bat` + `gpx.fmt` | Builds `phone_track.gpx` from phone-photo GPS, then geotags the DSLR files. `EXTRA_GPX` adds a fallback track; `MAXSECS` sets how far outside the track a photo may sit and still be tagged (default 30 minutes). |
| `pano_batch.py` | Panorama batch: groups frames into bursts by capture-time gap (30 s), develops, stitches, exports. Skips bursts whose output already exists. One failed burst does not stop the batch. Writes `pano_batch.log`. |
| `assess_exposure.py` | Ranks each burst by exposure spread, computed from EXIF. |
| `assess_clipping.py` | Reports blown highlights and crushed shadows per burst, read from raw sensor data. |

## Requirements

Developed and run on **Windows**. The two `.bat` files are Windows batch scripts, and `pano_batch.py` calls the Hugin tools as `.exe` files from `C:/Program Files/Hugin/bin` (the `HUGIN_BIN` constant at the top of the script).

- [ExifTool](https://exiftool.org) on `PATH`
- [Hugin](https://hugin.sourceforge.io) command-line tools
- Python 3.10+ with `numpy rawpy opencv-python imageio tifffile pillow`

There is no pinned `requirements.txt` yet.

## Usage

Edit the `set` lines at the top of each `.bat` file for your trip first. The values in the repo (a 7-hour shift, `+02:00`, `NIKON`) are from this one.

```bat
REM 1) preview, confirm, then repair timestamps
fix_dslr_time.bat

REM 2) build the GPS track, confirm, then geotag
build_gpx_and_geotag.bat
```

`pano_batch.py` reads `.NEF` frames from a `Panos` folder in the directory you run it from:

```bash
python pano_batch.py --list       # list detected bursts and exit
python pano_batch.py --limit 1    # first burst only, as a smoke test
python pano_batch.py              # every burst -> JPGs in Panos/
python pano_batch.py --out DIR    # write the panoramas somewhere else
python pano_batch.py --redo       # rebuild even if the output exists
```

The two triage scripts read `./panos_meta.json`, an ExifTool JSON export of the same folder. The repo does not include the command that made it; an export of this shape provides the fields they read:

```bash
exiftool -n -json -FileName -DateTimeOriginal -ExposureTime -FNumber -ISO -ext NEF Panos > panos_meta.json
python assess_exposure.py
python assess_clipping.py
```

## Limits

- Paths and tuning values (`SRC`, `HUGIN_BIN`, `GAP_SECS`, the look and sanity thresholds) are constants at the top of `pano_batch.py`, not command-line options.
- No automated tests and no CI.
- The photo library itself is not in the repo, so the batch cannot be re-run from a clone without your own raw files.

---
*Built 2026. Code written by an AI agent (Claude Code); problem scoping, quality decisions, auditing and verification by a human.*
