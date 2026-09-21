"""
Model Registry — Phase 5 / 8.

Every supported algorithm declares its capabilities here.
The LLM queries this to know what's available before validating a plan.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

TaskType = Literal["regression", "classification", "both"]


@dataclass
class ModelSpec:
    name: str                          # canonical key used in plans
    display_name: str                  # human-readable
    task: TaskType                     # "regression" | "classification" | "both"
    library: str                       # pip package
    supported_metrics: list[str]
    aliases: list[str] = field(default_factory=list)
    notes: str = ""


REGISTRY: dict[str, ModelSpec] = {
    "linear_regression": ModelSpec(
        name="linear_regression",
        display_name="Linear Regression",
        task="regression",
        library="scikit-learn",
        supported_metrics=["mae", "mse", "rmse", "r2", "mape"],
        aliases=["linear", "lr", "linearreg", "linear regression"],
    ),
    "logistic_regression": ModelSpec(
        name="logistic_regression",
        display_name="Logistic Regression",
        task="classification",
        library="scikit-learn",
        supported_metrics=["accuracy", "precision", "recall", "f1", "roc_auc"],
        aliases=["logistic", "logreg", "logistic regression"],
    ),
    "random_forest": ModelSpec(
        name="random_forest",
        display_name="Random Forest",
        task="both",
        library="scikit-learn",
        supported_metrics=["mae", "mse", "rmse", "r2", "mape",
                           "accuracy", "precision", "recall", "f1", "roc_auc"],
        aliases=["rf", "randomforest", "random forest"],
    ),
    "extra_trees": ModelSpec(
        name="extra_trees",
        display_name="Extra Trees",
        task="both",
        library="scikit-learn",
        supported_metrics=["mae", "mse", "rmse", "r2", "mape",
                           "accuracy", "precision", "recall", "f1"],
        aliases=["et", "extratrees", "extra trees", "extremely randomized trees"],
    ),
    "gradient_boosting": ModelSpec(
        name="gradient_boosting",
        display_name="Gradient Boosting",
        task="both",
        library="scikit-learn",
        supported_metrics=["mae", "mse", "rmse", "r2", "mape",
                           "accuracy", "precision", "recall", "f1"],
        aliases=["gb", "gradientboosting", "gradient boosting", "gbm"],
    ),
    "xgboost": ModelSpec(
        name="xgboost",
        display_name="XGBoost",
        task="both",
        library="xgboost",
        supported_metrics=["mae", "mse", "rmse", "r2", "mape",
                           "accuracy", "precision", "recall", "f1", "roc_auc"],
        aliases=["xgb", "xg boost", "extreme gradient boosting"],
        notes="Tree-based boosting. Does NOT use neural-network activation functions.",
    ),
    "decision_tree": ModelSpec(
        name="decision_tree",
        display_name="Decision Tree",
        task="both",
        library="scikit-learn",
        supported_metrics=["mae", "mse", "rmse", "r2",
                           "accuracy", "precision", "recall", "f1"],
        aliases=["dt", "decisiontree", "decision tree"],
    ),
    "svm": ModelSpec(
        name="svm",
        display_name="Support Vector Machine",
        task="both",
        library="scikit-learn",
        supported_metrics=["mae", "mse", "rmse",
                           "accuracy", "precision", "recall", "f1"],
        aliases=["svr", "svc", "support vector", "support vector machine"],
    ),
    "knn": ModelSpec(
        name="knn",
        display_name="K-Nearest Neighbors",
        task="both",
        library="scikit-learn",
        supported_metrics=["mae", "mse", "rmse",
                           "accuracy", "precision", "recall", "f1"],
        aliases=["kneighbors", "k nearest neighbors", "k-nearest neighbors"],
    ),
    "neural_network": ModelSpec(
        name="neural_network",
        display_name="Neural Network (MLP)",
        task="both",
        library="scikit-learn",
        supported_metrics=["mae", "mse", "rmse", "r2",
                           "accuracy", "precision", "recall", "f1"],
        aliases=["mlp", "nn", "neural net", "multilayer perceptron",
                 "deep learning", "dense"],
        notes="MLP via scikit-learn. Supports activation functions including relu, tanh, logistic.",
    ),
}

# Alias → canonical key lookup
_ALIAS_MAP: dict[str, str] = {}
for key, spec in REGISTRY.items():
    _ALIAS_MAP[key] = key
    for alias in spec.aliases:
        _ALIAS_MAP[alias.lower().replace("-", "").replace(" ", "")] = key


def resolve_algorithm(name: str) -> str | None:
    """Resolve a user-supplied algorithm name to its canonical registry key."""
    clean = name.lower().strip().replace("-", "").replace(" ", "").replace("_", "")
    return _ALIAS_MAP.get(clean)


def get_spec(name: str) -> ModelSpec | None:
    key = resolve_algorithm(name)
    return REGISTRY.get(key) if key else None


def list_algorithms(task: str | None = None) -> list[str]:
    if not task:
        return list(REGISTRY.keys())
    return [k for k, s in REGISTRY.items()
            if s.task == task or s.task == "both"]
