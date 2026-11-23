"""Step 5. Interactive Leaflet map of the step-4 list -> late_minimarkets_map.html (in the data folder)."""
import json, os
import pandas as pd

from config import S
mm = pd.read_csv(S + "rome_gra_late_minimarkets.csv", encoding="utf-8-sig")
allp = pd.read_csv(S + "google_gra_all_places.csv")
base = allp[allp.relevant_type & ~allp.is_chain & (allp.status == "OPERATIONAL")]
gra = json.load(open(S + "gra_inner.geojson"))


def band(t):
    return "23:00–23:59" if t < 24 else ("00:00–00:59" if t < 25 else "01:00 or later")


def pts(df, extra):
    return [dict(lat=round(r.lat, 6), lon=round(r.lon, 6), **{k: (None if pd.isna(getattr(r, k)) else getattr(r, k)) for k in extra})
            for r in df.itertuples()]


clean = mm[~mm.flag_off_type].copy(); clean["band"] = clean.med_close.map(band)
off = mm[mm.flag_off_type]
data = dict(clean=pts(clean, ["name", "address", "close_time", "band", "weekday_text"]),
            off=pts(off, ["name", "address", "close_time", "primary_type"]),
            base=pts(base, ["name"]), gra=gra)

html = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Late-night minimarkets, Rome</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<style>
 html,body,#map{height:100%;margin:0;font-family:-apple-system,Helvetica,Arial,sans-serif}
 .box{background:#fff;padding:8px 10px;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.3);font-size:13px;line-height:1.5}
 .box h4{margin:0 0 4px;font-size:14px}
 .dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;vertical-align:middle;border:1px solid #333}
 .wk{font-size:11px;color:#555}
</style></head><body><div id="map"></div><script>
const D = __DATA__;
const COL = {"23:00–23:59":"#f6c445","00:00–00:59":"#e8743b","01:00 or later":"#b0203b"};
const map = L.map('map',{preferCanvas:true}).setView([41.893,12.49],12);
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
  {maxZoom:19,attribution:'&copy; OpenStreetMap contributors &copy; CARTO | shop data: Google Places'}).addTo(map);
L.geoJSON(D.gra,{style:{color:'#444',weight:1.5,fill:false,dashArray:'4 4'}}).addTo(map);
const esc = s => (s??'').toString().replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const base = L.layerGroup(D.base.map(p=>L.circleMarker([p.lat,p.lon],{radius:2,color:'#9aa3ad',weight:0,fillOpacity:.6})
  .bindTooltip(esc(p.name))));
const off = L.layerGroup(D.off.map(p=>L.circleMarker([p.lat,p.lon],{radius:4,color:'#555',weight:1,fillColor:'#ccc',fillOpacity:.9})
  .bindPopup(`<b>${esc(p.name)}</b><br>${esc(p.address)}<br>closes ${esc(p.close_time)} · ${esc(p.primary_type)}<br><i>flagged off-type</i>`)));
const clean = L.layerGroup(D.clean.map(p=>L.circleMarker([p.lat,p.lon],{radius:5,color:'#222',weight:.6,fillColor:COL[p.band],fillOpacity:.95})
  .bindPopup(`<b>${esc(p.name)}</b><br>${esc(p.address)}<br>usually closes <b>${esc(p.close_time)}</b><div class="wk">${esc(p.weekday_text).split(' | ').join('<br>')}</div>`)));
clean.addTo(map);
L.control.layers(null,{
  [`Late-night minimarkets (${D.clean.length})`]:clean,
  [`All independent food shops, Google (${D.base.length})`]:base,
  [`Flagged off-type (${D.off.length})`]:off},{collapsed:false}).addTo(map);
const lg = L.control({position:'bottomright'});
lg.onAdd = () => { const d=L.DomUtil.create('div','box');
  d.innerHTML='<h4>Usual closing time</h4>'+Object.entries(COL).map(([k,c])=>`<div><span class="dot" style="background:${c}"></span>${k}</div>`).join('')
   +'<div style="margin-top:4px"><span class="dot" style="background:#9aa3ad;border-color:#9aa3ad"></span>other independent food shops</div>'
   +'<div class="wk" style="margin-top:4px">Inside the GRA · Google Places, Oct 2026</div>'; return d; };
lg.addTo(map);
</script></body></html>"""
open(S + "late_minimarkets_map.html", "w").write(html.replace("__DATA__", json.dumps(data, ensure_ascii=False)))
print("clean", len(clean), "off", len(off), "base", len(base), "bands", clean.band.value_counts().to_dict())
