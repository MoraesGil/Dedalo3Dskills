"""Synthetic regressions. These prove software contracts, not physical cleaning."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from xml.etree import ElementTree as E
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/printing/torre-burj/scripts'))
from burj.gcode import trace,Block,Phase,Layer,Trace
from burj.options import Options
from burj.geometry import make_plan,slab_mesh
from burj.audit import audit
from burj.project import CORE,Project,add_tower,md

def fixture_trace():
    layers=[];phases=[]
    for i in range(80):
        z=(i+1)*.2;layer=Layer(z)
        for tool in ((0,) if i<2 else (0,1)):
            p=Phase(z,tool,bool(phases) and phases[-1].tool!=tool,1)
            # Copies are far apart; their intrinsic size is 42 -> 12 mm.
            for key,shift in (((1,0),0),((1,1),150)):
                w=42-i*.38;b=Block('model',instance_key=key);b.model_bounds=[shift,0,shift+w,w];b.bounds=list(b.model_bounds);p.blocks.append(b)
            layer.phases.append(p);phases.append(p)
        layers.append(layer)
    return Trace(phases,layers,[],[],{},[],0,set())

def native_project(path):
    root=E.Element(f'{{{CORE}}}model',unit='millimeter');E.SubElement(root,f'{{{CORE}}}metadata',name='Snapmaker_Orca:3mfVersion').text='1'
    E.SubElement(root,f'{{{CORE}}}metadata',name='Application').text='Snapmaker_Orca-2.4.1'
    res=E.SubElement(root,f'{{{CORE}}}resources');obj=E.SubElement(res,f'{{{CORE}}}object',id='1',type='model');E.SubElement(obj,f'{{{CORE}}}mesh')
    E.SubElement(E.SubElement(root,f'{{{CORE}}}build'),f'{{{CORE}}}item',objectid='1',transform='1 0 0 0 1 0 0 0 1 100 100 0')
    cfg=E.Element('config');o=E.SubElement(cfg,'object',id='1');md(o,'name','model');p=E.SubElement(cfg,'plate');md(p,'plater_id',1);i=E.SubElement(p,'model_instance')
    for k,v in {'object_id':1,'instance_id':0,'identify_id':1}.items():md(i,k,v)
    conf={'printable_area':['0x0','270x0','270x270','0x270'],'enable_prime_tower':'0','purge_in_prime_tower':'0',
          'filament_type':['PETG','PLA'],'filament_diameter':['1.75','1.75'],'additional_cooling_fan_speed':['0','0'],
          'curr_bed_type':'Supertack Plate','supertack_plate_temp':['70','70'],'nozzle_temperature':['230','215']}
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('3D/3dmodel.model',E.tostring(root));z.writestr('Metadata/model_settings.config',E.tostring(cfg));z.writestr('Metadata/project_settings.config',json.dumps(conf))
    return conf

class Burj(unittest.TestCase):
    def opts(self):return Options.parse({'model_tools':[0,1],'primary_object_ids':[1],'minimum_width_mm':12,'maximum_width_mm':24,'purge_volume_mm3':{'0':1,'1':1},'envelope_taper_power':2,'line_width_mm':.3})
    def test_per_instance_not_layout_envelope(self):
        t=fixture_trace();p=make_plan(t,self.opts(),{'model'})
        self.assertAlmostEqual(p['rows'][0]['envelope_mm'],42)
        self.assertAlmostEqual(p['height_mm'],16)
        self.assertAlmostEqual(p['rows'][-1]['width_mm'],12)
        self.assertTrue(all(r['target_mm3']==0 for row in p['rows'] for r in row['regions'] if r['purpose']=='structure'))
    def test_last_change_cutoff_no_single_colour_tail(self):
        t=fixture_trace();last=t.phases[-1];z=20.;b=Block('model',instance_key=(1,0));b.model_bounds=[0,0,1,1];p=Phase(z,last.tool,False,9,[b]);t.phases.append(p);t.layers.append(Layer(z,[p],{last.tool}))
        plan=make_plan(t,self.opts(),{'model'});self.assertAlmostEqual(plan['height_mm'],16)
    def test_parser_retains_id_and_copy(self):
        t=trace('T0\nM83\n;Z:0.2\nG0 Z0.2\n;WIDTH:0.5\n;TYPE:Outer wall\n; printing object model id:7 copy 2\nG1 X10 Y0 E1 F1200\n',diameters=[1.75],tower_names=set())
        self.assertEqual(t.phases[0].blocks[0].instance_key,(7,2));self.assertEqual(t.fallback_width_depositions,0)
    def test_nested_regions_fill_center(self):
        p=make_plan(fixture_trace(),self.opts(),{'model'})
        for row in p['rows']:
            regions=sorted(row['regions'],key=lambda r:r['inner']);self.assertEqual(regions[0]['inner'],0)
            self.assertEqual(regions[-1]['outer'],1)
            for a,b in zip(regions,regions[1:]):self.assertAlmostEqual(a['outer'],b['inner'])
    def test_mesh_winding_volume_positive(self):
        for inner in (0,.3):
            v,f=slab_mesh(24,inner,1,0,.2);vol=0
            for a,b,c in f:
                x,y,z=v[a];X,Y,Z=v[b];u,w,t=v[c];vol+=(x*(Y*t-Z*w)+y*(Z*u-X*t)+z*(X*w-Y*u))/6
            self.assertGreater(vol,0)
    def test_signed_integrity_materials_and_determinism(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td);config=native_project(td/'in.3mf');project=Project(td/'in.3mf');opts=self.opts();tr=fixture_trace();plan=make_plan(tr,opts,{'model'})
            add_tower(project,opts,tr,plan,[50,50],{'prepass_3mf_sha256':project.sha256})
            h1=project.publish(td/'a.3mf');h2=project.publish(td/'b.3mf');self.assertEqual(h1,h2)
            saved=Project(td/'a.3mf');self.assertIsNotNone(saved.signed_record())
            for key in config:
                if key not in ('enable_prime_tower','purge_in_prime_tower'):self.assertEqual(saved.config[key],config[key])
            root=next(x for x in saved.resources if x.get('id')==str(saved.signed_record()['tower_object_id']));root.set('name','tampered')
            with self.assertRaisesRegex(ValueError,'changed'):saved.signed_record()
    def test_build_transform_printable_and_instances_are_bound(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td);native_project(td/'in.3mf');p=Project(td/'in.3mf');o=self.opts();t=fixture_trace()
            r=add_tower(p,o,t,make_plan(t,o,{'model'}),[50,50],{})
            self.assertIsNotNone(p.signed_record());item=next(i for i in p.build if i.get('objectid')==str(r['tower_object_id']))
            original=dict(item.attrib)
            item.set('transform','1 0 0 0 1 0 0 0 1 1000 1000 0')
            with self.assertRaises(ValueError):p.signed_record()
            item.attrib.clear();item.attrib.update(original);item.set('printable','0')
            with self.assertRaises(ValueError):p.signed_record()
            item.attrib.clear();item.attrib.update(original);p.build.append(copy.deepcopy(item))
            with self.assertRaises(ValueError):p.signed_record()
    def test_unknown_active_command_and_macro_fail_closed(self):
        text='T0\nM83\n;Z:0.2\nG0 Z0.2\n;WIDTH:0.5\n;TYPE:Outer wall\n; printing object model id:7 copy 2\nG1 X10 Y0 E1 F1200\nG53 G0 X0 Y0\n'
        with self.assertRaisesRegex(ValueError,'Unsupported command'):trace(text,diameters=[1.75],tower_names=set())
        text=text.replace('G53 G0 X0 Y0','UNCLASSIFIED_PURGE_AND_MOVE\nG1 X20 E1')
        t=trace(text,diameters=[1.75],tower_names=set());self.assertEqual(t.active_macros,['UNCLASSIFIED_PURGE_AND_MOVE'])
        report=audit(t,t,{'height_mm':.2,'rows':[]},Options.parse({'model_tools':[0],'primary_object_ids':[1]}))
        self.assertFalse(report['passed']);self.assertFalse(report['firmware_semantics_verified']);self.assertIsNone(report['custom_priming_effective'])
    def test_pure_explicit_gcode_can_fully_pass(self):
        def text(tower):
            parts=['M83','T0','M104 S230 T0','M104 S230 T1','M140 S70']
            for i,tool in enumerate((0,1),1):
                z=i*.2
                parts += [f';Z:{z}',f'G0 Z{z}']
                if i>1:parts += [f'T{tool}']
                if tower:
                    parts += ['; printing object tower id:9 copy 0',';WIDTH:0.5',';TYPE:Outer wall','G0 X50 Y50', 'G1 X51 E1 F1200',';TYPE:Sparse infill','G1 Y51 E1','; stop printing object tower id:9 copy 0']
                parts += ['; printing object model id:1 copy 0',';WIDTH:0.5',';TYPE:Outer wall','G0 X100 Y100','G1 X101 E1 F1200','; stop printing object model id:1 copy 0']
            return '\n'.join(parts)
        before=trace(text(False),diameters=[1.75,1.75],tower_names={'tower'});after=trace(text(True),diameters=[1.75,1.75],tower_names={'tower'})
        o=Options.parse({'model_tools':[0,1],'primary_object_ids':[1],'purge_volume_mm3':{'0':1,'1':1}})
        plan={'height_mm':.4,'rows':[{'z':.2,'regions':[{'tool':0,'purpose':'structure','target_mm3':0,'density':10}]},
                                    {'z':.4,'regions':[{'tool':1,'purpose':'prime_after_change','target_mm3':1,'density':10}]}]}
        report=audit(before,after,plan,o)
        self.assertTrue(report['passed'],report);self.assertTrue(report['custom_priming_effective']);self.assertTrue(report['commanded_gcode_passed'])
        missing=text(True);start=missing.index('; printing object tower');stop=missing.index('; stop printing object tower',start);stop=missing.index('\n',stop)
        missing=missing[:start]+missing[stop+1:]
        no_foundation=trace(missing,diameters=[1.75,1.75],tower_names={'tower'})
        rejected=audit(before,no_foundation,plan,o)
        self.assertFalse(rejected['commanded_gcode_passed']);self.assertIn('missing_planned_structural_region',rejected['failures'])
    def test_strict_unknown_and_nonfinite(self):
        for delta in ({'bogus':1},{'speed_mm_s':float('nan')},{'model_tools':[True]}, {'interface_tool':0}):
            v={'model_tools':[0],'primary_object_ids':[1]};v.update(delta)
            with self.assertRaises(ValueError):Options.parse(v)
    def test_audit_rejects_model_before_complete_pass(self):
        t=fixture_trace();plan=make_plan(t,self.opts(),{'model'});report=audit(t,t,plan,self.opts())
        self.assertFalse(report['passed']);self.assertIn('missing_tower_after_change',report['failures'])

if __name__=='__main__':unittest.main()
