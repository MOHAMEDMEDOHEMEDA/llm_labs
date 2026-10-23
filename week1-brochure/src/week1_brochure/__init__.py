"""Week 1: generate a short company brochure from the company's own website."""

from .config import Settings
from .pipeline import BrochureResult, FetchFailure, generate_brochure

__all__ = ["BrochureResult", "FetchFailure", "Settings", "generate_brochure"]
