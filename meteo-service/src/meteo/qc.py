"""Контроль качества (QC): применение флагов qc_flag.

Правила из задания:
  * флаг вида "<параметр>:<причина>" исключает из расчёта ТОЛЬКО этот параметр,
    остальные значения строки используются;
  * dup_conflict исключает строку ЦЕЛИКОМ (несколько противоречивых записей
    на один срок);
  * время не округляем и не сдвигаем.
"""

from __future__ import annotations

import pandas as pd

from .loader import PARAMS

DUP_FLAG = "dup_conflict"


def qc_stats(df: pd.DataFrame) -> list[dict]:
    """Статистика контроля качества по месяцам — для панели «проверка расчёта».

    Принимает СЫРЫЕ данные (до apply_qc). Для каждого месяца:
    n_rows — записей всего, n_dup — исключено строк dup_conflict,
    params — сколько значений каждого параметра помечено флагом,
    reasons — разбивка флагов по причинам (range, fault).
    """
    flags = df["qc_flag"].fillna("")
    is_dup = flags.str.contains(DUP_FLAG)

    exploded = flags.str.split(";").explode().str.strip()
    exploded = exploded[exploded.str.contains(":", na=False)]
    parts = exploded.str.split(":", n=1)
    param_of_flag = parts.str[0]
    reason_of_flag = parts.str[1]

    months = df["datetime"].dt.strftime("%Y-%m")
    out = []
    for month, idx in df.groupby(months).groups.items():
        flagged = param_of_flag.loc[param_of_flag.index.isin(idx)]
        reasons = reason_of_flag.loc[reason_of_flag.index.isin(idx)]
        params = {}
        for p, cnt in flagged.value_counts().items():
            if p in PARAMS:
                params[p] = int(cnt)
        out.append({
            "month": month,
            "n_rows": len(idx),
            "n_dup": int(is_dup.loc[idx].sum()),
            "params": params,
            "reasons": {k: int(v) for k, v in reasons.value_counts().items()},
        })
    return out


def apply_qc(df: pd.DataFrame) -> pd.DataFrame:
    """Вернуть копию df, где ошибочные значения заменены на NaN,
    а строки с dup_conflict удалены."""
    flags = df["qc_flag"].fillna("")

    # 1. Строки с dup_conflict исключаются целиком
    out = df.loc[~flags.str.contains(DUP_FLAG)].copy()
    flags = out["qc_flag"].fillna("")

    # 2. Точечные флаги: "<param>:<reason>" -> NaN только в этом параметре.
    #    Флагов может быть несколько через ";".
    exploded = (
        flags.str.split(";")
        .explode()
        .str.strip()
    )
    exploded = exploded[exploded.str.contains(":", na=False)]
    param_of_flag = exploded.str.split(":", n=1).str[0]

    for param in param_of_flag.unique():
        if param in PARAMS:
            bad_idx = exploded.index[param_of_flag == param]
            out.loc[bad_idx, param] = pd.NA

    return out
