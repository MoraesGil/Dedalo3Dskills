"""Minimal new 3MF adapter. No upstream Project/preset/service code is included.

Preserves product resources, painting, transforms, materials and temperatures.
Only native project archives are supported, never mesh-only 3MF conversion.
"""
from __future__ import annotations
import copy
import hashlib
import io
import json
import math
import posixpath
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from .geometry import mesh_groups, profile
from .gcode import Footprint, SIGNATURE

CORE='http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
MAIN='3D/3dmodel.model'
SETTINGS='Metadata/model_settings.config'
PROCESS='Metadata/project_settings.config'
RECEIPT='Metadata/dedalo_burj.json'
OWNER='Dedalo3D.Burj.v1'
SEQ=('first_layer_print_sequence','other_layers_print_sequence','other_layers_print_sequence_nums')
NATIVE_OFF={'enable_prime_tower':'0','purge_in_prime_tower':'0'}

def digest(blob): return hashlib.sha256(blob).hexdigest()
def encoded(value): return (json.dumps(value,sort_keys=True,allow_nan=False,separators=(',',':'))+'\n').encode()
def metadata(node):
    values={}
    for element in node.findall('metadata'):
        key=element.get('key')
        if key in values: raise ValueError('Duplicate native metadata key')
        values[key]=element.get('value','')
    return values

def md(node,key,value):
    found=[e for e in node.findall('metadata') if e.get('key')==key]
    if len(found)>1: raise ValueError('Duplicate native metadata key')
    if value is None:
        if found: node.remove(found[0])
        return
    e=found[0] if found else ET.SubElement(node,'metadata',key=key)
    e.set('value', str(int(value)) if isinstance(value,bool) else str(value))

def xml(blob):
    if b'<!DOCTYPE' in blob.upper() or b'<!ENTITY' in blob.upper():
        raise ValueError('DTD/entity declarations are not supported')
    for _, ns in ET.iterparse(io.BytesIO(blob),events=('start-ns',)):
        prefix,uri=ns
        if not re.fullmatch(r'ns\d+',prefix): ET.register_namespace(prefix,uri)
    return ET.fromstring(blob)

def xmlbytes(node):
    if node.tag==f'{{{CORE}}}model': ET.register_namespace('',CORE)
    return ET.tostring(node,encoding='utf-8',xml_declaration=True)
def values(v): return v if isinstance(v,list) else str(v).split(',')
def off(v): return str(v).lower() in {'0','false','none',''}

