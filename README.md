---
title: LA Homeless Outreach Map
emoji: 🗺️
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
---

# LA Homeless Outreach Map

Interactive day-by-day map of homeless encampment activity across Los Angeles in 2025, built for DataSci 112. The project combines citizen 311 reports, county outreach forms, LAPD crime data, HUD poverty indicators, and shelter inventory into a Dash/Plotly web app. A separate analysis pipeline merges these sources and fits a discrete spatiotemporal point process model (`surveillance::hhh4`).

## Quick Start

**Run the map locally** (from project root):

```bash
pip install -r requirements.txt
python map/app.py
```

Open [http://127.0.0.1:7860](http://127.0.0.1:7860). Data is read from `data/` at the project root.

**Run with Docker** (matches Hugging Face deployment):

```bash
docker build -t la-encampment-map .
docker run -p 7860:7860 la-encampment-map
```

See [map/DEPLOY_HUGGINGFACE.md](map/DEPLOY_HUGGINGFACE.md) for full deployment instructions.

**Analysis notebooks** — run Jupyter from the project root so `data/` paths resolve:

```bash
pip install -e .
jupyter notebook notebooks/
```

For poverty-signal cleaning, copy `.env.example` to `.env` and set `CENSUS_API_KEY`.

## Repository Layout

```
datasci112_finalproject/
├── data/              Raw and derived CSVs (LAHSA, LAPD, MyLA311, census, shelters, merged, plots)
├── map/               Deployable Dash application (app.py, map_builder.py)
├── notebooks/
│   ├── cleaning/      ETL: precinct assignment, HUD QCT, HIC shelter data
│   ├── exploration/   EDA and event-table merge for modeling
│   └── modeling/      Canonical hhh4 lag-1 point process (R)
├── scripts/           Standalone utilities (precinct circle PNG)
├── scraping/          News article scraper (separate from map)
└── archive/modeling/  Superseded modeling attempts (Python Hawkes, multilag R, glmnet)
```

## Data Sources

| Source | Description | Used by |
|--------|-------------|---------|
| **MyLA311** | City 311 encampment service requests (~96k in 2025) | Map, merge, EDA |
| **LAHSA** | County homeless encampment outreach request forms (~900) | Map, merge, EDA |
| **LAPD NIBRS** | Crime offenses with homeless-involvement flags | Map, merge, modeling |
| **HUD QCT** | Qualified Census Tracts (poverty context by precinct) | Map, cleaning, modeling |
| **LAHSA HIC** | 2025 Housing Inventory Count (shelter beds) | Map, merge, modeling |

Canonical MyLA311 file: `data/MyLA311/MyLA311_Service_Request_Homeless_Encampment_Combined_2025_20260524.csv`. Older exports live in `data/archive/MyLA311/`.

## Analysis Pipeline

1. **Clean** — `notebooks/cleaning/` assigns LAPD precincts to LAHSA sites, aggregates HUD QCT counts, and processes shelter/HIC data.
2. **Explore** — `notebooks/exploration/explore_csv.ipynb` compares MyLA311 and LAHSA spatially and temporally.
3. **Merge** — `notebooks/exploration/merge_events_for_modeling.ipynb` builds `data/merged/events_merged.csv`.
4. **Model** — `notebooks/modeling/point_process_hhh4_lag1.Rmd` fits an endemic-epidemic hhh4 model on a 22-precinct × 365-day panel.

## Key Findings

- **Two parallel systems** — MyLA311 records resident complaints (LA City); LAHSA records county outreach responses. They overlap spatially only ~2% of the time.
- **Heavy duplicate reporting** — DBSCAN deduplication shows ~73% of MyLA311 encampment reports are re-reports of the same location within a week.
- **Anonymous reports** — 36.6% of encampment 311 reports are anonymous, vs. ~10% for other request types.
- **Poverty concentration** — QCT counts per precinct (Hollenbeck: 97, Southeast: 76, Newton: 53) track areas of high encampment activity.

For full per-file documentation, see [PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md).
