#!/usr/bin/env python3
"""Triage every Panos burst by its exposure (EV) spread, straight from EXIF.
EV per frame = log2(N^2 / t) - log2(ISO/100).  Spread = max-min EV across the burst.
Bigger spread = camera re-metered more = bigger scene dynamic range = harder pano."""
import json, math, datetime as dt

M = json.load(open(r"./panos_meta.json"))

def parse(d):
    return dt.datetime.strptime(d, "%Y:%m:%d %H:%M:%S")

rows = []
for m in M:
    try:
        t  = float(m["ExposureTime"]); N = float(m["FNumber"]); iso = float(m["ISO"])
        ev = math.log2(N*N / t) - math.log2(iso/100.0)
        rows.append((m["FileName"], parse(m["DateTimeOriginal"]), ev))
    except Exception:
        rows.append((m.get("FileName","?"), parse(m.get("DateTimeOriginal","2000:01:01 00:00:00")), None))
rows.sort(key=lambda r: (r[1]))

# group into bursts: new burst if >30s gap
bursts, cur = [], []
for r in rows:
    if cur and (r[1]-cur[-1][1]).total_seconds() > 30:
        bursts.append(cur); cur=[]
    cur.append(r)
if cur: bursts.append(cur)

print(f"{'burst (first frame)':32} {'n':>3} {'EVmin':>6} {'EVmax':>6} {'spread':>6}  class")
print("-"*78)
buckets={"EVEN":0,"MODERATE":0,"HIGH-DR":0}
hard=[]
for b in bursts:
    evs=[ev for _,_,ev in b if ev is not None]
    if not evs: continue
    lo,hi=min(evs),max(evs); spread=hi-lo
    cls = "EVEN" if spread<1.5 else ("MODERATE" if spread<3.0 else "HIGH-DR")
    buckets[cls]+=1
    if cls=="HIGH-DR": hard.append((b[0][0], spread, len(b)))
    flag = "  <-- shade/sun" if cls=="HIGH-DR" else ""
    print(f"{b[0][0]:32} {len(b):>3} {lo:6.1f} {hi:6.1f} {spread:6.1f}  {cls}{flag}")
print("-"*78)
print("summary:", buckets, f"  ({len(bursts)} bursts, {sum(len(b) for b in bursts)} frames)")
if hard:
    print("\nHIGH-DR bursts (would benefit from HDR / flat-develop):")
    for fn,sp,n in sorted(hard,key=lambda x:-x[1]):
        print(f"  {fn}  spread={sp:.1f} stops  ({n} frames)")
