"""Load the standalone relief skill regression suite."""
import importlib.util
from pathlib import Path


def load_tests(loader, tests, pattern):
    path = Path(__file__).resolve().parents[1] / 'skills/printing/destacar-relevo-3d/tests/test_relief.py'
    spec = importlib.util.spec_from_file_location('relief_skill_tests', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return loader.loadTestsFromModule(module)
