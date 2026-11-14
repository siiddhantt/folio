"""Stable RQ import path for jobs queued before ingestion was grouped as a feature."""

from folio.ingestion.processing import process_attempt

__all__ = ["process_attempt"]
