import requests
import json
import time
from datetime import datetime, timezone

PACKAGES = [
    {
        "name": "db2-sqlglot-dialect",
        "framework": "SQLGlot"
    },
    {
        "name": "ibm-dbt-db2",
        "framework": "dbt"
    },
    {
        "name": "lfx-ibm",
        "framework": "Langflow Db2 AI connector"
    },
    {
        "name": "langchain-db2",
        "framework": "LangChain Db2 connector"
    },
    {
        "name": "ibm-db-haystack",
        "framework": "Haystack Db2 connector"
    },
    {
        "name": "llama-index-vector-stores-db2",
        "framework": "LlamaIndex Db2 connector"
    }
]

PYPISTATS_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "db2-opensource-telemetry/1.0 (+https://github.com/ShubhamKapoor992/db2-opensource-telemetry)"
}

PEPY_HEADERS = {
    "Accept":    "application/json",
    "X-Api-Key": "CLNCvUFl8juaVTabc1TWzm9lYJZxmRqL"
}

SLEEP_BETWEEN_CALLS = 0     # TEST MODE — set to 60 for production
SLEEP_ON_RATE_LIMIT = 0     # TEST MODE — set to 120 for production

# Track whether this is the very first call so we don't sleep before it
_first_call = True


def get_json(url, pkg_name):
    """Fetch URL and return parsed JSON, or None on any error.

    Sleeps SLEEP_BETWEEN_CALLS seconds before every call (except the first
    call ever, and except after a 429 retry — the backoff already covers it).
    On a 429 response, waits SLEEP_ON_RATE_LIMIT seconds then retries once.
    """
    global _first_call
    is_retry = False

    for attempt in (1, 2):
        # Sleep before the call — skip before the very first call ever,
        # and skip on a retry (the 429 backoff sleep already ran).
        if _first_call:
            _first_call = False
        elif not is_retry:
            print(f"  Sleeping {SLEEP_BETWEEN_CALLS}s before next call …")
            time.sleep(SLEEP_BETWEEN_CALLS)

        is_retry = False  # reset for next iteration

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
            print(f"  [{pkg_name}] not found on PyPI Stats (404) — skipping")
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


result = []

for pkg in PACKAGES:
    name = pkg["name"]

    # ── Tab 1 · PyPIStats ────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  [Tab 1 · PyPIStats] Fetching: {name}")
    print(f"  Source: https://pypistats.org/api/packages/{name}/")
    print(f"{'='*60}")

    recent_url  = f"https://pypistats.org/api/packages/{name}/recent"
    overall_url = f"https://pypistats.org/api/packages/{name}/overall?mirrors=false"

    print(f"  → GET {recent_url}")
    recent_data = get_json(recent_url, name)

    print(f"  → GET {overall_url}")
    overall_data = get_json(overall_url, name)

    if recent_data is None or overall_data is None:
        print(f"  [PyPIStats/{name}] skipped — incomplete data")
        continue

    series = [
        x for x in overall_data["data"]
        if x["category"] == "without_mirrors"
    ]
    all_time   = sum(x["downloads"] for x in series)
    last_month = recent_data["data"]["last_month"]
    last_day   = recent_data["data"]["last_day"]

    print(f"  [PyPIStats/{name}] ✓ all_time={all_time}  last_month={last_month}  last_day={last_day}")

    # ── Tab 2 · Pepy ─────────────────────────────────────────────────────────
    print(f"\n  [Tab 2 · Pepy] Fetching: {name}")
    pepy_url = f"https://api.pepy.tech/api/v2/projects/{name}"
    print(f"  Source: {pepy_url}")
    print(f"  → GET {pepy_url}  (X-Api-Key header included)")

    pepy_all_time   = None
    pepy_last_month = None
    pepy_last_day   = None
    pepy_series     = []
    try:
        pepy_resp = requests.get(pepy_url, headers=PEPY_HEADERS, timeout=15)
        print(f"  [Pepy/{name}] Status: {pepy_resp.status_code}")
        if pepy_resp.ok:
            pepy_data     = pepy_resp.json()

            # total_downloads = all-time
            pepy_all_time = pepy_data.get("total_downloads")

            # downloads = { "YYYY-MM-DD": { "version": count, ... } }
            raw_dl = pepy_data.get("downloads") or {}

            # Build daily series: sum all versions per day, sort ascending by date
            pepy_series = sorted(
                [
                    {"date": d, "downloads": sum(v for v in versions.values())}
                    for d, versions in raw_dl.items()
                ],
                key=lambda x: x["date"]
            )

            # last_day   = most recent day's total
            # last_month = sum of last 30 days
            if pepy_series:
                pepy_last_day   = pepy_series[-1]["downloads"]
                pepy_last_month = sum(e["downloads"] for e in pepy_series[-30:])

            print(f"  [Pepy/{name}] ✓ all_time={pepy_all_time}  last_month={pepy_last_month}  last_day={pepy_last_day}  series_days={len(pepy_series)}")
        else:
            print(f"  [Pepy/{name}] HTTP {pepy_resp.status_code} — data unavailable")
    except Exception as exc:
        print(f"  [Pepy/{name}] error: {exc}")

    # ── stats.json entry — fields grouped by source ───────────────────────
    result.append({
        "package":   name,
        "framework": pkg["framework"],
        # Tab 1 · PyPIStats (excludes mirror downloads)
        "pypistats": {
            "all_time":   all_time,
            "last_month": last_month,
            "last_day":   last_day,
            "series":     series
        },
        # Tab 2 · Pepy (includes mirror downloads)
        "pepy": {
            "all_time":   pepy_all_time,
            "last_month": pepy_last_month,
            "last_day":   pepy_last_day,
            "series":     pepy_series
        }
    })

    print(f"\n  Saved to stats.json → pypistats.all_time={all_time} | pepy.all_time={pepy_all_time}")

with open("stats.json", "w") as f:
    json.dump(
        {
            "generated": datetime.now(timezone.utc).isoformat(),
            "packages":  result
        },
        f,
        indent=2
    )

print(f"\n{'='*60}")
print(f"Done. Wrote {len(result)}/{len(PACKAGES)} packages to stats.json")
print(f"  Tab 1 (PyPIStats) fields: all_time, last_month, last_day, series")
print(f"  Tab 2 (Pepy)      fields: all_time, last_month, last_day, series")
print(f"{'='*60}")