class Project:
    def __init__(self,path):
        self.path=Path(path)
        blob=self.path.read_bytes(); self.sha256=digest(blob)
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            infos=z.infolist()
            if len(infos)>20000 or sum(i.file_size for i in infos)>1024**3:
                raise ValueError('Project exceeds the finite 1 GiB/20000-member archive limit')
            if len({i.filename for i in infos})!=len(infos): raise ValueError('Duplicate ZIP members')
            if any(i.filename.startswith('/') or '..' in Path(i.filename).parts or '\\' in i.filename for i in infos):
                raise ValueError('Unsafe package member')
            self.data={i.filename:z.read(i) for i in infos}
        try:
            self.model=xml(self.data[MAIN]); self.settings=xml(self.data[SETTINGS])
            self.config=json.loads(self.data[PROCESS])
        except KeyError as exc: raise ValueError('Complete native project members are required') from exc
        if self.model.get('unit','millimeter')!='millimeter': raise ValueError('Millimeter projects are required')
        tags={e.get('name'):e.text for e in self.model.findall(f'{{{CORE}}}metadata')}
        if tags.get('Snapmaker_Orca:3mfVersion')!='1' or not str(tags.get('Application','')).startswith('Snapmaker_Orca'):
            raise ValueError('Save a complete native Snapmaker Orca project first')
        self.resources=self.model.find(f'{{{CORE}}}resources')
        self.build=self.model.find(f'{{{CORE}}}build')
        if self.resources is None or self.build is None: raise ValueError('Native resources/build are required')
        self.plates=self.settings.findall('plate')
        ids=[int(metadata(p).get('plater_id','0')) for p in self.plates]
        if len(set(ids))!=len(ids) or not all(i>0 for i in ids): raise ValueError('Unique positive plate IDs required')

    def plate(self,pid):
        found=[p for p in self.plates if int(metadata(p)['plater_id'])==pid]
        if len(found)!=1: raise ValueError('Unknown plate')
        return found[0]

    def members(self,pid):
        return [metadata(i) for i in self.plate(pid).findall('model_instance')]

    def names(self,pid,ids):
        members={int(m['object_id']) for m in self.members(pid)}
        if not set(ids)<=members: raise ValueError('Selected object IDs must belong to target plate')
        result=[]
        for oid in ids:
            objs=[o for o in self.settings.findall('object') if o.get('id')==str(oid)]
            if len(objs)!=1: raise ValueError('Selected root requires native object settings')
            name=metadata(objs[0]).get('name')
            if not name or name.startswith(SIGNATURE): raise ValueError('Selected root must be a named product object')
            result.append(name)
        return set(result)

    def bed(self):
        try:
            pts=[[float(v) for v in point.split('x')] for point in self.config['printable_area']]
            if len(pts)!=4 or any(len(p)!=2 or not all(math.isfinite(v) for v in p) for p in pts): raise ValueError
            if len({p[0] for p in pts})!=2 or len({p[1] for p in pts})!=2: raise ValueError
            return [min(p[0] for p in pts),min(p[1] for p in pts),max(p[0] for p in pts),max(p[1] for p in pts)]
        except (KeyError,ValueError,TypeError): raise ValueError('A finite rectangular printable_area is required') from None

    def check_materials(self,options):
        types=values(self.config.get('filament_type',[]))
        ds=[float(v) for v in values(self.config.get('filament_diameter',[]))]
        if not 1<=len(types)<=4 or len(ds)!=len(types) or any(not math.isfinite(v) or not 0<v<=4 for v in ds):
            raise ValueError('Explicit one-to-four physical filament types/diameters required')
        if any(t>=len(types) for t in options.tools): raise ValueError('Tool slot is not present in project')
        families={str(types[t]).strip().upper().split()[0] for t in options.tools}
        if not families<={'PLA','PETG'}: raise ValueError('This release supports explicit PLA/PETG slots')
        if any(str(v)!='standard' for v in values(self.config.get('filament_volume_type',['standard']))):
            raise ValueError('Mixed/High Flow recipes need a separate native validation; use physical standard slots')
        fan=values(self.config.get('additional_cooling_fan_speed',[]))
        if len(fan)!=len(types) or any(float(v)!=0 for v in fan): raise ValueError('Auxiliary fan must be explicitly zero in every physical slot')
        return ds

    def native_off(self,pid):
        plate=metadata(self.plate(pid))
        return all(off(plate.get(k,self.config.get(k,'0'))) for k in NATIVE_OFF)

    def signed_record(self):
        if RECEIPT not in self.data: return None
        r=json.loads(self.data[RECEIPT])
        if r.get('owner')!=OWNER or r.get('schema')!=1: raise ValueError('Foreign Burj provenance')
        builds=[i for i in self.build if i.get('objectid')==str(r['tower_object_id'])]
        members=[(int(metadata(plate)['plater_id']),metadata(i)) for plate in self.plates for i in plate.findall('model_instance') if metadata(i).get('object_id')==str(r['tower_object_id'])]
        if len(builds)!=1 or builds[0].get('printable','1')!='1' or len(members)!=1 or members[0][0]!=r['plate'] or members[0][1].get('instance_id')!='0':
            raise ValueError('Burj requires exactly one enabled instance on the bound plate')
        if r.get('tower_geometry_sha256')!=self.geometry_hash(r['tower_object_id'],r['part_ids']):
            raise ValueError('Signed tower changed; do not replace it automatically')
        return r

    def geometry_hash(self,oid,pids):
        nodes=[o for o in self.resources.findall(f'{{{CORE}}}object') if int(o.get('id')) in {oid,*pids}]
        cfg=[o for o in self.settings.findall('object') if o.get('id')==str(oid)]
        if len(nodes)!=1+len(pids) or len(cfg)!=1: raise ValueError('Incomplete signed tower geometry')
        def canonical(n):
            return [n.tag,sorted(n.attrib.items()),(n.text or '').strip(),[canonical(c) for c in n]]
        builds=[i for i in self.build if i.get('objectid')==str(oid)]
        memberships=[i for plate in self.plates for i in plate.findall('model_instance') if metadata(i).get('object_id')==str(oid)]
        return digest(encoded([canonical(n) for n in nodes+cfg+builds+memberships]))

    def external_hash(self,oid,pids):
        """Hash product geometry/painting/transforms plus current process state."""
        owned={oid,*pids};model=copy.deepcopy(self.model);settings=copy.deepcopy(self.settings)
        res=model.find(f'{{{CORE}}}resources');build=model.find(f'{{{CORE}}}build')
        for obj in list(res):
            if obj.get('id','').isdigit() and int(obj.get('id')) in owned:res.remove(obj)
        for item in list(build):
            if int(item.get('objectid'))==oid:build.remove(item)
        for obj in settings.findall('object'):
            if obj.get('id')==str(oid):settings.remove(obj)
        for plate in settings.findall('plate'):
            for inst in plate.findall('model_instance'):
                if metadata(inst).get('object_id')==str(oid):plate.remove(inst)
        def canonical(n):
            return [n.tag,sorted(n.attrib.items()),(n.text or '').strip(),[canonical(c) for c in n]]
        other={k:digest(v) for k,v in self.data.items() if k.startswith('3D/') and k!=MAIN}
        return digest(encoded({'model':canonical(model),'settings':canonical(settings),'config':self.config,'other_geometry':other}))

    def remove_owned(self,pid):
        record=self.signed_record()
        if record is None:
            if any(metadata(o).get('name','').startswith(SIGNATURE) for o in self.settings.findall('object')):
                raise ValueError('Foreign/legacy auxiliary: remove by reviewed explicit ID before preparing')
            return []
        if record['plate']!=pid: raise ValueError('Prepared operation is limited to the signed tower plate')
        oid,pids=record['tower_object_id'],record['part_ids']; owned={oid,*pids}
        for obj in self.resources.findall(f'{{{CORE}}}object'):
            if int(obj.get('id')) not in owned and any(int(c.get('objectid')) in owned for c in obj.iter(f'{{{CORE}}}component')):
                raise ValueError('Signed tower is shared by product geometry')
        for item in list(self.build):
            if int(item.get('objectid'))==oid: self.build.remove(item)
        for obj in list(self.resources):
            if obj.get('id','').isdigit() and int(obj.get('id')) in owned: self.resources.remove(obj)
        for obj in self.settings.findall('object'):
            if obj.get('id')==str(oid): self.settings.remove(obj)
        for plate in self.plates:
            for inst in plate.findall('model_instance'):
                if metadata(inst).get('object_id')==str(oid): plate.remove(inst)
        node=self.plate(pid)
        if all(metadata(node).get(k)==v for k,v in record.get('owned_sequence',{}).items()):
            for k,v in record.get('previous_sequence',{}).items(): md(node,k,v)
        del self.data[RECEIPT]
        return sorted(owned)

    def check_ordinals(self):
        # Inserting the tower first changes importer root ordinals. Refuse an
        # archive rather than silently attach old per-object payloads elsewhere.
        for key in ('Metadata/layer_config_ranges.xml','Metadata/cut_information.xml','Metadata/brim_ear_points.txt'):
            if self.data.get(key,b'').strip(): raise ValueError(f'Explicit ordinal remapping is required for {key}')
        key='Metadata/layer_heights_profile.txt'
        if key in self.data and not self.data[key].startswith(b'layer_heights_profile_format_version=2'):
            raise ValueError('Convert layer-height profiles to native format version 2 first')

    def prepare(self,pid):
        self.plate(pid); self.check_ordinals()
        if len(self.plates)>1 and any(not self.native_off(int(metadata(p)['plater_id'])) for p in self.plates if p is not self.plate(pid)):
            raise ValueError('Native tower globals affect other plates; disable their native tower explicitly first')
        removed=self.remove_owned(pid)
        self.config.update(NATIVE_OFF)
        for k,v in NATIVE_OFF.items(): md(self.plate(pid),k,v)
        return removed

    def publish(self,path):
        path=Path(path)
        if path.resolve()==self.path.resolve() or path.exists(): raise ValueError('Output must be a new path; source is never overwritten')
        data=dict(self.data);data[MAIN]=xmlbytes(self.model);data[SETTINGS]=xmlbytes(self.settings);data[PROCESS]=encoded(self.config)
        # Only derived caches disappear. Original product members remain intact.
        for key in list(data):
            if re.fullmatch(r'Metadata/(?:plate|top|pick)_\d+(?:[_.].*)?\.(?:gcode(?:\.md5)?|json|png|jpe?g|webp)',key,re.I) or key=='Metadata/slice_info.config':
                del data[key]
        # Avoid dangling cache relationships/content-type overrides.
        removed=set(self.data)-set(data)
        for key,blob in list(data.items()):
            if key.endswith('.rels'):
                rels=xml(blob); changed=False
                source=posixpath.join(posixpath.dirname(posixpath.dirname(key)),posixpath.basename(key)[:-5])
                for r in list(rels):
                    target=r.get('Target','')
                    resolved=posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join(posixpath.dirname(source),target))
                    if resolved in removed and r.get('TargetMode')!='External': rels.remove(r);changed=True
                if changed:data[key]=xmlbytes(rels)
        if '[Content_Types].xml' in data:
            root=xml(data['[Content_Types].xml'])
            for e in list(root):
                if e.get('PartName','').lstrip('/') in removed:root.remove(e)
            data['[Content_Types].xml']=xmlbytes(root)
        with path.open('xb') as dest:
            with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
                for key in sorted(data):
                    info=zipfile.ZipInfo(key,date_time=(1980,1,1,0,0,0)); info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o600<<16
                    z.writestr(info,data[key])
        return digest(path.read_bytes())


