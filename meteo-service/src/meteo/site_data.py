"""Сборка данных для статического HTML-отчёта.

Весь контроль качества и правила полноты остаются в Python (см. qc.py,
coverage.py) — здесь мы лишь прогоняем готовый контур по всем станциям
и сериализуем агрегаты в JSON, который встраивается в страницу.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .aggregate import daily_table, decade_table, monthly_table, pentad_table
from .analytics import diurnal_cycle, wind_rose
from .coverage import daily_validity, monthly_coverage
from .loader import PARAMS, load_dataset, station_title
from .qc import apply_qc, qc_stats


def _records(df: pd.DataFrame, ndigits: int = 2) -> list[dict]:
    """DataFrame -> список словарей с округлением и NaN -> null."""
    return json.loads(df.round(ndigits).to_json(orient="records"))


def _stringify_dates(df: pd.DataFrame, cols: dict[str, str]) -> pd.DataFrame:
    out = df.copy()
    for col, fmt in cols.items():
        out[col] = pd.to_datetime(out[col]).dt.strftime(fmt)
    return out


def build_site_data(data_dir: str | Path) -> dict:
    """Полный контур: загрузка -> QC -> полнота -> агрегаты, по станциям."""
    raw = load_dataset(data_dir)
    stations = {}
    for station, g in raw.groupby("station"):
        g = g.reset_index(drop=True)
        stats = qc_stats(g)          # статистика исключений — по сырым данным
        qc = apply_qc(g)
        dv = daily_validity(qc)
        dt = daily_table(qc, dv)

        daily = _stringify_dates(dt, {"date": "%Y-%m-%d"})
        decade = _stringify_dates(decade_table(dt), {"month_start": "%Y-%m-%d"})
        pentad = _stringify_dates(pentad_table(dt), {"month_start": "%Y-%m-%d"})
        monthly = _stringify_dates(
            monthly_table(dt, dv), {"month_start": "%Y-%m-%d"}
        )
        cov = monthly_coverage(dv)

        # Средний суточный ход температуры по годам (для «поляна vs поле»)
        diurnal = {}
        for year, gy in qc.groupby(qc["datetime"].dt.year):
            dc = diurnal_cycle(gy, "t_air")
            diurnal[str(year)] = _records(dc)

        params_available = [p for p in PARAMS if qc[p].notna().any()]
        years = sorted(int(y) for y in g["datetime"].dt.year.unique())
        stations[station] = {
            "title": station_title(station, years),
            "params": params_available,
            "daily": _records(daily),
            "decade": _records(decade),
            "pentad": _records(pentad),
            "monthly": _records(monthly),
            "coverage": _records(cov, ndigits=0),
            "qc_stats": stats,
            "rose": _records(wind_rose(qc)),
            "diurnal": diurnal,
        }

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "stations": stations,
    }
