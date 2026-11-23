"""Step 3. Google Places opening hours for the step-1 candidates (non-chain, open, score >= 3).
Resumable: shops already queried are skipped; stops cleanly on quota (HTTP 429).
Usage: python3 src/google_hours.py"""
import json, math, os, re, time, unicodedata
from difflib import SequenceMatcher
import numpy as np, pandas as pd, requests

from config import S, google_key

KEY = google_key()
URL = "https://places.googleapis.com/v1/places:searchText"
FIELDS = ("places.id,places.displayName,places.formattedAddress,places.location,places.types,"
          "places.primaryType,places.businessStatus,places.regularOpeningHours")
RAW = S + "google_candidates_raw.jsonl"
SCORE_MIN = 3


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def dist_m(lat1, lon1, lat2, lon2):
    return 6371000 * math.hypot(math.radians(lon2 - lon1) * math.cos(math.radians(lat1)), math.radians(lat2 - lat1))


def search(query, lat, lon):
    body = {"textQuery": query, "pageSize": 5, "languageCode": "it",
            "locationBias": {"circle": {"center": {"latitude": lat, "longitude": lon}, "radius": 150.0}}}
    r = requests.post(URL, json=body, timeout=30, headers={"X-Goog-Api-Key": KEY, "X-Goog-FieldMask": FIELDS})
    r.raise_for_status()
    return r.json().get("places", [])


def hours_features(periods):
    """days_open, median and max closing hour (past midnight -> +24), 24h flag."""
    if not periods:
        return dict(days_open=np.nan, med_close=np.nan, max_close=np.nan, h24=np.nan)
    if len(periods) == 1 and "close" not in periods[0]:
        return dict(days_open=7, med_close=24.0, max_close=24.0, h24=True)
    close = {}
    for q in periods:
        o, c = q["open"], q.get("close", {"day": q["open"]["day"], "hour": 24, "minute": 0})
        t = c["hour"] + c["minute"] / 60
        if c["day"] != o["day"] or t <= 5:
            t += 24
        close[o["day"]] = max(close.get(o["day"], 0), t)
    v = list(close.values())
    return dict(days_open=len(close), med_close=float(np.median(v)), max_close=max(v), h24=False)


d = pd.read_csv(S + "rome_minimarket_candidates.csv")
c = d[(d.score >= SCORE_MIN) & ~d.is_chain & ~d.fsq_closed & ~d.ov_not_open].reset_index(drop=True)

done = {}
for f in (RAW,):
    if os.path.exists(f):
        for line in open(f):
            x = json.loads(line); done[x["gmaps"]] = x
todo = [r for _, r in c.iterrows() if r.gmaps not in done]
print(f"candidates {len(c)}, already queried {len(c) - len(todo)}, to query {len(todo)}")

stopped = None
with open(RAW, "a") as out:
    for r in todo:
        name = r["name"] if isinstance(r["name"], str) else "minimarket"
        addr = r.address if isinstance(r.address, str) and r.address != "nan nan" else ""
        q = f"{name} {addr} Roma".strip()
        try:
            places = search(q, r.lat, r.lon)
        except requests.HTTPError as e:
            stopped = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
            break
        x = {"gmaps": r.gmaps, "query": q, "places": places}
        out.write(json.dumps(x) + "\n"); out.flush(); done[r.gmaps] = x
        time.sleep(0.1)
if stopped:
    print("stopped:", stopped)

rows = []
for _, r in c.iterrows():
    rec = dict(gmaps=r.gmaps, queried=r.gmaps in done, g_found=False)
    best, best_s = None, -1
    for p in done.get(r.gmaps, {}).get("places", []):
        dd = dist_m(r.lat, r.lon, p["location"]["latitude"], p["location"]["longitude"])
        sim = SequenceMatcher(None, norm(r["name"]), norm(p["displayName"]["text"])).ratio()
        shop = bool(re.search(r"store|market|grocery|supermarket|shop|food", p.get("primaryType") or ""))
        if dd <= 120 and (sim >= 0.5 or (dd <= 25 and shop)) and sim - dd / 120 > best_s:
            best, best_s, bd, bsim = p, sim - dd / 120, dd, sim
    if best is not None:
        oh = best.get("regularOpeningHours", {})
        rec.update(g_found=True, g_place_id=best["id"], g_name=best["displayName"]["text"], g_dist_m=round(bd),
                   g_name_sim=round(bsim, 2), g_primary_type=best.get("primaryType"), g_status=best.get("businessStatus"),
                   g_hours_known=bool(oh.get("periods")), g_weekday_text=" | ".join(oh.get("weekdayDescriptions", [])),
                   **hours_features(oh.get("periods")))
    rows.append(rec)
g = pd.DataFrame(rows).drop_duplicates("gmaps")
g["late22"] = g.med_close >= 22
g["late23"] = g.med_close >= 23
res = c.merge(g, on="gmaps", how="left", validate="many_to_one")
res.to_csv(S + "google_hours_candidates.csv", index=False)
q = res[res.queried]
print(f"queried {len(q)}/{len(res)}; matched {q.g_found.sum()}; hours known {q.g_hours_known.fillna(False).sum()}; "
      f"close>=23 {q.late23.sum()}; close>=22 {q.late22.sum()}")
