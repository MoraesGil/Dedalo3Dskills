#!/usr/bin/env python3
"""Read-only geometric detector for articulated eight-arm 3MF heads.

API: inspect_project(path) -> project JSON data; analyze(path, root_id) -> root.
CLI: python detect_octopus.py input.3mf [--root-id 57] [--compact]
Only numpy, trimesh and lxml are external dependencies. No mesh export, source
mutation, metadata names, source paths, credentials or personal fields in output.
Positive detection requires exactly eight radial chains, each with >=4 distinct
low-bed solids, consistent radial rings and a central body. This recognizes a
geometry pattern; it does not establish support clearance or physical movement.
Explicit Skull/Skeleton filenames or root names route common-only before meshes
are loaded. All other positive decisions are geometric. Coordinates are root-local
millimeters; build transforms and IDs are reported separately, without changes.
"""
import argparse
import hashlib
import io
import itertools
import json
import math
import pathlib
import posixpath
import re
import sys
import urllib.parse
import zipfile

import numpy as np
import trimesh
from lxml import etree as E

CORE='http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
PROD='{http://schemas.microsoft.com/3dmanufacturing/production/2015/06}'
NS={'m':CORE}
MAIN='3D/3dmodel.model'
NORMAL={'normal_part','model',''}
REFERENCE_RINGS=np.array([22.001130785,30.717479992,38.730666246,45.878208495,52.469198375])
MAX_FACES=5_000_000
MAX_COMPONENTS=2048

# Common geometry reader is inherited from the generic Prender3D skill.
import importlib.util
_basepath=pathlib.Path(__file__).resolve().parents[2]/'prender-3d/scripts/geometry_project.py'
_spec=importlib.util.spec_from_file_location('prender3d_geometry',_basepath)
_geometry=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_geometry)
GeometryError=_geometry.GeometryError
_matrix=_geometry._matrix
_metadata=_geometry._metadata

def _exempt(value):return bool(re.search(r'skull|skeleton',value,re.I))

class _Project(_geometry.Project):
    def __init__(self,path):
        super().__init__(path)
        self.filename_exempt=_exempt(pathlib.Path(path).stem)


def _summary(mesh,identity):
    bounds=mesh.bounds;center=mesh.center_mass if mesh.is_watertight and mesh.is_winding_consistent and abs(mesh.volume)>1e-10 else mesh.centroid
    if not np.isfinite(center).all():center=bounds.mean(0)
    return {**identity,'bounds':bounds,'center':center,'height':float(mesh.extents[2]),'volume':abs(float(mesh.volume)),'watertight':bool(mesh.is_watertight)}


def _rings(radii,tolerance):
    order=np.argsort(radii);groups=[]
    for i in order:
        if not groups or radii[i]-radii[groups[-1][-1]]>tolerance:groups.append([int(i)])
        else:groups[-1].append(int(i))
    labels=np.empty(len(radii),int)
    for k,group in enumerate(groups):labels[group]=k
    return labels,groups


def _fit_center(points,center,labels,ring_count):
    radii=np.linalg.norm(points-center,axis=1);state=np.r_[center,[radii[labels==k].mean()for k in range(ring_count)]]
    for _ in range(12):
        delta=points-state[:2];r=np.maximum(np.linalg.norm(delta,axis=1),1e-12);residual=r-state[2:][labels]
        jac=np.zeros((len(points),2+ring_count));jac[:,:2]=-delta/r[:,None];jac[np.arange(len(points)),labels+2]=-1
        step=np.linalg.lstsq(jac,-residual,rcond=None)[0];state+=step
        if np.linalg.norm(step)<1e-9:break
    return state[:2],state[2:],residual