def placement(result,options,bed):
    outline=profile(options.maximum_width_mm); margin=options.brim_mm+options.clearance_mm+options.line_width_mm/2
    local=[min(x for x,y in outline)-margin,min(y for x,y in outline)-margin,max(x for x,y in outline)+margin,max(y for x,y in outline)+margin]
    occupied=Footprint()
    for phase in result.phases:
        for block in phase.blocks:
            if block.volume_mm3 and not block.footprint.rows: raise ValueError('Missing external deposition occupancy')
            occupied.update(block.footprint)
    def valid(c):
        box=[local[0]+c[0],local[1]+c[1],local[2]+c[0],local[3]+c[1]]
        return box[0]>=bed[0] and box[1]>=bed[1] and box[2]<=bed[2] and box[3]<=bed[3] and not occupied.intersects_box(box)
    if options.center_xy is not None:
        if not valid(options.center_xy): raise ValueError('Tower/brim leaves bed or conflicts with conservative deposition occupancy')
        return list(options.center_xy)
    candidates=[[x,y] for x in range(math.ceil(bed[0]-local[0]),math.floor(bed[2]-local[2])+1,4)
                for y in range(math.ceil(bed[1]-local[1]),math.floor(bed[3]-local[3])+1,4) if valid((x,y))]
    if not candidates: raise ValueError('No clear tower/brim position; approved product positions remain fixed')
    a=occupied.bounds; cx,cy=(a[0]+a[2])/2,(a[1]+a[3])/2
    return min(candidates,key=lambda p:((p[0]-cx)**2+(p[1]-cy)**2,p[0],p[1]))


