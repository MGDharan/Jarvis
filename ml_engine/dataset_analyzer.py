"""
Dataset Analyzer — Phase 2.

Loads CSV / XLSX / Parquet and produces a structured schema dict.
No LLM involved — pure deterministic pandas analysis.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .exceptions import DatasetError

# Heuristic column-name fragments that strongly suggest a target
_TARGET_HINTS = [
    "target", "label", "output", "result", "class", "y", "predict",
    "salary", "price", "sales", "revenue", "profit", "income",
    "churn", "fraud", "default", "death", "survived", "diagnosis",
    "score", "grade", "rating", "demand", "yield", "return",
]


def load_dataset(path: str | Path) -> pd.DataFrame:
    """Load CSV / XLSX / Parquet. Raises DatasetError on failure."""
    p = Path(path)
    if not p.exists():
        raise DatasetError(f"File not found: {p}")
    suffix = p.suffix.lower()
    try:
        if suffix == ".csv":
            return pd.read_csv(p)
        elif suffix in (".xls", ".xlsx"):
            return pd.read_excel(p)
        elif suffix == ".parquet":
            return pd.read_parquet(p)
        else:
            # Try CSV as fallback
            try:
                return pd.read_csv(p)
            except Exception:
                raise DatasetError(f"Unsupported file type: {suffix}")
    except DatasetError:
        raise
    except Exception as exc:
        raise DatasetError(f"Could not read dataset: {exc}") from exc


def _hash_df(df: pd.DataFrame) -> str:
    raw = pd.util.hash_pandas_object(df, index=True).values.tobytes()
    return hashlib.md5(raw).hexdigest()[:12]


def _rank_target_candidates(df: pd.DataFrame) -> list[str]:
    """
    Rank columns by how likely they are to be the target.
    Returns ordered list, best first.
    """
    scored: list[tuple[float, str]] = []
    cols = list(df.columns)

    for col in cols:
        score = 0.0
        col_lower = col.lower().replace(" ", "").replace("_", "")

        # Strong name hint
        for hint in _TARGET_HINTS:
            if hint in col_lower:
                score += 3.0
                break

        # Last column convention
        if col == cols[-1]:
            score += 1.5

        # Continuous numeric → regression candidate
        if pd.api.types.is_numeric_dtype(df[col]):
            nuniq = df[col].nunique()
            if nuniq > 20:
                score += 1.0
            elif 2 <= nuniq <= 20:
                score += 0.5   # could be classification

        # Binary column → strong classification signal
        if df[col].nunique() == 2:
            score += 1.0

        scored.append((score, col))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [col for _, col in scored if _ > 0]


def analyze_dataset(df: pd.DataFrame, file_name: str = "") -> dict[str, Any]:
    """
    Full deterministic analysis. Returns a rich schema dict.
    """
    rows, cols = df.shape
    dtypes = df.dtypes

    numerical_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    categorical_cols = [c for c in df.columns if pd.api.types.is_object_dtype(df[c])
                        or pd.api.types.is_categorical_dtype(df[c])]
    date_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]

    missing = int(df.isnull().sum().sum())
    missing_per_col = df.isnull().sum().to_dict()
    missing_per_col = {k: int(v) for k, v in missing_per_col.items() if v > 0}

    duplicates = int(df.duplicated().sum())

    unique_per_col = {c: int(df[c].nunique()) for c in df.columns}

    # Basic stats for numeric columns
    stats: dict[str, Any] = {}
    for c in numerical_cols[:20]:   # cap at 20 cols for speed
        s = df[c].describe()
        stats[c] = {
            "min":  round(float(s.get("min", 0)), 4),
            "max":  round(float(s.get("max", 0)), 4),
            "mean": round(float(s.get("mean", 0)), 4),
            "std":  round(float(s.get("std", 0)), 4),
        }

    targets = _rank_target_candidates(df)
    top_target = targets[0] if targets else (df.columns[-1] if len(df.columns) > 1 else None)

    # Infer task from top target
    task_hint = "unknown"
    if top_target and top_target in df.columns:
        col_data = df[top_target].dropna()
        nuniq = col_data.nunique()
        if nuniq == 2:
            task_hint = "classification"
        elif nuniq <= 20 and not pd.api.types.is_float_dtype(df[top_target]):
            task_hint = "classification"
        else:
            task_hint = "regression"

    return {
        "file_name":          file_name or "dataset",
        "hash":               _hash_df(df),
        "rows":               rows,
        "columns":            cols,
        "column_names":       list(df.columns),
        "numerical_columns":  numerical_cols,
        "categorical_columns":categorical_cols,
        "date_columns":       date_cols,
        "missing_values":     missing,
        "missing_per_column": missing_per_col,
        "duplicates":         duplicates,
        "unique_per_column":  unique_per_col,
        "statistics":         stats,
        "potential_targets":  targets[:5],
        "top_target":         top_target,
        "task_hint":          task_hint,
        "features":           cols - 1 if top_target else cols,
    }
