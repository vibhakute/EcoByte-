"""Generate EcoByte_2025_Synthetic_Canteen_Data.xlsx (SYNTHETIC demonstration data).

Usage:  python -m scripts.generate_dataset [output_path]

If you have the real/provided 2025 workbook, place it at backend/data/ with that file name
instead and the seeder will import it (column names are matched flexibly).
"""
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import HISTORICAL_XLSX  # noqa: E402
from app.services.synthetic import generate_days  # noqa: E402

COLUMNS = {
    "date": "Date", "day": "Day", "meal_type": "Meal_Type", "is_holiday": "Is_Holiday", "event": "Event",
    "main_dish": "Main_Dish", "menu_items": "Menu_Items", "advance_confirmations": "Advance_Confirmations",
    "slot_bookings": "Slot_Bookings", "actual_attendance": "Actual_Attendance",
    "meals_prepared": "Meals_Prepared", "meals_served": "Meals_Served", "prepared_kg": "Food_Prepared_kg",
    "served_kg": "Food_Served_kg", "leftover_kg": "Leftover_Food_kg", "plate_waste_kg": "Plate_Waste_kg",
    "total_waste_kg": "Total_Waste_kg", "cost_per_kg": "Cost_per_kg_INR", "waste_cost": "Waste_Cost_INR",
}


def build(path: Path) -> Path:
    rows = generate_days(date(2025, 1, 1), date(2025, 12, 31), seed=2025, era="legacy")
    df = pd.DataFrame(rows)
    df["day"] = pd.to_datetime(df["date"]).dt.strftime("%A")
    df["meal_type"] = df["meal_type"].str.capitalize()
    df["is_holiday"] = df["is_holiday"].map({True: "Yes", False: "No"})
    df = df[list(COLUMNS)].rename(columns=COLUMNS)
    readme = pd.DataFrame({"About this file": [
        "EcoByte 2025 canteen dataset - SYNTHETIC DEMONSTRATION DATA.",
        "These records were generated programmatically and do NOT describe a real canteen.",
        "Model: ~620 enrolled diners, Mon-Sat, breakfast/lunch/dinner, weekday + seasonal + menu effects,",
        "holidays, vacations, exams, college events and random noise. Pre-EcoByte preparation used",
        "a cook's estimate (+7-19% margin), so leftover waste is deliberately higher than after EcoByte.",
        "Waste_Cost_INR = Total_Waste_kg x Cost_per_kg_INR.",
        "Replace with real canteen records as soon as they are available.",
    ]})
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        readme.to_excel(xw, sheet_name="README", index=False)
        df.to_excel(xw, sheet_name="Daily_Records", index=False)
        ws = xw.sheets["Daily_Records"]
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = max(12, min(40, len(str(col[0].value)) + 4))
        xw.sheets["README"].column_dimensions["A"].width = 110
    return path


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else HISTORICAL_XLSX
    p = build(out)
    print(f"Wrote {p} ({p.stat().st_size // 1024} KB)")
