# Yardage book generator — prototype

Builds a tour-style yardage book page for a golf hole entirely from free,
public data. First target: **Bridlewood Golf Club, Flower Mound TX — hole 1,
black tees**.

## Output

`out/bridlewood_01.pdf` — three 4in x 7in pages:

1. **Green page** — hole badge, note area, green blow-up with a 5x5 grid,
   6-inch contours and downhill arrows at 4% and steeper.
2. **Hole page** — layout with the tee at the bottom and green at the top,
   reference stations, bunker carries, distance arcs, tee table.
3. **Legend** — the number convention, the data sources, and what is missing.

Par 5s get two hole pages (tee and approach); the green blow-up appears once,
on the page carrying the approach.

## Data sources

| Layer | Source | Licence |
|---|---|---|
| Green, bunker, water, tee, hole centreline | OpenStreetMap | ODbL, attribution required |
| Elevations, green contours, slope | USGS 3DEP 1 m bare-earth lidar | public domain |
| Mown envelope, tree canopy | USDA NAIP 4-band imagery | public domain |
| Hole yardage and par | published scorecard | reference only |

Nothing is surveyed on the ground and nothing is traced from a licensed
basemap.

## Pipeline

```
pipeline/naip.py      fetch NAIP imagery over the hole corridor
pipeline/classify.py  turf / tree / sand / water classification
pipeline/turf.py      vectorise the mown envelope
pipeline/trees.py     vectorise tree canopy
pipeline/model.py     local metric frame, OSM loader, DEM sampler
pipeline/build.py     line of play, green front/back, stations, carries, tees
pipeline/greens.py    green contours and slope field from lidar
pipeline/render.py    draw the PDF
```

Run in that order from the `pipeline/` directory. Intermediates are cached on
disk, so repeat runs do not re-download.

## Known gaps on this hole

- **Sprinkler-head numbers** have no public source. Reference points are
  stations along the line of play instead.
- **Fairway / rough mowing line** is not separable — the NAIP capture is
  drought-dormant and has no mowing contrast.
- **The black tee box** is absent from OpenStreetMap. The mapped ladder tops
  out at 381 yd to the green centre against a scorecard 428; the tee table
  prints scorecard yardages and the page geometry is drawn from the mapped
  tees.
- **Green contours** come from airborne lidar (~3-5 cm effective vertical on a
  smooth surface). Good for structure, not a substitute for a ground survey.

## Converting pages from another generator

`convert/` re-lays pages produced by another yardage-book app into this
format. Run order:

```
convert/extract.py   segment the source page; trace green, corridor, hazards
convert/build2.py    calibrate px->yards, rotate the play line up
convert/render2.py   draw the pages
```

Calibration uses two figures printed on the source page: the stated green
depth sets the green-panel scale, and the stated tee-to-green distance sets
the hole-panel scale. Traced green extents came back at 15 x 35 yd against
16 x 35 stated, and 26 x 33 against 26 x 33 stated.

`out/converted_holes.pdf` holds Cowboys 9 (vector source) and Bridlewood 9
(satellite source), plus a page of conversion notes.

### The gap this exposed

The source green panel carries an outline, a depth, a width and perimeter
depth figures — and no surface data. No contours, no slope. That is the
centre of this format's green page, so conversion alone cannot fill it.
Filling it needs a second source: lidar (see `pipeline/greens.py`), a drone
survey, or bought green maps.

## Converting a vector source book

`convert/pdfx3.py` -> `convert/book.py` -> `convert/draw.py` converts a Shot
Pattern yardage-book PDF (39 pages, 3.75 x 6.5 in, fully vector) into this
format. `out/cowboys_pro_book.pdf` is Cowboys Golf Club, all 18 holes, 42
pages: cover, legend, then a green page and one or two hole pages per hole.

### How the layers are read

Quartz emits a filled-and-stroked shape as two separate operations, so shapes
are identified by fill/stroke colour pairs and then re-paired:

| Feature | Fill | Stroke |
|---|---|---|
| putting green | 0.94, 0.975, 0.93 | 0.56, 0.74, 0.50 |
| short grass | 0.89, 0.94, 0.87 | 0.70, 0.82, 0.66 |
| water | 0.80, 0.89, 0.97 | 0.42, 0.63, 0.85 |
| sand | 0.94, 0.88, 0.72 | 0.74, 0.63, 0.42 |
| trees | 0.50, 0.70, 0.42 | - |
| tee box | short-grass fill | ink, w >= 0.7 |

Text is stamped nine times on a 0.7 pt cross to fake bold, and minus signs are
U+2212; both need normalising before anything parses.

### Calibration

Scale and aim point come from a circle fit on the source range arcs. On hole 9
the three arcs share one centre to 0.5 pt with radii at exactly 1 : 1.5 : 2.0
against their 100/150/200 labels. Par 3s carry no arcs, so those calibrate from
the tee box centroid to the green centroid against the printed "yd to green".

### Accuracy

Every carry number printed in the source book was re-derived from the extracted
geometry. Across 38 numbers the median difference is **0.4 yd**, the 90th
percentile **1.2 yd**, and the largest **2.0 yd**.

### Still missing

The source book has no green contour or slope data, so the centre of each green
page stays open. Everything else in this format converts.
