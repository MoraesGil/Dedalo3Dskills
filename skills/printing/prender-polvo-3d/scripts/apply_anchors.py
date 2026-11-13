"""Octopus specialization of generic Prender3D: protected arms and radial contacts."""
from __future__ import annotations
import math,uuid
import numpy as np
from lxml import etree as E

CORE='http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
PROD='http://schemas.microsoft.com/3dmanufacturing/production/2015/06'
NS={'m':CORE};Q=lambda s:'{'+CORE+'}'+s
IDENTITY='1 0 0 0 1 0 0 0 1 0 0 0'
DEFAULTS={'enable_support':'1','support_type':'tree(manual)','support_style':'tree_slim','support_on_build_plate_only':'1','support_top_z_distance':'0','support_bottom_z_distance':'0.16','support_object_xy_distance':'0','support_object_first_layer_gap':'0.6','tree_support_branch_diameter':'3','tree_support_branch_diameter_organic':'3','tree_support_tip_diameter':'1.2','tree_support_branch_diameter_angle':'0','tree_support_auto_brim':'0','tree_support_brim_width':'0','tree_support_branch_angle':'25','tree_support_wall_count':'2','raft_first_layer_expansion':'0','brim_type':'no_brim','brim_width':'0'}

from pathlib import Path
import importlib.util
_corepath=Path(__file__).resolve().parents[2]/'prender-3d/scripts/prender3d_core.py'
_spec=importlib.util.spec_from_file_location('prender3d_parent',_corepath);_parent=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_parent)
md,matrix,mesh,cube,cylinder=_parent.md,_parent.matrix,_parent.mesh,_parent.cube,_parent.cylinder


def _target_radii(data,root_id,frame,height,angles):
    import sys,trimesh
    from shapely.geometry import LineString
    from shapely.ops import polygonize,unary_union
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'prender-3d/scripts'))
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    from geometry_project import Project
    from detect_octopus import _detect
    project=Project.from_members(data);components=project.components(root_id);result={'matches_octopus':False};_detect(components,result)
    if not result['matches_octopus']:raise ValueError('Half-body profile needs confirmed geometry')
    arms={(tuple(s['component_path_ids']),s['connected_component_index'])for arm in result['arms']for s in arm['segments']}
    fixed=trimesh.util.concatenate([m for m,i in components if (tuple(i['component_path_ids']),i['connected_component_index'])not in arms])
    seg=trimesh.intersections.mesh_plane(fixed,[0,0,1],[0,0,frame['bed_z_local']+height-.2]);outline=unary_union(list(polygonize([LineString(np.round(a[:,:2],6))for a in seg])))
    center=np.asarray(frame['center_xy']);radii=[]
    for a in angles:
        v=np.array([math.cos(math.radians(a)),math.sin(math.radians(a))]);hit=outline.intersection(LineString([center,center+v*100*frame['xy_scale']]))
        pieces=list(hit.geoms)if hasattr(hit,'geoms')else[hit];coords=[c for p in pieces if hasattr(p,'coords')for c in p.coords]
        if not coords:raise ValueError('Requested contact sector misses fixed body')
        radii.append(max(float(np.linalg.norm(np.asarray(c)-center))for c in coords)+.4)
    moving_top=max(float(m.bounds[1,2])for m,i in components if (tuple(i['component_path_ids']),i['connected_component_index'])in arms)
    return radii,moving_top


def _upper_blocker(data,root_id,frame,height):
    """Cover the fixed-body contact band, leaving tentacles to their guards."""
    import sys,trimesh
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'prender-3d/scripts'))
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    from geometry_project import Project,conformal_blocker
    from detect_octopus import _detect
    components=Project.from_members(data).components(root_id)
    detection={'matches_octopus':False};_detect(components,detection)
    if not detection['matches_octopus']:raise ValueError('Contour blocker requires a geometrically confirmed octopus')
    arms={(tuple(s['component_path_ids']),s['connected_component_index'])for arm in detection['arms']for s in arm['segments']}
    fixed=trimesh.util.concatenate([m for m,i in components if (tuple(i['component_path_ids']),i['connected_component_index'])not in arms])
    lower=float(frame['bed_z_local'])+height;upper=lower+3.
    slab=fixed.slice_plane([0,0,lower],[0,0,1],cap=False)
    slab=slab.slice_plane([0,0,upper],[0,0,-1],cap=False)
    if not len(slab.vertices):raise ValueError('Fixed body does not cross the upper blocker band')
    descriptor,measurement=conformal_blocker(slab,lower,upper,margin_mm=.6,
                                           center_xy=frame['center_xy'],shape='cylinder',segments=128)
    measurement['basis']='fixed_positive_body_in_blocker_z_band_excluding_articulated_arms'
    return descriptor,measurement

