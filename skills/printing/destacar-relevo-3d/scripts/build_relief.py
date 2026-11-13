"""Build one planar relief mesh from a reviewed millimetre polygon, not an image or 3MF."""
import argparse
import json
import math
import os
from pathlib import Path
import tempfile

from shapely.geometry import Polygon
import trimesh


def build(mask, *, mode, width, surface_z, rise, root):
    """Return a closed mesh and measurements; retain every explicit hole."""
    if not all(math.isfinite(x) for x in (surface_z, rise, root)) or rise <= 0 or root <= 0:
        raise ValueError('surface_z must be finite; rise and root must be finite and positive')
    try:
        points = [mask['outer'], *mask.get('holes', [])]
        if any(len(p) != 2 or not all(math.isfinite(x) for x in p) for r in points for p in r):
            raise ValueError('polygon points must be finite XY pairs in millimetres')
        polygon = Polygon(points[0], points[1:])
    except (KeyError, TypeError) as exc:
        raise ValueError('mask needs outer and optional holes rings') from exc
    if polygon.is_empty or not polygon.is_valid or polygon.area <= 0:
        raise ValueError('mask must be a nonempty valid polygon; do not silently repair the art')
    if mode == 'outline':
        if width is None or not math.isfinite(width) or width <= 0:
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
    pieces = [shape] if shape.geom_type == 'Polygon' else list(shape.geoms)
    meshes = []
    for piece in pieces:
        part = trimesh.creation.extrude_polygon(piece, height=rise + root, engine='earcut')
        part.apply_translation([0, 0, surface_z - root])
        meshes.append(part)
    mesh = trimesh.util.concatenate(meshes)
    if not mesh.is_watertight or not mesh.is_winding_consistent or mesh.volume <= 0:
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
    output = args.output.resolve()
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
        # Exclusive creation also rejects a path that appeared after the earlier check.
        with output.open('xb') as target:
            target.write(mesh.export(file_type='stl'))
    except (ValueError, OSError) as exc:
        parser.exit(2, f'{exc}\n')
    print(json.dumps(info, indent=2))


if __name__ == '__main__':
    main()
