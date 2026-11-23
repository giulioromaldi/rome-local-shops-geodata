"""Step 4. Final list of independent late-night (close >= 23:00) food shops inside the GRA.
Union of the Google grid search (main source) and the earlier candidate-based Google lookup;
off-type shops are flagged, not dropped."""
import os
import pandas as pd, geopandas as gpd
from shapely.geometry import Point

from config import S
from lexicons import CHAINS, GENERIC_MARKET, TRADITIONAL, GOOGLE_KEEP_TYPES as KEEP_TYPES

gra = gpd.read_file(S + "gra_inner.geojson").geometry.iloc[0]

# main source: grid search
a = pd.read_csv(S + "google_gra_all_places.csv")
grid = a[a.relevant_type & ~a.is_chain & (a.status == "OPERATIONAL") & a.late23].copy()
grid["source"] = "grid"

# complement: late shops from the earlier lookup that the grid never returned
o = pd.read_csv(S + "google_hours_candidates.csv")
o = o[(o.late23 == True) & (o.g_status == "OPERATIONAL")].drop_duplicates("g_place_id")
o = o[[gra.contains(Point(x, y)) for x, y in zip(o.lon, o.lat)]]
o = o[~o.g_place_id.isin(a.g_place_id)]
o = pd.DataFrame(dict(g_place_id=o.g_place_id, name=o.g_name, address=o.address, lat=o.lat, lon=o.lon,
                      primary_type=o.g_primary_type, status=o.g_status, hours_known=True, weekday_text=o.g_weekday_text,
                      days_open=o.days_open, med_close=o.med_close, max_close=o.max_close, late23=True,
                      source="candidate_lookup"))
o = o[~o.name.str.contains(CHAINS, case=False, regex=True)]

df = pd.concat([grid, o], ignore_index=True).drop_duplicates("g_place_id")

OFF_TYPE = (TRADITIONAL + r"|eataly|cocomer|anguria|pasta ?(?:&|and)? ?go|take ?away|gastronom|rosticceria|"
            r"gelat|vino|wine|birr|beer ?shop|cantina|distill|caffe|coffee|bar\b|tabacc|edicola|"
            r"frutta secca|dolci|cioccolat|pizza|kebab|sushi|bio\b|natura|vegan|"
            r"cloth|dropship|dummy|studio|fiori|piante|locker|amazon|protein|nutri|fit\b|hemp|cbd|canap|ristorator|"
            r"benessere|salute|mercatino|mercato |casalingh|delivery|bambolina|ingrosso|intollerant|caesar pasta|"
            r"^via |^viale |^piazza |^circonvallazione |srl$|srls$|"
            r"glovo|km ?0|traditional food|camping|bistr|pizz|panin|pesce|\bpane\b|carne|mense|\bpub\b|exchange|sportello")
df["flag_off_type"] = df.name.str.contains(OFF_TYPE, case=False, regex=True) & \
    ~df.name.str.contains(r"mini ?-?market|minimarket|minimercato|alimentar|market", case=False, regex=True)
df["flag_off_type"] |= ~df.primary_type.isin(KEEP_TYPES)
df["name_minimarket"] = df.name.str.contains(GENERIC_MARKET + r"|alimentar", case=False, regex=True)
df["name_fruit_shop"] = df.name.str.contains(r"frutt|fruit|verdura|vegetabl|ortofrutt", case=False, regex=True) & \
    ~df.name.str.contains(r"mini ?-?market|minimarket|alimentar", case=False, regex=True)
df["open_24h"] = df.max_close >= 28
df["close_time"] = df.med_close.map(lambda t: f"{int(t) % 24:02d}:{int(round((t % 1) * 60)):02d}")

cols = ["g_place_id", "name", "address", "lat", "lon", "primary_type", "close_time", "med_close", "max_close",
        "days_open", "open_24h", "weekday_text", "name_minimarket", "name_fruit_shop", "flag_off_type", "source"]
df = df[cols].sort_values(["flag_off_type", "med_close"], ascending=[True, False]).reset_index(drop=True)
df.to_csv(S + "rome_gra_late_minimarkets.csv", index=False, encoding="utf-8-sig")
gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat), crs=4326).to_file(S + "rome_gra_late_minimarkets.geojson", driver="GeoJSON")
print(f"total {len(df)} (grid {(df.source == 'grid').sum()}, candidate_lookup {(df.source == 'candidate_lookup').sum()}); "
      f"flag_off_type {df.flag_off_type.sum()}; fruit_shop {(df.name_fruit_shop & ~df.flag_off_type).sum()}; kept {(~df.flag_off_type).sum()}; open_24h {df.open_24h.sum()}")
