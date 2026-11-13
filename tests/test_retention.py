"""Synthetic regression tests; no slicer, printer or production fixture required."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np
import trimesh
from lxml import etree as E

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
GENERIC = REPO / 'skills/printing/prender-3d/scripts'
CHILD = REPO / 'skills/printing/prender-polvo-3d/scripts'
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(GENERIC))
from synthetic_project import make_project, encode_members, ROOT_ID
import prender3d_core as core
from geometry_project import Project, conformal_blocker
import apply_retention
import prepare_retention_grid


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def process(brim='no_brim'):
    return {'enable_support': '1', 'support_type': 'tree(manual)',
            'support_style': 'tree_slim', 'support_filament': '1',
            'support_interface_filament': '1', 'brim_type': brim,
            'brim_width': '4' if brim != 'no_brim' else '0'}


def regions():
    return [{'role': 'east', 'label': 'Fixed-wall contact', 'subtype': 'support_enforcer',
             'shape': 'cube', 'values': [[4, 2, 3], [10, 0, 1.5]]},
            {'role': 'upper', 'label': 'Circular height band', 'subtype': 'support_blocker',
             'shape': 'cylinder', 'values': [10.7, 3, [0, 0, 4.5], 128]}]


def product_snapshot(data):
    model = E.fromstring(data[core.MAIN])
    cfg = E.fromstring(data[core.CONFIG])
    root = model.find(f"m:resources/m:object[@id='{ROOT_ID}']", core.NS)
    obj = cfg.find(f"object[@id='{ROOT_ID}']")
    owned = {p.get('id') for p in obj.findall('part')
             if any(x.get('key') == 'name' and x.get('value', '').startswith(('Prender3D |', 'prenderPolvo3D |'))
                    for x in p.findall('metadata'))}
    canonical = lambda x: E.tostring(x, method='c14n')
    meshes = {x.get('id'): canonical(x) for x in model.findall('m:resources/m:object', core.NS)
              if x.get('id') != str(ROOT_ID)}
    parts = [canonical(x) for x in obj.findall('part') if x.get('id') not in owned]
    components = [canonical(x) for x in root.findall('m:components/m:component', core.NS)
                  if x.get('objectid') not in owned]
    builds = [canonical(x) for x in model.findall('m:build/m:item', core.NS)]
    return meshes, parts, components, builds, data['Metadata/project_settings.config']


class GeometryTests(unittest.TestCase):
    def test_circle_and_nonround_contours_cover_measured_outline(self):
        for label, scale, expected in [('circle', [1, 1, 1], 'cylinder'),
                                       ('ellipse', [2, 1, 1], 'contour')]:
            with self.subTest(label=label):
                body = trimesh.creation.cylinder(radius=10, height=25, sections=64)
                body.apply_scale(scale)
                descriptor, measurement = conformal_blocker(body, 3, 6)
                self.assertEqual(measurement['shape'], expected)
                self.assertTrue(measurement['covers_positive_projection_and_margin'])
                self.assertEqual(measurement['z_bounds_local_mm'], [3, 6])
                if expected == 'contour':
                    mask = trimesh.Trimesh(vertices=descriptor['values'][0], faces=descriptor['values'][1], process=False)
                    self.assertTrue(mask.is_watertight)
                    self.assertTrue(mask.is_winding_consistent)
                    self.assertGreater(mask.volume, 0)
        box = trimesh.creation.box(extents=[8, 25, 20])
        descriptor, result = conformal_blocker(box, 3, 6)
        self.assertEqual(result['shape'], 'contour')
        self.assertTrue(result['covers_positive_projection_and_margin'])

    def test_reader_excludes_functional_negatives_without_subtracting_them(self):
        reader = Project(encode_members(make_project(negative=True)))
        try:
            parts = reader.components(ROOT_ID)
            self.assertEqual(len(parts), 1)
            self.assertEqual(reader.excluded, {2})
        finally:
            reader.zip.close()


class CoreTests(unittest.TestCase):
    def test_idempotent_native_modifiers_preserve_product_paint_and_negatives(self):
        data = make_project(negative=True)
        before = product_snapshot(data)
        result = core.apply_regions(data, ROOT_ID, {'bed_z_local': 0, 'top_z_local': 30},
                                    regions(), process(), height_limit_mm=3)
        again = core.apply_regions(data, ROOT_ID, {'bed_z_local': 0, 'top_z_local': 30},
                                   regions(), process(), height_limit_mm=3)
        self.assertEqual(result['generated_ids'], again['generated_ids'])
        self.assertEqual(before, product_snapshot(data))
        cfg = E.fromstring(data[core.CONFIG])
        native = [p for p in cfg.find(f"object[@id='{ROOT_ID}']").findall('part')
                  if p.get('id') in {str(v) for v in result['generated_ids'].values()}]
        self.assertEqual({p.get('subtype') for p in native}, {'support_enforcer', 'support_blocker'})
        self.assertTrue(again['native_slicing_required'])

    def test_rejected_solid_is_atomic_even_with_deprecated_opt_in(self):
        for opt_in in [False, True]:
            with self.subTest(opt_in=opt_in):
                data = make_project()
                before = copy.deepcopy(data)
                bad = regions()
                bad[0]['subtype'] = 'normal_part'
                with self.assertRaises(ValueError):
                    core.apply_regions(data, ROOT_ID, {'bed_z_local': 0, 'top_z_local': 30},
                                       bad, process(), height_limit_mm=3,
                                       allow_sacrificial_normal_parts=opt_in)
                self.assertEqual(data, before)

    def test_enforcer_cannot_escape_height_ceiling(self):
        data = make_project()
        before = copy.deepcopy(data)
        bad = regions()
        bad[0]['values'][0][2] = 8
        with self.assertRaises(ValueError):
            core.apply_regions(data, ROOT_ID, {'bed_z_local': 0, 'top_z_local': 30},
                               bad, process(), height_limit_mm=3)
        self.assertEqual(data, before)

    def test_off_bed_tilted_and_scaled_builds_are_rejected_atomically(self):
        builds = ['1 0 0 0 1 0 0 0 1 70 70 1',
                  '1 0 0 0 0 1 0 -1 0 70 70 0',
                  '2 0 0 0 2 0 0 0 2 70 70 0']
        for transform in builds:
            with self.subTest(transform=transform):
                data = make_project(transform=transform)
                before = copy.deepcopy(data)
                with self.assertRaises(ValueError):
                    core.apply_regions(data, ROOT_ID, {'bed_z_local': 0, 'top_z_local': 30},
                                       regions(), process(), height_limit_mm=3)
                self.assertEqual(data, before)


class WrapperTests(unittest.TestCase):
    def test_single_root_cli_stages_without_replacing_source(self):
        with tempfile.TemporaryDirectory(prefix='dedalo-synthetic-') as temporary:
            directory = Path(temporary)
            source = directory / 'source.3mf'
            raw = encode_members(make_project(negative=True))
            source.write_bytes(raw)
            hash_value = hashlib.sha256(raw).hexdigest()
            rfile = directory / 'regions.json'
            pfile = directory / 'process.json'
            rfile.write_text(json.dumps(regions()))
            pfile.write_text(json.dumps(process()))
            output = directory / 'candidate.3mf'
            command = [sys.executable, str(GENERIC / 'apply_retention.py'), str(source), str(output),
                       '--expect-sha256', hash_value, '--root-id', str(ROOT_ID),
                       '--regions-json', str(rfile), '--process-json', str(pfile), '--height-mm', '3']
            done = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            result = json.loads(done.stdout)
            self.assertTrue(result['native_support_only'])
            self.assertFalse(result['physical_validation'])
            self.assertEqual(source.read_bytes(), raw)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            with zipfile.ZipFile(output) as archive:
                staged = {n: archive.read(n) for n in archive.namelist()}
            self.assertEqual(product_snapshot(staged), product_snapshot(make_project(negative=True)))
            rejected = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertEqual(source.read_bytes(), raw)

    def test_stale_hash_rejects_without_output(self):
        with tempfile.TemporaryDirectory(prefix='dedalo-stale-') as temporary:
            directory = Path(temporary)
            source = directory / 'source.3mf'
            source.write_bytes(encode_members(make_project()))
            output = directory / 'candidate.3mf'
            with self.assertRaisesRegex(ValueError, 'hash changed'):
                apply_retention.prepare(source, output, '0' * 64, ROOT_ID, regions(), process(), 3)
            self.assertFalse(output.exists())

    def test_public_synthetic_example_applies_four_contacts_and_height_band(self):
        with tempfile.TemporaryDirectory(prefix='dedalo-example-') as temporary:
            directory = Path(temporary)
            source = directory / 'source.3mf'
            raw = encode_members(make_project())
            source.write_bytes(raw)
            example = GENERIC.parent / 'examples'
            result = apply_retention.prepare(source, directory / 'candidate.3mf',
                        hashlib.sha256(raw).hexdigest(), ROOT_ID,
                        json.loads((example / 'regions.json').read_text()),
                        json.loads((example / 'process.json').read_text()), 3)
            self.assertEqual(set(result['generated_ids']), {'east', 'north', 'west', 'south', 'upper'})
            self.assertEqual(source.read_bytes(), raw)

    def test_wrapper_rejects_machine_material_quality_and_raft_overrides(self):
        forbidden = {'extruder': '2', 'nozzle_temperature': '260', 'filament_type': 'PLA',
                     'printer_settings_id': 'Another machine', 'curr_bed_type': 'Another plate',
                     'machine_start_gcode': 'G28', 'support_multi_bed_types': '0',
                     'outer_wall_speed': '200', 'raft_layers': '2'}
        with tempfile.TemporaryDirectory(prefix='dedalo-preserve-') as temporary:
            directory = Path(temporary)
            source = directory / 'source.3mf'
            raw = encode_members(make_project())
            source.write_bytes(raw)
            for field, value in forbidden.items():
                with self.subTest(field=field):
                    reviewed = process()
                    reviewed[field] = value
                    output = directory / 'candidate.3mf'
                    with self.assertRaises(ValueError):
                        apply_retention.prepare(source, output, hashlib.sha256(raw).hexdigest(),
                                                ROOT_ID, regions(), reviewed, 3)
                    self.assertFalse(output.exists())
                    self.assertEqual(source.read_bytes(), raw)

    def test_grid_candidate_keeps_independent_roots_and_original(self):
        with tempfile.TemporaryDirectory(prefix='dedalo-grid-') as temporary:
            directory = Path(temporary)
            source = directory / 'source.3mf'
            raw = encode_members(make_project(plate_count=2))
            source.write_bytes(raw)
            output = directory / 'candidate.3mf'
            result = prepare_retention_grid.prepare(source, output, hashlib.sha256(raw).hexdigest(), ROOT_ID,
                        count=4, height_mm=3, min_gap_ratio=.1, pitch_mm=25,
                        process_overrides=process('outer_only'), native_profile={}, retention_extruder=1)
            self.assertEqual(len(set(result['root_ids'])), 4)
            self.assertTrue(result['native_support_only'])
            self.assertEqual(result['positive_retention_parts'], 0)
            self.assertEqual(source.read_bytes(), raw)


class OctopusTests(unittest.TestCase):
    def test_installed_sibling_imports_and_synthetic_octopus_application(self):
        detector = load('dedalo_octopus_detector', CHILD / 'detect_octopus.py')
        application = load('dedalo_octopus_apply', CHILD / 'apply_anchors.py')
        with tempfile.TemporaryDirectory(prefix='dedalo-octopus-') as temporary:
            source = Path(temporary) / 'toy_radial.3mf'
            data = make_project(octopus=True)
            raw = encode_members(data)
            source.write_bytes(raw)
            detected = detector.analyze(source, ROOT_ID)
            self.assertTrue(detected['matches_octopus'], detected['reasons'])
            self.assertEqual(detected['arm_count'], 8)
            self.assertEqual(detected['segment_count'], 40)
            frame = {k: detected[k] for k in ['center_xy', 'bed_z_local', 'top_z_local', 'arm_angles_deg', 'xy_scale']}
            before = product_snapshot(data)
            first = application.apply(data, ROOT_ID, frame, height_limit_mm=3)
            second = application.apply(data, ROOT_ID, frame, height_limit_mm=3)
            self.assertEqual(first['generated_ids'], second['generated_ids'])
            self.assertEqual(before, product_snapshot(data))
            cfg = E.fromstring(data[core.CONFIG])
            parts = cfg.find(f"object[@id='{ROOT_ID}']").findall('part')
            self.assertEqual(sum(p.get('subtype') == 'support_enforcer' for p in parts), 9)
            self.assertEqual(sum(p.get('subtype') == 'support_blocker' for p in parts), 9)
            self.assertEqual(first['coverage_height_mm'], 3)
            profile = json.loads(data[core.PROVENANCE])['roots'][str(ROOT_ID)]['profile']
            self.assertEqual(profile['upper_blocker']['shape'], 'cylinder')
            self.assertEqual(profile['upper_blocker']['z_bounds_local_mm'], [3, 6])
            self.assertEqual(source.read_bytes(), raw)

    def test_ordinary_grip_is_not_misclassified(self):
        detector = load('dedalo_negative_detector', CHILD / 'detect_octopus.py')
        with tempfile.TemporaryDirectory(prefix='dedalo-not-octopus-') as temporary:
            source = Path(temporary) / 'toy_grip.3mf'
            source.write_bytes(encode_members(make_project()))
            self.assertFalse(detector.analyze(source, ROOT_ID)['matches_octopus'])


if __name__ == '__main__':
    unittest.main()
