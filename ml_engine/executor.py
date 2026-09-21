"""
ML Execution Engine — Phase 5 / 9.

The ONLY place models are trained and predictions made.
The LLM calls this through the tool interface — never generates ML code itself.
"""
from __future__ import annotations

import importlib
import time
from typing import Any

import numpy as np
import pandas as pd

from .evaluator import compute_classification_metrics, compute_regression_metrics
from .exceptions import LibraryNotInstalledError, ModelError
from .model_registry import get_spec
from .preprocessing import Preprocessor, encode_target
from .splitter import split_dataset


def _build_model(algorithm: str, task: str, params: dict):
    """Instantiate the right model class based on algorithm + task."""
    p = {k: v for k, v in params.items() if v is not None}
    rs = p.get("random_state", 42)

    if algorithm == "linear_regression":
        from sklearn.linear_model import LinearRegression
        return LinearRegression()

    if algorithm == "logistic_regression":
        from sklearn.linear_model import LogisticRegression
        return LogisticRegression(random_state=rs, max_iter=1000,
                                   C=p.get("C", 1.0))

    if algorithm == "random_forest":
        if task == "regression":
            from sklearn.ensemble import RandomForestRegressor
            return RandomForestRegressor(
                n_estimators=p.get("n_estimators", 100),
                max_depth=p.get("max_depth", None),
                random_state=rs, n_jobs=-1,
            )
        else:
            from sklearn.ensemble import RandomForestClassifier
            return RandomForestClassifier(
                n_estimators=p.get("n_estimators", 100),
                max_depth=p.get("max_depth", None),
                random_state=rs, n_jobs=-1,
            )

    if algorithm == "extra_trees":
        if task == "regression":
            from sklearn.ensemble import ExtraTreesRegressor
            return ExtraTreesRegressor(
                n_estimators=p.get("n_estimators", 100),
                random_state=rs, n_jobs=-1,
            )
        else:
            from sklearn.ensemble import ExtraTreesClassifier
            return ExtraTreesClassifier(
                n_estimators=p.get("n_estimators", 100),
                random_state=rs, n_jobs=-1,
            )

    if algorithm == "gradient_boosting":
        if task == "regression":
            from sklearn.ensemble import GradientBoostingRegressor
            return GradientBoostingRegressor(
                n_estimators=p.get("n_estimators", 100),
                max_depth=p.get("max_depth", 3),
                learning_rate=p.get("learning_rate", 0.1),
                random_state=rs,
            )
        else:
            from sklearn.ensemble import GradientBoostingClassifier
            return GradientBoostingClassifier(
                n_estimators=p.get("n_estimators", 100),
                max_depth=p.get("max_depth", 3),
                learning_rate=p.get("learning_rate", 0.1),
                random_state=rs,
            )

    if algorithm == "xgboost":
        try:
            from xgboost import XGBClassifier, XGBRegressor
        except ImportError:
            raise LibraryNotInstalledError("XGBoost is not installed. Run: pip install xgboost")
        common = dict(
            n_estimators=p.get("n_estimators", 100),
            max_depth=p.get("max_depth", 6),
            learning_rate=p.get("learning_rate", 0.1),
            random_state=rs,
            verbosity=0,
            n_jobs=-1,
        )
        if task == "regression":
            return XGBRegressor(**common)
        else:
            return XGBClassifier(**common, use_label_encoder=False,
                                  eval_metric="logloss")

    if algorithm == "decision_tree":
        if task == "regression":
            from sklearn.tree import DecisionTreeRegressor
            return DecisionTreeRegressor(
                max_depth=p.get("max_depth", None), random_state=rs)
        else:
            from sklearn.tree import DecisionTreeClassifier
            return DecisionTreeClassifier(
                max_depth=p.get("max_depth", None), random_state=rs)

    if algorithm == "svm":
        if task == "regression":
            from sklearn.svm import SVR
            return SVR(C=p.get("C", 1.0), kernel=p.get("kernel", "rbf"))
        else:
            from sklearn.svm import SVC
            return SVC(C=p.get("C", 1.0), kernel=p.get("kernel", "rbf"),
                        probability=True, random_state=rs)

    if algorithm == "knn":
        if task == "regression":
            from sklearn.neighbors import KNeighborsRegressor
            return KNeighborsRegressor(n_neighbors=p.get("n_neighbors", 5), n_jobs=-1)
        else:
            from sklearn.neighbors import KNeighborsClassifier
            return KNeighborsClassifier(n_neighbors=p.get("n_neighbors", 5), n_jobs=-1)

    if algorithm == "neural_network":
        activation = p.get("activation", "relu")
        layers = tuple(p.get("layers", [100, 50]))
        if task == "regression":
            from sklearn.neural_network import MLPRegressor
            return MLPRegressor(
                hidden_layer_sizes=layers,
                activation=activation,
                max_iter=p.get("epochs", 200),
                random_state=rs,
            )
        else:
            from sklearn.neural_network import MLPClassifier
            return MLPClassifier(
                hidden_layer_sizes=layers,
                activation=activation,
                max_iter=p.get("epochs", 200),
                random_state=rs,
            )

    raise ModelError(f"Algorithm '{algorithm}' is not implemented in the execution engine.")


