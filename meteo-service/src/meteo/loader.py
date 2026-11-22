"""Загрузка файлов наблюдений в единую схему.

Схема колонок (README набора):
    datetime      срок наблюдения, "ГГГГ-ММ-ДД ЧЧ:ММ" (без округления и сдвига)
    t_air         температура воздуха, °C
    rh            относительная влажность, %
    wind_speed    средняя скорость ветра, м/с
    wind_gust     порыв ветра, м/с
    wind_dir      направление ветра, градусы 0-360
    soil_05/10/20 температура почвы, °C (только АМЕ-60)
    pressure_hpa  давление, гПа (только Сокол М1)
    qc_flag       флаги качества через ";"

Если параметр в году не измерялся, колонки в файле нет — после объединения
в ней будут NaN. Загрузчик ориентирован на схему, а не на конкретные файлы:
новый файл того же формата подхватывается без правок кода.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

# Известные станции получают человекочитаемые названия. Неизвестный идентификатор
# тоже поддерживается: он попадёт в отчёт как «Станция <ID>».
# Ряды разных станций НЕ объединяются между собой.
STATIONS = {
    "ame60": {"kind": "ame60", "title": "АМЕ-60"},
    "kr1": {"kind": "sokol", "title": "Сокол М1, Кр1 — поляна"},
    "kr2": {"kind": "sokol", "title": "Сокол М1, Кр2 — поле"},
}

# Все измеряемые параметры (datetime и qc_flag — служебные)
PARAMS = [
    "t_air",
    "rh",
    "wind_speed",
    "wind_gust",
    "wind_dir",
    "soil_05",
    "soil_10",
    "soil_20",
    "pressure_hpa",
]

# <station>_<year>.csv; station — латинский идентификатор без подчёркиваний.
# Каталог внутри data/ значения не имеет: поиск рекурсивный.
_FILE_RE = re.compile(
    r"(?P<station>[a-z][a-z0-9-]*)_(?P<year>\d{4})\.csv", re.IGNORECASE
)


def station_kind(station: str) -> str:
    """Правило полноты: АМЕ-60 — 15 минут, остальные — почасовое."""
    return STATIONS.get(station, {}).get("kind", "sokol")


def station_title(station: str, years: list[int] | tuple[int, ...]) -> str:
    """Название и фактический диапазон лет из загруженных файлов."""
    base = STATIONS.get(station, {}).get("title", f"Станция {station.upper()}")
    if not years:
        return base
    first, last = min(years), max(years)
    period = str(first) if first == last else f"{first}–{last}"
    return f"{base} ({period})"


def load_station(path: str | Path, station: str | None = None) -> pd.DataFrame:
    """Загрузить один CSV наблюдений.

    station: если не указана, определяется по имени файла (kr3_2025.csv → kr3).
    """
    path = Path(path)
    m = _FILE_RE.fullmatch(path.name)
    if station is None:
        if not m:
            raise ValueError(f"Не могу определить станцию по имени файла: {path.name}")
        station = m.group("station").lower()
    year = int(m.group("year")) if m else None

    df = pd.read_csv(path)
    df["datetime"] = pd.to_datetime(df["datetime"], format="%Y-%m-%d %H:%M")
    df["station"] = station
    if year is not None:
        df["year"] = year
    # Колонки, которых нет в файле (параметр не измерялся), — NaN
    for p in PARAMS:
        if p not in df.columns:
            df[p] = float("nan")
    if "qc_flag" not in df.columns:
        df["qc_flag"] = pd.NA
    return df.sort_values("datetime").reset_index(drop=True)


def load_dataset(data_dir: str | Path) -> pd.DataFrame:
    """Загрузить весь каталог data/ (все станции и годы) в один DataFrame.

    Обрабатываются только файлы с именем вида <станция>_<год>.csv —
    посторонние csv (например, coverage_by_month.csv) пропускаются.
    """
    all_csv = sorted(Path(data_dir).rglob("*.csv"))
    files = [f for f in all_csv if _FILE_RE.fullmatch(f.name)]
    skipped = [f.name for f in all_csv if f not in files]
    if skipped:
        print(f"Пропущены файлы не по шаблону имени: {skipped}")
    if not files:
        raise FileNotFoundError(f"В {data_dir} не найдено csv-файлов наблюдений")
    out = pd.concat([load_station(f) for f in files], ignore_index=True)
    for p in PARAMS:
        out[p] = pd.to_numeric(out[p], errors="coerce")
    return out
