"""Stage independent copies with native lateral supports and a connected brim.

Only support_enforcer/support_blocker volumes are generated. No printable
collar, foot, rib, web, raft or sacrificial normal part is created. Existing
owned solid retention cells can be replaced in place with --update-existing.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import io
import json
import math
import tempfile
import uuid
import zipfile
from pathlib import Path
import numpy as np
import trimesh
from lxml import etree as E
from geometry_project import Project, conformal_blocker
from assemblies import separate, encode
from prender3d_core import apply_regions, md, matrix, CORE, PROD, NS, Q

MAIN='3D/3dmodel.model'
CONFIG='Metadata/model_settings.config'
SETTINGS='Metadata/project_settings.config'
PROVENANCE='Metadata/Prender3D.json'


def metadata(element):
    return {m.get('key'):m.get('value') for m in element.findall('metadata')}


def product_signature(main,config,root_id):
    obj=main.find(f"m:resources/m:object[@id='{root_id}']",NS)
    conf=config.find(f"object[@id='{root_id}']")
    if obj is None or conf is None or obj.find('m:components',NS) is None:
        raise ValueError('A configured multipart product root is required')
    own={p.get('id') for p in conf.findall('part')
         if metadata(p).get('name','').startswith('Prender3D |')}
    return tuple((c.get('objectid'),c.get('{'+PROD+'}path'),c.get('transform'))
                 for c in obj.findall('m:components/m:component',NS)
                 if c.get('objectid') not in own)


def regions_for(body,height_mm,profile):
    """Create modifier geometry only, in the measured product's root frame."""
    bed=float(body.bounds[0,2]);top=float(body.bounds[1,2])
    if not math.isfinite(height_mm) or not 0<height_mm<top-bed:
        raise ValueError('Support height must be inside the product height')
    center=body.bounds.mean(axis=0)[:2]
    if profile.get('regions'):
        regions=copy.deepcopy(profile['regions'])
        if any(r.get('subtype') not in {'support_enforcer','support_blocker'} for r in regions):
            raise ValueError('Prender3D accepts native support modifiers only')
    elif profile.get('region_mode','patches')=='envelope':
        radius=float(profile.get('envelope_radius_mm',np.linalg.norm(body.extents[:2])/2+1))
        regions=[dict(role='lateral_enforcer',label='enforcer de apoio lateral',
                      subtype='support_enforcer',shape='cylinder',
                      values=[radius,height_mm,[*center,bed+height_mm/2]])]
    elif profile.get('region_mode','patches')=='patches':
        band=float(profile.get('band_height_mm',min(3,height_mm)))
        radius=float(profile.get('patch_radius_mm',max(body.extents[:2])/2-1))
        radial=float(profile.get('patch_radial_size_mm',4))
        tangential=float(profile.get('patch_tangential_size_mm',2))
        if not 0<band<=height_mm or radius<=0 or radial<=0 or tangential<=0:
            raise ValueError('Invalid lateral modifier dimensions')
        regions=[]
        for i,angle in enumerate(profile.get('angles_deg',[0,90,180,270])):
            angle=float(angle);theta=math.radians(angle)
            point=center+radius*np.array([math.cos(theta),math.sin(theta)])
            regions.append(dict(role=f'lateral_{i+1}',label=f'enforcer lateral {i+1}',
                                subtype='support_enforcer',shape='cube',
                                values=[[radial,tangential,band],
                                        [*point,bed+height_mm-band/2],angle]))
    else:
        raise ValueError('Choose patches, envelope, or explicit native regions')
    if any(r.get('role')=='upper' for r in regions):
        raise ValueError('Upper height blocker is managed by this helper')
    blocker_height=min(float(profile.get('upper_blocker_height_mm',3)),top-bed-height_mm+2)
    if not math.isfinite(blocker_height) or blocker_height<=0:
        raise ValueError('Upper blocker band must have a positive finite height')
    if 'upper_blocker_xy_size_mm' in profile:
        raise ValueError('Legacy rectangular upper blocker needs a measured contour; remove upper_blocker_xy_size_mm and review the contour/clearance')
    blocker_shape,blocker_measurement=conformal_blocker(
        body,bed+height_mm,bed+height_mm+blocker_height,
        margin_mm=profile.get('upper_blocker_margin_mm',.6),
        shape=profile.get('upper_blocker_shape','auto'))
    regions.append(dict(role='upper',label=f'blocker faixa acima de {height_mm:g} mm',
                        subtype='support_blocker',**blocker_shape))
    return regions,{'bed_z_local':bed,'top_z_local':top,
                    'upper_blocker_contour':blocker_measurement}