def execute_plan(
    df: pd.DataFrame,
    plan: dict[str, Any],
) -> dict[str, Any]:
    """
    Full ML pipeline execution.

    Returns a result dict with actual metrics, split sizes, and model object.
    The LLM only reads this dict — it NEVER generates metrics itself.
    """
    task          = plan["task"]
    algorithm     = plan["algorithm"]
    target        = plan["target"]
    features      = plan.get("features") or [c for c in df.columns if c != target]
    split         = plan.get("split") or {"train": 0.8, "validation": 0.1, "test": 0.1}
    metrics_req   = [m.lower() for m in (plan.get("metrics") or [])]
    random_state  = int(plan.get("random_state", 42))
    params        = plan.get("params") or {}
    params["random_state"] = random_state

    # ── 1. Validate columns exist ─────────────────────────────────────────────
    missing_cols = [c for c in features + [target] if c not in df.columns]
    if missing_cols:
        raise ModelError(f"Columns not found in dataset: {missing_cols}")

    # Keep only relevant columns
    df_work = df[features + [target]].copy()

    # ── 2. Split BEFORE preprocessing (no leakage) ───────────────────────────
    X_train, X_val, X_test, y_train, y_val, y_test = split_dataset(
        df_work, target, split, random_state, task
    )

    # ── 3. Preprocess (fit on TRAIN only) ────────────────────────────────────
    preprocessor = Preprocessor()
    X_train_arr = preprocessor.fit_transform(X_train)
    X_val_arr   = preprocessor.transform(X_val)
    X_test_arr  = preprocessor.transform(X_test)

    y_train_arr, label_encoder = encode_target(y_train, task)
    y_val_arr,   _             = encode_target(y_val,   task)
    y_test_arr,  _             = encode_target(y_test,  task)

    # ── 4. Build and train model ──────────────────────────────────────────────
    model = _build_model(algorithm, task, params)

    t0 = time.perf_counter()
    model.fit(X_train_arr, y_train_arr)
    train_time = round(time.perf_counter() - t0, 4)

    # ── 5. Predict on all splits ──────────────────────────────────────────────
    pred_val  = model.predict(X_val_arr)
    pred_test = model.predict(X_test_arr)

    prob_val  = None
    prob_test = None
    if task == "classification" and hasattr(model, "predict_proba"):
        try:
            prob_val  = model.predict_proba(X_val_arr)
            prob_test = model.predict_proba(X_test_arr)
            if prob_val.shape[1] == 2:
                prob_val  = prob_val[:, 1]
                prob_test = prob_test[:, 1]
        except Exception:
            pass

    # ── 6. Compute metrics ────────────────────────────────────────────────────
    n_classes = len(np.unique(y_train_arr)) if task == "classification" else 0

    if task == "regression":
        val_metrics  = compute_regression_metrics(y_val_arr,  pred_val,  metrics_req or None)
        test_metrics = compute_regression_metrics(y_test_arr, pred_test, metrics_req or None)
    else:
        val_metrics  = compute_classification_metrics(
            y_val_arr,  pred_val,  prob_val,  metrics_req or None, n_classes)
        test_metrics = compute_classification_metrics(
            y_test_arr, pred_test, prob_test, metrics_req or None, n_classes)

    # ── 7. Feature importance (if available) ─────────────────────────────────
    feature_importance: dict[str, float] = {}
    if hasattr(model, "feature_importances_"):
        fi = model.feature_importances_
        feature_importance = {
            features[i]: round(float(fi[i]), 6)
            for i in range(min(len(features), len(fi)))
        }
        feature_importance = dict(
            sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
        )

    return {
        "status":               "success",
        "algorithm":            algorithm,
        "task":                 task,
        "target":               target,
        "features":             features,
        "split": {
            "train":      len(X_train),
            "validation": len(X_val),
            "test":       len(X_test),
        },
        "validation_metrics":   val_metrics,
        "test_metrics":         test_metrics,
        "training_time_seconds":train_time,
        "feature_importance":   feature_importance,
        "n_classes":            n_classes,
        "_model":               model,           # kept in memory, not serialized
        "_preprocessor":        preprocessor,
        "_label_encoder":       label_encoder,
    }
