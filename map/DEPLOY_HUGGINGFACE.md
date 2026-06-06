# Deploying the Map to Hugging Face Spaces

This tutorial walks through deploying `map_builder.py` to a free, persistent Hugging Face Space so anyone can view the map at a public URL.

**What you will create:**
- A Docker-based HF Space at `https://huggingface.co/spaces/<your-username>/<space-name>`
- Three new files in this repo: `app.py`, `Dockerfile`, `requirements.txt`

**Time estimate:** ~30 minutes the first time.

---

## Prerequisites

You need two tools installed. Check with:
```bash
git --version        # should be ≥ 2.x
git lfs version      # if this fails, install git-lfs (step below)
```

Install `git-lfs` if missing (needed for the 32 MB CSV):
```bash
brew install git-lfs   # macOS
```

---

## Part 1 — Create the HF Space

1. Go to [huggingface.co](https://huggingface.co) and sign in (create a free account if needed).

2. Click your profile icon → **New Space**.

3. Fill in the form:
   - **Space name:** e.g. `la-homeless-outreach-map`
   - **License:** MIT (or leave blank)
   - **Space SDK:** select **Docker**
   - **Visibility:** Public (required for a free shareable link)

4. Click **Create Space**. HF creates a new git repo at  
   `https://huggingface.co/spaces/<your-username>/la-homeless-outreach-map`

5. Go to **Settings → Access Tokens** at  
   `https://huggingface.co/settings/tokens`  
   and create a **Write** token. Copy and save it — you will use it when pushing.

---

## Part 2 — Create the deployment files

### `requirements.txt`

Create this file in the root of the repo with the following content:

```
dash>=4.1.0
pandas>=3.0.1
plotly>=6.7.0
gunicorn>=23.0.0
```

This is intentionally minimal — it includes only what `map_builder.py` imports at runtime.

---

### `app.py`

This is a thin entry-point wrapper that starts the server on the port HF Spaces expects (`7860`), and exposes the Flask `server` object so gunicorn can find it.

```python
from map_builder import (
    build_layers,
    build_app,
    DailyMarkerIndex,
    PrecinctLayer,
    ShelterLayer,
    PRECINCT_PATH,
    NIBRS_PATH,
    SHELTER_PATH,
)

layers = build_layers()
index = DailyMarkerIndex(layers)
precinct_layer = PrecinctLayer()
precinct_layer.load(PRECINCT_PATH, NIBRS_PATH)
shelter_layer = ShelterLayer()
shelter_layer.load(SHELTER_PATH)

app = build_app(index, layers, precinct_layer, shelter_layer)
server = app.server  # gunicorn entry point: app:server

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7860)
```

---

### `Dockerfile`

HF Spaces Docker containers must listen on port `7860` and run as user `1000`.

```dockerfile
FROM python:3.13-slim

# HF Spaces requires user 1000
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

# Install dependencies first (cached layer if requirements.txt unchanged)
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source and data
COPY --chown=user map_builder.py app.py ./

COPY --chown=user \
    data/MyLA311/MyLA311_Service_Request_Homeless_Encampment_Combined_2025_20260524.csv \
    data/MyLA311/

COPY --chown=user \
    data/LAHSA/LA_County_Homeless_Encampment_Request_Forms_with_precinct.csv \
    data/LAHSA/

COPY --chown=user \
    data/LAPD/LAPD_NIBRS_Offenses_Dataset_2024_to_2025_20260526.csv \
    data/LAPD/lapd_precincts_combined.csv \
    data/LAPD/

COPY --chown=user \
    data/census_indicators/qct_by_prec.csv \
    data/census_indicators/

COPY --chown=user \
    data/shelters/2025_HIC_All_Projects.csv \
    data/shelters/

EXPOSE 7860

# --workers 1: the app holds all data in memory; multiple workers would duplicate that
# --timeout 120: loading the 32 MB CSV at startup takes ~10-20 s; allow extra margin
CMD ["gunicorn", "app:server", "--bind", "0.0.0.0:7860", "--workers", "1", "--timeout", "120"]
```

> **Why copy each file explicitly?**  
> The `data/` folder contains several large files not needed by the map (e.g. the 29 MB
> `MyLA311_Cases_March_2025_to_December_2025_20260524.csv`). Copying only what
> `map_builder.py` uses keeps the Docker image smaller and the build faster.

---

### Update `README.md`

HF Spaces reads metadata from a YAML block at the very top of `README.md`. Prepend these lines to the existing `README.md` (replace the values in angle brackets):

```yaml
---
title: LA Homeless Outreach Map
emoji: 🗺️
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
---
```

---

## Part 3 — Set up Git LFS for large files

HF Spaces is a git repo. The 32 MB CSV must be stored in Git LFS or HF will reject the push.

```bash
# One-time setup (run from inside the datasci112_finalproject folder)
git lfs install

# Tell LFS to track the two large CSVs used by map_builder.py
git lfs track "data/MyLA311/MyLA311_Service_Request_Homeless_Encampment_Combined_2025_20260524.csv"
git lfs track "data/LAPD/LAPD_NIBRS_Offenses_Dataset_2024_to_2025_20260526.csv"

# Stage the updated .gitattributes file that lfs just created/modified
git add .gitattributes
```

Verify that LFS is tracking the right files:
```bash
git lfs ls-files
# should list the two CSVs above (once you stage them in step 4 below)
```

---

## Part 4 — Add the HF remote and push

```bash
# Add HF Space as a second remote (your existing GitHub remote stays unchanged)
git remote add space https://huggingface.co/spaces/<your-username>/la-homeless-outreach-map

# Stage all new files
git add requirements.txt app.py Dockerfile README.md .gitattributes
git add data/MyLA311/MyLA311_Service_Request_Homeless_Encampment_Combined_2025_20260524.csv
git add data/LAPD/LAPD_NIBRS_Offenses_Dataset_2024_to_2025_20260526.csv

git commit -m "Add HF Spaces deployment files"

# Push to HF — you will be prompted for credentials
# Username: your HF username
# Password: the Write token you created in Part 1
git push space main
```

If your local branch is named `master` instead of `main`:
```bash
git push space master:main
```

---

## Part 5 — Monitor the build

1. Go to `https://huggingface.co/spaces/<your-username>/la-homeless-outreach-map`.

2. Click the **Logs** tab. You will see Docker building the image and then gunicorn starting.

3. The first build takes **5–15 minutes** (downloading Python, installing packages, uploading the LFS files).

4. Once the status dot turns green, click **App** to open the live map.

Your public URL is:
```
https://<your-username>-la-homeless-outreach-map.hf.space
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Build fails: `file too large` | CSV not tracked by LFS | Re-run `git lfs track ...` and push again |
| App crashes on startup | gunicorn timeout too short while loading CSV | Increase `--timeout` in `Dockerfile` CMD |
| `ModuleNotFoundError` | Missing package in `requirements.txt` | Add the package and push again |
| Blank white page after load | Port mismatch | Confirm `EXPOSE 7860` and `--bind 0.0.0.0:7860` match `app_port: 7860` in README |
| Push rejected: `LFS objects missing` | LFS files not staged | `git add <csv-file>` then commit and push again |

---

## Keeping the Space updated

After any code or data change, push to HF the same way:

```bash
git add <changed files>
git commit -m "your message"
git push space main          # pushes to HF Space
git push origin main         # pushes to GitHub (unchanged workflow)
```

HF will automatically rebuild the Docker image on each push.
