"""Build one planar relief mesh from a reviewed millimetre polygon, not an image or 3MF."""
import argparse
import io
import json
import math
import os
from pathlib import Path
import tempfile

import numpy as np
from shapely.geometry import Polygon
import trimesh


def finite_number(value):
    """Reject JSON booleans, malformed scalars and integers beyond float range."""
    try:
        return not isinstance(value, bool) and math.isfinite(value)
    except (TypeError, OverflowError):
        return False


def build(mask, *, mode, width, surface_z, rise, root):
    """Return a closed mesh and measurements; retain every explicit hole."""
    if not all(finite_number(x) for x in (surface_z, rise, root)) or rise <= 0 or root <= 0:
        raise ValueError('surface_z must be finite; rise and root must be finite and positive')
    height, bottom = rise + root, surface_z - root
    top = bottom + height
    if (not all(finite_number(x) for x in (height, bottom, top))
            or not math.isclose(surface_z - bottom, root, rel_tol=1e-9)
            or not math.isclose(top - surface_z, rise, rel_tol=1e-9)):
        raise ValueError('dimensions cannot represent the requested root and rise at this surface_z')
    try:
        points = [mask['outer'], *mask.get('holes', [])]
        if any(not isinstance(r, (list, tuple)) or len(r) < 3 for r in points):
            raise ValueError('every polygon ring needs at least three XY points')
        if any(len(p) != 2 or not all(finite_number(x) for x in p) for r in points for p in r):
            raise ValueError('polygon points must be finite XY pairs in millimetres')
        polygon = Polygon(points[0], points[1:])
    except (KeyError, TypeError) as exc:
        raise ValueError('mask needs outer and optional holes rings') from exc
    if (polygon.is_empty or not polygon.is_valid
            or not math.isfinite(polygon.area) or polygon.area <= 0):
        raise ValueError('mask must be a nonempty valid polygon; do not silently repair the art')
    if mode == 'outline':
        if not finite_number(width) or width <= 0:
            raise ValueError('outline width must be finite and positive')
        inset = polygon.buffer(-width, join_style='mitre')
        if inset.is_empty:
            raise ValueError('outline consumes the complete mask; reduce width or explicitly choose filled')
        shape = polygon.difference(inset)
    elif mode == 'filled':
        if width is not None:
            raise ValueError('width applies only to outline')
        shape = polygon
    else:
        raise ValueError('mode must be outline or filled')
    if not math.isfinite(shape.area * height) or shape.area * height <= 0:
        raise ValueError('relief volume must be finite and positive')
    pieces = [shape] if shape.geom_type == 'Polygon' else list(shape.geoms)
    meshes = []
    for piece in pieces:
        part = trimesh.creation.extrude_polygon(piece, height=height, engine='earcut')
        part.apply_translation([0, 0, bottom])
        meshes.append(part)
    mesh = trimesh.util.concatenate(meshes)
    if (not mesh.is_watertight or not mesh.is_winding_consistent
            or not np.isfinite(mesh.vertices).all() or not math.isfinite(mesh.volume)
            or mesh.volume <= 0):
        raise ValueError('extrusion failed closed-solid checks')
    return mesh, dict(mode=mode, width_mm=width, surface_z_mm=surface_z, rise_mm=rise,
                      root_mm=root, area_mm2=shape.area, volume_mm3=float(mesh.volume),
                      bounds_mm=mesh.bounds.tolist(), holes=len(polygon.interiors),
                      watertight=bool(mesh.is_watertight))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mask', type=Path)
    parser.add_argument('output', type=Path, help='New .stl inside the system temporary directory')
    parser.add_argument('--mode', required=True, choices=['outline', 'filled'])
    parser.add_argument('--width', type=float)
    parser.add_argument('--surface-z', type=float, required=True)
    parser.add_argument('--rise', type=float, required=True)
    parser.add_argument('--root', type=float, required=True)
    args = parser.parse_args()
    # Keep the final path component intact: O_EXCL must reject symlinks too.
    output = args.output.parent.resolve() / args.output.name
    temp_roots = [Path(tempfile.gettempdir()).resolve()]
    if os.name == 'posix' and Path('/tmp').is_dir():
        temp_roots.append(Path('/tmp').resolve())
    if not any(output.is_relative_to(root) for root in temp_roots) or output.suffix.lower() != '.stl':
        parser.error('output must be a new .stl in the system temporary directory')
    if output.exists():
        parser.error('refusing to overwrite output')
    try:
        mesh, info = build(json.loads(args.mask.read_text()), mode=args.mode, width=args.width,
                           surface_z=args.surface_z, rise=args.rise, root=args.root)
        # Binary STL stores float32 coordinates. Do not silently lose roots or holes
        # at large offsets; 0.0001 mm is the maximum per-coordinate export error.
        with np.errstate(over='ignore', invalid='ignore'):
            stl_vertices = mesh.vertices.astype(np.float32).astype(np.float64)
        if (not np.isfinite(stl_vertices).all()
                or not np.allclose(stl_vertices, mesh.vertices, atol=.0001, rtol=0)):
            raise ValueError('STL coordinate precision exceeds 0.0001 mm; use a reviewed local frame')
        data = mesh.export(file_type='stl')
        # Validate the serialized artifact too: a small coordinate error can
        # still close a narrow hole or erase a very shallow buried root.
        saved = trimesh.load_mesh(io.BytesIO(data), file_type='stl', process=True)
        if (not saved.is_watertight or not saved.is_winding_consistent
                or not math.isfinite(saved.volume) or saved.volume <= 0
                or saved.euler_number != mesh.euler_number
                or saved.body_count != mesh.body_count):
            raise ValueError('STL serialization changes solid topology; use a reviewed local frame or wider features')
        if not saved.bounds[0, 2] < args.surface_z < saved.bounds[1, 2]:
            raise ValueError('STL serialization loses the requested buried root or exposed rise')
        info.update(export_bounds_mm=saved.bounds.tolist(), export_watertight=True,
                    stl_max_coordinate_error_mm=float(np.max(np.abs(stl_vertices-mesh.vertices))))
        # Exclusive creation also rejects a path that appeared after the earlier check.
        with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as target:
            target.write(data)
    except (ValueError, OSError) as exc:
        parser.exit(2, f'{exc}\n')
    print(json.dumps(info, indent=2))


if __name__ == '__main__':
    main()
