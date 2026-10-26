"""Send exactly ten PRESELECTED, held-out historical cases to POST /evaluate.

Usage from repository root:
    python backend/demo_evaluate.py backend/models/heldout_10_cases.csv

Do NOT fill the labels using predictions from the model. Labels must
come from independently documented historical observations or identified proxies.
"""
import csv
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REQUIRED = [
    "case_id", "month", "temperature_c_median", "pH_median", "DO_mg_l_median",
    "insitu_chl_a_ug_l_median", "satellite_chl_monthly_median",
    "actual_bloom", "label_type",
]
FLOATS = [
    "temperature_c_median", "pH_median", "DO_mg_l_median",
    "insitu_chl_a_ug_l_median", "satellite_chl_monthly_median",
]


def main():
    if len(sys.argv) not in (2, 3):
        raise SystemExit("Usage: python backend/demo_evaluate.py <10_cases.csv> [http://127.0.0.1:8000]")
    file_path = Path(sys.argv[1])
    base_url = sys.argv[2].rstrip("/") if len(sys.argv) == 3 else "http://127.0.0.1:8000"
    with file_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = [key for key in REQUIRED if key not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(f"CSV missing columns: {missing}")
        cases = []
        for row in reader:
            case = {key: row[key] for key in REQUIRED}
            try:
                case.update({key: float(row[key]) for key in FLOATS})
                case["actual_bloom"] = int(row["actual_bloom"])
            except (ValueError, TypeError) as exc:
                raise SystemExit(f"Invalid numeric value on CSV row {len(cases) + 2}: {exc}") from exc
            if case["actual_bloom"] not in (0, 1) or case["label_type"] not in ("verified", "proxy"):
                raise SystemExit(f"Invalid label on CSV row {len(cases) + 2}")
            cases.append(case)
    if len(cases) != 10:
        raise SystemExit(f"Expected exactly ten preselected cases, found {len(cases)}")

    request = Request(
        f"{base_url}/evaluate",
        data=json.dumps({"cases": cases}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            result = json.load(response)
    except HTTPError as exc:
        raise SystemExit(f"API HTTP {exc.code}: {exc.read().decode()}") from exc
    except URLError as exc:
        raise SystemExit(f"Cannot reach API: {exc}") from exc
    print(f"Historical score: {result['score_out_of_10']} ({result['accuracy_against_supplied_labels']:.0%})")
    print(f"Always-bloom baseline: {result['always_bloom_baseline_accuracy']:.0%}")
    print(f"Score type: {result['score_type']}")
    print("\nCASE ID        TARGET    P(BLOOM)  PREDICTION ACTUAL     CORRECT")
    for c in result["results"]:
        print(f"{c['case_id'][:14]:14} {c['forecast_month']:9} {c['bloom_probability']:8.1%} "
              f"{c['prediction']:10} {c['actual']:10} {str(c['correct']):>5}")
    print("\nWARNING:", result["warning"])


if __name__ == "__main__":
    main()
