#!/usr/bin/env python3
# =============================================================================
#  pano_batch.py  -  batch panorama builder for the 2026-06 Panos\ folder
# -----------------------------------------------------------------------------
#  For every burst of frames in Panos\ (auto-detected by capture-time gaps):
#    1. develop each NEF from raw with a "natural" dynamic look
#         - highlight recovery + LUMINANCE-preserving filmic tone curve
#           (expands the raw's latitude without per-channel hue shifts)
#         - ONE exposure normalization per burst (frames stay mutually
#           consistent -> seamless blend)
#         - gentle local contrast + vibrance
#    2. stitch with Hugin  (pto_gen -> cpfind --celeste -> cpclean ->
#         linefind -> autooptimiser -> pano_modify -> nona + enblend)
#         - ADAPTIVE projection chosen from the measured field of view
#         - sanity checks; weak/unconnected stitches are skipped + logged
#           for manual finishing in the Hugin GUI (not emitted broken)
#    3. export a high-quality JPG into Panos\, copying GPS + capture date
#         from the first frame so the panorama lands on the map/timeline
#
#  Idempotent: a burst whose output JPG already exists is skipped (use --redo
#  to force). Per-burst failures are logged and do NOT stop the batch.
#
#  Requires: Python (rawpy, opencv-python, imageio, numpy, pillow), exiftool
#  on PATH, and Hugin installed (CLI tools).  All validated 2026-07-01.
#
#  Usage:
#    python pano_batch.py              # process every burst -> Panos\
#    python pano_batch.py --limit 1    # just the first burst (smoke test)
#    python pano_batch.py --out D:\tmp # write panos elsewhere (testing)
#    python pano_batch.py --list       # list detected bursts and exit
#    python pano_batch.py --redo       # re-make even if output exists
# =============================================================================
import os, sys, glob, json, math, time, shutil, argparse, subprocess, datetime as dt
import numpy as np

# ------------------------------- CONFIG --------------------------------------
SRC       = r"./Panos"   # frames in
OUT_DEF   = r"./Panos"   # panos out
HUGIN_BIN = r"C:/Program Files/Hugin/bin"
EXIFTOOL  = "exiftool"
WORK_ROOT = os.path.join(os.environ.get("TEMP", "/tmp"), "pano_batch_work")
GAP_SECS  = 30           # new burst when capture-time gap exceeds this
JPEG_Q    = 95
# look (natural): mid-grey target, CLAHE clip/tile, vibrance
GREY_TARGET, CLAHE_CLIP, CLAHE_TILE, VIBRANCE = 0.155, 1.15, 12, 0.13
# stitch sanity thresholds
MIN_CP_PER_PAIR = 8      # expect >= this many control points per adjacent pair
HFOV_BROKEN     = 320    # optimized HFOV above this => failed solve
# -----------------------------------------------------------------------------

def log(msg):
    line = f"{dt.datetime.now():%H:%M:%S}  {msg}"
    print(line, flush=True)
    with open(os.path.join(OUT, "pano_batch.log"), "a", encoding="utf-8") as fh:
        fh.write(line + "\n")

def run(cmd, **kw):
    """Run a command, return (rc, stdout+stderr)."""
    p = subprocess.run(cmd, capture_output=True, text=True, **kw)
    return p.returncode, (p.stdout or "") + (p.stderr or "")

# ---------------------------- burst detection --------------------------------
def detect_bursts():
    files = glob.glob(os.path.join(SRC, "*.NEF"))
    meta = json.loads(subprocess.run(
        [EXIFTOOL, "-n", "-json", "-DateTimeOriginal", "-FileName", *files],
        capture_output=True, text=True).stdout)
    def when(m):
        try: return dt.datetime.strptime(m["DateTimeOriginal"], "%Y:%m:%d %H:%M:%S")
        except Exception: return dt.datetime(2000,1,1)
    rows = sorted(({"path": os.path.join(SRC, m["FileName"]), "t": when(m)} for m in meta),
                  key=lambda r: r["t"])
    bursts, cur = [], []
    for r in rows:
        if cur and (r["t"] - cur[-1]["t"]).total_seconds() > GAP_SECS:
            bursts.append(cur); cur = []
        cur.append(r)
    if cur: bursts.append(cur)
    return bursts

def out_name(burst):
    t = burst[0]["t"]
    return f"Pano_{t:%Y-%m-%d_%H%M%S}_{len(burst)}f.jpg"

