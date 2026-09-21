"""
Splitter — Phase 8.

Implements the exact 80/10/10 (or custom) split correctly.
Uses stratification for classification when possible.
Guarantees no data leakage between splits.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from .exceptions import SplitError


def split_dataset(
    df: pd.DataFrame,
    target: str,
    split: dict[str, float],
    random_state: int = 42,
    task: str = "regression",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame,
           pd.Series, pd.Series, pd.Series]:
    """
    Split df into (X_train, X_val, X_test, y_train, y_val, y_test).

    split: {"train": 0.8, "validation": 0.1, "test": 0.1}

    Algorithm:
        1. Full dataset → 80% TRAIN + 20% TEMP
        2. TEMP → 50% VALIDATION + 50% TEST   (which gives 10/10 overall)
    """
    train_r = float(split.get("train", 0.8))
    val_r   = float(split.get("validation", 0.1))
    test_r  = float(split.get("test", 0.1))

    total = round(train_r + val_r + test_r, 6)
    if abs(total - 1.0) > 0.001:
        raise SplitError(
            f"Split ratios must sum to 1.0, got {total:.4f}."
        )

    X = df.drop(columns=[target])
    y = df[target]

    n = len(df)
    if n < 10:
        raise SplitError(f"Dataset too small to split ({n} rows). Need at least 10.")

    # For stratified split in classification
    stratify_y = None
    if task == "classification":
        vc = y.value_counts()
        # Only stratify if every class has at least 2 samples
        if vc.min() >= 2:
            stratify_y = y

    temp_r = val_r + test_r   # fraction going to TEMP

    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y,
        test_size=temp_r,
        random_state=random_state,
        stratify=stratify_y,
    )

    # Within TEMP, val and test share equally by default
    val_of_temp = val_r / temp_r   # e.g. 0.1/0.2 = 0.5

    stratify_temp = None
    if task == "classification" and stratify_y is not None:
        vc_temp = y_temp.value_counts()
        if vc_temp.min() >= 2:
            stratify_temp = y_temp

    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp,
        test_size=1 - val_of_temp,
        random_state=random_state,
        stratify=stratify_temp,
    )

    return X_train, X_val, X_test, y_train, y_val, y_test
