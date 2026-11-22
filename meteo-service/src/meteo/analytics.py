"""Аналитика поверх агрегатов: отклонения, суточный ход, сравнение точек, роза ветров."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .aggregate import period_mean


def deviations_from_period(
    monthly_tab: pd.DataFrame, param: str, years: list[int] | None = None
) -> tuple[pd.DataFrame, int]:
    """Отклонение месячных средних от «среднего за выбранный период».

    Возвращает (таблица, n_years): month, year, value, period_mean, deviation.
    """
    pm, n_years = period_mean(monthly_tab, years)
    pm = pm[["month", param]].rename(columns={param: "period_mean"})

    d = monthly_tab.copy()
    d["year"] = d["month_start"].dt.year
    d["month"] = d["month_start"].dt.month
    if years is not None:
        d = d[d["year"].isin(years)]
    out = d.merge(pm, on="month")
    out["value"] = out[f"{param}_mean"]
    out["deviation"] = out["value"] - out["period_mean"]
    return out[["year", "month", "value", "period_mean", "deviation"]], n_years


def diurnal_cycle(df: pd.DataFrame, param: str) -> pd.DataFrame:
    """Средний суточный ход параметра: среднее по часу суток.

    df — данные после QC (субсуточный шаг). Учитываются только валидные
    значения параметра; время не округляется (берём час записи как есть).
    """
    d = df[["datetime", param]].dropna()
    out = d.groupby(d["datetime"].dt.hour)[param].agg(["mean", "count"])
    return out.rename_axis("hour").reset_index()


def compare_glade_field(
    daily_glade: pd.DataFrame, daily_field: pd.DataFrame, param: str = "t_air"
) -> pd.DataFrame:
    """Сравнение «поляна vs поле» (Кр1 vs Кр2): разница средних по месяцам.

    На вход — суточные таблицы обеих точек за общий период (напр. 2025).
    Возвращает: month, glade, field, diff (поляна минус поле).
    """
    def monthly(dt: pd.DataFrame, name: str) -> pd.DataFrame:
        d = dt.copy()
        d["month"] = d["date"].values.astype("datetime64[M]")
        return d.groupby("month")[f"{param}_mean"].mean().rename(name)

    out = pd.concat(
        [monthly(daily_glade, "glade"), monthly(daily_field, "field")], axis=1
    ).dropna()
    out["diff"] = out["glade"] - out["field"]
    return out.reset_index()


def wind_rose(df: pd.DataFrame, n_sectors: int = 16) -> pd.DataFrame:
    """Роза ветров: повторяемость направлений по секторам.

    Невалидные данные исключены на этапе QC (1998 — нет колонки,
    2021 — флаг wind_dir:fault), поэтому «плохие» годы сюда не попадут.
    Возвращает: sector (центр сектора, °), label (румб), freq (доля, %).
    """
    d = df["wind_dir"].dropna().astype(float) % 360
    width = 360 / n_sectors
    sector = ((d + width / 2) // width).astype(int) % n_sectors
    counts = sector.value_counts().sort_index()
    labels = _sector_labels(n_sectors)
    out = pd.DataFrame({"sector": range(n_sectors)})
    out["freq"] = out["sector"].map(counts).fillna(0) / max(len(d), 1) * 100
    out["angle"] = out["sector"] * width
    out["label"] = labels
    out["n_obs"] = len(d)
    return out


def _sector_labels(n: int) -> list[str]:
    if n == 16:
        return ["С", "ССВ", "СВ", "ВСВ", "В", "ВЮВ", "ЮВ", "ЮЮВ",
                "Ю", "ЮЮЗ", "ЮЗ", "ЗЮЗ", "З", "ЗСЗ", "СЗ", "ССЗ"]
    if n == 8:
        return ["С", "СВ", "В", "ЮВ", "Ю", "ЮЗ", "З", "СЗ"]
    return [f"{int(a)}" for a in np.arange(0, 360, 360 / n)]
