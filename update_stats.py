import requests
import json
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

result = []

for pkg in PACKAGES:

    recent = requests.get(
        f"https://pypistats.org/api/packages/{pkg['name']}/recent"
    ).json()

    overall = requests.get(
        f"https://pypistats.org/api/packages/{pkg['name']}/overall?mirrors=false"
    ).json()

    series = [
        x for x in overall["data"]
        if x["category"] == "without_mirrors"
    ]

    all_time = sum(x["downloads"] for x in series)

    result.append({
        "package": pkg["name"],
        "framework": pkg["framework"],
        "all_time": all_time,
        "last_month": recent["data"]["last_month"],
        "last_day": recent["data"]["last_day"],
        "series": series
    })

with open("stats.json", "w") as f:
    json.dump(
        {
            "generated": datetime.utcnow().isoformat(),
            "packages": result
        },
        f,
        indent=2
    )
