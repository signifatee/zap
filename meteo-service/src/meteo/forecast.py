"""Краткосрочный прогноз из Open-Meteo API (бесплатно, без ключа).

Координаты — урочище «Красное», Центрально-Лесной заповедник
(метеостанция ВМО 26488 «Лесной Заповедник», пос. Заповедный).
Собственную модель прогноза по заданию строить не нужно — используем
внешний погодный сервис.
"""

from __future__ import annotations

import pandas as pd
import requests

LAT, LON = 56.45, 32.97  # урочище Красное, ЦЛЗ (уточнить при наличии точных координат станции)
URL = "https://api.open-meteo.com/v1/forecast"

HOURLY = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
    "wind_direction_10m",
    "surface_pressure",
]


def get_forecast(days: int = 3, lat: float = LAT, lon: float = LON) -> pd.DataFrame:
    """Почасовой прогноз на days суток вперёд.

    Возвращает DataFrame: time, temperature_2m, relative_humidity_2m,
    precipitation, wind_speed_10m, wind_direction_10m, surface_pressure.
    """
    resp = requests.get(
        URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join(HOURLY),
            "forecast_days": days,
            "timezone": "Europe/Moscow",
        },
        timeout=20,
    )
    resp.raise_for_status()
    h = resp.json()["hourly"]
    df = pd.DataFrame(h)
    df["time"] = pd.to_datetime(df["time"])
    return df