def apply(data,root_id,frame,*,first_layer_gap=0.6,height_limit_mm=None,height_ratio=0.5):
    """Modify the dict of ZIP members, preserving all original normal mesh bytes.

    frame is geometrically verified in the object's own upright millimetre frame.
    A caller must independently gate open files and bind the source hash.
    """
    cx,cy=map(float,frame['center_xy']);bed=float(frame['bed_z_local']);top=float(frame['top_z_local']);scale=float(frame['xy_scale'])
    # The themed head top is not automatically the user's retention-body top.
    # The 3 mm common-base profile is a reference, not half of an arbitrary head.
    body_top=frame.get('retention_body_top_z_local')
    if height_limit_mm is not None:
        height=float(height_limit_mm);height_policy='explicit'
    elif body_top is not None:
        if not bed<float(body_top)<=top:raise ValueError('Retention body region must be inside the model height')
        height=(float(body_top)-bed)*height_ratio;height_policy='half_confirmed_body_region'
    else:
        height=3.;height_policy='reference_common_base_3mm'
    if not 0<height<top-bed:raise ValueError('Coverage must be inside the fixed body height')
    legacy=abs(height-3)<1e-7
    if not .85<=scale<=1.15:raise ValueError('Octopus size requires a fresh support design')
    directions=sorted(float(x)%360 for x in frame['arm_angles_deg'])
    if len(directions)!=8:raise ValueError('Eight verified tentacles required')
    root=E.fromstring(data['3D/3dmodel.model']);cfg=E.fromstring(data['Metadata/model_settings.config'])
    obj=root.find(f"m:resources/m:object[@id='{root_id}']",NS);ocfg=cfg.find(f"object[@id='{root_id}']")
    if obj is None or ocfg is None:raise ValueError('Verified root missing')
    builds=root.findall(f"m:build/m:item[@objectid='{root_id}']",NS)
    for item in builds:
        b=matrix(item.get('transform'))
        if not np.allclose(b[2,:3],[0,0,1],atol=1e-6) or not np.allclose(b[:2,2],0,atol=1e-6) or not np.allclose(b[:3,:3].T@b[:3,:3],np.eye(3),atol=1e-6) or abs(b[2,3]+bed)>1e-4:
            raise ValueError('Build must be upright with its normal geometry on the plate')
    components=obj.find('m:components',NS)
    if components is None:raise ValueError('Direct-mesh roots require a compatible component wrapper; preserve IDs and paint explicitly')
    oldcomponents={int(c.get('objectid')):c for c in components}
    owned=[p for p in ocfg.findall('part') if p.find("metadata[@key='name']") is not None and p.find("metadata[@key='name']").get('value','').startswith('prenderPolvo3D |')]
    existing={};fallback=[]
    for p in owned:
        name=p.find("metadata[@key='name']").get('value');pid=int(p.get('id'))
        marker=p.find("metadata[@key='Prender3D_role']")
        role=marker.get('value')if marker is not None else None
        if role in {'upper','internal',*[f'guard{i}'for i in range(1,9)],*[f'gap{i}'for i in range(1,9)]}:
            if role in existing:raise ValueError('Duplicate owned support role requires explicit reconciliation')
            existing[role]=pid
        elif 'mini blocker tentáculo ' in name:existing['guard'+name.rsplit(' ',1)[1]]=pid
        elif 'blocker acima' in name or 'blocker compacto' in name:existing['upper']=pid
        elif 'enforcer' in name:
            c=oldcomponents[pid];path=c.get('{'+PROD+'}path','/3D/3dmodel.model').lstrip('/')
            doc=E.fromstring(data[path]);verts=doc.find(f"m:resources/m:object[@id='{pid}']/m:mesh/m:vertices",NS)
            v=np.array([[float(v.get(k)) for k in 'xyz'] for v in verts]);M=matrix(c.get('transform'));v=v@M[:3,:3].T+M[:3,3];center=(v.min(0)+v.max(0))/2
            delta=center[:2]-[cx,cy]
            if np.linalg.norm(delta)<1:existing['internal']=pid
            else:
                angle=math.degrees(math.atan2(delta[1],delta[0]))%360
                fallback.append((angle,pid))
    gapangles=[(directions[0]-22.5+k*45)%360 for k in range(8)]
    for angle,pid in fallback:
        j=int(np.argmin([abs((angle-a+180)%360-180) for a in gapangles]));role='gap'+str(j+1)
        if role in existing:raise ValueError('Duplicate owned lateral enforcers require explicit reconciliation')
        existing[role]=pid
    regions=[]
    def add(role,label,subtype,shape,values):
        regions.append({'role':role,'label':label,'subtype':subtype,'shape':shape.__name__,'values':list(values)})
        return role
    band=min(3.,height)
    inner=add('internal','enforcer interior Z=3 mm','support_enforcer',cylinder,(10.4*scale,min(3.,height),[cx,cy,bed+min(3.,height)/2]))
    upper_shape,upper_measurement=_upper_blocker(data,root_id,frame,height)
    upper='upper'
    regions.append(dict(role=upper,label=f'blocker compacto circular Z={height:g}..{height+3:g} mm',
                        subtype='support_blocker',**upper_shape))
    gaps=[];guards=[]
    if legacy:
        radii=[16.5*scale]*8;guard_height=3.2
    else:
        radii,moving_top=_target_radii(data,root_id,frame,height,gapangles)
        guard_height=min(height+.2,moving_top-bed+.25)
    for i,(a,r)in enumerate(zip(gapangles,radii)):
        t=math.radians(a)
        gaps.append(add('gap'+str(i+1),f'enforcer faixa Z={band:g} mm | vão {i+1}','support_enforcer',cube,([7*scale,1.6*scale,band],[cx+r*math.cos(t),cy+r*math.sin(t),bed+height-band/2],a)))
    for i,a in enumerate(directions):
        t=math.radians(a);r=(22 if legacy else 37)*scale
        guards.append(add('guard'+str(i+1),f'mini blocker tentáculo {i+1}','support_blocker',cube,([(16 if legacy else 50)*scale,(8 if legacy else 12)*scale,guard_height],[cx+r*math.cos(t),cy+r*math.sin(t),bed+guard_height/2],a)))
    settings=dict(DEFAULTS);settings['support_object_first_layer_gap']=f'{first_layer_gap:g}'
    profile={'kind':'octopus','coverage_height_mm':height,'height_policy':height_policy,'retention_body_top_z_local':body_top,'height_ratio':height_ratio if body_top is not None and height_limit_mm is None else None,'contact_enforcer_thickness_mm':band,'internal_low_pad_height_mm':min(3.,height),'legacy_3mm':legacy,'arm_count':8,'upper_blocker':upper_measurement,'validation_status':'reference_profile_requires_fresh_native_audit'if legacy else'candidate_requires_geometry_adapter_and_native_audit'}
    result=_parent.apply_regions(data,root_id,frame,regions,settings,owner='prenderPolvo3D',existing_roles=existing,height_limit_mm=height,profile=profile)
    ids=result['generated_ids']
    return {**result,'instances':len(builds),'production_plates':result['affected_plates'],'frame':frame,'internal_enforcer_id':ids[inner],'lateral_enforcer_ids':[ids[r]for r in gaps],'upper_blocker_id':ids[upper],'mini_blocker_ids':[ids[r]for r in guards],'enforcer_height_mm':band,'coverage_height_mm':height,'modified_product_meshes':False,'native_slicing_and_footprint_validation_required':True}

