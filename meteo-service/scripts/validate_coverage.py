"""Сверка расчёта покрытия с эталоном coverage_by_month.csv.

Запуск:  uv run python scripts/validate_coverage.py [путь_к_архиву_каталога]
Ожидание: все 420 строк эталона совпадают (README: прежние 396 строк
за прежние годы совпали у организаторов; 24 строки за 2024 добавлены).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from meteo import apply_qc, daily_validity, load_dataset, monthly_coverage  # noqa: E402

DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data")
for cand in (DATA / "coverage_by_month.csv",
             DATA.parent / "coverage_by_month.csv",
             Path("coverage_by_month.csv")):
    if cand.exists():
        REF = cand
        break
else:
    raise FileNotFoundError("Не найден coverage_by_month.csv рядом с data/ или внутри неё")

parts = []
for _, df in load_dataset(DATA).groupby("station"):
    parts.append(daily_validity(apply_qc(df.reset_index(drop=True))))
daily = pd.concat(parts, ignore_index=True)
ours = monthly_coverage(daily)

ref = pd.read_csv(REF)
merged = ref.merge(
    ours,
    on=["station", "year", "month"],
    how="outer",
    suffixes=("_ref", "_ours"),
    indicator=True,
)

bad_days = merged[merged["valid_days_ref"] != merged["valid_days_ours"]]
bad_flag = merged[merged["month_valid_ref"] != merged["month_valid_ours"]]
missing = merged[merged["_merge"] != "both"]

print(f"Эталон: {len(ref)} строк | Рассчитано: {len(ours)} строк")
print(f"Расхождения в valid_days: {len(bad_days)}")
print(f"Расхождения в month_valid: {len(bad_flag)}")
print(f"Строки без пары: {len(missing)}")
if len(bad_days) or len(bad_flag) or len(missing):
    print(pd.concat([bad_days, bad_flag, missing]).head(20).to_string())
    sys.exit(1)
print("OK: покрытие совпадает с эталоном полностью.")