# ------------------------------- develop -------------------------------------
def _filmic(x):
    a,b,c,d,e = 2.51,0.03,2.43,0.59,0.14
    return np.clip((x*(a*x+b))/(x*(c*x+d)+e), 0, 1)

def develop_burst(burst, wdir):
    import rawpy, imageio.v3 as iio, cv2
    paths = [r["path"] for r in burst]
    # pass 1 (half-res, low memory): burst-wide median luminance -> exposure gain
    meds = []
    for p in paths:
        with rawpy.imread(p) as raw:
            rgb = raw.postprocess(use_camera_wb=True, no_auto_bright=True, half_size=True,
                                  output_bps=16, gamma=(1,1),
                                  highlight_mode=rawpy.HighlightMode.Blend,
                                  output_color=rawpy.ColorSpace.sRGB)
        meds.append(np.median((rgb.astype(np.float32)/65535.0).reshape(-1,3).mean(1)))
    gain = GREY_TARGET / max(float(np.median(meds)), 1e-5)
    # pass 2 (full res): develop linear, luminance-tone-map, write 16-bit TIFF
    tifs = []
    for p in paths:
        with rawpy.imread(p) as raw:
            lin = raw.postprocess(use_camera_wb=True, no_auto_bright=True, output_bps=16,
                                  gamma=(1,1), highlight_mode=rawpy.HighlightMode.Blend,
                                  demosaic_algorithm=rawpy.DemosaicAlgorithm.AHD,
                                  output_color=rawpy.ColorSpace.sRGB).astype(np.float32)/65535.0
        x = np.clip(lin*gain, 0, None)
        lum = np.maximum(x @ np.array([0.2126,0.7152,0.0722], np.float32), 1e-6)
        x = np.clip(x * (_filmic(lum)/lum)[...,None], 0, 1)           # DR curve, hue preserved
        img8 = (x*255).astype(np.uint8)
        lab = cv2.cvtColor(img8, cv2.COLOR_RGB2LAB); L,A,B = cv2.split(lab)
        L = cv2.createCLAHE(clipLimit=CLAHE_CLIP, tileGridSize=(CLAHE_TILE,CLAHE_TILE)).apply(L)
        img8 = cv2.cvtColor(cv2.merge([L,A,B]), cv2.COLOR_LAB2RGB)
        hsv = cv2.cvtColor(img8, cv2.COLOR_RGB2HSV).astype(np.float32); s = hsv[:,:,1]/255.0
        hsv[:,:,1] = np.clip((s+(1-s)*VIBRANCE)*255, 0, 255)
        img8 = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)
        tif = os.path.join(wdir, os.path.splitext(os.path.basename(p))[0] + ".tif")
        iio.imwrite(tif, (img8.astype(np.uint16)*257))
        tifs.append(tif)
        del lin, x, lum, img8, lab
    return tifs, gain

# -------------------------------- stitch -------------------------------------
def _pto_stat(pto):
    """Return (num_images, num_ctrl_pts, hfov, connected?)."""
    imgs = cps = 0; hfov = 0.0; seen = set(); nimg = 0
    for ln in open(pto, encoding="utf-8", errors="ignore"):
        if ln.startswith("i "): nimg += 1
        elif ln.startswith("c "):
            cps += 1
            for tok in ln.split():
                if tok[0]=="n": seen.add(int(tok[1:]))
                elif tok[0]=="N": seen.add(int(tok[1:]))
        elif ln.startswith("p "):
            for tok in ln.split():
                if tok.startswith("v"):
                    try: hfov = float(tok[1:])
                    except Exception: pass
    connected = (nimg <= 1) or (len(seen) >= nimg)
    return nimg, cps, hfov, connected