def existing_grid(main,config,provenance,source_root_id):
    """Recover ownership from provenance, or native names after a slicer save."""
    records=provenance.get('roots',{})
    roots=[int(rid) for rid,record in records.items()
           if record.get('owner')=='Prender3D'
           and record.get('profile',{}).get('grid_source_root_id')==source_root_id]
    signature=product_signature(main,config,source_root_id)
    signed=[]
    for conf in config.findall('object'):
        if any(metadata(p).get('name','').startswith('Prender3D |') for p in conf.findall('part')):
            if product_signature(main,config,conf.get('id'))==signature:
                signed.append(int(conf.get('id')))
    if roots and set(roots)!=set(signed):
        raise ValueError('Grid provenance and native ownership disagree')
    return sorted(roots or signed)


def new_grid(data,root_id,count,pitch,body,label,orientation_label):
    main=E.fromstring(data[MAIN]);config=E.fromstring(data[CONFIG])
    settings=json.loads(data[SETTINGS]);oldplates=config.findall('plate')
    oldcount=len(oldplates);newcount=oldcount+1
    columns=math.ceil(math.sqrt(newcount))
    if newcount>36 or math.ceil(math.sqrt(oldcount))!=columns:
        raise ValueError('New plate changes native grid; adapt all placements explicitly')
    area=np.array([list(map(float,p.split('x'))) for p in settings['printable_area']])
    lo=area.min(axis=0);hi=area.max(axis=0);dims=hi-lo;center=(lo+hi)/2
    origin=np.array([(oldcount%columns)*dims[0]*1.2,-(oldcount//columns)*dims[1]*1.2])
    nx=math.ceil(math.sqrt(count));ny=math.ceil(count/nx)
    positions=[center+[(i%nx-(nx-1)/2)*pitch,(i//nx-(ny-1)/2)*pitch] for i in range(count)]
    if any(np.any(pos-pitch/2-7<lo) or np.any(pos+pitch/2+7>hi) for pos in positions):
        raise ValueError('Products and brim do not fit the plate')
    plate=E.SubElement(config,'plate')
    for item in oldplates[0].findall('metadata'):
        if item.get('key') in {'filament_maps','filament_map_mode','bed_type'}:
            plate.append(copy.deepcopy(item))
    for key,value in [('plater_id',newcount),('plater_name',f'{count} {label}s - Prender3D suporte nativo - {orientation_label}'),('locked','false'),('print_sequence','by layer')]:
        md(plate,key,value)
    original=main.find(f"m:resources/m:object[@id='{root_id}']",NS)
    original_config=config.find(f"object[@id='{root_id}']")
    used={int(o.get('id')) for o in main.findall('m:resources/m:object',NS)}
    used|={int(p.get('id')) for p in config.findall('object/part')}
    rid=max(used)+1
    obj=copy.deepcopy(original);obj.set('id',str(rid));obj.set('{'+PROD+'}UUID',str(uuid.uuid4()))
    for component in obj.findall('m:components/m:component',NS):
        component.set('{'+PROD+'}UUID',str(uuid.uuid4()))
    main.find('m:resources',NS).append(obj)
    conf=copy.deepcopy(original_config);conf.set('id',str(rid));md(conf,'name',label)
    config.insert(list(config).index(original_config)+1,conf)
    transform=np.eye(4);transform[:2,3]=positions[0]+origin;transform[2,3]=-body.bounds[0,2]
    E.SubElement(main.find('m:build',NS),Q('item'),objectid=str(rid),transform=encode(transform),printable='1',attrib={'{'+PROD+'}UUID':str(uuid.uuid4())})
    instance=E.SubElement(plate,'model_instance')
    identify=max([int(m.get('value','0')) for m in config.findall("plate/model_instance/metadata[@key='identify_id']")]+[0])+1
    for key,value in [('object_id',rid),('instance_id',0),('identify_id',identify)]:md(instance,key,value)
    for key,value in [('wipe_tower_x',hi[0]-60),('wipe_tower_y',hi[1]-60)]:
        values=list(settings[key])
        if len(values)!=oldcount:raise ValueError('Unresolved native tower positions')
        settings[key]=values+[format(value,'g')]
    data[MAIN]=E.tostring(main,encoding='UTF-8',xml_declaration=True)
    data[CONFIG]=E.tostring(config,encoding='UTF-8',xml_declaration=True)
    data[SETTINGS]=(json.dumps(settings,ensure_ascii=False,indent=2)+'\n').encode()
    assembly=separate(data,rid,target_count=count,positions=[(p+origin).tolist() for p in positions])
    return assembly['root_ids'],newcount


def prepare(source,output,expected,root_id,*,count=9,min_gap_ratio=.1,height_mm=10.,
            process_overrides=None,label='peça',orientation_label='orientação original',
            retention_extruder=None,native_profile=None,update_existing=False,
            reflow=False,pitch_mm=None):
    source=Path(source).resolve();output=Path(output).resolve();root_id=int(root_id)
    if output==source or output.exists() or not any(output.is_relative_to(p) for p in [Path('/tmp').resolve(),Path(tempfile.gettempdir()).resolve()]):
        raise ValueError('A new scratch output is required')
    if not isinstance(count,int) or isinstance(count,bool) or not 1<=count<=64:
        raise ValueError('Choose an explicit supported copy count')
    if not math.isfinite(min_gap_ratio) or min_gap_ratio<.1:
        raise ValueError('Review smaller spacing explicitly before using this grid adapter')
    if not isinstance(update_existing,bool) or not isinstance(reflow,bool):
        raise ValueError('Grid update/reflow options must be explicit booleans')
    if not process_overrides:raise ValueError('Explicit reviewed object process is required')
    if any('gcode' in key.lower() or key in {'post_process','printer_settings_id','filament_settings_id','extruder'} for key in process_overrides):
        raise ValueError('Process cannot replace machine/material integration')
    raw=source.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if sha!=expected:raise ValueError('Source hash changed')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if len(archive.namelist())!=len(set(archive.namelist())):raise ValueError('Duplicate ZIP members')
        data={name:archive.read(name) for name in archive.namelist()}
    original_data=dict(data);main=E.fromstring(data[MAIN]);config=E.fromstring(data[CONFIG])
    provenance=json.loads(data.get(PROVENANCE,b'{"schema":1,"roots":{}}'))
    targets=existing_grid(main,config,provenance,root_id)
    if targets and not update_existing:raise ValueError('Grid exists; use --update-existing for its owned auxiliary regions')
    if update_existing and not targets:raise ValueError('No owned grid matches this source')
    source_config=config.find(f"object[@id='{root_id}']")
    if any(metadata(p).get('name','').startswith('Prender3D |') for p in source_config.findall('part')):
        raise ValueError('Select the original product root, separate from its retained copies')
    if any(p.get('subtype')=='negative_part' for p in source_config.findall('part')) and not (native_profile or {}).get('regions'):
        raise ValueError('Functional negatives require reviewed explicit blocker regions')
    project=Project(source)
    if project.unit!='millimeter':raise ValueError('Explicit unit adaptation is required')
    body=trimesh.util.concatenate([mesh for mesh,identity in project.components(root_id)])
    minimum_pitch=float(max(body.extents[:2])*(1+min_gap_ratio))
    requested_pitch=minimum_pitch if pitch_mm is None else float(pitch_mm)
    if not math.isfinite(requested_pitch) or requested_pitch<minimum_pitch-1e-7:
        raise ValueError('Pitch violates the requested minimum product spacing')
    painted=any(t.get('paint_color') not in (None,'') for path,oid in project.meshes for t in project.doc(path)[1][oid].findall('m:mesh/m:triangles/m:triangle',NS))
    if painted and retention_extruder is None:raise ValueError('Resolve the effective painted support material explicitly')
    settings=json.loads(data[SETTINGS]);slots=len(settings['filament_colour'])
    selected=retention_extruder if retention_extruder is not None else int(metadata(source_config).get('extruder','1'))
    if isinstance(selected,bool) or not isinstance(selected,int) or not 1<=selected<=slots:
        raise ValueError('Support must use an existing logical filament slot')
    native_profile=copy.deepcopy(native_profile or {})
    regions,frame=regions_for(body,float(height_mm),native_profile)
    process=copy.deepcopy(process_overrides)
    process.update(native_profile.get('process',{}))
    process.update(enable_support='1',support_filament=str(selected),support_interface_filament=str(selected),raft_layers='0')
    if any('gcode' in key.lower() or key in {'post_process','printer_settings_id','filament_settings_id','extruder'} for key in process):
        raise ValueError('Native support process cannot replace machine/material integration')
    if process.get('support_type') not in {'tree(manual)','normal(manual)'}:
        raise ValueError('An explicit native manual support process is required')
    if float(process.get('brim_width','0'))<=0 or process.get('brim_type')=='no_brim':
        raise ValueError('This grid requires a connected native brim')
    if targets:
        if len(targets)!=count:raise ValueError('Existing grid count differs; adapt explicitly')
        memberships=[]
        for rid in targets:
            if len(main.findall(f"m:build/m:item[@objectid='{rid}']",NS))!=1:raise ValueError('Each retained copy needs an independent root')
            members=[int(metadata(p)['plater_id']) for p in config.findall('plate') for inst in p.findall('model_instance') if metadata(inst).get('object_id')==str(rid)]
            if len(members)!=1:raise ValueError('Ambiguous grid plate membership')
            memberships.extend(members)
        if len(set(memberships))!=1:raise ValueError('Owned grid spans multiple plates')
        plate_id=memberships[0]
    else:
        if reflow:raise ValueError('Reflow applies only to an existing owned grid')
        targets,plate_id=new_grid(data,root_id,count,requested_pitch,body,label,orientation_label)
    layout_changes=[]
    current_main=E.fromstring(data[MAIN])
    build_items=[current_main.find(f"m:build/m:item[@objectid='{rid}']",NS) for rid in targets]
    positions=np.array([matrix(item.get('transform'))[:2,3] for item in build_items])
    if reflow:
        center=positions.mean(axis=0);nx=math.ceil(math.sqrt(count));ny=math.ceil(count/nx)
        offsets=np.array([[(i%nx-(nx-1)/2)*requested_pitch,(i//nx-(ny-1)/2)*requested_pitch] for i in range(count)])
        proposed=center+offsets-offsets.mean(axis=0)
        area=np.array([list(map(float,p.split('x'))) for p in settings['printable_area']])
        lo=area.min(axis=0);hi=area.max(axis=0);dims=hi-lo
        columns=math.ceil(math.sqrt(len(config.findall('plate'))))
        origin=np.array([((plate_id-1)%columns)*dims[0]*1.2,-((plate_id-1)//columns)*dims[1]*1.2])
        margin=body.extents[:2]/2+float(process['brim_width'])+3
        if any(np.any(point-origin-margin<lo) or np.any(point-origin+margin>hi) for point in proposed):
            raise ValueError('Reflowed products/brim exceed the printable area')
        for rid,item,before,after in zip(targets,build_items,positions,proposed):
            transform=matrix(item.get('transform'));transform[:2,3]=after;item.set('transform',encode(transform))
            layout_changes.append({'root_id':rid,'before_xy_mm':before.tolist(),'after_xy_mm':after.tolist()})
        positions=proposed
        data[MAIN]=E.tostring(current_main,encoding='UTF-8',xml_declaration=True)
    actual_pitch=float(min(np.linalg.norm(a-b) for i,a in enumerate(positions) for b in positions[i+1:])) if count>1 else requested_pitch
    if pitch_mm is not None and targets and not reflow and abs(actual_pitch-requested_pitch)>1e-5:
        raise ValueError('Changing existing grid pitch requires --reflow')
    if actual_pitch<minimum_pitch-1e-5:raise ValueError('Existing grid violates requested product spacing')
    original_target_signature=product_signature(main,config,root_id)
    before_owned_paths=set()
    for rid in targets:
        old=main.find(f"m:resources/m:object[@id='{rid}']",NS)
        conf=config.find(f"object[@id='{rid}']")
        if old is not None:
            own={p.get('id') for p in conf.findall('part') if metadata(p).get('name','').startswith('Prender3D |')}
            before_owned_paths|={c.get('{'+PROD+'}path','').lstrip('/') for c in old.findall('m:components/m:component',NS) if c.get('objectid') in own}
    reports=[]
    for index,rid in enumerate(targets):
        current=E.fromstring(data[CONFIG]);obj=current.find(f"object[@id='{rid}']")
        md(obj,'name',f'{label} {index+1:02d} - Prender3D')
        data[CONFIG]=E.tostring(current,encoding='UTF-8',xml_declaration=True)
        old_profile=provenance.get('roots',{}).get(str(rid),{}).get('profile',{})
        profile={**old_profile,'kind':'native_lateral_support','purpose':'lateral vibration bracing, not load-bearing','grid_source_root_id':root_id,'grid_plate':plate_id,'grid_count':count,'grid_index':index,'orientation':orientation_label,'height_mm':float(height_mm),'support_extruder':selected,'native_support_profile':native_profile,'preserve_process_keys':list(process),'object_process':process,'no_printable_retention_geometry':True}
        profile.update(pitch_mm=actual_pitch,gap_mm=actual_pitch-float(max(body.extents[:2])),gap_ratio=actual_pitch/float(max(body.extents[:2]))-1,minimum_gap_ratio_requested=min_gap_ratio)
        profile['upper_blocker_contour']=frame['upper_blocker_contour']
        for stale in ['collar','retention_extruder','web_height_mm']:profile.pop(stale,None)
        reports.append(apply_regions(data,rid,frame,regions,process,owner='Prender3D',height_limit_mm=float(height_mm),profile=profile))
    final_main=E.fromstring(data[MAIN]);final_config=E.fromstring(data[CONFIG])
    for rid in targets:
        if product_signature(final_main,final_config,rid)!=original_target_signature:raise AssertionError('Product component references changed')
        obj=final_config.find(f"object[@id='{rid}']")
        owned=[p for p in obj.findall('part') if metadata(p).get('name','').startswith('Prender3D |')]
        if any(p.get('subtype') not in {'support_enforcer','support_blocker'} for p in owned):raise AssertionError('Printable auxiliary geometry is forbidden')
    for name,payload in original_data.items():
        if name.startswith('3D/Objects/') and name not in before_owned_paths and data.get(name)!=payload:
            raise AssertionError('Existing product mesh/paint resource changed')
    if hashlib.sha256(source.read_bytes()).hexdigest()!=expected:raise ValueError('Source changed during staging')
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for name,payload in data.items():archive.writestr(name,payload)
    return {'source_sha256':sha,'output_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
            'plate':plate_id,'source_root_id':root_id,'root_ids':targets,'count':count,
            'updated_existing':bool(update_existing),'native_support_only':True,
            'positive_retention_parts':0,'height_limit_mm':float(height_mm),
            'pitch_mm':actual_pitch,'minimum_product_gap_mm':actual_pitch-float(max(body.extents[:2])),
            'layout_changes':layout_changes,
            'anchors':reports,'native_slicing_required':True,'physical_validation':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--expect-sha256',required=True);parser.add_argument('--root-id',required=True,type=int)
    parser.add_argument('--process-json',required=True,type=Path);parser.add_argument('--native-profile-json',required=True,type=Path)
    parser.add_argument('--count',type=int,default=9);parser.add_argument('--height-mm',type=float,default=10)
    parser.add_argument('--gap-ratio',type=float,default=.1);parser.add_argument('--label',default='peça')
    parser.add_argument('--orientation-label',default='orientação original')
    parser.add_argument('--support-extruder','--retention-extruder',dest='retention_extruder',type=int)
    parser.add_argument('--update-existing',action='store_true');parser.add_argument('--report',type=Path)
    parser.add_argument('--reflow',action='store_true',help='Explicitly reposition only the owned grid, retaining its center, scale and orientation')
    parser.add_argument('--pitch-mm',type=float,help='Reviewed center spacing; must meet --gap-ratio minimum')
    args=parser.parse_args()
    result=prepare(args.source,args.output,args.expect_sha256,args.root_id,count=args.count,min_gap_ratio=args.gap_ratio,
                   height_mm=args.height_mm,process_overrides=json.loads(args.process_json.read_text()),
                   native_profile=json.loads(args.native_profile_json.read_text()),label=args.label,
                   orientation_label=args.orientation_label,retention_extruder=args.retention_extruder,update_existing=args.update_existing,
                   reflow=args.reflow,pitch_mm=args.pitch_mm)
    if args.report:
        with args.report.open('x') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='anchors'},indent=2))
