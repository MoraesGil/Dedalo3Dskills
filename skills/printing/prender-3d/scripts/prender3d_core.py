"""Native-support 3MF modifiers only; no solid collars, file I/O or slicing.

Coordinates and the supplied frame are root-local millimetres. Every target
build must be upright, rigid and seated at world Z=0. Callers own source hashes,
open-document checks, process selection and native toolpath/physical validation.
The input ZIP-member dict changes only after the complete revision validates.
"""
from __future__ import annotations

import json
import math
import posixpath
import re
import uuid
from urllib.parse import unquote, urlsplit

import numpy as np
from lxml import etree as E

CORE = 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
PROD = 'http://schemas.microsoft.com/3dmanufacturing/production/2015/06'
NS = {'m': CORE}
Q = lambda s: '{' + CORE + '}' + s
IDENTITY = '1 0 0 0 1 0 0 0 1 0 0 0'
MAIN = '3D/3dmodel.model'
CONFIG = 'Metadata/model_settings.config'
PROVENANCE = 'Metadata/Prender3D.json'
RELS = '3D/_rels/3dmodel.model.rels'
PACKAGE = 'http://schemas.openxmlformats.org/package/2006/relationships'
MODEL_REL = 'http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel'
EPS = 1e-7


def md(node, key, value):
    """Set one native metadata value, rejecting ambiguous duplicate keys."""
    items = node.xpath('./metadata[@key=$key]', key=key)
    if len(items) > 1:
        raise ValueError('Duplicate metadata: ' + key)
    item = items[0] if items else E.SubElement(node, 'metadata', key=key)
    item.set('value', str(value))


def matrix(text):
    """Decode a finite, nonsingular 3MF 4x3 transform to a 4x4 matrix."""
    try:
        values = np.asarray(list(map(float, text.split())) if text else
                            [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0])
    except (TypeError, ValueError) as exc:
        raise ValueError('Invalid 3MF transform') from exc
    if values.shape != (12,) or not np.isfinite(values).all():
        raise ValueError('Invalid 3MF transform')
    result = np.eye(4)
    result[:3, :] = values.reshape(4, 3).T
    if abs(np.linalg.det(result[:3, :3])) < 1e-12:
        raise ValueError('Singular 3MF transform')
    return result


def _array(value, shape, label):
    try:
        result = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError('Invalid ' + label) from exc
    if result.shape != shape or not np.isfinite(result).all():
        raise ValueError('Invalid ' + label)
    return result


def _positive(value, label):
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('Invalid ' + label) from exc
    if not math.isfinite(number) or number <= 0:
        raise ValueError('Expected positive finite ' + label)
    return number


def _id(value):
    if isinstance(value, bool) or not re.fullmatch(r'[1-9][0-9]*', str(value)):
        raise ValueError('Expected a positive integer object ID')
    return int(value)


