"""
ML Planner — Phase 3.

Converts natural-language instructions into a structured plan dict.
Uses Gemini to parse intent — but Gemini NEVER generates Python or metrics.
It only outputs JSON describing what to do.
"""
from __future__ import annotations

import json
import re
import warnings
from pathlib import Path


_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "api_keys.json"

_PLAN_SCHEMA = """
Return ONLY valid JSON with these optional keys (omit any key you can't determine):
{
  "action": "activate|load_dataset|set_target|set_task|set_algorithm|set_split|set_metrics|run|history|compare|status|auto",
  "target": "column_name",
  "task": "regression|classification",
  "algorithm": "algorithm_name",
  "split": {"train": 0.8, "validation": 0.1, "test": 0.1},
  "metrics": ["mae","mse","rmse","r2","mape","accuracy","precision","recall","f1","roc_auc"],
  "activation": "relu|tanh|sigmoid|etc",
  "params": {"n_estimators": 100, "max_depth": 6, "learning_rate": 0.1},
  "random_state": 42
}
Rules:
- split values must be fractions (0.8 not 80), must sum to 1.0
- algorithm must be the plain name: xgboost, random_forest, linear_regression, neural_network, etc.
- metrics must be lowercase: mae, mse, rmse, r2, accuracy, f1, etc.
- action "run" means: execute the training now
- action "auto" means: run with whatever is already configured
- If the user says "keep the same X", do NOT include X in the JSON
"""


def _load_api_key() -> str:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8")).get("gemini_api_key", "")
    except Exception:
        return ""


def parse_nl_to_plan(
    user_text: str,
    session_context: dict | None = None,
) -> dict:
    """
    Convert natural language to a structured ML plan patch.
    Falls back to rule-based parsing if Gemini is unavailable.
    """
    api_key = _load_api_key()

    if api_key:
        result = _gemini_parse(user_text, session_context or {}, api_key)
        if result:
            return result

    return _rule_based_parse(user_text)


def _gemini_parse(text: str, ctx: dict, api_key: str) -> dict | None:
    try:
        from google import genai
        ctx_str = json.dumps(ctx, indent=2) if ctx else "{}"
        prompt = (
            f"You are the ML planning module for JARVIS AI assistant.\n"
            f"Current workspace state:\n{ctx_str}\n\n"
            f"User instruction: \"{text}\"\n\n"
            f"Parse this instruction into a structured plan JSON.\n"
            f"{_PLAN_SCHEMA}"
        )
        client = genai.Client(api_key=api_key)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
        raw = (resp.text or "").strip()
        # Strip markdown fences
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```\s*$", "", raw)
        raw = raw.strip()
        return json.loads(raw)
    except Exception:
        return None


# ── Rule-based fallback (no API needed) ──────────────────────────────────────

_ALGO_HINTS = {
    "xgboost": "xgboost", "xgb": "xgboost",
    "random forest": "random_forest", "randomforest": "random_forest", "rf": "random_forest",
    "linear regression": "linear_regression", "linear": "linear_regression",
    "logistic regression": "logistic_regression", "logistic": "logistic_regression",
    "extra trees": "extra_trees", "extratrees": "extra_trees",
    "gradient boosting": "gradient_boosting", "gbm": "gradient_boosting",
    "decision tree": "decision_tree",
    "neural network": "neural_network", "mlp": "neural_network",
    "svm": "svm", "svr": "svm", "svc": "svm",
    "knn": "knn",
}

_METRIC_HINTS = {
    "mae": "mae", "mean absolute error": "mae",
    "mse": "mse", "mean squared error": "mse",
    "rmse": "rmse", "root mean squared": "rmse",
    "r2": "r2", "r squared": "r2", "r^2": "r2",
    "mape": "mape",
    "accuracy": "accuracy",
    "precision": "precision",
    "recall": "recall",
    "f1": "f1",
    "roc": "roc_auc", "roc auc": "roc_auc", "auc": "roc_auc",
}


def _rule_based_parse(text: str) -> dict:
    low = text.lower()
    plan: dict = {}

    # Action keywords
    if any(w in low for w in ("activate", "open workspace", "start workspace", "ml workspace")):
        plan["action"] = "activate"
    elif any(w in low for w in ("run", "train", "execute", "start experiment", "go")):
        plan["action"] = "run"
    elif any(w in low for w in ("history", "experiments", "past runs")):
        plan["action"] = "history"
    elif any(w in low for w in ("compare", "versus", "vs")):
        plan["action"] = "compare"
    elif any(w in low for w in ("status", "what is set", "current config")):
        plan["action"] = "status"

    # Algorithm
    for hint, canon in _ALGO_HINTS.items():
        if hint in low:
            plan["algorithm"] = canon
            break

    # Task
    if "regression" in low:
        plan["task"] = "regression"
    elif "classification" in low:
        plan["task"] = "classification"

    # Metrics
    found_metrics = []
    for hint, canon in _METRIC_HINTS.items():
        if hint in low and canon not in found_metrics:
            found_metrics.append(canon)
    if found_metrics:
        plan["metrics"] = found_metrics

    # Split — match patterns like "80 10 10", "80/10/10", "80% 10% 10%"
    split_pat = re.search(
        r"(\d+)[%\s/,]+(\d+)[%\s/,]+(\d+)", text
    )
    if split_pat:
        tr, va, te = int(split_pat.group(1)), int(split_pat.group(2)), int(split_pat.group(3))
        total = tr + va + te
        if total > 0:
            plan["split"] = {
                "train":      round(tr / total, 4),
                "validation": round(va / total, 4),
                "test":       round(te / total, 4),
            }

    # Activation function
    for act in ("relu", "tanh", "sigmoid", "softmax"):
        if act in low:
            plan["activation"] = act
            break

    # Target — "predict X" or "target is X"
    target_pat = re.search(
        r"(?:predict|target|output|label|y\s+is|column\s+is)\s+['\"]?(\w+)['\"]?",
        low
    )
    if target_pat:
        plan["target"] = target_pat.group(1)

    return plan
