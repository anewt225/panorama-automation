# Repairing 2,394 Travel Photos with an AI Agent — and Auditing Its Work
### A case study in scoping, directing, and quality-controlling an AI coding agent

**Alex Newton** · 2026

---

## TL;DR
I used an AI coding agent (Claude Code) to solve a real, messy data problem end-to-end: **2,394** raw travel photos had the wrong timezone baked into every timestamp and **zero** location data, and **38** hand-held panorama bursts sat un-stitched. I scoped the problem, directed the agent to build a reproducible pipeline, and — critically — **audited its output against professional practice and caught its mistakes.** Result: **100% of the photos correctly time-stamped and geotagged**, and an automated raw-to-panorama batch that recovers each scene's full dynamic range.

The transferable takeaway isn't the photos. It's a documented example of **working effectively with AI**: knowing what to delegate, what to verify, and when to overrule the machine.

---

## The problem (Situation)
Two weeks of travel (Netherlands → Norway) produced ~1,750 Nikon D610 raw+JPEG pairs. Two things made them nearly useless for search, mapping, or sharing:

1. **Every timestamp was wrong.** The camera clock had been left on U.S. Central time. The *instant* each photo was taken was correct, but the *timezone label* was off by 7 hours — so photos sorted wrong and wouldn't line up with anything else.
2. **No location data.** The DSLR has no GPS. None of the photos were geotagged.

Separately, 38 panorama sweeps (320 frames) were still raw, unstitched brackets — and many were backlit lake/fjord scenes where a single exposure renders flat and lifeless.

**Constraints I set:** never touch my phone photos, always be reversible, verify against ground truth, and make everything re-runnable for future trips.

## What I built (Action)
Working through the agent, I built a pipeline in four stages:

- **Time repair** — an idempotent ExifTool script that shifts every capture timestamp (EXIF **and** the XMP/IPTC blocks that editing tools had added) by +7h and stamps the true `+02:00` zone — guarded to only touch Nikon files, with backups.
- **Geotagging** — build a GPS track from my phone's photos, convert to GPX, and time-match it to the corrected DSLR photos (local time + offset → UTC). 
- **Gap-filling** — where the phone had no signal, fall back to a Google Timeline export; where neither existed, **infer location from the photo content itself** (I identified the University of Oslo, Mount Fløyen, etc.) and stamp neighborhood-level coordinates.
- **Panoramas** — a raw-develop → **Hugin** batch stitcher with adaptive projection and single-exposure dynamic-range recovery.

## The judgment calls that mattered (the interesting part)
Automation gets you 80% of the way. The value was in the 20% where I had to direct or **overrule** the agent:

- **I caught a color bug the agent introduced.** Its first tone-mapping pushed each RGB channel through the curve separately, tinting bright clouds red/green. I diagnosed it as a per-channel hue shift and had it switch to **luminance-only** tone-mapping. *(See `02_...` and develop before/after.)*
- **I rejected its default projection.** The agent's stitch bowed the foreground shoreline into a "smile." I compared cylindrical vs. **Panini** and had it choose projection **adaptively by field of view** — rectilinear for tight architectural shots, Panini for wide vistas.
- **I insisted on measuring, not guessing.** Rather than draft-stitch 38 panoramas to find exposure problems, I had it read exposure/clipping straight from the raw sensor data — proving the scenes needed shadow recovery, not true HDR, and saving hours.
- **I audited the whole approach against photographer forums** (PanoTools, etc.) before committing — confirming the pipeline was canonical and adding the real-world robustness they flag (low-texture skies starving the stitcher → flag those for manual finishing instead of shipping broken output).

## Results
| | |
|---|---|
| Photos time-corrected & verified | **2,394** (100%) |
| Geotagged | **100%** — 78% automatic (phone track), 8% Timeline fallback, rest inferred & verified to the meter |
| Time-fix accuracy | verified against phone GPS to **within ~40 seconds** |
| Panorama pipeline | **38 bursts** automated; adaptive projection + DR recovery; re-runnable |
| Reproducibility | every step parameterized for future trips; fully reversible |

**Verification, not vibes:** I confirmed the time fix by checking a corrected photo's UTC against the matching phone GPS timestamp (39-second delta = PASS), and confirmed geotags landed within ~11 m of the true location.

## Human vs. AI — who did what
- **The agent did:** wrote all the code, ran the batch operations, handled the ExifTool/Hugin/rawpy mechanics.
- **I did:** scoped the problem and constraints, made every quality/tradeoff decision, caught and corrected the agent's errors, audited the approach against expert practice, and verified the results.

That division of labor — *fluent delegation plus rigorous oversight* — is the actual skill on display.

## Skills demonstrated
Problem scoping · AI agent orchestration · workflow automation · Python (rawpy, OpenCV, ExifTool, Hugin) · geospatial/metadata engineering · dynamic-range/image processing · QA & verification · auditing AI output · clear technical communication.

---
*Artifacts: hero panorama, develop and projection before/afters, geotag route map, and the source scripts accompany this case study.*
