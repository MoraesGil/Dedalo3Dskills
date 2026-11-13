"""Synthetic geometry preflight and footprint plans; no client models or slicer."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import math
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

import numpy as np
from lxml import etree as E
from shapely.geometry import Polygon
import trimesh
from synthetic_project import make_project, encode_members, ROOT_ID, Q, metadata

ROOT = Path(__file__).resolve().parents[1]
NS = {'m': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P = load('new_geometry_preflight', ROOT/'skills/analysis/analyze-3d-geometry/scripts/preflight.py')
F = load('new_custom_footprint', ROOT/'skills/printing/custom-footprint/scripts/plan_footprint.py')
A = load('new_footprint_consumer', ROOT/'skills/printing/prender-3d/scripts/apply_retention.py')


def fixture(mesh=None, *, negative=False, transform=None):
    data = make_project(negative=negative, transform=transform)
    if mesh is not None:
        doc = E.fromstring(data['3D/3dmodel.model'])
        old = doc.find("m:resources/m:object[@id='1']/m:mesh", NS)
        obj = old.getparent()
        obj.remove(old)
        native = E.SubElement(obj, Q('mesh'))
        vv, ff = E.SubElement(native, Q('vertices')), E.SubElement(native, Q('triangles'))
        for point in mesh.vertices:
            E.SubElement(vv, Q('vertex'), **dict(zip('xyz', (format(float(v), '.15g')for v in point))))
        for i, face in enumerate(mesh.faces):
            attrs = dict(zip(('v1','v2','v3'), map(str, face)))
            if i == 0:attrs['paint_color'] = '2'
            E.SubElement(ff, Q('triangle'), **attrs)
        data['3D/3dmodel.model'] = E.tostring(doc, xml_declaration=True, encoding='UTF-8')
    return data


def default_options(**patch):
    return {'shape': 'auto', 'all_positive_fixed': True, 'height_mm': 3,
            'contact_angles_deg': [0,90,180,270], **patch}


class PreflightTests(unittest.TestCase):
    def test_inward_cavity_shell_is_refused_instead_of_filled(self):
        outer=trimesh.creation.box(extents=[20,20,30]);outer.apply_translation([0,0,15])
        inner=trimesh.creation.box(extents=[10,10,29.9]);inner.apply_translation([0,0,15]);inner.invert()
        data=fixture(trimesh.util.concatenate([outer,inner]));raw=encode_members(data)
        with self.assertRaisesRegex(ValueError,'solid_topology_adapter'):
            P.inspect(raw)
        with self.assertRaisesRegex(ValueError,'solid_topology_adapter'):
            F.plan(raw,ROOT_ID,default_options(),hashlib.sha256(raw).hexdigest())

    def test_nested_resource_transforms_and_modifier_inventory(self):
        data = fixture(negative=True,transform='0 1 0 -1 0 0 0 0 1 70 70 0')
        main = E.fromstring(data['3D/3dmodel.model'])
        resource = E.Element(Q('model'),nsmap={None:NS['m']},unit='millimeter')
        res = E.SubElement(resource,Q('resources'))
        for old,new in [('1','200'),('2','201')]:
            obj = copy.deepcopy(main.find(f"m:resources/m:object[@id='{old}']",NS));obj.set('id',new)
            if old=='2':
                for v in obj.findall('m:mesh/m:vertices/m:vertex',NS):v.set('z',str(float(v.get('z'))-22))
            res.append(obj)
        blocker=copy.deepcopy(res[0]);blocker.set('id','202');res.append(blocker)
        nested=E.SubElement(res,Q('object'),id='500',type='model');parts=E.SubElement(nested,Q('components'))
        for oid,x in [('200',3),('201',3),('202',100)]:
            E.SubElement(parts,Q('component'),objectid=oid,transform=f'1 0 0 0 1 0 0 0 1 {x} 0 0')
        rootparts=main.find("m:resources/m:object[@id='1000']/m:components",NS);rootparts.clear()
        E.SubElement(rootparts,Q('component'),objectid='500',transform='1 0 0 0 1 0 0 0 1 5 0 0',
                     **{'{http://schemas.microsoft.com/3dmanufacturing/production/2015/06}path':'/3D/Objects/nested.model'})
        cfg=E.fromstring(data['Metadata/model_settings.config'])
        for p in cfg.find("object[@id='1000']").findall('part'):p.getparent().remove(p)
        E.SubElement(cfg.find("object[@id='1000']"),'part',id='500',subtype='normal_part')
        settings=E.SubElement(cfg,'object',id='500')
        for oid,subtype in [('200','normal_part'),('201','negative_part'),('202','support_blocker')]:
            E.SubElement(settings,'part',id=oid,subtype=subtype)
        data.update({'3D/3dmodel.model':E.tostring(main),'3D/Objects/nested.model':E.tostring(resource),
                     'Metadata/model_settings.config':E.tostring(cfg)})
        root=P.inspect(encode_members(data))['roots'][0]
        self.assertEqual(root['positive_bounds_root_mm'],[[-2.,-10.,0.],[18.,10.,30.]])
        self.assertEqual(root['instances'][0]['bounds_build_mm'],[[60.,68.,0.],[80.,88.,30.]])
        self.assertEqual(root['positive_connected_components'],1)
        self.assertEqual(root['negative_connected_components'],1)
        self.assertIn('support_blocker',{p['subtype']for p in root['part_inventory']})
        self.assertLess(root['instances'][0]['first_layer']['net_geometric_area_mm2'],302)

    def test_real_first_layer_section_and_negative_cutout(self):
        data = fixture(negative=True)
        doc = E.fromstring(data['3D/3dmodel.model'])
        for vertex in doc.findall("m:resources/m:object[@id='2']/m:mesh/m:vertices/m:vertex", NS):
            vertex.set('z', str(float(vertex.get('z'))-22))
        data['3D/3dmodel.model'] = E.tostring(doc)
        before = encode_members(data)
        report = P.inspect(before, root_id=ROOT_ID, include_geometry=True)
        root = report['roots'][0]
        layer = root['instances'][0]['first_layer']
        circle = 64/2*100*math.sin(2*math.pi/64)
        hole = 16/2*4*math.sin(2*math.pi/16)
        self.assertAlmostEqual(layer['net_geometric_area_mm2'], circle-hole, places=5)
        self.assertLess(layer['positive_area_mm2'], 400)
        self.assertTrue(layer['section_complete'])
        self.assertEqual(root['negative_connected_components'], 1)
        self.assertIn('negative_part', {p['subtype']for p in root['part_inventory']})
        self.assertEqual(report['source_sha256'], hashlib.sha256(before).hexdigest())

    def test_small_foot_is_not_the_projection_of_a_wide_top(self):
        foot = trimesh.creation.cylinder(radius=2, height=5, sections=32)
        foot.apply_translation([0,0,2.5])
        head = trimesh.creation.cylinder(radius=10, height=25, sections=32)
        head.apply_translation([0,0,17.5])
        report = P.inspect(encode_members(fixture(trimesh.util.concatenate([foot, head]))))
        root = report['roots'][0]
        self.assertEqual(root['positive_bounds_root_mm'][1][0], 10)
        self.assertLess(root['instances'][0]['first_layer']['net_geometric_area_mm2'], 13)

    def test_floating_part_has_zero_first_layer_area(self):
        raw = encode_members(fixture(transform='1 0 0 0 1 0 0 0 1 70 70 5'))
        instance = P.inspect(raw)['roots'][0]['instances'][0]
        self.assertFalse(instance['on_bed'])
        self.assertFalse(instance['retention_adapter_eligible'])
        self.assertEqual(instance['first_layer']['net_geometric_area_mm2'], 0)

    def test_scaled_build_is_measured_but_not_eligible(self):
        raw = encode_members(fixture(transform='2 0 0 0 2 0 0 0 2 70 70 0'))
        instance = P.inspect(raw)['roots'][0]['instances'][0]
        self.assertFalse(instance['upright_unscaled_rigid'])
        self.assertFalse(instance['retention_adapter_eligible'])
        with self.assertRaises(ValueError):
            F.plan(raw, ROOT_ID, default_options(), hashlib.sha256(raw).hexdigest())


class FootprintTests(unittest.TestCase):
    def _plan(self, options=None, data=None):
        raw = encode_members(data or fixture())
        return F.plan(raw, ROOT_ID, options or default_options(), hashlib.sha256(raw).hexdigest())

    def test_all_shapes_cover_geometry_and_make_closed_native_masks(self):
        hexagon = [[12*math.cos(i*math.pi/3),12*math.sin(i*math.pi/3)]for i in range(6)]
        cases = [('circle',{}),('ellipse',{'radii_mm':[13,10]}),
                 ('rounded_rectangle',{'size_mm':[22,22],'corner_radius_mm':2}),
                 ('hull',{}),('polygon',{'points_xy':hexagon})]
        for shape, parameters in cases:
            with self.subTest(shape=shape):
                result = self._plan(default_options(shape=shape,shape_parameters=parameters))
                self.assertTrue(result['report']['measured_band_and_margin_covered'])
                self.assertEqual(len(result['report']['contacts']), 4)
                self.assertEqual(result['report']['upper_blocker_z_root_mm'],[3.,6.])
                upper = next(r for r in result['regions']if r['role']=='upper')
                mesh = trimesh.Trimesh(*upper['values'],process=False)
                self.assertTrue(mesh.is_watertight)
                self.assertTrue(mesh.is_winding_consistent)
                self.assertAlmostEqual(mesh.volume,result['report']['footprint_area_mm2']*3,places=5)

    def test_valid_concave_custom_polygon(self):
        a = trimesh.creation.box(extents=[20,10,30]);a.apply_translation([0,-5,15])
        b = trimesh.creation.box(extents=[10,10,30]);b.apply_translation([-5,5,15])
        data = fixture(trimesh.util.concatenate([a,b]))
        polygon = [[-11,-11],[11,-11],[11,1],[1,1],[1,11],[-11,11]]
        result = self._plan(default_options(shape='polygon',shape_parameters={'points_xy':polygon}),data)
        mesh = trimesh.Trimesh(*next(r for r in result['regions']if r['role']=='upper')['values'],process=False)
        self.assertTrue(mesh.is_watertight)
        self.assertTrue(result['report']['measured_band_and_margin_covered'])
        self.assertLess(result['report']['footprint_area_mm2'],24*24)

    def test_undersized_shape_and_missing_fixed_surface_confirmation_fail(self):
        with self.assertRaises(ValueError):
            self._plan(default_options(shape='circle',shape_parameters={'radius_mm':4}))
        options = default_options();options.pop('all_positive_fixed')
        with self.assertRaises(ValueError):self._plan(options)
        with self.assertRaises(ValueError):self._plan(default_options(fixed_part_ids=[True],all_positive_fixed=False))

    def test_keepout_can_reject_or_explicitly_skip_a_contact(self):
        obstacle = [[8,-2],[12,-2],[12,2],[8,2]]
        options = default_options(keepout_polygons_xy=[obstacle],keepout_clearance_mm=0)
        with self.assertRaises(ValueError):self._plan(options)
        result = self._plan({**options,'skip_unsafe_contacts':True,'min_contacts':3})
        self.assertEqual(len(result['report']['contacts']),3)
        self.assertEqual(result['report']['rejected_contacts'][0]['angle_deg'],0)
        self.assertEqual(result['report']['keepout_modifier_count'],1)

    def test_unselected_radial_parts_are_protected_without_joint_inference(self):
        data = make_project(octopus=True)
        options = {'shape':'circle','fixed_part_ids':[1],'height_mm':3,
                   'contact_angles_deg':[22.5+45*i for i in range(8)]}
        result = self._plan(options,data)
        self.assertEqual(len(result['report']['contacts']),8)
        self.assertEqual(result['report']['keepout_modifier_count'],40)
        self.assertIn('static_mesh_keepouts_not_inferred_joint_motion', result['report']['limits'])

    def test_neighbor_contact_collision_is_checked_below_the_upper_band(self):
        data = fixture()
        doc = E.fromstring(data['3D/3dmodel.model']);cfg = E.fromstring(data['Metadata/model_settings.config'])
        root = copy.deepcopy(doc.find("m:resources/m:object[@id='1000']",NS));root.set('id','1001');doc.find('m:resources',NS).append(root)
        E.SubElement(doc.find('m:build',NS),Q('item'),objectid='1001',transform='1 0 0 0 1 0 0 0 1 92 70 0',printable='1')
        conf = copy.deepcopy(cfg.find("object[@id='1000']"));conf.set('id','1001');cfg.append(conf)
        instance = E.SubElement(cfg.find('plate'),'model_instance')
        for key,value in [('object_id',1001),('instance_id',0),('identify_id',2)]:metadata(instance,key,value)
        data['3D/3dmodel.model']=E.tostring(doc);data['Metadata/model_settings.config']=E.tostring(cfg)
        with self.assertRaisesRegex(ValueError,'another printable part'):
            self._plan(default_options(contact_depth_mm=8),data)

    def test_explicit_brim_patch_and_native_consumer_preserve_source(self):
        options = default_options(brim={'type':'outer_only','width_mm':4,'tree_width_mm':0})
        data = fixture(negative=True);raw = encode_members(data);result = self._plan(options,data)
        self.assertEqual(result['report']['brim_process_patch'],{'brim_type':'outer_only','brim_width':'4','tree_support_brim_width':'0'})
        with tempfile.TemporaryDirectory()as td:
            source = Path(td)/'source.3mf';output=Path(td)/'candidate.3mf';source.write_bytes(raw)
            process = json.loads((ROOT/'skills/printing/prender-3d/examples/process.json').read_text())
            process.update(result['report']['brim_process_patch'])
            applied = A.prepare(source,output,hashlib.sha256(raw).hexdigest(),ROOT_ID,result['regions'],process,3)
            self.assertTrue(applied['native_support_only'])
            self.assertEqual(source.read_bytes(),raw)
            self.assertTrue(output.exists())
            with zipfile.ZipFile(output)as archive:
                staged=E.fromstring(archive.read('3D/3dmodel.model'))
                self.assertEqual(archive.read('Metadata/project_settings.config'),data['Metadata/project_settings.config'])
            original=E.fromstring(data['3D/3dmodel.model'])
            for oid in ['1','2']:
                query=f"m:resources/m:object[@id='{oid}']"
                self.assertEqual(E.tostring(original.find(query,NS),method='c14n'),
                                 E.tostring(staged.find(query,NS),method='c14n'))

    def test_installed_sibling_and_checkout_wrapper_help(self):
        with tempfile.TemporaryDirectory()as td:
            skills = Path(td)/'skills';skills.mkdir()
            for category,name in [('printing','prender-3d'),('analysis','analyze-3d-geometry'),('printing','custom-footprint')]:
                shutil.copytree(ROOT/'skills'/category/name,skills/name)
            for path in [skills/'analyze-3d-geometry/scripts/preflight.py',skills/'custom-footprint/scripts/plan_footprint.py',
                         ROOT/'tools/dedalo3d/geometry_preflight.py',ROOT/'tools/dedalo3d/footprint.py']:
                result=subprocess.run([sys.executable,str(path),'--help'],capture_output=True,text=True)
                self.assertEqual(result.returncode,0,(path,result.stderr))

    def test_flat_install_cli_preflight_plan_and_guarded_apply(self):
        with tempfile.TemporaryDirectory()as td:
            directory=Path(td);skills=directory/'skills';skills.mkdir()
            for category,name in [('printing','prender-3d'),('analysis','analyze-3d-geometry'),('printing','custom-footprint')]:
                shutil.copytree(ROOT/'skills'/category/name,skills/name)
            source=directory/'source.3mf';raw=encode_members(fixture(negative=True));source.write_bytes(raw)
            sha=hashlib.sha256(raw).hexdigest();preflight=directory/'preflight.json'
            regions=directory/'regions.json';report=directory/'plan.json';patch=directory/'patch.json'
            def run(*args):
                done=subprocess.run([sys.executable,*map(str,args)],capture_output=True,text=True)
                self.assertEqual(done.returncode,0,done.stderr)
                return done
            run(skills/'analyze-3d-geometry/scripts/preflight.py',source,'--output',preflight)
            self.assertEqual(json.loads(preflight.read_text())['source_sha256'],sha)
            run(skills/'custom-footprint/scripts/plan_footprint.py',source,regions,'--root-id',ROOT_ID,
                '--expect-sha256',sha,'--options-json',skills/'custom-footprint/examples/cylinder.json',
                '--report',report,'--process-patch-output',patch)
            reviewed=json.loads((skills/'prender-3d/examples/process.json').read_text())
            reviewed.update(json.loads(patch.read_text()));process=directory/'process.json';process.write_text(json.dumps(reviewed))
            candidate=directory/'candidate.3mf'
            run(skills/'prender-3d/scripts/apply_retention.py',source,candidate,'--expect-sha256',sha,
                '--root-id',ROOT_ID,'--regions-json',regions,'--process-json',process,'--height-mm',3)
            self.assertEqual(source.read_bytes(),raw)
            self.assertTrue(candidate.exists())
            for path in [preflight,regions,report,patch,candidate]:
                self.assertEqual(path.stat().st_mode & 0o777,0o600)


if __name__ == '__main__':unittest.main()
