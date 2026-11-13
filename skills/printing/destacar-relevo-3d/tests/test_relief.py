"""Synthetic planar masks: topology, dimensions, keepouts and refusal boundaries."""
import importlib.util
from pathlib import Path
import tempfile
import subprocess
import sys
import os
import json
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/build_relief.py'
spec = importlib.util.spec_from_file_location('relief', SCRIPT)
relief = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relief)

MASK = {'outer': [[0, 0], [20, 0], [20, 16], [0, 16]],
        'holes': [[[8, 6], [12, 6], [12, 10], [8, 10]]]}

class ReliefTests(unittest.TestCase):
    def test_filled_preserves_functional_hole_and_z_contract(self):
        mesh, info = relief.build(MASK, mode='filled', width=None, surface_z=3,
                                  rise=.64, root=.4)
        self.assertTrue(mesh.is_watertight)
        self.assertTrue(mesh.is_winding_consistent)
        self.assertAlmostEqual(mesh.bounds[0, 2], 2.6)
        self.assertAlmostEqual(mesh.bounds[1, 2], 3.64)
        self.assertAlmostEqual(mesh.volume, (320-16)*1.04, places=5)
        self.assertEqual(info['holes'], 1)

    def test_outline_is_smaller_and_keeps_hole(self):
        filled, _ = relief.build(MASK, mode='filled', width=None, surface_z=3, rise=.64, root=.4)
        mesh, info = relief.build(MASK, mode='outline', width=.85, surface_z=3, rise=.64, root=.4)
        self.assertTrue(mesh.is_watertight)
        self.assertLess(mesh.volume, filled.volume)
        self.assertAlmostEqual(info['area_mm2'], 304-(18.3*14.3-5.7*5.7), places=5)

    def test_refuses_invalid_masks_dimensions_and_collapsed_outline(self):
        for key, value in [('rise', 0), ('root', -1), ('surface_z', float('nan'))]:
            kwargs = dict(mode='filled', width=None, surface_z=3, rise=.64, root=.4)
            kwargs[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): relief.build(MASK, **kwargs)
        with self.assertRaises(ValueError):
            relief.build(MASK, mode='outline', width=20, surface_z=3, rise=.64, root=.4)
        with self.assertRaises(ValueError):
            relief.build({'outer': [[0,0],[2,2],[0,2],[2,0]]}, mode='filled', width=None, surface_z=3, rise=.64, root=.4)

    @unittest.skipUnless(os.name == 'posix' and Path('/tmp').is_dir(), 'Unix alternate temp root')
    def test_cli_accepts_unix_tmp_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            mask = Path(tmp)/'mask.json'
            mask.write_text(json.dumps(MASK))
            output = Path(tmp)/'relief.stl'
            command = [sys.executable, str(SCRIPT), str(mask), str(output), '--mode', 'outline',
                       '--width', '.85', '--surface-z', '3', '--rise', '.64', '--root', '.4']
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            original = output.read_bytes()
            second = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(second.returncode, 2)
            self.assertEqual(output.read_bytes(), original)

    def test_serialize_roundtrip_geometry(self):
        mesh, _ = relief.build(MASK, mode='outline', width=.85, surface_z=3, rise=.64, root=.4)
        import trimesh
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'relief.stl'
            mesh.export(path)
            loaded = trimesh.load_mesh(path, process=True)
            self.assertTrue(loaded.is_watertight)
            self.assertAlmostEqual(loaded.volume, mesh.volume, places=3)

if __name__ == '__main__': unittest.main()
