"""GUI package for the BPSR Fishing Bot (Demon Soul edition)."""

# Note: importing `run` pulls in PyQt6. Import lazily where PyQt6 may be absent.
from .app import run  # noqa: F401
