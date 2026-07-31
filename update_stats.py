import requests
import json
import time
from datetime import datetime, timezone

# ── Feature flags — toggle each source on/off independently ──────────────────
ENABLE_PYPISTATS = False   # set True to fetch from pypistats.org
ENABLE_PEPY      = True    # set True to fetch from api.pepy.tech
# ─────────────────────────────────────────────────────────────────────────────

PACKAGES = [
    {"name": "db2-sqlglot-dialect",            "framework": "SQLGlot"},
    {"name": "ibm-dbt-db2",                    "framework": "dbt"},
    {"name": "lfx-ibm",                        "framework": "Langflow Db2 AI connector"},
    {"name": "langchain-db2",                  "framework": "LangChain Db2 connector"},
    {"name": "ibm-db-haystack",                "framework": "Haystack Db2 connector"},
    {"name": "llama-index-vector-stores-db2",  "framework": "LlamaIndex Db2 connector"},
]

PYPISTATS_HEADERS = {
    "Accept":     "application/json",
    "User-Agent": "db2-opensource-telemetry/1.0 (+https://github.com/ShubhamKapoor992/db2-opensource-telemetry)"
}

PEPY_HEADERS = {
    "Accept":    "application/json",
    "X-Api-Key": "CLNCvUFl8juaVTabc1TWzm9lYJZxmRqL"
}

SLEEP_BETWEEN_CALLS = 60    # seconds between PyPIStats calls (rate-limit headroom)
SLEEP_ON_RATE_LIMIT  = 120  # seconds to back off on a 429 before one retry

# Per-source result tracking
pypistats_ok     = []  # package names written successfully from PyPIStats
pypistats_errors = []  # (package, reason) tuples for PyPIStats failures
pepy_ok          = []  # package names written successfully from Pepy
pepy_errors      = []  # (package, reason) tuples for Pepy failures

# Tracks whether this is the very first PyPIStats call (skip leading sleep)
_first_call = True


# ── PyPIStats fetch helper ────────────────────────────────────────────────────
def get_json(url, pkg_name):
    """Fetch a pypistats.org URL with rate-limit retry. Returns JSON or None."""
    global _first_call
    is_retry = False

    for attempt in (1, 2):
        if _first_call:
            _first_call = False
        elif not is_retry:
            print(f"  Sleeping {SLEEP_BETWEEN_CALLS}s before next call …")
            time.sleep(SLEEP_BETWEEN_CALLS)

        is_retry = False

        try:
            resp = requests.get(url, headers=PYPISTATS_HEADERS, timeout=15)
        except requests.RequestException as exc:
            print(f"  [{pkg_name}] network error: {exc}")
            return None

        print(f"  Status: {resp.status_code}")
        print(f"  Headers: {resp.headers.get('Content-Type')}")
        print(f"  Body: {resp.text[:500]}")

        if resp.status_code == 429:
            if attempt == 1:
                print(f"  [{pkg_name}] rate-limited (429) — sleeping {SLEEP_ON_RATE_LIMIT}s then retrying …")
                time.sleep(SLEEP_ON_RATE_LIMIT)
                is_retry = True
                continue
            else:
                print(f"  [{pkg_name}] rate-limited (429) again after retry — skipping")
                return None

        if resp.status_code == 404:
            print(f"  [{pkg_name}] not found on PyPIStats (404) — skipping")
            return None

        if not resp.ok:
            print(f"  [{pkg_name}] HTTP {resp.status_code} — skipping")
            return None

        text = resp.text.strip()
        if not text:
            print(f"  [{pkg_name}] empty response body — skipping")
            return None

        try:
            return resp.json()
        except requests.exceptions.JSONDecodeError:
            print(f"  [{pkg_name}] invalid JSON: {text[:120]}")
            return None

    return None


# ── PyPIStats fetch for one package ──────────────────────────────────────────
def fetch_pypistats(name):
    """Returns (all_time, last_month, last_day, series) or None on failure."""
    print(f"\n{'='*60}")
    print(f"  [PyPIStats] Fetching: {name}")
    print(f"  Source: https://pypistats.org/api/packages/{name}/")
    print(f"{'='*60}")

    recent_url  = f"https://pypistats.org/api/packages/{name}/recent"
    overall_url = f"https://pypistats.org/api/packages/{name}/overall?mirrors=false"

    print(f"  → GET {recent_url}")
    recent_data = get_json(recent_url, name)

    print(f"  → GET {overall_url}")
    overall_data = get_json(overall_url, name)

    if recent_data is None or overall_data is None:
        reason = "recent endpoint failed" if recent_data is None else "overall endpoint failed"
        print(f"  ✗ [PyPIStats] {name} — ERROR: {reason}")
        pypistats_errors.append((name, reason))
        return None

    series     = [x for x in overall_data["data"] if x["category"] == "without_mirrors"]
    all_time   = sum(x["downloads"] for x in series)
    last_month = recent_data["data"]["last_month"]
    last_day   = recent_data["data"]["last_day"]

    print(f"  ✓ [PyPIStats] {name} — all_time={all_time}  last_month={last_month}  last_day={last_day}")
    pypistats_ok.append(name)
    return all_time, last_month, last_day, series


