"""Synthetic planar masks: topology, dimensions, keepouts and refusal boundaries."""
import importlib.util
from pathlib import Path
import tempfile
import subprocess
import sys
import os
import json
import unittest
import numpy as np

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/build_relief.py'
spec = importlib.util.spec_from_file_location('relief', SCRIPT)
relief = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relief)

MASK = {'outer': [[0, 0], [20, 0], [20, 16], [0, 16]],
        'holes': [[[8, 6], [12, 6], [12, 10], [8, 10]]]}

class ReliefTests(unittest.TestCase):
    def run_cli(self, mask, output, *, surface_z=3, rise=.64, root=.4):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(mask), str(output), '--mode', 'filled',
             '--surface-z', str(surface_z), '--rise', str(rise), '--root', str(root)],
            capture_output=True, text=True, timeout=30)

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

    def test_refuses_malformed_numeric_dimensions(self):
        for key in ('surface_z', 'rise', 'root', 'width'):
            for value in (True, '3', None, 10**400):
                kwargs = dict(mode='outline', width=.85, surface_z=3, rise=.64, root=.4)
                kwargs[key] = value
                with self.subTest(key=key, value_type=type(value).__name__):
                    with self.assertRaises(ValueError):
                        relief.build(MASK, **kwargs)

    def test_refuses_malformed_coordinates(self):
        for value in (True, 10**400):
            mask = dict(MASK, outer=[[value, 0], [20, 0], [20, 16], [0, 16]])
            with self.subTest(value_type=type(value).__name__), self.assertRaises(ValueError):
                relief.build(mask, mode='filled', width=None, surface_z=3, rise=.64, root=.4)

    def test_refuses_empty_or_degenerate_hole_rings(self):
        for hole in ([], [[1, 1]], [[1, 1], [2, 2]]):
            with self.subTest(hole=hole), self.assertRaises(ValueError):
                relief.build(dict(MASK, holes=[hole]), mode='filled', width=None,
                             surface_z=3, rise=.64, root=.4)

    def test_refuses_unrepresentable_z_contract(self):
        for surface_z, rise, root in ((1e16, 3, 3), (0, 1e308, 1e308)):
            with self.subTest(surface_z=surface_z), self.assertRaises(ValueError):
                relief.build(MASK, mode='filled', width=None, surface_z=surface_z,
                             rise=rise, root=root)

    def test_refuses_overflowed_measurements(self):
        for size, rise in ((1e200, .64), (1e150, 1e20)):
            mask = {'outer': [[0, 0], [size, 0], [size, size], [0, size]]}
            with self.subTest(size=size), np.errstate(over='ignore', invalid='ignore'):
                with self.assertRaises(ValueError):
                    relief.build(mask, mode='filled', width=None, surface_z=3,
                                 rise=rise, root=.4)

    def test_cli_refuses_stl_precision_loss_before_creating_output(self):
        offset_mask = {'outer': [[1e8, 1e8], [1e8+20, 1e8],
                                 [1e8+20, 1e8+16], [1e8, 1e8+16]]}
        with tempfile.TemporaryDirectory() as tmp:
            mask_path = Path(tmp)/'mask.json'
            for index, (mask, z) in enumerate(((MASK, 1e7), (offset_mask, 3))):
                output = Path(tmp)/f'relief-{index}.stl'
                mask_path.write_text(json.dumps(mask))
                with self.subTest(surface_z=z):
                    result = self.run_cli(mask_path, output, surface_z=z)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertFalse(output.exists())
                    self.assertEqual(result.stdout, '')

    def test_cli_refuses_serialized_hole_collapse(self):
        mask = {'outer': [[1000, 0], [1020, 0], [1020, 16], [1000, 16]],
                'holes': [[[1010, 6], [1010.00001, 6], [1010.00001, 10], [1010, 10]]]}
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp)/'mask.json', Path(tmp)/'relief.stl'
            source.write_text(json.dumps(mask))
            result = self.run_cli(source, output)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn('topology', result.stderr)
            self.assertFalse(output.exists())

    def test_cli_refuses_serialized_root_loss_even_if_mesh_stays_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp)/'mask.json', Path(tmp)/'relief.stl'
            source.write_text(json.dumps(MASK))
            result = self.run_cli(source, output, surface_z=1000, rise=.5, root=.0000152587890625)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn('root', result.stderr)
            self.assertFalse(output.exists())

    @unittest.skipUnless(hasattr(os, 'symlink'), 'symlinks unavailable')
    def test_cli_refuses_dangling_output_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            mask = Path(tmp)/'mask.json'
            mask.write_text(json.dumps(MASK))
            output = Path(tmp)/'relief.stl'
            target = Path(tmp)/'unexpected.stl'
            output.symlink_to(target)
            result = self.run_cli(mask, output)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertTrue(output.is_symlink())
            self.assertFalse(target.exists())

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