def _template_scale(rings):
    """Nominal XY scale versus the five-ring articulated reference."""
    rings=np.sort(rings)
    if 4<=len(rings)<=5:
        best=None
        for indices in itertools.combinations(range(5),len(rings)):
            ref=REFERENCE_RINGS[list(indices)];scale=float(np.dot(ref,rings)/np.dot(ref,ref));error=float(np.linalg.norm(rings-scale*ref)/np.linalg.norm(rings))
            if best is None or error<best[0]:best=(error,scale)
        return best[1],best[0]
    return float(rings[-1]/REFERENCE_RINGS[-1]),None


def _detect(components,result):
    if not components:result['reasons']=['no_normal_geometry'];return
    records=[_summary(mesh,identity)for mesh,identity in components]
    bounds=np.array([np.min([r['bounds'][0]for r in records],axis=0),np.max([r['bounds'][1]for r in records],axis=0)])
    bed=float(bounds[0,2]);span=float(max(bounds[1,:2]-bounds[0,:2]));tol=max(.02,.001*span)
    result.update(bed_z_local=bed,top_z_local=float(bounds[1,2]),bounds_root_mm=bounds.tolist(),connected_component_count=len(records))
    if span<=1e-6:result['reasons']=['degenerate_xy_extent'];return
    low=[r for r in records if abs(r['bounds'][0,2]-bed)<=tol and r['height']<=.30*span and r['volume']>max(1e-8,span**3*1e-7)and r['watertight']]
    if len(low)<32:result['reasons']=['fewer_than_32_disconnected_low_bed_solids'];return
    initial=np.median([r['center'][:2]for r in low],axis=0)
    candidates=[r for r in low if .12*span<np.linalg.norm(r['center'][:2]-initial)<.8*span]
    if len(candidates)<32:result['reasons']=['insufficient_radial_segments'];return
    points=np.array([r['center'][:2]for r in candidates]);radii=np.linalg.norm(points-initial,axis=1)
    labels,groups=_rings(radii,.015*span)
    if len(groups)<4:result['reasons']=['fewer_than_four_distinct_radial_rings'];return
    center,rings,residual=_fit_center(points,initial,labels,len(groups))
    angles=np.degrees(np.arctan2(points[:,1]-center[1],points[:,0]-center[0]))%360
    phase=(np.degrees(np.angle(np.mean(np.exp(1j*np.radians(angles*8)))))/8)%45
    chains=(np.rint((angles-phase)/45).astype(int))%8
    expected=(phase+45*chains)%360;errors=np.abs((angles-expected+180)%360-180)
    counts=[int(np.sum(chains==k))for k in range(8)]
    result['candidate_segment_counts']=counts
    if errors.max()>2:result['reasons']=['low_segments_do_not_form_exactly_eight_regular_angular_chains'];return
    if min(counts)<4:result['reasons']=['one_or_more_arms_have_fewer_than_four_segments'];return
    if max(counts)!=min(counts):result['reasons']=['unequal_segment_counts_between_arms'];return
    if any(len(set(labels[chains==k]))!=counts[k]for k in range(8)):result['reasons']=['multiple_segments_share_a_ring_in_one_arm'];return
    if any(len(group)!=8 for group in groups):result['reasons']=['radial_rings_do_not_each_have_eight_segments'];return
    rms=float(np.sqrt(np.mean(residual**2)))
    if rms>.005*span:result['reasons']=['radial_circle_fit_is_not_consistent'];return
    inner=float(min(rings))
    central=[r for r in records if np.linalg.norm(r['center'][:2]-center)<.5*inner and abs(r['bounds'][0,2]-bed)<=tol and np.min(r['bounds'][1,:2]-r['bounds'][0,:2])>.8*inner]
    if not central:result['reasons']=['central_low_bed_body_not_found'];return
    scale,scale_error=_template_scale(rings)
    arm_angles=[];arm_data=[]
    for k in range(8):
        indices=np.flatnonzero(chains==k);indices=indices[np.argsort(np.linalg.norm(points[indices]-center,axis=1))]
        arm_angles.append(float((phase+45*k)%360))
        arm_data.append({'arm_index':k,'angle_deg':arm_angles[-1],'segments':[{'mesh_object_id':candidates[i]['mesh_object_id'],'component_path_ids':candidates[i]['component_path_ids'],'connected_component_index':candidates[i]['connected_component_index'],'center_xyz':candidates[i]['center'].tolist(),'bounds_root_mm':candidates[i]['bounds'].tolist()}for i in indices]})
    result.update(matches_octopus=True,route='octopus-anchors',center_xy=center.tolist(),arm_angles_deg=arm_angles,xy_scale=scale,segment_counts=counts,arm_count=8,segment_count=sum(counts),ring_radii_mm=sorted(map(float,rings)),arms=arm_data,reasons=['eight_regular_articulated_radial_chains','at_least_four_distinct_low_bed_segments_per_chain','central_articulated_body_present'],evidence={'circle_fit_rms_mm':rms,'max_angular_error_deg':float(errors.max()),'segment_bed_scatter_mm':float(max(abs(r['bounds'][0,2]-bed)for r in candidates)),'central_body_component_count':len(central),'xy_scale_basis':'best uniform fit to supported reference arm centroid rings','template_scale_relative_rms':scale_error})