# ── Pepy fetch for one package ────────────────────────────────────────────────
def fetch_pepy(name):
    """Returns (all_time, last_month, last_day, series) or None on failure."""
    print(f"\n{'='*60}")
    print(f"  [Pepy] Fetching: {name}")
    pepy_url = f"https://api.pepy.tech/api/v2/projects/{name}"
    print(f"  Source: {pepy_url}")
    print(f"  → GET {pepy_url}  (X-Api-Key header included)")
    print(f"{'='*60}")

    try:
        resp = requests.get(pepy_url, headers=PEPY_HEADERS, timeout=15)
        print(f"  Status: {resp.status_code}")

        if not resp.ok:
            reason = f"HTTP {resp.status_code}"
            print(f"  ✗ [Pepy] {name} — ERROR: {reason}")
            pepy_errors.append((name, reason))
            return None

        data      = resp.json()
        all_time  = data.get("total_downloads")
        raw_dl    = data.get("downloads") or {}

        series = sorted(
            [
                {"date": d, "downloads": sum(v for v in versions.values())}
                for d, versions in raw_dl.items()
            ],
            key=lambda x: x["date"]
        )

        last_day   = series[-1]["downloads"] if series else None
        last_month = sum(e["downloads"] for e in series[-30:]) if series else None

        print(f"  ✓ [Pepy] {name} — all_time={all_time}  last_month={last_month}  last_day={last_day}  series_days={len(series)}")
        pepy_ok.append(name)
        return all_time, last_month, last_day, series

    except Exception as exc:
        reason = str(exc)
        print(f"  ✗ [Pepy] {name} — ERROR: {reason}")
        pepy_errors.append((name, reason))
        return None


# ── Main loop ─────────────────────────────────────────────────────────────────
result = []

for pkg in PACKAGES:
    name = pkg["name"]

    # ── PyPIStats ─────────────────────────────────────────────────────────────
    if ENABLE_PYPISTATS:
        ps = fetch_pypistats(name)
        if ps is None:
            # fetch failed — skip this package entirely for PyPIStats
            pypistats_entry = {"all_time": None, "last_month": None, "last_day": None, "series": []}
        else:
            ps_all_time, ps_last_month, ps_last_day, ps_series = ps
            pypistats_entry = {
                "all_time":   ps_all_time,
                "last_month": ps_last_month,
                "last_day":   ps_last_day,
                "series":     ps_series
            }
    else:
        print(f"  [PyPIStats] {name} — SKIPPED (ENABLE_PYPISTATS=False)")
        pypistats_entry = {"all_time": None, "last_month": None, "last_day": None, "series": []}

    # ── Pepy ──────────────────────────────────────────────────────────────────
    if ENABLE_PEPY:
        pepy = fetch_pepy(name)
        if pepy is None:
            pepy_entry = {"all_time": None, "last_month": None, "last_day": None, "series": []}
        else:
            pepy_all_time, pepy_last_month, pepy_last_day, pepy_series = pepy
            pepy_entry = {
                "all_time":   pepy_all_time,
                "last_month": pepy_last_month,
                "last_day":   pepy_last_day,
                "series":     pepy_series
            }
    else:
        print(f"  [Pepy]      {name} — SKIPPED (ENABLE_PEPY=False)")
        pepy_entry = {"all_time": None, "last_month": None, "last_day": None, "series": []}

    result.append({
        "package":   name,
        "framework": pkg["framework"],
        "pypistats": pypistats_entry,
        "pepy":      pepy_entry
    })

# ── Write stats.json ──────────────────────────────────────────────────────────
with open("stats.json", "w") as f:
    json.dump(
        {
            "generated": datetime.now(timezone.utc).isoformat(),
            "packages":  result
        },
        f,
        indent=2
    )

# ── Final summary ─────────────────────────────────────────────────────────────
total = len(PACKAGES)
print(f"\n{'='*60}")
print(f"  SUMMARY")
print(f"{'='*60}")

if ENABLE_PYPISTATS:
    print(f"  PyPIStats  Wrote {len(pypistats_ok)}/{total} packages")
    for n in pypistats_ok:
        print(f"    ✓  {n}")
    if pypistats_errors:
        print(f"  PyPIStats  Errors ({len(pypistats_errors)}/{total}):")
        for n, reason in pypistats_errors:
            print(f"    ✗  {n}  →  {reason}")
else:
    print(f"  PyPIStats  DISABLED (ENABLE_PYPISTATS=False)")

print()

if ENABLE_PEPY:
    print(f"  Pepy       Wrote {len(pepy_ok)}/{total} packages")
    for n in pepy_ok:
        print(f"    ✓  {n}")
    if pepy_errors:
        print(f"  Pepy       Errors ({len(pepy_errors)}/{total}):")
        for n, reason in pepy_errors:
            print(f"    ✗  {n}  →  {reason}")
else:
    print(f"  Pepy       DISABLED (ENABLE_PEPY=False)")

print(f"{'='*60}")
