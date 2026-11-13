"""Checkout entry point for the canonical analysis skill; no duplicated logic."""
from pathlib import Path
import runpy

if __name__ == '__main__':
    target = Path(__file__).resolve().parents[2] / 'skills/analysis/analyze-3d-geometry/scripts/preflight.py'
    runpy.run_path(str(target), run_name='__main__')
