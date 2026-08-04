"""Convert the official UK CoFID 2021 workbook into the app's compact food list."""

import argparse
import json
from pathlib import Path

import openpyxl


SOURCE_URL = "https://www.gov.uk/government/publications/composition-of-foods-integrated-dataset-cofid"


def convert(source: Path, destination: Path):
    workbook = openpyxl.load_workbook(source, read_only=True, data_only=True)
    sheet = workbook["1.3 Proximates"]
    rows = list(sheet.iter_rows(values_only=True))
    headers = rows[0]
    name_index = headers.index("Food Name")
    code_index = headers.index("Food Code")
    carbohydrate_index = headers.index("Carbohydrate (g)")
    foods = []
    used_names = set()

    for row in rows[3:]:
        name = str(row[name_index] or "").strip()
        if not name:
            continue
        value = row[carbohydrate_index]
        if value == "Tr":
            carbs = 0.0
        else:
            try:
                carbs = float(value)
            except (TypeError, ValueError):
                continue
        if carbs < 0:
            continue
        display_name = name
        if display_name.casefold() in used_names:
            display_name = f"{name} (CoFID {row[code_index]})"
        used_names.add(display_name.casefold())
        foods.append({
            "name": display_name,
            "serving": "100 g",
            "carbs_g": round(carbs, 2),
            "source": "UK CoFID 2021",
            "cofid_code": str(row[code_index] or ""),
        })

    payload = {
        "source": "McCance and Widdowson's Composition of Foods Integrated Dataset 2021",
        "source_url": SOURCE_URL,
        "carbohydrate_basis": "grams per 100 g of food; trace values represented as 0 g",
        "foods": sorted(foods, key=lambda item: item["name"].casefold()),
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return len(foods)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(f"Imported {convert(args.source, args.destination)} foods")