def add_tower(project,options,result,plan,center,bindings):
    project.check_ordinals()
    if not project.native_off(options.plate): raise ValueError('Prepare and fresh-slice with native tower disabled first')
    if RECEIPT in project.data: raise ValueError('Prepared input still contains a signed tower')
    used={int(e.get(k)) for e in [*project.model.iter(),*project.settings.iter()] for k in ('id','objectid') if e.get(k,'').isdigit()}
    oid=max(used,default=0)+1; token=digest(encoded({'options':options.to_dict(),'plan':plan,'bindings':bindings}))[:32]
    name=SIGNATURE+token
    obj=ET.Element(f'{{{CORE}}}object',id=str(oid),type='model',name=name);comps=ET.SubElement(obj,f'{{{CORE}}}components')
    meta=ET.Element('object',id=str(oid));md(meta,'name',name)
    native={'enable_support':False,'flush_into_objects':True,'flush_into_infill':True,'flush_into_support':False,
            'brim_type':'outer_only','brim_width':options.brim_mm,'brim_object_gap':0,'wall_loops':1,
            'bottom_shell_layers':0,'bottom_shell_thickness':0,'top_shell_layers':0,'top_shell_thickness':0,
            'infill_combination':False,'sparse_infill_pattern':'rectilinear','seam_slope_type':'none','extruder':options.model_tools[0]+1}
    for k in ('outer_wall_line_width','inner_wall_line_width','sparse_infill_line_width','internal_solid_infill_line_width','initial_layer_line_width'):native[k]=options.line_width_mm
    for k in ('outer_wall_speed','inner_wall_speed','sparse_infill_speed','internal_solid_infill_speed','initial_layer_speed','initial_layer_infill_speed','bridge_speed','internal_bridge_speed','gap_infill_speed','small_perimeter_speed'):native[k]=options.speed_mm_s
    for k,v in native.items():md(meta,k,v)
    pids=[]
    for i,((tool,density),(vertices,faces)) in enumerate(sorted(mesh_groups(plan).items()),1):
        pid=oid+i;pids.append(pid)
        part=ET.SubElement(project.resources,f'{{{CORE}}}object',id=str(pid),type='model')
        mesh=ET.SubElement(part,f'{{{CORE}}}mesh');vs=ET.SubElement(mesh,f'{{{CORE}}}vertices');fs=ET.SubElement(mesh,f'{{{CORE}}}triangles')
        for v in vertices:ET.SubElement(vs,f'{{{CORE}}}vertex',dict(zip('xyz',(format(n,'.12g') for n in v))))
        for f in faces:ET.SubElement(fs,f'{{{CORE}}}triangle',dict(zip(('v1','v2','v3'),map(str,f))))
        ET.SubElement(comps,f'{{{CORE}}}component',objectid=str(pid))
        cfg=ET.SubElement(meta,'part',id=str(pid),subtype='normal_part')
        for k,v in {'name':f'Burj T{tool} contour + infill {density}%','extruder':tool+1,'sparse_infill_density':f'{density}%',
                    'wall_loops':1,'top_shell_layers':0,'bottom_shell_layers':0,'top_shell_thickness':0,'bottom_shell_thickness':0}.items():md(cfg,k,v)
    project.resources.insert(0,obj);project.settings.insert(0,meta)
    bed=project.bed();columns=math.ceil(math.sqrt(len(project.plates)));pos=project.plates.index(project.plate(options.plate))
    # Native PartPlate grid: 20% logical gap, rows run towards negative Y.
    origin=((pos%columns)*(bed[2]-bed[0])*1.2,-(pos//columns)*(bed[3]-bed[1])*1.2)
    project.build.insert(0,ET.Element(f'{{{CORE}}}item',objectid=str(oid),printable='1',
        transform='1 0 0 0 1 0 0 0 1 '+format(center[0]+origin[0],'.12g')+' '+format(center[1]+origin[1],'.12g')+' 0'))
    instance=ET.Element('model_instance')
    for k,v in {'object_id':oid,'instance_id':0,'identify_id':oid}.items():md(instance,k,v)
    plate=project.plate(options.plate);plate.insert(len(plate.findall('metadata')),instance)
    previous={k:metadata(plate).get(k) for k in SEQ};flat=[]
    for index,layer in enumerate(result.layers,1):
        tools=[p.tool for p in layer.phases]
        if len(tools)!=len(set(tools)): raise ValueError('Repeated native phase at one Z is not supported')
        order=tools+[t for t in range(4) if t not in tools]
        if index==1:md(plate,SEQ[0],' '.join(str(t+1) for t in order))
        else:flat.extend([index,index,*[t+1 for t in order]])
    md(plate,SEQ[1],' '.join(map(str,flat)));md(plate,SEQ[2],len(result.layers)-1)
    project.config.update(NATIVE_OFF,print_order='as_obj_list',print_sequence='by layer')
    for k,v in NATIVE_OFF.items():md(plate,k,v)
    record={'schema':1,'owner':OWNER,'mode':'deterministic_priming','native_flush_active':False,'native_flush_effective':False,'requested_flush_metadata':{'flush_into_objects':True,'flush_into_infill':True},
            'tower_object_id':oid,'part_ids':pids,'tower_name':name,'plate':options.plate,'center_xy':center,
            'options':options.to_dict(),'plan':plan,'bindings':bindings,'native_slicing_required':True,
            'previous_sequence':previous,'owned_sequence':{k:metadata(plate).get(k) for k in SEQ},
            'physical_cleaning_validated':False}
    record['tower_geometry_sha256']=project.geometry_hash(oid,pids)
    record['external_project_sha256']=project.external_hash(oid,pids)
    project.data[RECEIPT]=encoded(record)
    return record
