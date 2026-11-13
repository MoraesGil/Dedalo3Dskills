"""Read-only 3MF geometry preflight; sections are geometry, not slicer toolpaths."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import os

import numpy as np
from shapely.geometry import GeometryCollection, LineString, Polygon, mapping
from shapely.ops import unary_union
import trimesh


def _load_generic():
    file = Path(__file__).resolve()
    candidates = [file.parents[2] / 'prender-3d/scripts',
                  file.parents[3] / 'printing/prender-3d/scripts']
    for candidate in candidates:
        if (candidate / 'geometry_project.py').is_file():
            sys.path.insert(0, str(candidate))
            from geometry_project import Project, GeometryError, NS, MAIN, PROD, NORMAL, _matrix
            return Project, GeometryError, NS, MAIN, PROD, NORMAL, _matrix
    raise ImportError('Install prender-3d alongside analyze-3d-geometry, or use the complete checkout')


Project, GeometryError, NS, MAIN, PROD, NORMAL, _matrix = _load_generic()
EPS = 1e-7


def number(value, label, *, positive=False, nonnegative=False):
    if isinstance(value, bool):
        raise ValueError(label + ' must be a finite number')
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0) or (nonnegative and result < 0):
        raise ValueError(label + ' must be a finite number in the permitted range')
    return result


def inventory(project, root_id):
    """Resolved component hierarchy, including negatives and support modifiers.

    Report technical IDs only; omit product names and source-file metadata.
    Modifier meshes are counted but never included in positive contact areas.
    """
    result = []
    def visit(path, oid, trail, active):
        key = (path, oid)
        if key in active or len(active) > 32:
            raise GeometryError('inventory_cycle_or_depth_limit')
        obj = project.doc(path)[1].get(oid)
        if obj is None:
            raise GeometryError('unresolved_inventory_object_id')
        children = obj.find('m:components', NS)
        if children is None:
            return
        types = project.config.get(oid, {}).get('types', {})
        for child in children:
            cid = int(child.get('objectid'))
            child_path = project.resource(path, child.get(PROD + 'path'))
            target = project.doc(child_path)[1].get(cid)
            if target is None:
                raise GeometryError('unresolved_inventory_component')
            result.append({'part_id': cid, 'parent_object_id': oid,
                           'component_path_ids': trail+[cid],
                           'subtype': types.get(cid, 'normal_part'),
                           'transform_4x4_project_units': _matrix(child.get('transform')).tolist(),
                           'geometry_kind': 'mesh' if target.find('m:mesh', NS) is not None else 'components'})
            visit(child_path, cid, trail+[cid], active | {key})
    visit(MAIN, int(root_id), [int(root_id)], set())
    return result


def negative_components(project, root_id):
    """Read actual negative meshes in measurement copies, without changing a 3MF."""
    result = []
    def visit(path, oid, matrix, trail, active, negative=False):
        key = (path, oid)
        if key in active or len(active) > 32:
            raise GeometryError('negative_component_cycle_or_depth_limit')
        obj = project.doc(path)[1].get(oid)
        if obj is None:
            raise GeometryError('unresolved_negative_object_id')
        if obj.find('m:mesh', NS) is not None:
            if negative:
                for index, source in enumerate(project.mesh_components(path, oid, obj)):
                    mesh = source.copy()
                    mesh.apply_transform(matrix)
                    mesh.vertices *= project.unit_mm
                    result.append((mesh, {'mesh_object_id': oid, 'component_path_ids': trail,
                                          'connected_component_index': index}))
            return
        children = obj.find('m:components', NS)
        if children is None:
            raise GeometryError('negative_object_without_mesh_or_components')
        types = project.config.get(oid, {}).get('types', {})
        for child in children:
            cid = int(child.get('objectid'))
            subtype = types.get(cid, 'normal_part')
            if not negative and subtype not in NORMAL and subtype != 'negative_part':
                continue
            visit(project.resource(path, child.get(PROD + 'path')), cid,
                  matrix @ _matrix(child.get('transform')), trail + [cid], active | {key},
                  negative or subtype == 'negative_part')
    visit(MAIN, int(root_id), np.eye(4), [int(root_id)], set())
    return result


def section_geometry(meshes, z):
    """Closed XY section rings at one real Z plane, with even-odd holes per mesh."""
    pieces, warnings = [], []
    for mesh in meshes:
        if mesh.is_watertight and mesh.volume < -EPS:
            # The shared reader splits disconnected boundary shells. An inward
            # shell can represent a cavity of its outer shell, so treating each
            # split as a separate filled solid would silently erase that void.
            raise GeometryError('inward_boundary_shell_requires_solid_topology_adapter')
        if z < mesh.bounds[0, 2] - EPS or z > mesh.bounds[1, 2] + EPS:
            continue
        section = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
        if section is None:
            continue
        solid = GeometryCollection()
        for points in section.discrete:
            points = np.asarray(points)
            if len(points) < 4 or not np.allclose(points[0], points[-1], atol=EPS, rtol=0):
                warnings.append('open_section_ring')
                continue
            polygon = Polygon(points[:, :2])
            if not polygon.is_valid or polygon.area <= EPS:
                warnings.append('invalid_or_degenerate_section_ring')
                continue
            solid = solid.symmetric_difference(polygon)
        if not solid.is_empty:
            pieces.append(solid)
    return unary_union(pieces), sorted(set(warnings))


def projected_band_geometry(meshes, lower, upper):
    """Projection of clipped boundary triangles plus actual section interiors.

    Covers the complete boundary projection, including vertical edges. It is not
    a negative-volume Boolean or a sampled approximation of an arbitrary motion.
    """
    pieces, points = [], []
    for mesh in meshes:
        if mesh.is_watertight and mesh.volume < -EPS:
            raise GeometryError('inward_boundary_shell_requires_solid_topology_adapter')
        if upper < mesh.bounds[0, 2] or lower > mesh.bounds[1, 2]:
            continue
        clipped = mesh.slice_plane([0, 0, lower], [0, 0, 1], cap=False)
        clipped = clipped.slice_plane([0, 0, upper], [0, 0, -1], cap=False)
        if not len(clipped.vertices):
            continue
        if len(clipped.faces) > 100_000:
            raise GeometryError('band_projection_face_limit_requires_adapter')
        points.append(np.asarray(clipped.vertices)[:, :2])
        for triangle in np.asarray(clipped.triangles)[:, :, :2]:
            polygon = Polygon(triangle)
            if polygon.area > EPS:
                pieces.append(polygon)
            else:
                line = LineString(np.vstack([triangle, triangle[0]]))
                if line.length > EPS:
                    pieces.append(line)
    # Section interiors make the covered region explicit for vertical prisms.
    for z in [lower + min((upper-lower)/4, 1e-5), (lower+upper)/2,
              upper - min((upper-lower)/4, 1e-5)]:
        section, warnings = section_geometry(meshes, z)
        if warnings:
            raise GeometryError('unresolved_section_in_footprint_band')
        if not section.is_empty:
            pieces.append(section)
    return unary_union(pieces), np.vstack(points) if points else np.empty((0, 2))


def _section_summary(positive, negative, z, include_geometry=False):
    p, pw = section_geometry(positive, z)
    n, nw = section_geometry(negative, z)
    net = p.difference(n)
    result = {'plane_z_mm': z, 'positive_area_mm2': float(p.area),
              'negative_overlap_area_mm2': float(p.intersection(n).area),
              'net_geometric_area_mm2': float(net.area),
              'net_bounds_xy_mm': None if net.is_empty else list(net.bounds),
              'section_complete': not pw and not nw, 'warnings': sorted(set(pw + nw)),
              'basis': 'geometric_section_with_resolved_negative_sections_subtracted_not_extrusion_WIDTH'}
    if include_geometry:
        result['geometry_xy'] = mapping(net)
    return result


def inspect(source, *, root_id=None, layer_height_mm=.2, bed_z_mm=0., include_geometry=False):
    height = number(layer_height_mm, 'layer height', positive=True)
    bed = number(bed_z_mm, 'bed Z')
    project = Project(source)
    try:
        required = {'Metadata/model_settings.config', 'Metadata/project_settings.config'}
        if not required <= set(project.zip.namelist()):
            raise GeometryError('complete_project_metadata_required')
        roots = list(project.instances)
        if root_id is not None:
            root_id = int(root_id)
            if root_id not in roots:
                raise GeometryError('requested_root_not_in_build')
            roots = [root_id]
        results = []
        for rid in roots:
            positive = project.components(rid)
            negative = negative_components(project, rid)
            if not positive:
                raise GeometryError('root_has_no_positive_geometry')
            bounds = np.array([np.min([m.bounds[0] for m, _ in positive], axis=0),
                               np.max([m.bounds[1] for m, _ in positive], axis=0)])
            row = {'root_id': rid, 'part_inventory': inventory(project, rid),
                   'positive_connected_components': len(positive),
                   'negative_connected_components': len(negative),
                   'positive_bounds_root_mm': bounds.tolist(),
                   'positive_volume_sum_mm3': sum(abs(float(m.volume)) for m, _ in positive),
                   'volume_basis': 'sum_of_positive_component_volumes_not_boolean_union',
                   'non_watertight_positive_components': sum(not m.is_watertight for m, _ in positive),
                   'instances': []}
            for instance in project.instances[rid]:
                transform = np.asarray(instance['transform_4x4'], dtype=float)
                transform[:3, 3] *= project.unit_mm
                pos, neg = [], []
                for components, target in [(positive, pos), (negative, neg)]:
                    for mesh, _ in components:
                        measured = mesh.copy()
                        measured.apply_transform(transform)
                        target.append(measured)
                wb = np.array([np.min([m.bounds[0] for m in pos], axis=0),
                               np.max([m.bounds[1] for m in pos], axis=0)])
                rot = transform[:3, :3]
                upright = bool(np.allclose(rot[2], [0, 0, 1], atol=EPS, rtol=0)
                               and np.allclose(rot[:2, 2], 0, atol=EPS, rtol=0)
                               and np.allclose(rot.T @ rot, np.eye(3), atol=EPS, rtol=0)
                               and math.isclose(float(np.linalg.det(rot)), 1, abs_tol=EPS))
                on_bed = abs(float(wb[0, 2])-bed) <= 1e-5
                row['instances'].append({'instance_id': instance['instance_id'],
                    'plate_ids': instance['plate_ids'], 'printable': instance['printable'],
                    'transform_4x4_mm': transform.tolist(), 'bounds_build_mm': wb.tolist(),
                    'upright_unscaled_rigid': upright, 'on_bed': on_bed,
                    'retention_adapter_eligible': upright and on_bed and project.unit == 'millimeter',
                    'first_layer': _section_summary(pos, neg, bed+height/2, include_geometry)})
            results.append(row)
        if not isinstance(source, (bytes, bytearray)) and hashlib.sha256(Path(source).read_bytes()).hexdigest() != project.sha256:
            raise ValueError('Source changed during preflight')
        return {'schema': 1, 'source_sha256': project.sha256, 'source_unit': project.unit,
                'coordinate_unit': 'millimeter', 'build_xy_frame': 'project_plater_coordinates_not_native_plate_origin_adjusted',
                'first_layer_height_mm': height, 'bed_z_mm': bed, 'roots': results,
                'scope': ['read_only_geometry_preflight', 'actual_plane_sections_not_bounding_box_projection',
                          'negative_2d_sections_subtracted_only', 'no_joint_or_motion_inference',
                          'no_slicer_toolpath_or_machine_clearance_certification'],
                'physical_validation': False}
    finally:
        project.zip.close()


def validate_output(path, source):
    path = Path(path).resolve()
    source = Path(source).resolve()
    if path == source or path.exists() or not path.parent.is_dir():
        raise ValueError('A new output path distinct from the source is required')
    temporary = Path(tempfile.gettempdir()).resolve()
    if not path.is_relative_to(temporary) and not path.is_relative_to(Path('/tmp').resolve()):
        raise ValueError('Write derived reports only inside a private system temporary directory')
    return path


def write_json(path, value, source):
    path = validate_output(path, source)
    data = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--root-id', type=int)
    parser.add_argument('--first-layer-height-mm', type=float, default=.2)
    parser.add_argument('--bed-z-mm', type=float, default=0.)
    parser.add_argument('--include-section-geometry', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.output:
        validate_output(args.output, args.source)
    report = inspect(args.source, root_id=args.root_id, layer_height_mm=args.first_layer_height_mm,
                     bed_z_mm=args.bed_z_mm, include_geometry=args.include_section_geometry)
    if args.output:
        write_json(args.output, report, args.source)
    else:
        print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
