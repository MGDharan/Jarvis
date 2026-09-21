"""
Preprocessing — Phase 7.

Rule: fit on TRAIN only, then transform TRAIN / VAL / TEST.
This prevents data leakage.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import LabelEncoder, StandardScaler, OrdinalEncoder


class Preprocessor:
    """
    Fit on training data, then transform any split.
    Handles: missing values, categorical encoding, feature scaling.
    """

    def __init__(self, strategy: str = "auto"):
        self.strategy = strategy
        self._num_imputer   = SimpleImputer(strategy="median")
        self._cat_imputer   = SimpleImputer(strategy="most_frequent")
        self._cat_encoder   = OrdinalEncoder(
            handle_unknown="use_encoded_value", unknown_value=-1
        )
        self._scaler        = StandardScaler()
        self._numerical_cols: list[str] = []
        self._categorical_cols: list[str] = []
        self._fitted = False

    def fit(self, X_train: pd.DataFrame) -> "Preprocessor":
        """Fit all transformers on training data only."""
        self._numerical_cols   = [c for c in X_train.columns
                                   if pd.api.types.is_numeric_dtype(X_train[c])]
        self._categorical_cols = [c for c in X_train.columns
                                   if not pd.api.types.is_numeric_dtype(X_train[c])]

        if self._numerical_cols:
            self._num_imputer.fit(X_train[self._numerical_cols])
            self._scaler.fit(X_train[self._numerical_cols])

        if self._categorical_cols:
            self._cat_imputer.fit(X_train[self._categorical_cols])
            temp = pd.DataFrame(
                self._cat_imputer.transform(X_train[self._categorical_cols]),
                columns=self._categorical_cols,
            )
            self._cat_encoder.fit(temp)

        self._fitted = True
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        """Transform a dataset split. Must call fit() first."""
        if not self._fitted:
            raise RuntimeError("Preprocessor not fitted. Call fit() on training data first.")

        parts = []
        if self._numerical_cols:
            num = X[self._numerical_cols].copy()
            num = pd.DataFrame(
                self._num_imputer.transform(num),
                columns=self._numerical_cols,
            )
            num = pd.DataFrame(
                self._scaler.transform(num),
                columns=self._numerical_cols,
            )
            parts.append(num.values)

        if self._categorical_cols:
            cat = X[self._categorical_cols].copy()
            cat = pd.DataFrame(
                self._cat_imputer.transform(cat),
                columns=self._categorical_cols,
            )
            cat = pd.DataFrame(
                self._cat_encoder.transform(cat),
                columns=self._categorical_cols,
            )
            parts.append(cat.values)

        if not parts:
            return np.empty((len(X), 0))
        return np.hstack(parts)

    def fit_transform(self, X_train: pd.DataFrame) -> np.ndarray:
        return self.fit(X_train).transform(X_train)


def encode_target(y: pd.Series, task: str) -> tuple[np.ndarray, "LabelEncoder | None"]:
    """
    Encode the target column.
    Regression: convert to float.
    Classification: LabelEncode to integers.
    Returns (encoded_array, encoder_or_None).
    """
    if task == "regression":
        return y.astype(float).values, None
    else:
        le = LabelEncoder()
        encoded = le.fit_transform(y.astype(str))
        return encoded, le