def stitch(tifs, burst, wdir, out_jpg):
    H = lambda t: os.path.join(HUGIN_BIN, t + ".exe")
    # focal length onto TIFFs so the solve starts from the true FoV
    for t in tifs:
        base = os.path.splitext(os.path.basename(t))[0]
        run([EXIFTOOL, "-q", "-overwrite_original", "-tagsFromFile",
             os.path.join(SRC, base + ".NEF"),
             "-FocalLength", "-FocalLengthIn35mmFormat", "-Make", "-Model", "-FNumber", t])
    pto = os.path.join(wdir, "p.pto")
    run([H("pto_gen"), *tifs, "-o", pto])
    run([H("cpfind"), "--multirow", "--celeste", "-o", pto, pto])
    run([H("cpclean"), "-o", pto, pto])
    run([H("linefind"), "-o", pto, pto])
    run([H("autooptimiser"), "-a", "-m", "-l", "-s", "-o", pto, pto])

    nimg, cps, hfov, connected = _pto_stat(pto)
    if not connected:
        return None, f"unconnected frames ({cps} cp) — needs manual GUI"
    if cps < MIN_CP_PER_PAIR * max(nimg-1, 1):
        return None, f"too few control points ({cps} for {nimg} frames) — low texture; manual GUI"
    if hfov <= 0 or hfov > HFOV_BROKEN:
        return None, f"bad optimized FoV ({hfov:.0f} deg) — manual GUI"

    # adaptive projection from field of view
    if   hfov < 100: proj, pname = 0, "rectilinear"
    elif hfov <= 140: proj, pname = 1, "cylindrical"
    elif hfov <= 170: proj, pname = 12, "panini"
    else:             proj, pname = 1, "cylindrical"   # ultra-wide: cylindrical is safest
    run([H("pano_modify"), f"--projection={proj}", "--fov=AUTO",
         "--canvas=AUTO", "--crop=AUTO", "-o", pto, pto])
    run([H("hugin_executor"), "--stitching", "--prefix=" + os.path.join(wdir, "pano"), pto])

    tif = os.path.join(wdir, "pano.tif")
    if not os.path.exists(tif):
        return None, "renderer produced no output — manual GUI"

    # 16-bit TIFF (often RGBA) -> high-quality sRGB JPG
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    Image.open(tif).convert("RGB").save(out_jpg, quality=JPEG_Q)
    # carry GPS + capture date so the panorama is placed correctly
    run([EXIFTOOL, "-q", "-overwrite_original", "-tagsFromFile", burst[0]["path"],
         "-GPSLatitude", "-GPSLatitudeRef", "-GPSLongitude", "-GPSLongitudeRef",
         "-DateTimeOriginal", "-CreateDate", "-OffsetTimeOriginal", "-Make", "-Model",
         "-Software=pano_batch.py (Hugin)", out_jpg])
    return (pname, hfov, cps), None

# --------------------------------- main --------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="process only first N bursts")
    ap.add_argument("--out", default=OUT_DEF, help="output folder for panoramas")
    ap.add_argument("--list", action="store_true", help="list bursts and exit")
    ap.add_argument("--redo", action="store_true", help="re-make even if output exists")
    a = ap.parse_args()
    global OUT; OUT = a.out
    os.makedirs(OUT, exist_ok=True); os.makedirs(WORK_ROOT, exist_ok=True)

    bursts = detect_bursts()
    log(f"detected {len(bursts)} bursts / {sum(len(b) for b in bursts)} frames in {SRC}")
    if a.list:
        for i,b in enumerate(bursts,1):
            print(f"  {i:2}. {out_name(b):34} {len(b):>3} frames  {b[0]['t']:%Y-%m-%d %H:%M}")
        return
    todo = bursts[:a.limit] if a.limit else bursts
    ok = skipped = failed = 0
    for i, b in enumerate(todo, 1):
        out_jpg = os.path.join(OUT, out_name(b))
        if os.path.exists(out_jpg) and not a.redo:
            log(f"[{i}/{len(todo)}] skip (exists) {os.path.basename(out_jpg)}"); skipped += 1; continue
        wdir = os.path.join(WORK_ROOT, f"b{i:02d}")
        shutil.rmtree(wdir, ignore_errors=True); os.makedirs(wdir)
        t0 = time.time()
        try:
            tifs, gain = develop_burst(b, wdir)
            info, err = stitch(tifs, b, wdir, out_jpg)
            if err:
                log(f"[{i}/{len(todo)}] FAIL {out_name(b)} :: {err}"); failed += 1
            else:
                pname, hfov, cps = info
                log(f"[{i}/{len(todo)}] OK   {os.path.basename(out_jpg)}  "
                    f"{pname} {hfov:.0f}deg {cps}cp gain={gain:.2f}  {time.time()-t0:.0f}s"); ok += 1
        except Exception as e:
            log(f"[{i}/{len(todo)}] ERROR {out_name(b)} :: {e!r}"); failed += 1
        finally:
            shutil.rmtree(wdir, ignore_errors=True)
    log(f"DONE  ok={ok} skipped={skipped} failed={failed}  -> {OUT}")
    log("Any FAIL/ERROR bursts: open the frames in the Hugin GUI to finish by hand.")

if __name__ == "__main__":
    OUT = OUT_DEF
    main()