def _inspect(path,root_id=None):
    project=_Project(path)
    try:
        root_ids=list(project.instances)
        if root_id is not None:
            root_id=int(root_id)
            if root_id not in root_ids:raise GeometryError('requested_root_not_in_build')
            root_ids=[root_id]
        roots=[]
        for oid in root_ids:
            instances=project.instances[oid]
            result={'root_id':oid,'matches_octopus':False,'route':'common-only','center_xy':None,'bed_z_local':None,'top_z_local':None,'arm_angles_deg':[],'xy_scale':None,'instance_count':len(instances),'instances':instances,'plate_ids':sorted({p for i in instances for p in i['plate_ids']}),'segment_counts':[],'arm_count':0,'segment_count':0,'connected_component_count':0,'excluded_part_ids':[],'reasons':[]}
            if project.filename_exempt or _exempt(project.config.get(oid,{}).get('name','')):
                result['reasons']=['explicit_skull_skeleton_exemption'];result['geometric_analysis_skipped']=True
            else:
                try:
                    components=project.components(oid);result['excluded_part_ids']=sorted(project.excluded);_detect(components,result)
                except GeometryError as exc:result['reasons']=[str(exc)]
            roots.append(result)
        return {'schema_version':1,'source_sha256':project.sha256,'source_size_bytes':len(project.source_bytes),'source_unit':project.unit,'coordinate_unit':'millimeter','roots':roots,'parser_stats':{'xml_resources_loaded':len(project.docs),'mesh_resources_loaded_once':len(project.meshes),'mesh_resources_split_once':len(project.splits)},'limits':['geometric_pattern_detection_only','no_support_toolpath_or_physical_validation','no_source_export_or_mutation']}
    finally:project.zip.close()


def inspect_project(path):
    """Inspect all build roots from one exact source-byte snapshot; JSON-safe result."""
    return _inspect(path)


def analyze(path,root_id):
    """Inspect one build root. This avoids loading meshes of unrelated build roots."""
    result=_inspect(path,root_id);root=result['roots'][0]
    return {**root,'source_sha256':result['source_sha256'],'coordinate_unit':'millimeter'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('source');parser.add_argument('--root-id',type=int);parser.add_argument('--compact',action='store_true');args=parser.parse_args(argv)
    try:
        result=analyze(args.source,args.root_id)if args.root_id is not None else inspect_project(args.source)
        print(json.dumps(result,indent=None if args.compact else 2,allow_nan=False));return 0
    except (GeometryError,OSError,ValueError,zipfile.BadZipFile,E.XMLSyntaxError)as exc:
        reason=str(exc)if isinstance(exc,GeometryError)else type(exc).__name__
        print(json.dumps({'error':'inspection_failed','reason':reason}),file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