def main():
    import argparse,hashlib,importlib.util,io,json,tempfile,zipfile
    from pathlib import Path
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--expect-sha256',required=True);p.add_argument('--report',type=Path);p.add_argument('--height-mm',type=float);p.add_argument('--body-height-mm',type=float,help='Measured retention-body region from bed; never infer this from themed head height');p.add_argument('--height-ratio',type=float,default=.5);args=p.parse_args()
    if args.height_mm is not None and args.body_height_mm is not None:raise ValueError('Select explicit coverage or measured body height, not both')
    source=args.source.resolve();output=args.output.resolve()
    if output==source or output.exists() or not any(output.is_relative_to(t) for t in [Path('/tmp').resolve(),Path(tempfile.gettempdir()).resolve()]):raise ValueError('A new temporary staging output is required')
    raw=source.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if sha!=args.expect_sha256:raise ValueError('Source hash changed')
    here=Path(__file__).resolve().parent;detector_path=here/'detect_octopus.py'
    if not detector_path.exists():detector_path=here/'geometry/detect_octopus.py'
    spec=importlib.util.spec_from_file_location('octopus_detector',detector_path);detector=importlib.util.module_from_spec(spec);spec.loader.exec_module(detector)
    detection=detector.inspect_project(source)
    if detection['source_sha256']!=sha:raise ValueError('Source changed during inspection')
    candidates=[r for r in detection['roots'] if r['matches_octopus']]
    if not candidates:raise ValueError('PrenderPolvo3D requires the supported articulated pattern; use Prender3D explicit regions for other geometry')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:data={n:z.read(n) for n in z.namelist()}
    reports=[]
    for root in candidates:
        frame={k:root[k]for k in ['center_xy','bed_z_local','top_z_local','arm_angles_deg','xy_scale']}
        if args.body_height_mm is not None:frame['retention_body_top_z_local']=frame['bed_z_local']+args.body_height_mm
        reports.append(apply(data,root['root_id'],frame,height_limit_mm=args.height_mm,height_ratio=args.height_ratio))
    if hashlib.sha256(source.read_bytes()).hexdigest()!=sha:raise ValueError('Original changed; renew source')
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,blob in data.items():z.writestr(name,blob)
    result={'source_sha256':sha,'output_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'anchors':reports,'native_slicing_required':True,'physical_validation':False}
    if args.report:
        with args.report.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='anchors'},indent=2))

if __name__=='__main__':main()
