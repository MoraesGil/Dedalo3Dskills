"""Stage explicit native retention modifiers on one existing multipart root.

Coordinates in the reviewed regions JSON are root-local millimetres. The helper
measures the positive product's bed/top only; it does not choose safe contacts,
subtract functional negatives, rotate parts, create a grid, slice, or publish.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path

from geometry_project import Project
from prender3d_core import apply_regions


def digest(data):
    return hashlib.sha256(data).hexdigest()


def scratch_path(path, *, source):
    path = Path(path).resolve()
    roots = {Path('/tmp').resolve(), Path(tempfile.gettempdir()).resolve()}
    if path == source or path.exists() or not any(path.is_relative_to(p) for p in roots):
        raise ValueError('A new output in the system temporary directory is required')
    if not path.parent.is_dir():
        raise ValueError('Create the private scratch directory before staging')
    return path


def write_exclusive(path, data):
    """Write one new private file without replacing a concurrent output."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        Path(path).unlink(missing_ok=True)
        raise


def prepare(source, output, expected_sha256, root_id, regions, process, height_mm):
    source = Path(source).resolve()
    output = scratch_path(output, source=source)
    if not isinstance(expected_sha256, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', expected_sha256):
        raise ValueError('Supply the complete current source SHA-256')
    raw = source.read_bytes()
    expected_sha256 = expected_sha256.lower()
    if digest(raw) != expected_sha256:
        raise ValueError('Source hash changed')
    if not isinstance(regions, list) or not regions:
        raise ValueError('Regions JSON must be a nonempty list of explicit native modifiers')
    if not isinstance(process, dict) or not process:
        raise ValueError('A reviewed native process mapping is required')
    if not all(isinstance(key, str) for key in process):
        raise ValueError('Native process field names must be strings')
    if process.get('support_type') not in {'tree(manual)', 'normal(manual)'}:
        raise ValueError('An explicit native manual support process is required')
    enabled = process.get('enable_support')
    if not (enabled is True or enabled == 1 or enabled == '1'):
        raise ValueError('The reviewed process must explicitly enable native support')
    allowed_prefixes = ('support_', 'tree_support_', 'brim_', 'raft_')
    if any('gcode' in key.lower() or key == 'support_multi_bed_types' or
           not (key in {'enable_support', 'independent_support_layer_height'} or
                key.startswith(allowed_prefixes)) for key in process):
        raise ValueError('Retention settings cannot replace machine or material integration')
    if str(process.get('raft_layers', '0')).strip() not in {'0', '0.0', 'False'}:
        raise ValueError('Prender3D uses native supports and brim, not a printable raft')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        if len(entries) != len({p.filename for p in entries}):
            raise ValueError('Duplicate ZIP members are not supported')
        if len(entries) > 10000 or sum(p.file_size for p in entries) > 2 * 1024**3:
            raise ValueError('Project exceeds this staging helper resource limit')
        data = {p.filename: archive.read(p) for p in entries}
    settings = json.loads(data['Metadata/project_settings.config'])
    slots = len(settings.get('filament_colour', []))
    for field in ('support_filament', 'support_interface_filament'):
        value = process.get(field)
        if isinstance(value, bool) or not re.fullmatch(r'[1-9][0-9]*', str(value)) or not 1 <= int(value) <= slots:
            raise ValueError('Choose explicit existing physical support and interface filament slots')
    geometry = Project(raw)
    try:
        if geometry.unit != 'millimeter':
            raise ValueError('Explicit millimetre unit adaptation is required')
        components = geometry.components(int(root_id))
        if not components:
            raise ValueError('The selected root has no positive product geometry')
        bed = min(float(mesh.bounds[0, 2]) for mesh, _ in components)
        top = max(float(mesh.bounds[1, 2]) for mesh, _ in components)
    finally:
        geometry.zip.close()
    result = apply_regions(data, root_id, {'bed_z_local': bed, 'top_z_local': top},
                           regions, process, height_limit_mm=height_mm)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in data.items():
            archive.writestr(name, payload)
    payload = stream.getvalue()
    if digest(source.read_bytes()) != expected_sha256:
        raise ValueError('Source changed while staging; renew the input')
    write_exclusive(output, payload)
    if digest(source.read_bytes()) != expected_sha256:
        output.unlink()
        raise ValueError('Source changed while writing; staged output discarded')
    return {**result, 'source_sha256': expected_sha256,
            'output_sha256': digest(payload), 'measured_frame': {'bed_z_local': bed, 'top_z_local': top},
            'product_orientation_changed': False, 'physical_validation': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--expect-sha256', required=True)
    parser.add_argument('--root-id', required=True, type=int)
    parser.add_argument('--regions-json', required=True, type=Path)
    parser.add_argument('--process-json', required=True, type=Path)
    parser.add_argument('--height-mm', required=True, type=float)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if args.report:
        report_path = scratch_path(args.report, source=args.source.resolve())
        if report_path == args.output.resolve():
            raise ValueError('Report and project output must be distinct')
    result = prepare(args.source, args.output, args.expect_sha256, args.root_id,
                     json.loads(args.regions_json.read_text()),
                     json.loads(args.process_json.read_text()), args.height_mm)
    if args.report:
        write_exclusive(report_path, (json.dumps(result, indent=2, ensure_ascii=False) + '\n').encode())
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
