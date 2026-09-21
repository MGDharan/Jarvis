"""JARVIS ML Engine — deterministic ML execution, no LLM code generation."""
from .dataset_analyzer import analyze_dataset, load_dataset
from .evaluator import compute_classification_metrics, compute_regression_metrics
from .exceptions import (
    DatasetError, LibraryNotInstalledError, MetricError,
    MLEngineError, ModelError, SplitError, ValidationError,
)
from .executor import execute_plan
from .experiment import list_experiments, save_experiment
from .model_registry import REGISTRY, get_spec, list_algorithms, resolve_algorithm
from .preprocessing import Preprocessor, encode_target
from .splitter import split_dataset
from .validator import validate_plan

__all__ = [
    "analyze_dataset", "load_dataset",
    "compute_classification_metrics", "compute_regression_metrics",
    "DatasetError", "LibraryNotInstalledError", "MetricError",
    "MLEngineError", "ModelError", "SplitError", "ValidationError",
    "execute_plan", "list_experiments", "save_experiment",
    "REGISTRY", "get_spec", "list_algorithms", "resolve_algorithm",
    "Preprocessor", "encode_target", "split_dataset", "validate_plan",
]
