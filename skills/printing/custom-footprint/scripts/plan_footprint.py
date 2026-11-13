"""Plan a configurable native retention footprint; never create a printable base."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

import numpy as np
from shapely import affinity
from shapely.geometry import GeometryCollection, LineString, MultiPoint, Point, Polygon, mapping
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
import trimesh


def _load_preflight():
    file = Path(__file__).resolve()
    candidates = [file.parents[2] / 'analyze-3d-geometry/scripts/preflight.py',
                  file.parents[3] / 'analysis/analyze-3d-geometry/scripts/preflight.py']
    for candidate in candidates:
        if candidate.is_file():
            spec = importlib.util.spec_from_file_location('dedalo_geometry_preflight', candidate)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise ImportError('Install analyze-3d-geometry and prender-3d alongside custom-footprint, or use the complete checkout')


PREFLIGHT = _load_preflight()
Project = PREFLIGHT.Project
EPS = 1e-7


def cross2(a, b):
    return a[..., 0]*b[..., 1]-a[..., 1]*b[..., 0]


def _ids(value, label):
    if not isinstance(value, list) or any(isinstance(v, bool) or not isinstance(v, int) or v <= 0 for v in value):
        raise ValueError(label + ' must be a list of positive integer part IDs')
    return set(value)


def _number(options, key, default=None, *, positive=False, nonnegative=False):
    value = options[key] if key in options else default
    return PREFLIGHT.number(value, key, positive=positive, nonnegative=nonnegative)


def _point(value, label):
    a = np.asarray(value, dtype=float)
    if a.shape != (2,) or not np.isfinite(a).all():
        raise ValueError(label + ' requires two finite coordinates')
    return a


def _polygon(value, label):
    a = np.asarray(value, dtype=float)
    if a.ndim != 2 or a.shape[1:] != (2,) or not 3 <= len(a) <= 512 or not np.isfinite(a).all():
        raise ValueError(label + ' requires 3..512 finite XY points')
    polygon = Polygon(a)
    if not polygon.is_valid or polygon.area <= EPS:
        raise ValueError(label + ' must be a simple polygon with positive area')
    return orient(polygon, sign=1.)


def _prism(polygon, lower, upper):
    """Ear-clip a simple no-hole polygon; validate caps, winding and coverage."""
    polygon = orient(polygon, sign=1.)
    if polygon.interiors or not polygon.is_valid or polygon.area <= EPS:
        raise ValueError('A simple hole-free modifier outline is required')
    coords = np.asarray(polygon.exterior.coords[:-1], dtype=float)
    # Remove collinear vertices before ear clipping, without changing the outline.
    changed = True
    while changed and len(coords) > 3:
        changed = False
        for i in range(len(coords)):
            a, b, c = coords[i-1], coords[i], coords[(i+1) % len(coords)]
            if abs(float(cross2(b-a, c-b))) < 1e-10 and np.dot(b-a, c-b) >= 0:
                coords = np.delete(coords, i, axis=0)
                changed = True
                break
    if not 3 <= len(coords) <= 2048:
        raise ValueError('Modifier outline exceeds the supported triangulation bound')
    indices = list(range(len(coords)))
    cap = []
    while len(indices) > 3:
        ear = None
        for k, bidx in enumerate(indices):
            aidx, cidx = indices[k-1], indices[(k+1) % len(indices)]
            a, b, c = coords[[aidx, bidx, cidx]]
            if float(cross2(b-a, c-b)) <= 1e-12:
                continue
            other = np.asarray([coords[i] for i in indices if i not in {aidx, bidx, cidx}])
            ab = cross2(b-a, other-a)
            bc = cross2(c-b, other-b)
            ca = cross2(a-c, other-c)
            if np.any((ab >= -1e-12) & (bc >= -1e-12) & (ca >= -1e-12)):
                continue
            ear = k
            cap.append((aidx, bidx, cidx))
            break
        if ear is None:
            raise ValueError('Could not triangulate the reviewed modifier polygon')
        indices.pop(ear)
    cap.append(tuple(indices))
    covered = unary_union([Polygon(coords[list(t)]) for t in cap])
    if covered.symmetric_difference(polygon).area > 1e-6:
        raise ValueError('Modifier cap triangulation does not preserve the polygon')
    n = len(coords)
    vertices = np.vstack([np.c_[coords, np.full(n, lower)], np.c_[coords, np.full(n, upper)]])
    faces = []
    for i in range(n):
        j = (i+1) % n
        faces.extend([[i, j, n+j], [i, n+j, n+i]])
    faces += [[c, b, a] for a, b, c in cap]
    faces += [[a+n, b+n, c+n] for a, b, c in cap]
    mesh = trimesh.Trimesh(vertices, faces, process=False)
    if not mesh.is_watertight or not mesh.is_winding_consistent or mesh.volume <= 0:
        raise ValueError('Modifier prism failed its closed-mesh checks')
    return {'shape': 'mesh', 'values': [vertices.tolist(), faces]}


def _shape(shape, points, center, margin, params, segments):
    hull = MultiPoint(points).convex_hull
    if hull.geom_type != 'Polygon':
        raise ValueError('The fixed body needs a measurable two-dimensional band')
    if shape == 'auto':
        ideal = float(np.linalg.norm(points-center, axis=1).max())
        circle_area = math.pi*(ideal+margin)**2
        shape = 'circle' if circle_area/hull.buffer(margin).area <= 1.15 else 'hull'
    if shape == 'circle':
        radius = PREFLIGHT.number(params.get('radius_mm', np.linalg.norm(points-center, axis=1).max()),
                                  'radius_mm', positive=True)
        angle = np.arange(segments)*2*math.pi/segments
        xy = np.c_[np.cos(angle), np.sin(angle)]*(radius+margin)/math.cos(math.pi/segments)+center
        poly = Polygon(xy)
    elif shape == 'ellipse':
        default = np.maximum(np.max(np.abs(points-center), axis=0), EPS)
        radii = _point(params.get('radii_mm', default), 'radii_mm')
        if np.any(radii <= 0):
            raise ValueError('Ellipse radii must be positive')
        if 'radii_mm' not in params:
            radii *= max(1., float(np.linalg.norm((points-center)/radii, axis=1).max()))
        # Circumscribe the measured ellipse, then use a nearly exact outward
        # Euclidean offset rather than inflating its long axis by the short one.
        radii = radii/math.cos(math.pi/segments)
        angle = np.arange(segments)*2*math.pi/segments
        poly = Polygon(np.c_[np.cos(angle), np.sin(angle)]*radii+center)
        rotation = PREFLIGHT.number(params.get('rotation_deg', 0), 'rotation_deg')
        poly = affinity.rotate(poly, rotation, origin=tuple(center))
        if margin:
            poly = poly.buffer(margin/math.cos(math.pi/128), quad_segs=32)
    elif shape == 'rounded_rectangle':
        size = _point(params.get('size_mm', 2*np.max(np.abs(points-center), axis=0)), 'size_mm')
        if np.any(size <= 0):
            raise ValueError('Rectangle dimensions must be positive')
        corner = PREFLIGHT.number(params.get('corner_radius_mm', 0), 'corner radius', nonnegative=True)
        if corner > min(size)/2:
            raise ValueError('Corner radius exceeds half the short side')
        inner = np.maximum(size/2-corner, 0)
        # A degenerate core is valid for a capsule/circle, but not an empty box.
        if min(inner) > EPS:
            base = Polygon([center+[-inner[0], -inner[1]], center+[inner[0], -inner[1]],
                            center+[inner[0], inner[1]], center+[-inner[0], inner[1]]])
        elif max(inner) > EPS:
            delta = np.array([inner[0], inner[1]])
            base = LineString([center-delta, center+delta])
        else:
            base = Point(center)
        poly = base.buffer(corner+margin, quad_segs=32) if corner+margin else base
        rotation = PREFLIGHT.number(params.get('rotation_deg', 0), 'rotation_deg')
        poly = affinity.rotate(poly, rotation, origin=tuple(center))
    elif shape == 'hull':
        poly = hull.buffer(margin, quad_segs=32) if margin else hull
    elif shape == 'polygon':
        base = _polygon(params.get('points_xy'), 'points_xy')
        poly = base.buffer(margin, quad_segs=32) if margin else base
    else:
        raise ValueError('Choose auto, circle, ellipse, rounded_rectangle, hull, or polygon')
    if poly.geom_type != 'Polygon' or not poly.is_valid or poly.interiors:
        raise ValueError('The footprint must be one simple polygon without holes')
    return orient(poly, sign=1.), shape


def _selected(components, ids):
    return [(mesh, identity) for mesh, identity in components
            if set(identity['component_path_ids'][1:]) & ids]


def _outline_contact(section, center, angle):
    unit = np.array([math.cos(math.radians(angle)), math.sin(math.radians(angle))])
    bounds = np.asarray(section.bounds)
    reach = max(1., np.linalg.norm(bounds[2:]-bounds[:2])*4)
    hit = section.boundary.intersection(LineString([center, center+unit*reach]))
    points = []
    def collect(geometry):
        if geometry.is_empty:
            return
        if hasattr(geometry, 'geoms'):
            for part in geometry.geoms:
                collect(part)
        elif geometry.geom_type == 'Point':
            points.append(np.array(geometry.coords[0]))
        elif geometry.geom_type in {'LineString', 'LinearRing'}:
            points.extend(np.asarray(geometry.coords)[[0, -1]])
    collect(hit)
    if not points:
        raise ValueError('A contact ray does not reach a fixed wall; review center and angles')
    return max(points, key=lambda p: float(np.dot(p-center, unit)))


def _brim(options):
    value = options.get('brim')
    if value is None:
        return {}
    if not isinstance(value, dict) or set(value)-{'type', 'width_mm', 'tree_width_mm'}:
        raise ValueError('brim requires type and width_mm, with optional tree_width_mm')
    kind = value.get('type')
    if kind not in {'no_brim', 'outer_only', 'inner_only', 'outer_and_inner'}:
        raise ValueError('Choose an explicit native brim type')
    width = PREFLIGHT.number(value.get('width_mm'), 'brim width', nonnegative=True)
    if (kind == 'no_brim') != (width == 0):
        raise ValueError('no_brim requires zero width; enabled brim requires positive width')
    result = {'brim_type': kind, 'brim_width': format(width, 'g')}
    if 'tree_width_mm' in value:
        result['tree_support_brim_width'] = format(PREFLIGHT.number(value['tree_width_mm'], 'tree brim width', nonnegative=True), 'g')
    return result


def plan(source, root_id, options, expected_sha256):
    allowed = {'shape', 'shape_parameters', 'margin_mm', 'center_xy', 'segments',
               'height_mm', 'upper_band_height_mm', 'contact_band_height_mm',
               'contact_depth_mm', 'contact_width_mm', 'contact_angles_deg',
               'fixed_part_ids', 'all_positive_fixed', 'keepout_part_ids',
               'protect_unselected_parts', 'keepout_polygons_xy', 'keepout_clearance_mm',
               'obstacle_polygons_xy', 'min_contacts', 'skip_unsafe_contacts',
               'check_neighbor_parts', 'brim'}
    if not isinstance(options, dict) or set(options)-allowed:
        raise ValueError('Unknown footprint options; use the documented plan schema')
    project = Project(source)
    try:
        required = {'Metadata/model_settings.config', 'Metadata/project_settings.config'}
        if not required <= set(project.zip.namelist()):
            raise ValueError('Complete project metadata is required')
        if project.sha256 != str(expected_sha256).lower():
            raise ValueError('Source hash changed')
        if project.unit != 'millimeter':
            raise ValueError('Footprint plans require millimetre project geometry')
        rid = int(root_id)
        components = project.components(rid)
        if rid not in project.instances or not components:
            raise ValueError('The requested built root must have positive geometry')
        available = {pid for _, item in components for pid in item['component_path_ids'][1:]}
        for flag in ['all_positive_fixed', 'protect_unselected_parts', 'skip_unsafe_contacts', 'check_neighbor_parts']:
            if flag in options and not isinstance(options[flag], bool):
                raise ValueError(flag + ' must be an explicit boolean')
        fixed_ids = _ids(options.get('fixed_part_ids', []), 'fixed_part_ids')
        if fixed_ids and options.get('all_positive_fixed', False):
            raise ValueError('Use fixed_part_ids or all_positive_fixed, not both')
        if not fixed_ids and options.get('all_positive_fixed') is not True:
            raise ValueError('Explicitly select fixed_part_ids or confirm all_positive_fixed=true')
        if not fixed_ids <= available or rid in fixed_ids:
            raise ValueError('fixed_part_ids must identify positive component parts in this root')
        fixed = components if options.get('all_positive_fixed') is True else _selected(components, fixed_ids)
        if not fixed:
            raise ValueError('The selected fixed parts have no geometry')
        if not any(instance['printable'] for instance in project.instances[rid]):
            raise ValueError('The target root has no printable build')
        for instance in project.instances[rid]:
            build = np.asarray(instance['transform_4x4'])
            rot = build[:3, :3]
            if (not np.allclose(rot[2], [0, 0, 1], atol=EPS, rtol=0)
                or not np.allclose(rot[:2, 2], 0, atol=EPS, rtol=0)
                or not np.allclose(rot.T @ rot, np.eye(3), atol=EPS, rtol=0)
                or not math.isclose(float(np.linalg.det(rot)), 1, abs_tol=EPS)):
                raise ValueError('Footprint plans require upright unscaled rigid builds')
        bed = min(float(mesh.bounds[0, 2]) for mesh, _ in components)
        top = max(float(mesh.bounds[1, 2]) for mesh, _ in components)
        if any(abs(np.asarray(i['transform_4x4'])[2, 3]+bed) > 1e-5 for i in project.instances[rid]):
            raise ValueError('Every target build must be seated on the bed')
        height = _number(options, 'height_mm', positive=True)
        upper_height = _number(options, 'upper_band_height_mm', 3., positive=True)
        band = _number(options, 'contact_band_height_mm', min(3., height), positive=True)
        if height >= top-bed or band > height:
            raise ValueError('Contact band and support ceiling must be inside the product height')
        margin = _number(options, 'margin_mm', .6, nonnegative=True)
        clearance = _number(options, 'keepout_clearance_mm', .6, nonnegative=True)
        radial = _number(options, 'contact_depth_mm', 2., positive=True)
        tangential = _number(options, 'contact_width_mm', 2., positive=True)
        segments = options.get('segments', 128)
        if isinstance(segments, bool) or not isinstance(segments, int) or not 16 <= segments <= 256:
            raise ValueError('segments must be an integer between 16 and 256')
        fixed_meshes = [mesh for mesh, _ in fixed]
        measured, points = PREFLIGHT.projected_band_geometry(fixed_meshes, bed+height, bed+height+upper_height)
        if not len(points) or measured.is_empty:
            raise ValueError('The fixed body does not intersect the upper blocker band')
        center = _point(options.get('center_xy', (points.min(0)+points.max(0))/2), 'center_xy')
        params = options.get('shape_parameters', {})
        if not isinstance(params, dict) or set(params)-{'radius_mm','radii_mm','size_mm','corner_radius_mm','rotation_deg','points_xy'}:
            raise ValueError('shape_parameters contains unsupported fields')
        footprint, selected_shape = _shape(options.get('shape', 'auto'), points, center, margin, params, segments)
        target = measured.buffer(margin, quad_segs=32) if margin else measured
        if not footprint.buffer(1e-6).covers(target):
            raise ValueError('The requested footprint does not cover the measured fixed-body band and margin')
        angles = options.get('contact_angles_deg')
        if not isinstance(angles, list) or not 1 <= len(angles) <= 64:
            raise ValueError('Provide 1..64 explicit contact angles')
        angles = [PREFLIGHT.number(a, 'contact angle') % 360 for a in angles]
        if len(set(round(a, 8) for a in angles)) != len(angles):
            raise ValueError('Contact angles must be distinct modulo 360')
        min_contacts = options.get('min_contacts', len(angles))
        if isinstance(min_contacts, bool) or not isinstance(min_contacts, int) or not 1 <= min_contacts <= len(angles):
            raise ValueError('min_contacts must be inside the explicit contact count')
        negative = PREFLIGHT.negative_components(project, rid)
        keep_ids = _ids(options.get('keepout_part_ids', []), 'keepout_part_ids')
        if not keep_ids <= available:
            raise ValueError('keepout_part_ids must identify positive parts in the target root')
        protected = _selected(components, keep_ids)
        if options.get('protect_unselected_parts', True):
            keys = {(tuple(i['component_path_ids']), i['connected_component_index']) for _, i in fixed}
            protected += [(m, i) for m, i in components if (tuple(i['component_path_ids']), i['connected_component_index']) not in keys]
        keep_polys = []
        for mesh, _ in protected+negative:
            projected, xy = PREFLIGHT.projected_band_geometry([mesh], bed, bed+height+upper_height)
            if len(xy) >= 3:
                hull = MultiPoint(xy).convex_hull
                if hull.geom_type == 'Polygon':
                    keep_polys.append(hull.buffer(clearance, quad_segs=16) if clearance else hull)
        for value in options.get('keepout_polygons_xy', []):
            polygon = _polygon(value, 'keepout polygon')
            keep_polys.append(polygon.buffer(clearance, quad_segs=16) if clearance else polygon)
        keepout = unary_union(keep_polys)
        obstacles = [_polygon(p, 'obstacle polygon') for p in options.get('obstacle_polygons_xy', [])]
        obstacle = unary_union(obstacles)
        # The wall is measured at the middle of the intended contact band, not a bounding box edge.
        plane = bed+height-band/2
        section, warnings = PREFLIGHT.section_geometry(fixed_meshes, plane)
        voids, void_warnings = PREFLIGHT.section_geometry([m for m, _ in negative], plane)
        section = section.difference(voids)
        if warnings or void_warnings or section.is_empty:
            raise ValueError('No complete fixed-wall section exists in the contact band')
        regions, contacts, rejected = [], [], []
        patches = []
        for index, angle in enumerate(angles, 1):
            point = _outline_contact(section, center, angle)
            patch = Polygon([[-radial/2, -tangential/2], [radial/2, -tangential/2],
                             [radial/2, tangential/2], [-radial/2, tangential/2]])
            patch = affinity.rotate(patch, angle, origin=(0, 0))
            patch = affinity.translate(patch, *point)
            reason = None
            if patch.intersection(keepout).area > EPS:
                reason = 'protected_part_or_functional_keepout'
            elif patch.intersection(obstacle).area > EPS:
                reason = 'explicit_obstacle'
            elif patch.intersection(section).area <= EPS:
                reason = 'no_measured_fixed_wall_overlap'
            if reason:
                rejected.append({'angle_deg': angle, 'reason': reason})
                if not options.get('skip_unsafe_contacts', False):
                    raise ValueError('A requested contact intersects a keepout or misses a fixed wall; review the plan')
                continue
            regions.append({'role': f'contact_{index}', 'label': 'Measured fixed-wall contact',
                            'subtype': 'support_enforcer', 'shape': 'cube',
                            'values': [[radial, tangential, band], [*point.tolist(), bed+height-band/2], angle]})
            patches.append(patch)
            contacts.append({'angle_deg': angle, 'center_xy_root_mm': point.tolist(),
                             'mask_fixed_section_overlap_mm2': float(patch.intersection(section).area)})
        if len(contacts) < min_contacts:
            raise ValueError('Too few safe contacts remain for the explicitly requested minimum')
        regions.append({'role': 'upper', 'label': 'Measured configurable upper blocker',
                        'subtype': 'support_blocker', **_prism(footprint, bed+height, bed+height+upper_height)})
        for index, polygon in enumerate(keep_polys, 1):
            regions.append({'role': f'keepout_{index}', 'label': 'Explicit protected region',
                            'subtype': 'support_blocker', **_prism(polygon, bed, bed+height+upper_height)})
        if footprint.intersection(obstacle).area > EPS:
            raise ValueError('The footprint mask overlaps an explicit neighbouring obstacle')
        neighbor_checks = []
        if options.get('check_neighbor_parts', True):
            for own in project.instances[rid]:
                if not own['printable']:
                    continue
                if not own['plate_ids']:
                    raise ValueError('Target plate membership is required for neighbour checks')
                m = np.asarray(own['transform_4x4'])
                affine = [m[0, 0], m[0, 1], m[1, 0], m[1, 1], m[0, 3], m[1, 3]]
                own_poly = affinity.affine_transform(footprint, affine)
                own_contacts = affinity.affine_transform(unary_union(patches), affine)
                for other_id, instances in project.instances.items():
                    for other in instances:
                        if not other['printable'] or not set(own['plate_ids']) & set(other['plate_ids']):
                            continue
                        if other_id == rid and other['instance_id'] == own['instance_id']:
                            continue
                        meshes = []
                        for mesh, _ in project.components(other_id):
                            measured_mesh = mesh.copy()
                            measured_mesh.apply_transform(np.asarray(other['transform_4x4']))
                            meshes.append(measured_mesh)
                        projected, _ = PREFLIGHT.projected_band_geometry(meshes, height, height+upper_height)
                        contact_obstacle, _ = PREFLIGHT.projected_band_geometry(meshes, height-band, height)
                        area = float(own_poly.intersection(projected).area)
                        contact_area = float(own_contacts.intersection(contact_obstacle).area)
                        neighbor_checks.append({'target_instance_id': own['instance_id'], 'other_root_id': other_id,
                                                'other_instance_id': other['instance_id'], 'upper_mask_overlap_mm2': area,
                                                'enforcer_mask_overlap_mm2': contact_area})
                        if area > EPS or contact_area > EPS:
                            raise ValueError('A footprint mask overlaps another printable part on the same plate')
        report = {'schema': 1, 'source_sha256': project.sha256, 'root_id': rid,
                  'shape_requested': options.get('shape', 'auto'), 'shape_selected': selected_shape,
                  'frame': {'bed_z_local': bed, 'top_z_local': top},
                  'height_limit_mm': height, 'contact_band_height_mm': band,
                  'fixed_part_ids': sorted(fixed_ids),
                  'all_positive_fixed_confirmed': options.get('all_positive_fixed', False),
                  'keepout_part_ids': sorted(keep_ids),
                  'protect_unselected_parts': options.get('protect_unselected_parts', True),
                  'margin_mm': margin, 'center_xy_root_mm': center.tolist(),
                  'contact_depth_mm': radial, 'contact_width_mm': tangential,
                  'upper_blocker_z_root_mm': [bed+height, bed+height+upper_height],
                  'footprint_area_mm2': float(footprint.area), 'footprint_bounds_root_mm': list(footprint.bounds),
                  'footprint_outline_xy': [list(x) for x in footprint.exterior.coords[:-1]],
                  'measured_band_and_margin_covered': True, 'contacts': contacts,
                  'rejected_contacts': rejected, 'native_modifier_count': len(regions),
                  'keepout_modifier_count': len(keep_polys),
                  'neighbor_checks_enabled': options.get('check_neighbor_parts', True),
                  'neighbor_checks': neighbor_checks,
                  'brim_process_patch': _brim(options),
                  'limits': ['mask_plan_not_printable_base', 'contact_mask_overlap_is_not_native_support_contact',
                             'static_mesh_keepouts_not_inferred_joint_motion',
                             'protected_parts_use_conservative_band_hulls_not_exact_motion_envelopes',
                             'neighbor_checks_use_positive_band_projections_without_negative_subtraction',
                             'negative_sections_are_2d_checks_not_a_3d_boolean',
                             'native_brim_shape_and_tree_feet_require_a_fresh_slice',
                             'machine_edge_and_lift_travel_not_certified'],
                  'physical_validation': False, 'native_slicing_required': True}
        if not isinstance(source, (bytes, bytearray)) and hashlib.sha256(Path(source).read_bytes()).hexdigest() != project.sha256:
            raise ValueError('Source changed during planning')
        return {'regions': regions, 'report': report}
    finally:
        project.zip.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('regions_output', type=Path)
    parser.add_argument('--root-id', required=True, type=int)
    parser.add_argument('--expect-sha256', required=True)
    parser.add_argument('--options-json', required=True, type=Path)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--process-patch-output', type=Path)
    args = parser.parse_args()
    outputs = [p.resolve() for p in [args.regions_output, args.report, args.process_patch_output] if p]
    if len(outputs) != len(set(outputs)):
        raise ValueError('All derived output paths must be distinct')
    for output in outputs:
        PREFLIGHT.validate_output(output, args.source)
    result = plan(args.source, args.root_id, json.loads(args.options_json.read_text()), args.expect_sha256)
    PREFLIGHT.write_json(args.regions_output, result['regions'], args.source)
    if args.report:
        PREFLIGHT.write_json(args.report, result['report'], args.source)
    if args.process_patch_output:
        PREFLIGHT.write_json(args.process_patch_output, result['report']['brim_process_patch'], args.source)
    print(json.dumps({'source_sha256': result['report']['source_sha256'], 'regions': len(result['regions']),
                      'contacts': len(result['report']['contacts']), 'native_slicing_required': True}))


if __name__ == '__main__':
    main()
