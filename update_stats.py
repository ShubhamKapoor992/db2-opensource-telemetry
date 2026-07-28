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
        "name": "lbm-db-haystack",
        "framework": "Haystack Db2 connector"
    },
    {
        "name": "llama-index-vector-stores-db2",
        "framework": "LlamaIndex Db2 connector"
    }
]

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "db2-opensource-telemetry/1.0 (+https://github.com/ShubhamKapoor992/db2-opensource-telemetry)"
}

SLEEP_BETWEEN_CALLS = 35   # seconds to wait before every API call
SLEEP_ON_RATE_LIMIT = 60   # extra seconds to wait after a 429 before retrying

# Track whether this is the very first call so we don't sleep before it
_first_call = True


def get_json(url, pkg_name):
    """Fetch URL and return parsed JSON, or None on any error.

    Sleeps SLEEP_BETWEEN_CALLS seconds before every call (except the first).
    On a 429 response, waits an additional SLEEP_ON_RATE_LIMIT seconds then
    retries exactly once.
    """
    global _first_call

    for attempt in (1, 2):
        # Always sleep before making a request (skip only before the very first call)
        if _first_call:
            _first_call = False
        else:
            print(f"  Sleeping {SLEEP_BETWEEN_CALLS}s before next call …")
            time.sleep(SLEEP_BETWEEN_CALLS)

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
                print(f"  [{pkg_name}] rate-limited (429) — sleeping {SLEEP_ON_RATE_LIMIT}s then retrying …")
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

    overall_data = get_json(
        f"https://pypistats.org/api/packages/{name}/overall?mirrors=false",
        name
    )

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
            "generated": datetime.now(timezone.utc).isoformat(),
            "packages": result
        },
        f,
        indent=2
    )

print(f"\nDone. Wrote {len(result)}/{len(PACKAGES)} packages to stats.json")
