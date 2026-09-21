"""
Experiment Storage — Phase 7.

Saves config, metrics, and model for every run.
Enables comparison and reproducibility.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
import joblib
import sys

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

_BASE = _get_base_dir()
_EXP_DIR = _BASE / "experiments"
_MOD_DIR = _BASE / "models_storage"


def _next_experiment_id() -> str:
    _EXP_DIR.mkdir(parents=True, exist_ok=True)
    existing = sorted(_EXP_DIR.glob("experiment_*"))
    n = len(existing) + 1
    return f"experiment_{n:03d}"


def save_experiment(
    plan: dict,
    result: dict,
    dataset_name: str = "",
    workspace_id: str = "",
) -> str:
    """
    Save experiment artifacts. Returns the experiment directory path.
    """
    exp_id  = _next_experiment_id()
    exp_dir = _EXP_DIR / exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    model_dir = _MOD_DIR / exp_id
    model_dir.mkdir(parents=True, exist_ok=True)

    # ── config.json ──────────────────────────────────────────────────────────
    config = {
        "experiment_id":  exp_id,
        "workspace_id":   workspace_id,
        "dataset":        dataset_name,
        "algorithm":      plan.get("algorithm"),
        "task":           plan.get("task"),
        "target":         plan.get("target"),
        "features":       plan.get("features"),
        "split":          plan.get("split"),
        "metrics":        plan.get("metrics"),
        "random_state":   plan.get("random_state", 42),
        "preprocessing":  plan.get("preprocessing", "auto"),
        "timestamp":      time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (exp_dir / "config.json").write_text(
        json.dumps(config, indent=2), encoding="utf-8"
    )

    # ── metrics.json ─────────────────────────────────────────────────────────
    metrics_out = {
        "validation": result.get("validation_metrics", {}),
        "test":       result.get("test_metrics", {}),
        "split_sizes":result.get("split", {}),
        "training_time_seconds": result.get("training_time_seconds"),
    }
    # Remove non-serializable (confusion_matrix is ok — it's a list)
    def _clean(d):
        if isinstance(d, dict):
            return {k: _clean(v) for k, v in d.items()
                    if not isinstance(v, type)}
        if isinstance(d, list):
            return [_clean(i) for i in d]
        return d

    (exp_dir / "metrics.json").write_text(
        json.dumps(_clean(metrics_out), indent=2), encoding="utf-8"
    )

    # ── model.pkl ─────────────────────────────────────────────────────────────
    model_path = ""
    if result.get("_model") is not None:
        try:
            model_path = str(model_dir / "model.pkl")
            save_bundle = {
                "model":         result["_model"],
                "preprocessor":  result.get("_preprocessor"),
                "label_encoder": result.get("_label_encoder"),
                "features":      result.get("features"),
                "target":        result.get("target"),
                "task":          result.get("task"),
            }
            joblib.dump(save_bundle, model_path)
        except Exception as e:
            print(f"[MLEngine] Model save warning: {e}")

    # ── metadata.json ─────────────────────────────────────────────────────────
    import sklearn
    meta = {
        "experiment_id": exp_id,
        "model_path":    model_path,
        "python_version": sys.version,
        "sklearn_version": sklearn.__version__,
        "timestamp":     config["timestamp"],
    }
    try:
        import xgboost
        meta["xgboost_version"] = xgboost.__version__
    except ImportError:
        pass
    (exp_dir / "metadata.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )

    return str(exp_dir)


def list_experiments(workspace_id: str = "") -> list[dict]:
    """Return list of saved experiments, newest first."""
    _EXP_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for exp_dir in sorted(_EXP_DIR.glob("experiment_*"), reverse=True):
        cfg_file = exp_dir / "config.json"
        met_file = exp_dir / "metrics.json"
        if not cfg_file.exists():
            continue
        try:
            cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
            met = json.loads(met_file.read_text(encoding="utf-8")) if met_file.exists() else {}
            if workspace_id and cfg.get("workspace_id") != workspace_id:
                continue
            results.append({**cfg, "test_metrics": met.get("test", {})})
        except Exception:
            continue
    return results
