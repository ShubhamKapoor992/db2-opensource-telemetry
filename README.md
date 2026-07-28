# db2-opensource-telemetry

A lightweight telemetry dashboard that tracks open-source activity across IBM Db2 repositories on GitHub.

## Live dashboard

The `index.html` page reads `stats.json` and renders a sortable table of all tracked repositories with aggregated totals (stars, forks, open issues, contributors).

## How it works

| File | Purpose |
|------|---------|
| `update_stats.py` | Queries the GitHub Search API, aggregates repository stats, and writes `stats.json` |
| `stats.json` | Machine-generated data file consumed by the dashboard |
| `index.html` | Static dashboard — open locally or serve via GitHub Pages |
| `.github/workflows/update.yml` | GitHub Actions workflow that refreshes `stats.json` daily |

## Setup

### 1. Fork / clone this repository

```bash
git clone https://github.com/<your-org>/db2-opensource-telemetry.git
cd db2-opensource-telemetry
```

### 2. Configure repository variables (optional)

In **Settings → Secrets and variables → Actions → Variables**, add:

| Variable | Default | Description |
|----------|---------|-------------|
| `GITHUB_ORG` | `IBM` | GitHub organisation to query |
| `REPO_TOPICS` | `db2` | Comma-separated topic filters |

The built-in `GITHUB_TOKEN` secret is used automatically — no extra secret is needed.

### 3. Run locally

```bash
# Install no extra dependencies — uses only the Python standard library
python update_stats.py
```

Then open `index.html` in a browser (or serve with `python -m http.server`).

### 4. Enable GitHub Pages (optional)

Go to **Settings → Pages → Source** and select the `main` branch / root folder.  
Your dashboard will be published at `https://<org>.github.io/db2-opensource-telemetry/`.

## Automated updates

The workflow `.github/workflows/update.yml` runs every day at **02:00 UTC** and pushes a new `stats.json` commit when the data changes. You can also trigger it manually from the **Actions** tab.

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.
