"""VEAP Evidence R1: bounded, read-only synthetic trace evaluation."""
from .verdict import evaluate, canonical_hash, load_record, EvaluationError
__all__ = ["evaluate", "canonical_hash", "load_record", "EvaluationError"]
