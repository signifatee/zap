"""Полнота данных: валидность суток и месяцев.

Правила из задания (README):
  * Сутки валидны, если есть не менее 75% сроков:
      - АМЕ-60  — не менее 72 из 96 уникальных сроков;
      - Сокол М1 — данные не менее чем за 18 уникальных часов из 24
        (несколько записей в одном часу считаются за один час).
  * Месяц валиден, если невалидных дней не более 10
    и нет 5 и более невалидных дней подряд.
  * Строки с dup_conflict уже исключены на этапе QC.
"""

from __future__ import annotations

import calendar

import pandas as pd

from .loader import station_kind

MIN_SLOTS_AME60 = 72   # из 96 сроков по 15 минут
MIN_HOURS_SOKOL = 18   # из 24 уникальных часов
MAX_INVALID_DAYS = 10  # в месяце
MAX_INVALID_RUN = 5    # невалидных дней подряд


def daily_validity(df: pd.DataFrame, param: str | None = None) -> pd.DataFrame:
    """Валидность каждых суток после QC.

    Возвращает таблицу: station, date, n_slots (сроки или часы), day_valid.
    df — данные ОДНОЙ станции после apply_qc.

    param — считать полноту по конкретному параметру (учитываются только
    сроки с валидным значением). Так задание требует проверять давление
    Кр1 за 2024 год: по часам с валидным давлением, а не по общему
    покрытию станции.
    """
    station = df["station"].iloc[0]
    kind = station_kind(station)

    if param is not None:
        df = df[df[param].notna()]

    day = df["datetime"].dt.normalize()
    if kind == "ame60":
        n = df.groupby(day)["datetime"].nunique()
    else:  # sokol: уникальные часы, а не строки
        n = df.assign(hour=df["datetime"].dt.hour).groupby(day)["hour"].nunique()

    threshold = MIN_SLOTS_AME60 if kind == "ame60" else MIN_HOURS_SOKOL
    out = n.rename("n_slots").reset_index().rename(columns={"datetime": "date"})
    out["station"] = station
    out["day_valid"] = out["n_slots"] >= threshold
    return out[["station", "date", "n_slots", "day_valid"]]


def _max_run(mask: pd.Series) -> int:
    """Максимальная длина серии подряд идущих True."""
    run = best = 0
    for v in mask:
        run = run + 1 if v else 0
        best = max(best, run)
    return best


def monthly_coverage(daily: pd.DataFrame) -> pd.DataFrame:
    """Валидность месяцев по таблице валидности суток.

    Возвращает: station, year, month, days_in_month, valid_days, month_valid.
    Схема совпадает с coverage_by_month.csv из набора — удобно сверять.
    """
    rows = []
    d = daily.copy()
    d["year"] = d["date"].dt.year
    d["month"] = d["date"].dt.month

    # Эталон покрытия содержит все 12 месяцев каждого года, даже если
    # в файле за месяц нет ни одной записи — такой месяц невалиден.
    for (station, year), gy in d.groupby(["station", "year"]):
        for month in range(1, 13):
            days_in_month = calendar.monthrange(year, month)[1]
            full = pd.date_range(f"{year}-{month:02d}-01", periods=days_in_month, freq="D")
            g = gy[gy["month"] == month]
            valid_map = g.set_index("date")["day_valid"].reindex(full, fill_value=False)
            valid_days = int(valid_map.sum())
            invalid_days = days_in_month - valid_days
            month_valid = (
                invalid_days <= MAX_INVALID_DAYS
                and _max_run(~valid_map) < MAX_INVALID_RUN
            )
            rows.append(
                {
                    "station": station.upper(),
                    "year": year,
                    "month": month,
                    "days_in_month": days_in_month,
                    "valid_days": valid_days,
                    "month_valid": month_valid,
                }
            )
    return pd.DataFrame(rows)
