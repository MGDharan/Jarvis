"""
ML Workspace Tests — covers all 8 spec test cases.
Run with: python -m pytest tests/test_ml_workspace.py -v
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ml_engine import (
    analyze_dataset, execute_plan, validate_plan,
    SplitError, MetricError, ValidationError, load_dataset,
)
from ml_engine.splitter import split_dataset
from ml_engine.model_registry import resolve_algorithm


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_regression_df(n=1000):
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "age":        rng.integers(20, 65, n),
        "income":     rng.normal(50000, 15000, n),
        "experience": rng.integers(0, 40, n),
        "salary":     rng.normal(60000, 20000, n),
    })


def _make_classification_df(n=500):
    rng = np.random.default_rng(42)
    df = pd.DataFrame({
        "age":     rng.integers(20, 70, n),
        "balance": rng.normal(10000, 5000, n),
        "churn":   rng.integers(0, 2, n).astype(str),
    })
    return df


# ── Test 1: Correct 80/10/10 split for 1000 rows ─────────────────────────────

def test_split_1000_rows():
    df = _make_regression_df(1000)
    X_train, X_val, X_test, y_train, y_val, y_test = split_dataset(
        df, "salary",
        {"train": 0.8, "validation": 0.1, "test": 0.1},
        random_state=42,
        task="regression",
    )
    assert len(X_train) == 800, f"Expected 800 train, got {len(X_train)}"
    assert len(X_val)   == 100, f"Expected 100 val, got {len(X_val)}"
    assert len(X_test)  == 100, f"Expected 100 test, got {len(X_test)}"
    print("Test 1 passed: 800/100/100 split")


# ── Test 2: Missing values detected ──────────────────────────────────────────

def test_missing_values_detected():
    df = _make_regression_df(200)
    df.loc[0:9, "income"] = np.nan   # introduce 10 missing values
    schema = analyze_dataset(df, "test.csv")
    assert schema["missing_values"] == 10, (
        f"Expected 10 missing, got {schema['missing_values']}"
    )
    print("Test 2 passed: missing values detected")


# ── Test 3: Classification detection ─────────────────────────────────────────

def test_classification_detected():
    df = _make_classification_df(300)
    schema = analyze_dataset(df, "churn.csv")
    assert schema["task_hint"] == "classification", (
        f"Expected classification, got {schema['task_hint']}"
    )
    print("Test 3 passed: classification detected")


# ── Test 4: Regression detection ─────────────────────────────────────────────

def test_regression_detected():
    df = _make_regression_df(300)
    schema = analyze_dataset(df, "salary.csv")
    assert schema["task_hint"] == "regression", (
        f"Expected regression, got {schema['task_hint']}"
    )
    print("Test 4 passed: regression detected")


# ── Test 5: Invalid split rejected (80+30+20=130%) ───────────────────────────

def test_invalid_split_rejected():
    plan = {
        "task": "regression", "algorithm": "xgboost",
        "target": "salary", "metrics": ["mae"],
        "split": {"train": 0.8, "validation": 0.3, "test": 0.2},
    }
    with pytest.raises(SplitError) as exc:
        validate_plan(plan)
    assert "100" in str(exc.value) or "sum" in str(exc.value).lower() or "total" in str(exc.value).lower()
    print(f"Test 5 passed: invalid split rejected — {exc.value}")


# ── Test 6: XGBoost + ReLU validation warning ─────────────────────────────────

def test_xgboost_relu_rejected():
    plan = {
        "task": "regression", "algorithm": "xgboost",
        "target": "salary", "metrics": ["mae"],
        "split": {"train": 0.8, "validation": 0.1, "test": 0.1},
        "activation": "relu",
    }
    with pytest.raises(ValidationError) as exc:
        validate_plan(plan)
    msg = str(exc.value).lower()
    assert "relu" in msg or "activation" in msg or "tree" in msg
    print(f"Test 6 passed: XGBoost+ReLU rejected — {exc.value}")


# ── Test 7: Unknown target handled (planner level — not an engine error) ──────

def test_unknown_target_handled():
    df = _make_regression_df(100)
    schema = analyze_dataset(df, "data.csv")
    plan = {
        "task": "regression", "algorithm": "linear_regression",
        "target": "NONEXISTENT_COLUMN",
        "split": {"train": 0.8, "validation": 0.1, "test": 0.1},
        "metrics": ["mae"],
    }
    with pytest.raises(ValidationError) as exc:
        validate_plan(plan, schema)
    assert "NONEXISTENT_COLUMN" in str(exc.value) or "not found" in str(exc.value).lower()
    print(f"Test 7 passed: unknown target raises error — {exc.value}")


# ── Test 8: Unknown model handled ────────────────────────────────────────────

def test_unknown_model_handled():
    plan = {
        "task": "regression", "algorithm": "magic_ai_v9",
        "target": "salary", "metrics": ["mae"],
        "split": {"train": 0.8, "validation": 0.1, "test": 0.1},
    }
    with pytest.raises(ValidationError) as exc:
        validate_plan(plan)
    assert "not a supported" in str(exc.value).lower() or "not supported" in str(exc.value).lower()
    print(f"Test 8 passed: unknown model rejected — {exc.value}")


# ── Bonus: Full end-to-end XGBoost regression ─────────────────────────────────

def test_e2e_xgboost_regression():
    df = _make_regression_df(300)
    plan = {
        "task": "regression",
        "algorithm": "xgboost",
        "target": "salary",
        "features": ["age", "income", "experience"],
        "split": {"train": 0.8, "validation": 0.1, "test": 0.1},
        "metrics": ["mae", "mse", "rmse", "r2"],
        "random_state": 42,
    }
    validate_plan(plan)
    result = execute_plan(df, plan)

    assert result["status"] == "success"
    assert result["split"]["train"] == 240
    assert result["split"]["validation"] == 30
    assert result["split"]["test"] == 30

    test_metrics = result["test_metrics"]
    assert "mae" in test_metrics
    assert "r2"  in test_metrics
    assert isinstance(test_metrics["mae"], float)
    assert test_metrics["mae"] > 0
    print(f"Bonus test passed: XGBoost e2e — test MAE={test_metrics['mae']:.2f}, R²={test_metrics['r2']:.4f}")


# ── Bonus: Classification accuracy not allowed for regression ─────────────────

def test_regression_rejects_accuracy():
    plan = {
        "task": "regression", "algorithm": "xgboost",
        "target": "salary", "metrics": ["accuracy"],
        "split": {"train": 0.8, "validation": 0.1, "test": 0.1},
    }
    with pytest.raises(MetricError):
        validate_plan(plan)
    print("Bonus test passed: accuracy rejected for regression task")


if __name__ == "__main__":
    test_split_1000_rows()
    test_missing_values_detected()
    test_classification_detected()
    test_regression_detected()
    test_invalid_split_rejected()
    test_xgboost_relu_rejected()
    test_unknown_target_handled()
    test_unknown_model_handled()
    test_e2e_xgboost_regression()
    test_regression_rejects_accuracy()
    print("\nAll tests passed!")
