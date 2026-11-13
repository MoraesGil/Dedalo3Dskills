"""Checkout entry point for the canonical footprint skill; no duplicated logic."""
from pathlib import Path
import runpy

if __name__ == '__main__':
    target = Path(__file__).resolve().parents[2] / 'skills/printing/custom-footprint/scripts/plan_footprint.py'
    runpy.run_path(str(target), run_name='__main__')