def mesh(resource, oid, v, f):
    """Append a finite indexed triangle mesh; preserve the established API."""
    oid = _id(oid)
    try:
        vertices = np.asarray(v, dtype=float)
        faces = np.asarray(f, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError('Invalid mesh arrays') from exc
    if (vertices.ndim != 2 or vertices.shape[1:] != (3,) or len(vertices) < 3
            or not np.isfinite(vertices).all() or faces.ndim != 2
            or faces.shape[1:] != (3,) or not len(faces)
            or not np.isfinite(faces).all() or not np.equal(faces, np.floor(faces)).all()
            or faces.min() < 0 or faces.max() >= len(vertices)):
        raise ValueError('Invalid vertices or triangle indices')
    faces = faces.astype(np.int64)
    triangles = vertices[faces]
    areas = np.linalg.norm(np.cross(triangles[:, 1] - triangles[:, 0],
                                    triangles[:, 2] - triangles[:, 0]), axis=1)
    if np.any(areas <= 1e-12):
        raise ValueError('Degenerate mesh triangle')
    if resource.find(f"m:object[@id='{oid}']", NS) is not None:
        raise ValueError('Duplicate generated mesh ID')
    obj = E.SubElement(resource, Q('object'), id=str(oid), type='model')
    native = E.SubElement(obj, Q('mesh'))
    vv = E.SubElement(native, Q('vertices'))
    tt = E.SubElement(native, Q('triangles'))
    for xyz in vertices:
        E.SubElement(vv, Q('vertex'), **dict(zip('xyz', (f'{x:.15g}' for x in xyz))))
    for tri in faces:
        E.SubElement(tt, Q('triangle'), **dict(zip(('v1', 'v2', 'v3'), map(str, tri))))


def cube(resource, oid, size, center, angle=0):
    size = _array(size, (3,), 'cube size')
    center = _array(center, (3,), 'cube center')
    if np.any(size <= 0) or not math.isfinite(float(angle)):
        raise ValueError('Cube dimensions and angle must be finite and positive')
    vertices = np.array([[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
                         [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]]) * size / 2
    a = math.radians(float(angle))
    rotation = np.array([[math.cos(a), -math.sin(a), 0],
                         [math.sin(a), math.cos(a), 0], [0, 0, 1]])
    vertices = vertices @ rotation.T + center
    faces = [[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4],
             [1, 2, 6], [1, 6, 5], [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]]
    mesh(resource, oid, vertices, faces)


def cylinder(resource, oid, radius, height, center, segments=96):
    radius = _positive(radius, 'cylinder radius')
    height = _positive(height, 'cylinder height')
    center = _array(center, (3,), 'cylinder center')
    if isinstance(segments, bool) or int(segments) != segments or not 3 <= segments <= 4096:
        raise ValueError('Cylinder segments must be an integer from 3 to 4096')
    segments = int(segments)
    angles = np.arange(segments) * 2 * np.pi / segments
    ring = np.c_[np.cos(angles) * radius, np.sin(angles) * radius]
    vertices = np.vstack([np.c_[ring, np.full(segments, -height / 2)],
                          np.c_[ring, np.full(segments, height / 2)],
                          [[0, 0, -height / 2], [0, 0, height / 2]]]) + center
    faces = []
    for i in range(segments):
        j = (i + 1) % segments
        faces.extend([[i, j, segments + j], [i, segments + j, segments + i],
                      [2 * segments, j, i], [2 * segments + 1, segments + i, segments + j]])
    mesh(resource, oid, vertices, faces)


def _xml(blob):
    return E.fromstring(blob, E.XMLParser(resolve_entities=False, no_network=True))


def _bytes(node):
    return E.tostring(node, encoding='UTF-8', xml_declaration=True)


def _metadata(node):
    result = {}
    for item in node.findall('metadata'):
        key = item.get('key')
        if key in result:
            raise ValueError('Duplicate native metadata: ' + str(key))
        result[key] = item.get('value', '')
    return result


def _reference(current, target):
    if not target:
        return current
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError('Only package-local resource references are supported')
    path = unquote(parsed.path)
    member = posixpath.normpath(path.lstrip('/') if path.startswith('/') else
                               posixpath.join(posixpath.dirname(current), path))
    if member.startswith('../') or member in ('', '.'):
        raise ValueError('Unsafe package resource reference')
    return member


def _profile(value):
    # Profiles carry parameters and labels, not copied geometry or a mesh dump.
    def inspect(item):
        if isinstance(item, dict):
            if any(str(k).lower() in {'mesh', 'meshes', 'vertices', 'faces', 'triangles'} for k in item):
                raise ValueError('Profile must not contain mesh arrays')
            for child in item.values():
                inspect(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                inspect(child)
    inspect(value)
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError('Profile must be finite JSON data') from exc
    if len(encoded.encode('utf-8')) > 32768:
        raise ValueError('Profile must be compact; no geometry dump')
    return json.loads(encoded)


def _invalidate(candidate, plates):
    removed = set()
    for name in list(candidate):
        per_plate = any(re.fullmatch(
            rf'Metadata/(?:plate|top|pick)_{pid}(?:[_.].*)?\.(?:gcode(?:\.md5)?|json|png|jpe?g|webp)',
            name, flags=re.I) for pid in plates)
        if per_plate or name == 'Metadata/slice_info.config' or re.fullmatch(
                r'Metadata/thumbnail(?:_small)?\.(?:png|jpe?g|webp)', name, flags=re.I):
            removed.add(name)
            del candidate[name]
    # Keep package relationships consistent when preview/cache members disappear.
    for name, blob in list(candidate.items()):
        if not name.endswith('.rels'):
            continue
        rels = _xml(blob)
        base = posixpath.dirname(posixpath.dirname(name))
        source = posixpath.join(base, posixpath.basename(name)[:-5])
        changed = False
        for item in list(rels):
            if item.get('TargetMode') != 'External' and _reference(source, item.get('Target')) in removed:
                rels.remove(item)
                changed = True
        if changed:
            candidate[name] = _bytes(rels)
    if '[Content_Types].xml' in candidate:
        types = _xml(candidate['[Content_Types].xml'])
        changed = False
        for item in list(types):
            if item.get('PartName', '').lstrip('/') in removed:
                types.remove(item)
                changed = True
        if changed:
            candidate['[Content_Types].xml'] = _bytes(types)
    return sorted(removed)


def _content_types(candidate, model_member):
    namespace = 'http://schemas.openxmlformats.org/package/2006/content-types'
    types = (_xml(candidate['[Content_Types].xml']) if '[Content_Types].xml' in candidate else
             E.Element('{' + namespace + '}Types', nsmap={None: namespace}))
    wanted = {model_member: 'application/vnd.ms-package.3dmanufacturing-3dmodel+xml',
              PROVENANCE: 'application/json', RELS: 'application/vnd.openxmlformats-package.relationships+xml'}
    for member, mime in wanted.items():
        extension = member.rsplit('.', 1)[1]
        explicit = [e for e in types if e.get('PartName') == '/' + member]
        defaults = [e for e in types if e.get('Extension') == extension]
        if len(explicit) > 1 or len(defaults) > 1:
            raise ValueError('Ambiguous content type for generated member')
        if explicit:
            if explicit[0].get('ContentType') != mime:
                raise ValueError('Conflicting generated-member content type')
        elif not defaults:
            E.SubElement(types, '{' + namespace + '}Default', Extension=extension, ContentType=mime)
        elif defaults[0].get('ContentType') != mime:
            E.SubElement(types, '{' + namespace + '}Override', PartName='/' + member, ContentType=mime)
    candidate['[Content_Types].xml'] = _bytes(types)


def apply_regions(data, root_id, frame, regions, settings, *, owner='Prender3D',
                  existing_roles=None, height_limit_mm,
                  allow_sacrificial_normal_parts=False, profile=None):
    """Apply explicit auxiliary shapes to one configured multipart root.

    regions: dicts with role/label/subtype/shape/values; shape is cube, cylinder or
    mesh with the same positional arguments as the public geometry helpers.
    Existing IDs may be adopted only from this owner's signed parts in this root.
    Only support_enforcer/support_blocker regions are accepted. The deprecated
    allow_sacrificial_normal_parts keyword must stay False; it cannot authorize
    a solid collar or network. Material selection belongs to the root process
    support_filament/support_interface_filament settings, not region extruders.
    Signed legacy normal auxiliaries may be removed or converted to modifiers;
    unsigned product parts and foreign owners remain unchanged.
    Multiple owners coexist: per-part role markers recover older ownership when
    the compact root provenance entry records a newer owner's last application.
    Returns generated_ids, affected_plates, settings and native_slicing_required.
    No input bytes or dict entries change on validation failure.
    """
    if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, bytes) for k, v in data.items()):
        raise ValueError('Expected a ZIP-member dict of name:bytes')
    if not isinstance(allow_sacrificial_normal_parts, bool):
        raise ValueError('Sacrificial normal-part opt-in must be a boolean')
    if allow_sacrificial_normal_parts:
        raise ValueError('Deprecated normal-part opt-in is disabled; Prender3D creates native support only')
    rid = _id(root_id)
    if not isinstance(owner, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}', owner):
        raise ValueError('Owner must be a safe asset identifier')
    limit = _positive(height_limit_mm, 'height limit')
    try:
        bed, top = float(frame['bed_z_local']), float(frame['top_z_local'])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('Frame requires bed_z_local/top_z_local') from exc
    if not math.isfinite(bed) or not math.isfinite(top) or top <= bed:
        raise ValueError('Frame heights must be finite and ordered')
    if not isinstance(regions, (list, tuple)) or not isinstance(settings, dict):
        raise ValueError('Regions must be a sequence and settings a mapping')
    native_settings = {}
    for key, value in settings.items():
        if (not isinstance(key, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', key)
                or key in {'name', 'matrix', 'extruder', 'id', 'uuid'} or key.startswith(('source_', 'Prender3D'))):
            raise ValueError('Settings must contain process fields only')
        if not isinstance(value, (str, int, float, bool)) or (
                isinstance(value, (int, float)) and not math.isfinite(value)) or (
                isinstance(value, str) and re.fullmatch(r'[+-]?(?:nan|inf(?:inity)?)', value.strip(), re.I)):
            raise ValueError('Settings must be finite native scalar values')
        native_settings[key] = str(int(value)) if isinstance(value, bool) else str(value)
    try:
        root, cfg = _xml(data[MAIN]), _xml(data[CONFIG])
    except KeyError as exc:
        raise ValueError('Native model/settings members are required') from exc
    if root.get('unit', 'millimeter') != 'millimeter':
        raise ValueError('Explicit unit adaptation is required')
    objs = root.findall(f"m:resources/m:object[@id='{rid}']", NS)
    configs = cfg.findall(f"object[@id='{rid}']")
    if len(objs) != 1 or len(configs) != 1:
        raise ValueError('One configured multipart root is required')
    obj, ocfg = objs[0], configs[0]
    components = obj.find('m:components', NS)
    if components is None or obj.find('m:mesh', NS) is not None:
        raise ValueError('A multipart component root is required')
    builds = root.findall(f"m:build/m:item[@objectid='{rid}']", NS)
    if not builds:
        raise ValueError('The configured root has no build instances')
    for item in builds:
        transform = matrix(item.get('transform'))
        rotation = transform[:3, :3]
        if (not np.allclose(rotation[2], [0, 0, 1], atol=EPS, rtol=0)
                or not np.allclose(rotation[:2, 2], 0, atol=EPS, rtol=0)
                or not np.allclose(rotation.T @ rotation, np.eye(3), atol=EPS, rtol=0)
                or not math.isclose(float(np.linalg.det(rotation)), 1, abs_tol=EPS)
                or abs(transform[2, 3] + bed) > EPS):
            raise ValueError('Builds must be upright, unscaled, and seated on the plate')
    parts = {_id(p.get('id')): p for p in ocfg.findall('part')}
    refs = {_id(c.get('objectid')): c for c in components}
    if len(parts) != len(ocfg.findall('part')) or len(refs) != len(components):
        raise ValueError('Ambiguous duplicate component/part IDs')
    if parts.keys() != refs.keys():
        raise ValueError('Multipart root must have matching configured component IDs')
    signature = owner + ' | '
    owned = {pid for pid, p in parts.items() if _metadata(p).get('name', '').startswith(signature)}
    provenance = json.loads(data.get(PROVENANCE, b'{"schema":1,"roots":{}}'))
    if provenance.get('schema') != 1 or not isinstance(provenance.get('roots'), dict):
        raise ValueError('Unsupported Prender3D provenance schema')
    record = provenance['roots'].get(str(rid), {})
    own_record = record if record.get('owner') == owner else {}
    roles = dict(own_record.get('roles', {}))
    for pid in owned:
        metadata = _metadata(parts[pid])
        role = metadata.get('Prender3D_role')
        if not role:
            tagged=re.match(r'^'+re.escape(signature)+r'\[([A-Za-z0-9_-]+)\] ',metadata.get('name',''))
            if tagged:role=tagged.group(1)
        if role:
            if role in roles and _id(roles[role]) != pid:
                raise ValueError('Conflicting owned role provenance')
            roles[role] = pid
    if existing_roles is not None:
        if not isinstance(existing_roles, dict):
            raise ValueError('existing_roles must map roles to signed part IDs')
        for role, pid in existing_roles.items():
            if role in roles and _id(roles[role]) != _id(pid):
                raise ValueError('Explicit role conflicts with provenance')
            roles[role] = _id(pid)
    roles = {role: _id(pid) for role, pid in roles.items()}
    if len(set(roles.values())) != len(roles) or any(pid not in owned for pid in roles.values()):
        raise ValueError('Role IDs must be distinct signed auxiliaries in this root')
    for pid in owned:
        metadata = _metadata(parts[pid])
        if metadata.get('Prender3D_owner', owner) != owner or metadata.get('Prender3D_root', str(rid)) != str(rid):
            raise ValueError('Ownership marker conflicts with target root')
    owned_normal = {pid for pid in owned if parts[pid].get('subtype') == 'normal_part'}
    effective_profile = _profile(profile if profile is not None else own_record.get('profile'))
    plate_ids, memberships = set(), []
    for plate in cfg.findall('plate'):
        for instance in plate.findall('model_instance'):
            metadata = _metadata(instance)
            if metadata.get('object_id') == str(rid):
                memberships.append(int(metadata['instance_id']))
                plate_ids.add(_id(_metadata(plate).get('plater_id')))
    if sorted(memberships) != list(range(len(builds))):
        raise ValueError('Complete, unique plate memberships are required')
    path = f'/3D/Objects/{owner}_root_{rid}.model'
    member = path.lstrip('/')
    if member in data:
        prior = _xml(data[member])
        if any(_id(o.get('id')) not in owned for o in prior.findall('m:resources/m:object', NS)):
            raise ValueError('Generated asset contains a resource not owned by this root')
        for other in root.findall('m:resources/m:object', NS):
            for component in other.findall('m:components/m:component', NS):
                if _reference(MAIN, component.get('{' + PROD + '}path')) == member and (
                        other is not obj or _id(component.get('objectid')) not in owned):
                    raise ValueError('Owned asset is shared outside the selected auxiliary scope')
    used = {_id(o.get('id')) for o in root.findall('m:resources/m:object', NS)}
    used |= {_id(p.get('id')) for p in cfg.findall('object/part')}
    used |= {_id(c.get('objectid')) for c in root.findall('.//m:component', NS)}
    nextid = max(used, default=0) + 1
    asset = E.Element(Q('model'), nsmap={None: CORE}, unit='millimeter')
    resource = E.SubElement(asset, Q('resources'))
    generated, bounds = {}, {}
    for region in regions:
        if not isinstance(region, dict):
            raise ValueError('Every region must be a mapping')
        role, label = region.get('role'), region.get('label')
        if (not isinstance(role, str) or not role or len(role) > 128 or any(ord(c) < 32 for c in role)
                or role in generated or not isinstance(label, str) or not label or len(label) > 256):
            raise ValueError('Region roles and labels must be nonempty and unique')
        subtype = region.get('subtype')
        if subtype not in {'support_enforcer', 'support_blocker'}:
            raise ValueError('Prender3D creates native support only: use support_enforcer or support_blocker; normal_part is prohibited')
        if 'extruder' in region:
            raise ValueError('Choose native support material with root support_filament/support_interface_filament, not region extruder')
        shape, values = region.get('shape'), region.get('values')
        arities = {'cube': {2, 3}, 'cylinder': {3, 4}, 'mesh': {2}}
        if not isinstance(shape, str) or shape not in arities or not isinstance(values, (list, tuple)) or len(values) not in arities[shape]:
            raise ValueError('Invalid auxiliary shape/arguments')
        if role in roles:
            pid = roles[role]
        else:
            while nextid in used:
                nextid += 1
            pid = nextid
            used.add(pid)
            nextid += 1
        {'cube': cube, 'cylinder': cylinder, 'mesh': mesh}[shape](resource, pid, *values)
        vertices = resource.find(f"m:object[@id='{pid}']/m:mesh/m:vertices", NS)
        z = [float(v.get('z')) for v in vertices]
        lo, hi = min(z), max(z)
        if hi <= lo or (subtype != 'support_blocker' and (lo < bed - EPS or hi > bed + limit + EPS)):
            raise ValueError('Auxiliary lies outside its allowed Z interval')
        component = refs.get(pid)
        if component is None:
            component = E.SubElement(components, Q('component'), objectid=str(pid),
                                     attrib={'{' + PROD + '}UUID': str(uuid.uuid4())})
        component.set('{' + PROD + '}path', path)
        component.set('transform', IDENTITY)
        part = parts.get(pid)
        if part is None:
            part = E.SubElement(ocfg, 'part', id=str(pid), subtype=subtype)
        part.set('subtype', subtype)
        md(part, 'name', signature + ('['+role+'] 'if owner=='Prender3D'else'') + label)
        # A modifier does not own a normal-part material, including after migration.
        md(part, 'extruder', '0')
        md(part, 'matrix', ' '.join(map(str, np.eye(4).ravel())))
        md(part, 'Prender3D_owner', owner)
        md(part, 'Prender3D_root', rid)
        md(part, 'Prender3D_role', role)
        generated[role] = pid
        bounds[role] = [lo, hi]
    for pid in owned - set(generated.values()):
        components.remove(refs[pid])
        ocfg.remove(parts[pid])
    for key, value in native_settings.items():
        md(ocfg, key, value)
    provenance['roots'][str(rid)] = {'owner': owner, 'height_limit_mm': limit,
                                    'roles': generated, 'profile': effective_profile}
    candidate = dict(data)
    candidate[MAIN], candidate[CONFIG] = _bytes(root), _bytes(cfg)
    candidate[member] = _bytes(asset)
    candidate[PROVENANCE] = (json.dumps(provenance, ensure_ascii=False, allow_nan=False,
                                      sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')
    rels = _xml(candidate[RELS]) if RELS in candidate else E.Element('{' + PACKAGE + '}Relationships', nsmap={None: PACKAGE})
    if not any(_reference(MAIN, rel.get('Target')) == member for rel in rels):
        rid_text = f'{owner}-root-{rid}'
        taken = {rel.get('Id') for rel in rels}
        while rid_text in taken:
            rid_text += '-aux'
        E.SubElement(rels, '{' + PACKAGE + '}Relationship', Id=rid_text, Type=MODEL_REL, Target=path)
    candidate[RELS] = _bytes(rels)
    invalidated = _invalidate(candidate, plate_ids)
    _content_types(candidate, member)
    result = {'root_id': rid, 'generated_ids': dict(generated), 'settings': native_settings,
              'height_limit_mm': limit, 'affected_plates': sorted(plate_ids),
              'auxiliary_z_bounds_local_mm': bounds, 'invalidated_members': invalidated,
              'asset_member': member, 'native_slicing_required': True,
              'native_support_only': True,
              'removed_owned_part_ids': sorted(owned - set(generated.values())),
              'converted_owned_normal_part_ids': sorted(owned_normal & set(generated.values()))}
    # All operations above use parsed copies or candidate bytes; publish only now.
    data.clear()
    data.update(candidate)
    return result
