"""
Workspace Manager — orchestrates the full ML session.

The LLM calls this via structured tool calls.
All actual computation is delegated to ml_engine — no exec(), no generated Python.
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

from .schema import WorkspaceSession

# Lazy imports so the plugin loads fast even if ml_engine deps are missing
def _engine():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from ml_engine import (
        analyze_dataset, execute_plan, list_experiments,
        load_dataset, save_experiment, validate_plan,
        MLEngineError, ValidationError,
    )
    return (analyze_dataset, execute_plan, list_experiments,
            load_dataset, save_experiment, validate_plan,
            MLEngineError, ValidationError)


# Active sessions: workspace_id → WorkspaceSession
_sessions: dict[str, WorkspaceSession] = {}
_active_id: str | None = None


def get_active_session() -> WorkspaceSession | None:
    return _sessions.get(_active_id) if _active_id else None


# ─────────────────────────────────────────────────────────────────────────────
# Workspace actions
# ─────────────────────────────────────────────────────────────────────────────

def activate() -> tuple[WorkspaceSession, str]:
    """Create a new workspace session."""
    global _active_id
    session = WorkspaceSession()
    _sessions[session.workspace_id] = session
    _active_id = session.workspace_id
    msg = (
        f"ML Workspace activated. Session ID: {session.workspace_id}.\n"
        f"Upload your dataset (CSV, XLSX, or Parquet) and I will analyze it."
    )
    return session, msg


def load_dataset_action(file_path: str) -> tuple[WorkspaceSession | None, str]:
    """Load and analyze a dataset into the active session."""
    (analyze_dataset, execute_plan, list_experiments,
     load_dataset, save_experiment, validate_plan,
     MLEngineError, ValidationError) = _engine()

    session = get_active_session()
    if session is None:
        session, _ = activate()

    p = Path(file_path)
    if not p.exists():
        return session, f"File not found: {file_path}"

    try:
        df = load_dataset(file_path)
    except MLEngineError as e:
        return session, f"Dataset load failed: {e}"

    try:
        schema = analyze_dataset(df, p.name)
    except Exception as e:
        return session, f"Dataset analysis failed: {e}"

    session.dataset_path = file_path
    session.dataset_name = p.name
    session.schema       = schema

    # Auto-set target if confident
    top = schema.get("top_target")
    if top and len(schema.get("potential_targets", [])) == 1:
        session.target = top

    # Auto-set task hint
    if schema.get("task_hint") and schema["task_hint"] != "unknown":
        session.task = schema["task_hint"]

    # Build summary
    rows    = schema["rows"]
    cols    = schema["columns"]
    missing = schema["missing_values"]
    dups    = schema["duplicates"]
    num_c   = len(schema["numerical_columns"])
    cat_c   = len(schema["categorical_columns"])
    targets = schema["potential_targets"]

    lines = [
        f"Dataset loaded: {p.name}",
        f"  Rows        : {rows:,}",
        f"  Columns     : {cols}",
        f"  Numerical   : {num_c}  |  Categorical: {cat_c}",
        f"  Missing vals: {missing}",
        f"  Duplicates  : {dups}",
    ]
    if targets:
        lines.append(f"  Target candidates: {', '.join(targets[:5])}")
        if len(targets) == 1:
            lines.append(f"  Auto-selected target: {targets[0]}")
        else:
            lines.append("  Please specify which column you want to predict.")
    if session.task:
        lines.append(f"  Detected task: {session.task}")

    return session, "\n".join(lines)


def update_plan(patch: dict) -> tuple[WorkspaceSession | None, str]:
    """Apply a partial configuration update from the LLM."""
    session = get_active_session()
    if session is None:
        return None, "No active workspace. Say 'activate workspace' first."

    changed = session.apply_patch(patch)

    if not changed:
        return session, "No changes detected in your request."
    return session, "Updated: " + ", ".join(changed) + "."


def run_experiment() -> tuple[WorkspaceSession | None, str]:
    """Validate the current plan and execute the ML pipeline."""
    (analyze_dataset, execute_plan, list_experiments,
     load_dataset, save_experiment, validate_plan,
     MLEngineError, ValidationError) = _engine()

    session = get_active_session()
    if session is None:
        return None, "No active workspace."

    if not session.dataset_path:
        return session, "No dataset loaded. Please upload a dataset first."
    if not session.target:
        return session, "Target column not set. Please specify which column to predict."
    if not session.algorithm:
        return session, "Algorithm not selected. Please specify an algorithm (e.g. XGBoost, Random Forest)."
    if not session.task:
        return session, "Task not determined. Please specify 'regression' or 'classification'."

    plan = session.to_plan()

    # ── Validation ────────────────────────────────────────────────────────────
    try:
        validate_plan(plan, session.schema)
    except ValidationError as ve:
        return session, f"Validation error: {ve}"
    except MLEngineError as me:
        return session, f"Plan error: {me}"

    # ── Load data ─────────────────────────────────────────────────────────────
    try:
        df = load_dataset(session.dataset_path)
    except MLEngineError as e:
        return session, f"Could not reload dataset: {e}"

    # ── Execute ───────────────────────────────────────────────────────────────
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = execute_plan(df, plan)
    except MLEngineError as e:
        return session, f"Execution failed: {e}"
    except Exception as e:
        return session, f"Unexpected error during training: {e}"

    # ── Save experiment ────────────────────────────────────────────────────────
    try:
        exp_path = save_experiment(plan, result, session.dataset_name, session.workspace_id)
        session.last_experiment_path = exp_path
    except Exception as e:
        exp_path = "(save failed)"
        print(f"[MLWorkspace] Experiment save warning: {e}")

    session.last_result   = result
    session.experiments_run += 1

    # ── Format result ─────────────────────────────────────────────────────────
    return session, _format_result(result, session.dataset_name)


def _format_result(result: dict, dataset_name: str) -> str:
    algo     = result.get("algorithm", "?").replace("_", " ").title()
    task     = result.get("task", "?").title()
    sp       = result.get("split", {})
    t_met    = result.get("test_metrics", {})
    v_met    = result.get("validation_metrics", {})
    train_t  = result.get("training_time_seconds", 0)
    fi       = result.get("feature_importance", {})

    lines = [
        "Experiment completed.",
        "",
        f"  Model       : {algo} ({task})",
        f"  Dataset     : {dataset_name}",
        f"  Train       : {sp.get('train', '?'):,} samples",
        f"  Validation  : {sp.get('validation', '?'):,} samples",
        f"  Test        : {sp.get('test', '?'):,} samples",
        "",
        "  ── Validation Metrics ──",
    ]
    for k, v in v_met.items():
        if k == "confusion_matrix":
            lines.append(f"  Confusion Matrix: {v}")
        else:
            lines.append(f"  {k.upper():<12}: {v}")

    lines += ["", "  ── Test Metrics ──"]
    for k, v in t_met.items():
        if k == "confusion_matrix":
            lines.append(f"  Confusion Matrix: {v}")
        else:
            lines.append(f"  {k.upper():<12}: {v}")

    lines.append("")
    lines.append(f"  Training time : {train_t}s")

    if fi:
        lines += ["", "  ── Feature Importance ──"]
        for feat, score in list(fi.items())[:5]:
            bar = "█" * int(score * 20)
            lines.append(f"  {feat:<20}: {score:.4f}  {bar}")

    return "\n".join(lines)


def show_history() -> str:
    (analyze_dataset, execute_plan, list_experiments,
     load_dataset, save_experiment, validate_plan,
     MLEngineError, ValidationError) = _engine()

    session = get_active_session()
    ws_id   = session.workspace_id if session else ""
    exps    = list_experiments(ws_id)
    if not exps:
        return "No experiments recorded yet."

    lines = ["Experiment History:", ""]
    for e in exps[:10]:
        test_m = e.get("test_metrics", {})
        metric_str = "  |  ".join(
            f"{k.upper()}: {v}" for k, v in list(test_m.items())[:3]
            if k != "confusion_matrix"
        )
        lines.append(
            f"  [{e.get('experiment_id','?')}]  "
            f"{e.get('algorithm','?').replace('_',' ').title()}  "
            f"({e.get('task','?')})  "
            f"target={e.get('target','?')}  "
            f"{metric_str}"
        )
    return "\n".join(lines)


def compare_last_two() -> str:
    (analyze_dataset, execute_plan, list_experiments,
     load_dataset, save_experiment, validate_plan,
     MLEngineError, ValidationError) = _engine()

    session = get_active_session()
    ws_id   = session.workspace_id if session else ""
    exps    = list_experiments(ws_id)
    if len(exps) < 2:
        return "Need at least 2 experiments to compare."

    a, b = exps[0], exps[1]

    def _fmt_exp(e: dict) -> list[str]:
        test_m = e.get("test_metrics", {})
        lines = [
            f"  {e.get('experiment_id','?')} — "
            f"{e.get('algorithm','?').replace('_',' ').title()} "
            f"({e.get('task','?')})"
        ]
        for k, v in test_m.items():
            if k != "confusion_matrix":
                lines.append(f"    {k.upper():<12}: {v}")
        return lines

    out = ["Comparison:", ""] + _fmt_exp(a) + [""] + _fmt_exp(b)
    return "\n".join(out)


def status() -> str:
    session = get_active_session()
    if session is None:
        return "No active ML workspace."
    s = session
    lines = [
        f"Workspace: {s.workspace_id}  ({s.status})",
        f"  Dataset   : {s.dataset_name or 'not loaded'}",
        f"  Target    : {s.target or 'not set'}",
        f"  Task      : {s.task or 'not set'}",
        f"  Algorithm : {s.algorithm or 'not set'}",
        f"  Split     : {round(s.split.get('train',0)*100)}/"
                        f"{round(s.split.get('validation',0)*100)}/"
                        f"{round(s.split.get('test',0)*100)}",
        f"  Metrics   : {', '.join(s.metrics) or 'not set'}",
        f"  Runs      : {s.experiments_run}",
    ]
    return "\n".join(lines)
