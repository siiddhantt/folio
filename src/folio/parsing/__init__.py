"""PDF-to-evidence interface; importing it does not load the parser runtime."""

from .evidence import Element, Extraction, ExtractionError, Location, Page
from .parser import parse_pdf

__all__ = ["parse_pdf", "Extraction", "ExtractionError", "Page", "Element", "Location"]
