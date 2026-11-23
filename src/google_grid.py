"""Step 2. Google Places (Nearby Search, New) adaptive grid over the area inside the GRA.
A square cell is queried with its circumscribed circle; if Google returns the maximum (20)
the cell is split into 4. Cells not touching the GRA polygon are skipped.
Responses are cached in google_grid_raw_gra.jsonl, so a rerun reuses them and only
pays for missing cells. Hard cap on new paid calls.
Usage: python3 src/google_grid.py [max_new_calls]"""
import json, math, os, sys, time
import numpy as np, pandas as pd, requests, geopandas as gpd
from shapely.geometry import box, Point

from config import S, google_key
from lexicons import CHAINS, GOOGLE_KEEP_TYPES as KEEP

KEY = google_key()
URL = "https://places.googleapis.com/v1/places:searchNearby"
FIELDS = ("places.id,places.displayName,places.formattedAddress,places.location,places.types,"
          "places.primaryType,places.businessStatus,places.regularOpeningHours")
TYPES = ["convenience_store", "grocery_store", "supermarket", "asian_grocery_store", "liquor_store", "food_store", "market"]
START_SIDE, MIN_SIDE = 1600.0, 40.0   # metres
MAX_NEW = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
RAW = S + "google_grid_raw_gra.jsonl"

gra = gpd.read_file(S + "gra_inner.geojson").geometry.iloc[0]
lo0, la0, lo1, la1 = gra.bounds
M_LAT = 111320.0
M_LON = 111320.0 * math.cos(math.radians((la0 + la1) / 2))

cache = {}
if os.path.exists(RAW):
    for line in open(RAW):
        x = json.loads(line); cache[x["key"]] = x["places"]
new_calls = 0
log = open(RAW, "a")


def query(lat, lon, radius):
    global new_calls
    key = f"{lat:.6f},{lon:.6f},{radius:.1f}"
    if key in cache:
        return cache[key]
    body = {"includedPrimaryTypes": TYPES, "maxResultCount": 20, "rankPreference": "DISTANCE",
            "locationRestriction": {"circle": {"center": {"latitude": lat, "longitude": lon}, "radius": radius}}}
    for attempt in range(5):
        try:
            r = requests.post(URL, json=body, timeout=30, headers={"X-Goog-Api-Key": KEY, "X-Goog-FieldMask": FIELDS})
        except requests.RequestException:
            time.sleep(3 * (attempt + 1)); continue
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(3 * (attempt + 1)); continue
        break
    new_calls += 1
    r.raise_for_status()
    places = r.json().get("places", [])
    cache[key] = places
    log.write(json.dumps({"key": key, "n": len(places), "places": places}) + "\n"); log.flush()
    time.sleep(0.05)
    return places


ny = math.ceil((la1 - la0) * M_LAT / START_SIDE); nx = math.ceil((lo1 - lo0) * M_LON / START_SIDE)
stack = [(la0 + (la1 - la0) * i / ny, la0 + (la1 - la0) * (i + 1) / ny, lo0 + (lo1 - lo0) * j / nx, lo0 + (lo1 - lo0) * (j + 1) / nx)
         for i in range(ny) for j in range(nx)]
stack = [c for c in stack if gra.intersects(box(c[2], c[0], c[3], c[1]))]
places, sat_min, pending, err = {}, 0, [], None
while stack:
    a0, a1, b0, b1 = stack.pop()
    h, w = (a1 - a0) * M_LAT, (b1 - b0) * M_LON
    radius = math.hypot(h, w) / 2 + 1
    key = f"{(a0 + a1) / 2:.6f},{(b0 + b1) / 2:.6f},{radius:.1f}"
    if key not in cache and new_calls >= MAX_NEW:
        pending.append((a0, a1, b0, b1)); continue
    try:
        res = query((a0 + a1) / 2, (b0 + b1) / 2, radius)
    except requests.HTTPError as e:
        err = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
        pending.append((a0, a1, b0, b1)); pending += stack; break
    for p in res:
        places[p["id"]] = p
    if len(res) >= 20:
        if max(h, w) / 2 < MIN_SIDE:
            sat_min += 1; continue
        am, bm = (a0 + a1) / 2, (b0 + b1) / 2
        stack += [c for c in [(a0, am, b0, bm), (a0, am, bm, b1), (am, a1, b0, bm), (am, a1, bm, b1)]
                  if gra.intersects(box(c[2], c[0], c[3], c[1]))]
log.close()


def hours_features(periods):
    if not periods:
        return dict(days_open=np.nan, med_close=np.nan, max_close=np.nan)
    if len(periods) == 1 and "close" not in periods[0]:
        return dict(days_open=7, med_close=24.0, max_close=24.0)
    close = {}
    for q in periods:
        o, c = q["open"], q.get("close", {"day": q["open"]["day"], "hour": 24, "minute": 0})
        t = c["hour"] + c["minute"] / 60
        if c["day"] != o["day"] or t <= 5:
            t += 24
        close[o["day"]] = max(close.get(o["day"], 0), t)
    v = list(close.values())
    return dict(days_open=len(close), med_close=float(np.median(v)), max_close=max(v))


rows = []
for p in places.values():
    lat, lon = p["location"]["latitude"], p["location"]["longitude"]
    if not gra.contains(Point(lon, lat)):
        continue
    oh = p.get("regularOpeningHours", {})
    rows.append(dict(g_place_id=p["id"], name=p["displayName"]["text"], address=p.get("formattedAddress"), lat=lat, lon=lon,
                     primary_type=p.get("primaryType"), status=p.get("businessStatus"),
                     hours_known=bool(oh.get("periods")), weekday_text=" | ".join(oh.get("weekdayDescriptions", [])),
                     **hours_features(oh.get("periods"))))
df = pd.DataFrame(rows)
df["relevant_type"] = df.primary_type.isin(KEEP)
df["is_chain"] = df.name.str.contains(CHAINS, case=False, regex=True)
df["late23"] = df.med_close >= 23
df.to_csv(S + "google_gra_all_places.csv", index=False)
core = df[df.relevant_type & ~df.is_chain & (df.status == "OPERATIONAL")]
core[core.hours_known].to_csv(S + "google_gra_minimarkets_with_hours.csv", index=False)
json.dump(pending, open(S + "google_grid_pending_cells.json", "w"))
print(f"new paid calls {new_calls}, cached cells {len(cache)}; pending cells {len(pending)}{' (INCOMPLETE)' if pending else ''}; "
      f"saturated at min size {sat_min}; {err or ''}")
print(f"places inside GRA {len(df)}; relevant non-chain operational {len(core)}; with hours {core.hours_known.sum()}; "
      f"close>=23 {core.late23.sum()}")
