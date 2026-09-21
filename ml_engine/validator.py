"""
ML Plan Validator — Phase 4.

Validates every field of the structured ML plan before touching data.
Raises ValidationError with a natural-language message the LLM can relay to the user.
"""
from __future__ import annotations

from typing import Any

from .exceptions import MetricError, SplitError, ValidationError
from .model_registry import get_spec, resolve_algorithm

_REGRESSION_METRICS     = {"mae", "mse", "rmse", "r2", "mape"}
_CLASSIFICATION_METRICS = {"accuracy", "precision", "recall", "f1", "roc_auc", "confusion_matrix"}
_ALL_VALID_METRICS      = _REGRESSION_METRICS | _CLASSIFICATION_METRICS

# Activation functions that only make sense in neural networks
_NN_ONLY_ACTIVATIONS = {"relu", "sigmoid", "tanh", "softmax", "leaky_relu", "elu", "selu", "gelu"}


def validate_plan(plan: dict[str, Any], schema: dict[str, Any] | None = None) -> None:
    """
    Validate the ML plan in-place. Raises ValidationError (subclasses) on any issue.
    schema: dataset schema from dataset_analyzer.analyze_dataset()
    """
    task      = plan.get("task", "").lower()
    algorithm = plan.get("algorithm", "").lower()
    target    = plan.get("target")
    features  = plan.get("features") or []
    split     = plan.get("split") or {}
    metrics   = [m.lower() for m in (plan.get("metrics") or [])]

    # ── Algorithm ────────────────────────────────────────────────────────────
    canon = resolve_algorithm(algorithm)
    if canon is None:
        known = "linear_regression, random_forest, xgboost, neural_network, ..."
        raise ValidationError(
            f"'{algorithm}' is not a supported algorithm. "
            f"Available options include: {known}"
        )
    plan["algorithm"] = canon   # normalize to canonical key
    spec = get_spec(canon)

    # ── Activation function compatibility ────────────────────────────────────
    activation = (plan.get("activation") or "").lower()
    if activation and activation in _NN_ONLY_ACTIVATIONS:
        if canon != "neural_network":
            raise ValidationError(
                f"{spec.display_name} is a tree-based algorithm and does not use "
                f"'{activation}' activation functions. "
                f"Activation functions apply only to neural networks. "
                f"I can continue with {spec.display_name} without '{activation}', "
                f"or switch to a neural network where '{activation}' is applicable."
            )

    # ── Task compatibility ────────────────────────────────────────────────────
    if task and task not in ("regression", "classification"):
        raise ValidationError(
            f"Task must be 'regression' or 'classification', got '{task}'."
        )
    if task and spec.task != "both" and spec.task != task:
        raise ValidationError(
            f"{spec.display_name} supports {spec.task} only, "
            f"but the requested task is {task}."
        )

    # ── Target / features (if schema available) ──────────────────────────────
    if schema:
        col_names = schema.get("column_names", [])
        if target and target not in col_names:
            raise ValidationError(
                f"Target column '{target}' not found in the dataset. "
                f"Available columns: {', '.join(col_names[:10])}"
            )
        if features:
            bad = [f for f in features if f not in col_names]
            if bad:
                raise ValidationError(
                    f"Feature column(s) not found: {', '.join(bad)}. "
                    f"Available columns: {', '.join(col_names[:10])}"
                )

    # ── Split ─────────────────────────────────────────────────────────────────
    if split:
        train = float(split.get("train", 0))
        val   = float(split.get("validation", 0))
        test  = float(split.get("test", 0))
        total = round(train + val + test, 6)
        if abs(total - 1.0) > 0.001:
            total_pct = round(total * 100)
            raise SplitError(
                f"Train, validation and test percentages must total 100%. "
                f"You provided {round(train*100)}% + {round(val*100)}% + "
                f"{round(test*100)}% = {total_pct}%. "
                f"Please adjust so they sum to 100%."
            )
        if train <= 0 or test <= 0:
            raise SplitError("Train and test portions must both be greater than 0.")

    # ── Metrics ───────────────────────────────────────────────────────────────
    unknown_metrics = [m for m in metrics if m not in _ALL_VALID_METRICS]
    if unknown_metrics:
        raise MetricError(
            f"Unknown metric(s): {', '.join(unknown_metrics)}. "
            f"Supported regression metrics: mae, mse, rmse, r2, mape. "
            f"Supported classification metrics: accuracy, precision, recall, f1, roc_auc."
        )

    if task == "regression":
        bad = [m for m in metrics if m in _CLASSIFICATION_METRICS]
        if bad:
            raise MetricError(
                f"'{', '.join(bad)}' is not appropriate for a regression task. "
                f"For regression use: mae, mse, rmse, r2, mape."
            )

    if task == "classification":
        bad = [m for m in metrics if m in _REGRESSION_METRICS]
        if bad:
            raise MetricError(
                f"'{', '.join(bad)}' is not appropriate for a classification task. "
                f"For classification use: accuracy, precision, recall, f1, roc_auc."
            )

    # ── Library availability ──────────────────────────────────────────────────
    if spec.library == "xgboost":
        try:
            import xgboost  # noqa: F401
        except ImportError:
            raise ValidationError(
                "XGBoost is not installed. Run: pip install xgboost"
            )
