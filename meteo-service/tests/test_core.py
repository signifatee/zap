"""Тесты ядра на синтетических данных (uv run pytest)."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from meteo import apply_qc, daily_validity, monthly_coverage
from meteo.loader import load_dataset, station_title


def make_df(rows, station="kr1"):
    df = pd.DataFrame(rows, columns=["datetime", "t_air", "rh", "qc_flag"])
    df["datetime"] = pd.to_datetime(df["datetime"])
    df["station"] = station
    return df


def test_dup_conflict_drops_whole_row():
    df = make_df([
        ("2024-01-01 00:00", 5.0, 50, "dup_conflict"),
        ("2024-01-01 00:00", 9.0, 90, "dup_conflict"),
        ("2024-01-01 01:00", 6.0, 60, None),
    ])
    out = apply_qc(df)
    assert len(out) == 1 and out.iloc[0]["t_air"] == 6.0


def test_param_flag_blanks_only_that_param():
    df = make_df([("2024-01-01 00:00", 5.0, 999, "rh:range")])
    out = apply_qc(df)
    assert pd.isna(out.iloc[0]["rh"])      # влажность исключена
    assert out.iloc[0]["t_air"] == 5.0     # температура осталась


def test_multiple_flags_semicolon():
    df = make_df([("2024-01-01 00:00", 5.0, 50, "rh:range;t_air:range")])
    out = apply_qc(df)
    assert pd.isna(out.iloc[0]["rh"]) and pd.isna(out.iloc[0]["t_air"])


def test_sokol_day_validity_18_hours():
    rows = [(f"2024-01-01 {h:02d}:00", 1.0, 50, None) for h in range(18)]
    rows += [("2024-01-02 00:00", 1.0, 50, None)]  # 1 час из 24
    dv = daily_validity(make_df(rows))
    assert dv.iloc[0]["day_valid"] and not dv.iloc[1]["day_valid"]


def test_month_invalid_five_days_run():
    # 9 невалидных дней, но 5 подряд (6-10 января) -> месяц невалиден
    days = [d for d in range(1, 32) if d not in range(6, 11)]
    rows = [(f"2024-01-{d:02d} {h:02d}:00", 1.0, 50, None)
            for d in days for h in range(20)]
    mc = monthly_coverage(daily_validity(make_df(rows)))
    jan = mc[(mc["year"] == 2024) & (mc["month"] == 1)].iloc[0]
    assert jan["valid_days"] == 26 and not jan["month_valid"]


def test_month_valid_ten_scattered_invalid_days():
    # 10 невалидных дней без серий -> месяц валиден
    days = [d for d in range(1, 32) if d % 3 != 0][:21]
    rows = [(f"2024-01-{d:02d} {h:02d}:00", 1.0, 50, None)
            for d in days for h in range(20)]
    mc = monthly_coverage(daily_validity(make_df(rows)))
    jan = mc[(mc["year"] == 2024) & (mc["month"] == 1)].iloc[0]
    assert jan["valid_days"] == 21 and jan["month_valid"]


def test_new_station_discovered_from_nested_folder():
    with TemporaryDirectory() as tmp:
        folder = Path(tmp) / "kr3"
        folder.mkdir()
        pd.DataFrame(
            {
                "datetime": ["2025-01-01 00:00", "2025-01-01 01:00"],
                "t_air": [1.0, 2.0],
                "qc_flag": [None, None],
            }
        ).to_csv(folder / "kr3_2025.csv", index=False)
        (Path(tmp) / "coverage_by_month.csv").write_text("station,year\n", encoding="utf-8")

        out = load_dataset(tmp)
        assert out["station"].unique().tolist() == ["kr3"]
        assert out["year"].unique().tolist() == [2025]
        assert station_title("kr3", [2024, 2025]) == "Станция KR3 (2024–2025)"
