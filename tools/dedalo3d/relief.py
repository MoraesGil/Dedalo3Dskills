"""Checkout wrapper; implementation lives with destacar-relevo-3d."""
from pathlib import Path
import runpy
import sys
script = Path(__file__).resolve().parents[2] / "skills/printing/destacar-relevo-3d/scripts/build_relief.py"
sys.path.insert(0, str(script.parent))
runpy.run_path(str(script), run_name="__main__")
