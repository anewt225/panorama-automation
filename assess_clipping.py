#!/usr/bin/env python3
"""Per-burst highlight/shadow clipping straight from RAW sensor data (no demosaic).
Catches the locked-exposure high-DR case that EV-spread misses:
a shade->sun sweep with fixed exposure shows up here as blown highlights."""
import json, math, datetime as dt, glob, os, numpy as np, rawpy

SRC = r"./Panos"
meta = json.load(open(r"./panos_meta.json"))
order = {m["FileName"]: m["DateTimeOriginal"] for m in meta}
def parse(d): return dt.datetime.strptime(d, "%Y:%m:%d %H:%M:%S")

files = sorted(glob.glob(os.path.join(SRC,"*.NEF")), key=lambda f: parse(order.get(os.path.basename(f),"2000:01:01 00:00:00")))

def clip_stats(path):
    with rawpy.imread(path) as raw:
        a = raw.raw_image_visible.astype(np.float32)
        wl = float(raw.white_level)
        bl = float(np.mean(raw.black_level_per_channel))
        hi = float(np.mean(a >= wl*0.99)) * 100.0          # % blown
        lo = float(np.mean(a <= bl + 0.02*(wl-bl))) * 100.0 # % near-black
        return hi, lo

# group into bursts
rows=[(os.path.basename(f), parse(order.get(os.path.basename(f),"2000:01:01 00:00:00")), f) for f in files]
bursts, cur = [], []
for r in rows:
    if cur and (r[1]-cur[-1][1]).total_seconds()>30: bursts.append(cur); cur=[]
    cur.append(r)
if cur: bursts.append(cur)

print(f"{'burst':32} {'n':>3} {'maxHi%':>7} {'maxLo%':>7}  verdict")
print("-"*70)
flagged=[]
for b in bursts:
    his,los=[],[]
    for name,_,path in b:
        h,l=clip_stats(path); his.append(h); los.append(l)
    mh,ml=max(his),max(los)
    # high-DR if a frame blows >2% highlights AND another (or same scene) crushes >2% shadows
    verdict = "HIGH-DR" if (mh>2.0 and ml>5.0) else ("watch-highlights" if mh>5.0 else "ok")
    if verdict!="ok": flagged.append((b[0][0],mh,ml,verdict))
    print(f"{b[0][0]:32} {len(b):>3} {mh:7.2f} {ml:7.2f}  {verdict}")
print("-"*70)
print("flagged:", [f[0] for f in flagged] or "none")
