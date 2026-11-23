"""Step 1. Candidate dataset of independent small food shops in Rome.

Merges OpenStreetMap, Overture Maps Places and Foursquare Open Source Places,
keeps every classification signal as a separate column and builds an additive
score. Exploratory: no record is dropped on the basis of the score.

Usage: python3 src/build_candidates.py [merge_radius_m]   (default 60)"""
import json, os, re, unicodedata
import numpy as np, pandas as pd, duckdb
from difflib import SequenceMatcher

from config import S
from lexicons import CHAINS, GENERIC_MARKET, TOURIST_GOODS, TRADITIONAL, NON_RETAIL_OV, OSM_FOOD_SHOPS, OV_FOOD_CATS
con = duckdb.connect(); con.sql("LOAD spatial")

def norm(s):
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return ""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(srl|srls|sas|snc|s\.r\.l\.?|di|e|&|and|the|la|il)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def norm_addr(street, num=None):
    s = norm(street)
    s = re.sub(r"\b(via|viale|piazza|piazzale|largo|vicolo|circonvallazione|corso|lungotevere|p za|v le)\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if num:
        s = f"{s} {norm(num)}"
    m = re.match(r"(.*?)(\d+)", s)             # street + first house number only
    return f"{m.group(1).strip()} {m.group(2)}" if m else ""


def rx(pat, s):
    return bool(re.search(pat, s or "", flags=re.I))


# ---------- OSM ----------
els = json.load(open(S + "osm_rome_allshops.json"))["elements"]
osm = []
for e in els:
    t = e["tags"]
    lat = e.get("lat", e.get("center", {}).get("lat")); lon = e.get("lon", e.get("center", {}).get("lon"))
    osm.append(dict(osm_id=f"{e['type']}/{e['id']}", lat=lat, lon=lon, shop=t.get("shop"), name=t.get("name"),
                    brand=t.get("brand"), operator=t.get("operator"), opening_hours=t.get("opening_hours"),
                    vatin=t.get("ref:vatin"), street=t.get("addr:street"), housenumber=t.get("addr:housenumber")))
osm = pd.DataFrame(osm)
osm = con.sql(f"select osm.* from osm, '{S}rome_boundary.parquet' b where ST_Contains(b.geometry, ST_Point(lon,lat))").df()
STRONG = r"mini ?-?market|minimarket|food ?market|super ?market|\bmarket\b|grocery"
osm_hit = osm.name.fillna("").str.contains(STRONG, case=False, regex=True)
osm = osm[osm.shop.isin(OSM_FOOD_SHOPS) | osm_hit].copy()
osm["addr_key"] = [norm_addr(s, n) for s, n in zip(osm.street, osm.housenumber)]

# ---------- Overture ----------
ov = pd.read_parquet(S + "overture_rome_clipped.parquet")
ov_hit = ov.name.fillna("").str.contains(GENERIC_MARKET, case=False, regex=True)
cat = ov.tax_primary.fillna("")
WEAK_CATS = {"shopping", "gift_shop", "flea_market", "souvenir_store", ""}
ov = ov[(cat.isin(OV_FOOD_CATS - WEAK_CATS)) | (ov_hit & (cat.isin(WEAK_CATS) | ~cat.str.contains(NON_RETAIL_OV, regex=True)))].copy()
ov["src_datasets"] = ov.sources.apply(lambda x: ",".join(sorted({s["dataset"] for s in x})) if x is not None else "")
ov["addr_key"] = [norm_addr(a) for a in ov.addr]
ov["nname"] = ov.name.map(norm)

# dedupe Overture: same normalised name within 30 m, keep highest confidence
ov = ov.sort_values("confidence", ascending=False).reset_index(drop=True)
keep, taken = [], np.zeros(len(ov), bool)
lat_r = np.radians(ov.lat.values); lon_r = np.radians(ov.lon.values)
for i in range(len(ov)):
    if taken[i]:
        continue
    keep.append(i)
    d = 6371000 * np.sqrt(((lon_r - lon_r[i]) * np.cos(lat_r[i])) ** 2 + (lat_r - lat_r[i]) ** 2)
    taken |= (d < 30) & (ov.nname.values == ov.nname.values[i])
ov = ov.iloc[keep].reset_index(drop=True)


# ---------- merge ----------
def dist_matrix(a, b):
    la, lo = np.radians(a.lat.values)[:, None], np.radians(a.lon.values)[:, None]
    lb, lob = np.radians(b.lat.values)[None, :], np.radians(b.lon.values)[None, :]
    return 6371000 * np.sqrt(((lob - lo) * np.cos(la)) ** 2 + (lb - la) ** 2)


osm = osm.reset_index(drop=True)
osm["nname"] = osm.name.map(norm)
D = dist_matrix(osm, ov)
MERGE_R = float(__import__("sys").argv[1]) if len(__import__("sys").argv) > 1 else 60.0
pairs = []
for i in range(len(osm)):
    for j in np.where(D[i] < 150)[0]:
        sim = SequenceMatcher(None, osm.nname[i], ov.nname[j]).ratio() if osm.nname[i] and ov.nname[j] else 0
        same_addr = bool(osm.addr_key[i]) and osm.addr_key[i] == ov.addr_key[j]
        if (sim >= 0.6 and D[i, j] < MERGE_R) or (same_addr and (sim >= 0.3 or not osm.nname[i])):
            pairs.append((D[i, j] - 100 * same_addr - 50 * sim, i, j, D[i, j], sim, same_addr))
pairs.sort()
used_o, used_v, match = set(), set(), []
for _, i, j, d, sim, sa in pairs:
    if i in used_o or j in used_v:
        continue
    used_o.add(i); used_v.add(j); match.append((i, j, d, sim, sa))
m = pd.DataFrame(match, columns=["i", "j", "dist_m", "name_sim", "same_addr"])
m.to_csv(S + "merge_pairs_diag.csv", index=False)

recs = []
for i, j, d, sim, sa in match:
    o, v = osm.loc[i], ov.loc[j]
    recs.append(dict(osm_id=o.osm_id, overture_id=v.id, name=o["name"] or v["name"], name_overture=v["name"],
                     lat=o.lat, lon=o.lon, osm_shop=o.shop, ov_category=v.tax_primary, brand=o.brand or v.brand,
                     opening_hours=o.opening_hours, operator=o.operator, vatin=o.vatin, address=v.addr or f"{o.street or ''} {o.housenumber or ''}".strip(),
                     ov_confidence=v.confidence, ov_operating_status=v.operating_status, ov_sources=v.src_datasets, match_dist_m=round(d, 1)))
for i in set(range(len(osm))) - used_o:
    o = osm.loc[i]
    recs.append(dict(osm_id=o.osm_id, name=o["name"], lat=o.lat, lon=o.lon, osm_shop=o.shop, brand=o.brand, opening_hours=o.opening_hours,
                     operator=o.operator, vatin=o.vatin, address=f"{o.street or ''} {o.housenumber or ''}".strip() or None))
for j in set(range(len(ov))) - used_v:
    v = ov.loc[j]
    recs.append(dict(overture_id=v.id, name=v["name"], lat=v.lat, lon=v.lon, ov_category=v.tax_primary, brand=v.brand, address=v.addr,
                     ov_confidence=v.confidence, ov_operating_status=v.operating_status, ov_sources=v.src_datasets))
df = pd.DataFrame(recs)

# ---------- Foursquare OS Places: third source, merged onto OSM+Overture ----------
fsq = pd.read_parquet(S + "foursquare_rome_clipped.parquet")
fsq["labels"] = fsq.fsq_category_labels.apply(lambda x: " | ".join(x) if x is not None else "")
FSQ_CORE = r"Supermarket|Grocery Store|Food and Beverage Retail$|Food and Beverage Retail \||Convenience Store|Retail > Market$|Fruit and Vegetable|Liquor Store|Wine Store|Beer Store|Discount Store"
FSQ_WEAK = r"Souvenir|Flea Market|Gift|^Retail$|^$"
lab_last = fsq.fsq_category_labels.apply(lambda x: x[0] if x is not None and len(x) else "")
fsq_hit = fsq.name.fillna("").str.contains(GENERIC_MARKET, case=False, regex=True)
fsq_core = fsq.labels.str.contains(FSQ_CORE, regex=True) & ~fsq.labels.str.contains(r"Butcher|Meat|Fish|Cheese|Candy|Chocolate|Gourmet|Health Food|Organic|Farmers|Caterer|Coffee|Dairy", regex=True)
fsq_weak = lab_last.str.contains(FSQ_WEAK, regex=True)
fsq = fsq[fsq_core | (fsq_hit & (fsq_weak | ~fsq.labels.str.contains(r"Dining|Restaurant|Bar|Café|Services|Health|Beauty|Hotel|Lodging|Travel|Community|Education|Arts", regex=True)))].copy()
fsq = fsq.rename(columns={"latitude": "lat", "longitude": "lon"}).reset_index(drop=True)
fsq["nname"] = fsq.name.map(norm)
fsq["addr_key"] = [norm_addr(a) for a in fsq.address]

df["nname"] = df.name.map(norm)
df["addr_key"] = [norm_addr(a) for a in df.address.fillna("")]
D = dist_matrix(fsq, df)
pairs = []
for i in range(len(fsq)):
    for j in np.where(D[i] < 150)[0]:
        sim = SequenceMatcher(None, fsq.nname[i], df.nname[j]).ratio() if fsq.nname[i] and df.nname[j] else 0
        same_addr = bool(fsq.addr_key[i]) and fsq.addr_key[i] == df.addr_key[j]
        if (sim >= 0.6 and D[i, j] < MERGE_R) or (same_addr and sim >= 0.3):
            pairs.append((D[i, j] - 100 * same_addr - 50 * sim, i, j, D[i, j], sim, same_addr))
pairs.sort()
used_f, used_d, fmatch = set(), set(), []
for _, i, j, d, sim, sa in pairs:
    if i in used_f or j in used_d:
        continue
    used_f.add(i); used_d.add(j); fmatch.append((i, j, d, sim, sa))
pd.DataFrame(fmatch, columns=["i", "j", "dist_m", "name_sim", "same_addr"]).to_csv(S + "merge_pairs_fsq_diag.csv", index=False)

FSQ_COLS = dict(fsq_id="fsq_place_id", name_fsq="name", fsq_labels="labels", fsq_date_created="date_created",
                fsq_date_refreshed="date_refreshed", fsq_date_closed="date_closed")
for c in FSQ_COLS:
    df[c] = None
for i, j, d, sim, sa in fmatch:
    for c, src in FSQ_COLS.items():
        df.at[j, c] = fsq.at[i, src]
    if not isinstance(df.at[j, "address"], str) or not df.at[j, "address"]:
        df.at[j, "address"] = fsq.at[i, "address"]
new = fsq.loc[sorted(set(range(len(fsq))) - used_f)]
new = pd.DataFrame({"name": new.name, "lat": new.lat, "lon": new.lon, "address": new.address,
                    **{c: new[src] for c, src in FSQ_COLS.items()}})
df = pd.concat([df.drop(columns=["nname", "addr_key"]), new], ignore_index=True)


# ---------- features ----------
def closes_late(oh):
    """True if any closing time >= 22:00 or past midnight, or 24/7. None if unknown."""
    if not isinstance(oh, str) or not oh.strip():
        return None
    if "24/7" in oh:
        return True
    ends = re.findall(r"\d{1,2}:\d{2}\s*-\s*(\d{1,2}):(\d{2})", oh)
    if not ends:
        return None
    return any(int(h) >= 22 or int(h) <= 4 for h, _ in ends)


def seven_days(oh):
    if not isinstance(oh, str) or not oh.strip():
        return None
    return bool(re.search(r"24/7|mo-su|mo-sa.*su|monday-sunday", oh, re.I))


nm = (df.name.fillna("") + " " + df.name_overture.fillna("") + " " + df.name_fsq.fillna("")).str.strip()
fl = df.fsq_labels.fillna("")
df["in_osm"] = df.osm_id.notna()
df["in_overture"] = df.overture_id.notna()
df["in_fsq"] = df.fsq_id.notna()
df["is_chain"] = df.brand.notna() | nm.str.contains(CHAINS, case=False, regex=True)
df["name_missing"] = nm.eq("")
df["name_generic_market"] = nm.str.contains(GENERIC_MARKET, case=False, regex=True)
df["name_tourist_goods"] = nm.str.contains(TOURIST_GOODS, case=False, regex=True)
df["name_traditional"] = nm.str.contains(TRADITIONAL, case=False, regex=True)
df["name_alimentari"] = nm.str.contains(r"alimentar|frutta|frutteria|ortofrutta|market ?frutta", case=False, regex=True)
df["hours_known"] = df.opening_hours.notna()
df["late_hours"] = df.opening_hours.map(closes_late)
df["open_7_days"] = df.opening_hours.map(seven_days)
df["cat_convenience"] = df.osm_shop.isin(["convenience", "general", "variety_store"]) | df.ov_category.isin(["convenience_store", "grocery_store", "food_and_beverage_store", "asian_grocery_store", "international_grocery_store", "indian_grocery_store", "discount_store"]) | fl.str.contains(r"Grocery Store|Convenience Store|Food and Beverage Retail$|Discount Store", regex=True)
df["cat_other_food"] = ~df.cat_convenience & (df.osm_shop.isin(["greengrocer", "alcohol", "food", "deli", "supermarket", "grocery"]) | df.ov_category.isin(["liquor_store", "produce_store", "greengrocer", "beer_wine_spirits_store", "specialty_foods_store", "korean_grocery_store"]) | fl.str.contains(r"Supermarket|Fruit and Vegetable|Liquor|Wine Store|Beer Store|Retail > Market", regex=True))
df["ov_not_open"] = df.ov_operating_status.notna() & (df.ov_operating_status != "open")
df["fsq_closed"] = df.fsq_date_closed.notna()
df["fsq_stale"] = df.in_fsq & (df.fsq_date_refreshed.fillna("").str[:4] < "2022")
df["fsq_only_stale"] = df.fsq_stale & ~df.in_osm & ~df.in_overture

# additive score; missing hours = 0 (unknown), never negative
df["score"] = (2 * df.cat_convenience + 1 * df.cat_other_food + 2 * df.name_generic_market
               + 1 * df.name_tourist_goods + 0.5 * df.name_alimentari
               + 2 * df.late_hours.fillna(False).astype(bool) + 1 * df.open_7_days.fillna(False).astype(bool)
               - 3 * df.name_traditional - 5 * df.is_chain - 2 * df.ov_not_open - 2 * df.fsq_closed - 1 * df.fsq_only_stale)
df = df.sort_values("score", ascending=False).reset_index(drop=True)
df["gmaps"] = "https://www.google.com/maps/search/?api=1&query=" + df.lat.round(6).astype(str) + "%2C" + df.lon.round(6).astype(str)

df.to_csv(S + "rome_minimarket_candidates.csv", index=False)
g = con.sql("select * exclude (lat, lon), ST_Point(lon, lat) as geometry, lat, lon from df")
con.sql(f"COPY g TO '{S}rome_minimarket_candidates.geojson' WITH (FORMAT gdal, DRIVER 'GeoJSON')")
print("OSM kept", len(osm), "Overture kept", len(ov), "matched", len(match), "total", len(df))
