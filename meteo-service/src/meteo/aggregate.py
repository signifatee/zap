"""Агрегаты: суточные, декадные, месячные таблицы и «среднее за выбранный период».

Все расчёты идут по данным после QC и только по валидным суткам/месяцам
(см. coverage.py). Невалидные дни в средние не входят.
"""

from __future__ import annotations

import pandas as pd

from .coverage import monthly_coverage
from .loader import PARAMS

AGG = ["mean", "min", "max"]


def _valid_days(df: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    """Оставить только записи валидных суток."""
    days = set(daily.loc[daily["day_valid"], "date"])
    return df[df["datetime"].dt.normalize().isin(days)]


def daily_table(df: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    """Суточная таблица по валидным суткам.

    Среднее — по всем валидным значениям параметра за сутки (задание).
    Колонки: date, <param>_mean/min/max..., n_obs.
    """
    d = _valid_days(df, daily).copy()
    d["date"] = d["datetime"].dt.normalize()
    grouped = d.groupby("date")
    out = grouped[PARAMS].agg(AGG)
    out.columns = [f"{p}_{a}" for p, a in out.columns]
    out["n_obs"] = grouped.size()
    return out.reset_index()


def pentad_table(daily_tab: pd.DataFrame) -> pd.DataFrame:
    """Пентадная таблица из суточной (стандарт «Летописи природы»):
    1–5, 6–10, ..., 26-е — последний день месяца."""
    d = daily_tab.copy()
    d["pentad"] = (d["date"].dt.day - 1) // 5 + 1
    d["month_start"] = d["date"].values.astype("datetime64[M]")

    param_cols = [c for c in d.columns if c.endswith("_mean")]
    out = d.groupby(["month_start", "pentad"])[param_cols].mean()
    out.columns = [c.replace("_mean", "") for c in out.columns]
    out["n_days"] = d.groupby(["month_start", "pentad"]).size()
    return out.reset_index()


def decade_table(daily_tab: pd.DataFrame) -> pd.DataFrame:
    """Декадная таблица из суточной: 1–10, 11–20, 21–конец месяца."""
    d = daily_tab.copy()
    day = d["date"].dt.day
    d["decade"] = day.map(lambda x: 1 if x <= 10 else (2 if x <= 20 else 3))
    d["month_start"] = d["date"].values.astype("datetime64[M]")

    param_cols = [c for c in d.columns if c.endswith("_mean")]
    out = d.groupby(["month_start", "decade"])[param_cols].mean()
    out.columns = [c.replace("_mean", "") for c in out.columns]
    out["n_days"] = d.groupby(["month_start", "decade"]).size()
    return out.reset_index()


def monthly_table(daily_tab: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    """Месячная таблица. Считается только для валидных месяцев.

    Возвращает month (начало месяца), средние/мин/макс по параметрам,
    n_days — число валидных дней, month_valid — признак из правил полноты.
    """
    cov = monthly_coverage(daily)
    cov["month_start"] = pd.to_datetime(
        dict(year=cov["year"], month=cov["month"], day=1)
    )

    d = daily_tab.copy()
    d["month_start"] = d["date"].values.astype("datetime64[M]")
    pieces = {}
    for c in [c for c in d.columns if c.endswith("_mean")]:
        g = d.groupby("month_start")[c]
        p = c.removesuffix("_mean")
        pieces[f"{p}_mean"] = g.mean()
        pieces[f"{p}_min"] = g.min()
        pieces[f"{p}_max"] = g.max()
    out = pd.DataFrame(pieces)
    out["n_days"] = d.groupby("month_start").size()

    out = out.reset_index().merge(
        cov[["month_start", "month_valid", "valid_days"]], on="month_start", how="left"
    )
    return out[out["month_valid"].fillna(False)].reset_index(drop=True)


def period_mean(
    monthly_tab: pd.DataFrame, years: list[int] | None = None
) -> tuple[pd.DataFrame, int]:
    """«Среднее за выбранный период» по месяцам.

    years — список лет; None — все годы с валидными месяцами.
    Возвращает (таблица по месяцам, число лет, вошедших в расчёт).
    По заданию число лет всегда показывается пользователю.
    """
    d = monthly_tab.copy()
    d["year"] = d["month_start"].dt.year
    d["month"] = d["month_start"].dt.month
    if years is not None:
        d = d[d["year"].isin(years)]
    n_years = int(d["year"].nunique())

    param_cols = [c for c in d.columns if c.endswith("_mean")]
    out = d.groupby("month")[param_cols].mean()
    out.columns = [c.removesuffix("_mean") for c in out.columns]
    out["n_years_in_month"] = d.groupby("month")["year"].nunique()
    return out.reset_index(), n_years
