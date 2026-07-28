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
    },
    {
        "name": "ibm-airflow-provider-db2",
        "framework": "Airflow"
    },
    {
        "name": "ibis-db2",
        "framework": "Ibis"
    }
]

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "db2-opensource-telemetry/1.0 (+https://github.com/<your-github-username>/db2-opensource-telemetry)"
}


def get_json(url, pkg_name):
    """Fetch URL and return parsed JSON, or None on any error."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
    except requests.RequestException as exc:
        print(f"  [{pkg_name}] network error: {exc}")
        return None

    print("Status:", resp.status_code)
    print("Headers:", resp.headers.get("Content-Type"))
    print("Body:")
    print(resp.text[:500])

    if resp.status_code == 404:
        print(f"  [{pkg_name}] not found on PyPI Stats (404) — skipping")
        return None

    if resp.status_code == 429:
        print(f"  [{pkg_name}] rate-limited (429) — skipping")
        return None

    if not resp.ok:
        print(f"  [{pkg_name}] HTTP {resp.status_code} from {url} — skipping")
        return None

    text = resp.text.strip()
    if not text:
        print(f"  [{pkg_name}] empty response body from {url} — skipping")
        return None

    try:
        return resp.json()
    except requests.exceptions.JSONDecodeError:
        print(f"  [{pkg_name}] invalid JSON from {url}: {text[:120]}")
        return None


result = []

for i, pkg in enumerate(PACKAGES):
    name = pkg["name"]
    print(f"Fetching {name} …")

    # Polite delay between packages to avoid rate-limiting
    if i > 0:
        time.sleep(2)

    recent_data = get_json(
        f"https://pypistats.org/api/packages/{name}/recent",
        name
    )
    overall_data = get_json(
        f"https://pypistats.org/api/packages/{name}/overall?mirrors=false",
        name
    )

    # Skip package entirely if either endpoint failed
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
