"""
Evaluator — Phase 6.

Computes ALL metrics from ACTUAL predictions.
The LLM NEVER computes metrics — only this module does.
"""
from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)

from .exceptions import MetricError


def _mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    mask = y_true != 0
    if mask.sum() == 0:
        return float("nan")
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def compute_regression_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    requested: list[str] | None = None,
) -> dict[str, float]:
    """Compute regression metrics. requested=None → compute all."""
    y_true = np.array(y_true, dtype=float)
    y_pred = np.array(y_pred, dtype=float)

    all_metrics = {
        "mae":  round(float(mean_absolute_error(y_true, y_pred)), 6),
        "mse":  round(float(mean_squared_error(y_true, y_pred)), 6),
        "rmse": round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 6),
        "r2":   round(float(r2_score(y_true, y_pred)), 6),
        "mape": round(_mape(y_true, y_pred), 4),
    }

    if not requested:
        return all_metrics
    return {k: v for k, v in all_metrics.items() if k in requested}


def compute_classification_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: np.ndarray | None = None,
    requested: list[str] | None = None,
    n_classes: int = 2,
) -> dict[str, object]:
    avg = "binary" if n_classes == 2 else "weighted"

    result: dict[str, object] = {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 6),
    }

    try:
        result["precision"] = round(float(precision_score(
            y_true, y_pred, average=avg, zero_division=0)), 6)
        result["recall"]    = round(float(recall_score(
            y_true, y_pred, average=avg, zero_division=0)), 6)
        result["f1"]        = round(float(f1_score(
            y_true, y_pred, average=avg, zero_division=0)), 6)
    except Exception:
        pass

    if y_prob is not None:
        try:
            if n_classes == 2:
                result["roc_auc"] = round(float(roc_auc_score(y_true, y_prob)), 6)
            else:
                result["roc_auc"] = round(float(
                    roc_auc_score(y_true, y_prob, multi_class="ovr", average="weighted")), 6)
        except Exception:
            pass

    try:
        cm = confusion_matrix(y_true, y_pred).tolist()
        result["confusion_matrix"] = cm
    except Exception:
        pass

    if not requested:
        return result
    # Always include confusion_matrix if asked
    filtered = {k: v for k, v in result.items() if k in requested}
    if "confusion_matrix" in requested and "confusion_matrix" in result:
        filtered["confusion_matrix"] = result["confusion_matrix"]
    return filtered
