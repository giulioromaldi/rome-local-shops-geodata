# Mapping independent neighbourhood food shops in Rome

A Python pipeline that builds a geolocated dataset of independent small food shops in Rome
(minimarkets and convenience stores) and of their opening hours, by combining four open and
commercial sources of points of interest. It is part of my PhD research on how tourism reshapes
city neighbourhoods, where the composition of local retail is one of the outcomes of interest.

The current output is a map of independent shops inside Rome's ring road (the GRA) that usually
close at 23:00 or later, a type of shop that is hard to capture with official business registers.

## Pipeline

| Step | Script | What it does |
|---|---|---|
| 1 | `src/build_candidates.py` | Merges OpenStreetMap, Overture Maps Places and Foursquare Open Source Places into one candidate dataset. Records are matched within 60 m with similar names, or by normalised address. Every classification signal is kept as a separate column (category, generic shop names, chains, traditional shops, opening hours, closure flags) and combined in an additive score. |
| 2 | `src/google_grid.py` | Systematic search of Google Places (Nearby Search) inside the GRA with an adaptive quadtree: a cell is queried with its circumscribed circle and split into four whenever Google returns the maximum of 20 results. Responses are cached, so reruns only pay for missing cells, and new paid calls are capped. |
| 3 | `src/google_hours.py` | Looks up opening hours on Google Places for the step-1 candidates with a high score, matching each result by distance and name similarity. |
| 4 | `src/build_final_list.py` | Combines steps 2 and 3, excludes chains and shops that are not operational, and keeps shops whose median closing time is 23:00 or later. Shops whose name or type suggests a different activity are flagged rather than dropped. |
| 5 | `src/make_map.py` | Writes an interactive Leaflet map of the final list, by usual closing time. |

Shared name patterns and category lists are in `src/lexicons.py`, paths and credentials in `src/config.py`.

## Validation

A sample of 100 step-1 candidates, stratified by score, was checked by hand. Precision is about
4% in the lowest score band and about 46% for scores of 3 or more, which motivated the switch to
the systematic Google grid search (step 2) as the main source for the final list. In the current
run the final list contains 400 shops inside the GRA, of which 319 are retained after flagging
off-type activities.

## Data

No data are included in this repository. To run the pipeline, place the inputs in `data/` (or in a
folder set with the `ROME_SHOPS_DATA` environment variable):

- `osm_rome_allshops.json`: all `shop=*` features in the Rome area from the OpenStreetMap Overpass API;
- `overture_rome_clipped.parquet`: Overture Maps Places, clipped to the Rome boundary;
- `foursquare_rome_clipped.parquet`: Foursquare Open Source Places, clipped to the Rome boundary;
- `rome_boundary.parquet`: Rome municipal boundary;
- `gra_inner.geojson`: polygon of the area inside the GRA ring road, built from OpenStreetMap.

Steps 2 and 3 need a Google Places API key, read from the `GOOGLE_PLACES_API_KEY` environment
variable or from `~/.google_places_key`. Keys are never stored in the code.

Licences of the sources: OpenStreetMap (ODbL), Overture Maps (CDLA-Permissive-2.0 and ODbL,
depending on the source), Foursquare Open Source Places (Apache 2.0). Google Places content cannot
be redistributed under Google's terms of service, which is why outputs are not published here.

## Usage

```bash
pip install -r requirements.txt
python3 src/build_candidates.py
python3 src/google_grid.py 3000      # optional argument: cap on new paid calls
python3 src/google_hours.py
python3 src/build_final_list.py
python3 src/make_map.py
```

## Limitations

The dataset is a cross-section: the open sources do not record reliably when a shop opened, so
the pipeline does not yet support a panel. Opening hours come from Google Places and may be
outdated for some shops, and coverage of the open sources varies across neighbourhoods.

## Author

Giulio Romaldi, PhD candidate in Institutions and Policies, Università Cattolica del Sacro Cuore (Milan).
Code developed with the help of AI coding assistants.
