import requests
import json
import time
from datetime import datetime

PACKAGES = [
    {
        "name": "db2-sqlglot-dialect",
        "framework": "SQLGlot"
    },
    {
        "name": "ibm-dbt-db2",
        "framework": "dbt"
    }
]

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "db2-opensource-telemetry/1.0 (+https://github.com/ShubhamKapoor992/db2-opensource-telemetry)"
}

SLEEP_BETWEEN_CALLS = 35   # seconds between every API call
SLEEP_ON_RATE_LIMIT = 30   # extra seconds to wait after a 429


def get_json(url, pkg_name):
    """Fetch URL and return parsed JSON, or None on any error.
    On a 429 response, waits SLEEP_ON_RATE_LIMIT seconds then retries once.
    """
    for attempt in (1, 2):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
        except requests.RequestException as exc:
            print(f"  [{pkg_name}] network error: {exc}")
            return None

        print(f"  Status: {resp.status_code}")
        print(f"  Headers: {resp.headers.get('Content-Type')}")
        print(f"  Body: {resp.text[:500]}")

        if resp.status_code == 429:
            if attempt == 1:
                print(f"  [{pkg_name}] rate-limited (429) — sleeping {SLEEP_ON_RATE_LIMIT}s then retrying…")
                time.sleep(SLEEP_ON_RATE_LIMIT)
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
    print(f"\nFetching {name} …")

    recent_data = get_json(
        f"https://pypistats.org/api/packages/{name}/recent",
        name
    )
    print(f"  Sleeping {SLEEP_BETWEEN_CALLS}s …")
    time.sleep(SLEEP_BETWEEN_CALLS)

    overall_data = get_json(
        f"https://pypistats.org/api/packages/{name}/overall?mirrors=false",
        name
    )
    print(f"  Sleeping {SLEEP_BETWEEN_CALLS}s …")
    time.sleep(SLEEP_BETWEEN_CALLS)

    if recent_data is None or overall_data is None:
        print(f"  [{name}] skipped — incomplete data")
        continue

    series = [
        x for x in overall_data["data"]
        if x["category"] == "without_mirrors"
    ]

    all_time = sum(x["downloads"] for x in series)

    result.append({
        "package": name,
        "framework": pkg["framework"],
        "all_time": all_time,
        "last_month": recent_data["data"]["last_month"],
        "last_day": recent_data["data"]["last_day"],
        "series": series
    })

    print(f"  [{name}] all-time={all_time}  last_month={recent_data['data']['last_month']}  last_day={recent_data['data']['last_day']}")

with open("stats.json", "w") as f:
    json.dump(
        {
            "generated": datetime.utcnow().isoformat(),
            "packages": result
        },
        f,
        indent=2
    )

print(f"\nDone. Wrote {len(result)}/{len(PACKAGES)} packages to stats.json")
