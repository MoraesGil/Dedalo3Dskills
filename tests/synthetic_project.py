"""New toy geometry for tests only; no downloaded or production model assets."""
from __future__ import annotations

import io
import json
import math
import zipfile

import trimesh
from lxml import etree as E

CORE = 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
PROD = 'http://schemas.microsoft.com/3dmanufacturing/production/2015/06'
Q = lambda x: '{' + CORE + '}' + x
ROOT_ID = 1000
IDENTITY = '1 0 0 0 1 0 0 0 1 0 0 0'


def metadata(node, key, value):
    E.SubElement(node, 'metadata', key=key, value=str(value))


def encode_members(data):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, blob in data.items():
            archive.writestr(name, blob)
    return stream.getvalue()


def make_project(*, octopus=False, negative=False, plate_count=1, transform=None):
    model = E.Element(Q('model'), nsmap={None: CORE, 'p': PROD}, unit='millimeter')
    resources = E.SubElement(model, Q('resources'))
    config = E.Element('config')
    root_settings = E.SubElement(config, 'object', id=str(ROOT_ID))
    metadata(root_settings, 'name', 'Synthetic radial test' if octopus else 'Synthetic grip test')
    metadata(root_settings, 'extruder', 1)
    root = E.Element(Q('object'), id=str(ROOT_ID), type='model')
    components = E.SubElement(root, Q('components'))

    def add_part(mesh, subtype='normal_part', paint=False):
        oid = len(resources) + 1
        obj = E.SubElement(resources, Q('object'), id=str(oid), type='model')
        native = E.SubElement(obj, Q('mesh'))
        vv = E.SubElement(native, Q('vertices'))
        ff = E.SubElement(native, Q('triangles'))
        for point in mesh.vertices:
            E.SubElement(vv, Q('vertex'), **dict(zip('xyz', (format(float(v), '.15g') for v in point))))
        for index, face in enumerate(mesh.faces):
            attrs = dict(zip(('v1', 'v2', 'v3'), map(str, face)))
            if paint and index == 0:
                attrs['paint_color'] = '2'
            E.SubElement(ff, Q('triangle'), **attrs)
        E.SubElement(components, Q('component'), objectid=str(oid), transform=IDENTITY)
        part = E.SubElement(root_settings, 'part', id=str(oid), subtype=subtype)
        metadata(part, 'name', 'Synthetic part ' + str(oid))
        metadata(part, 'extruder', 1)

    body = trimesh.creation.cylinder(radius=19 if octopus else 10, height=30, sections=64)
    body.apply_translation([0, 0, 15])
    add_part(body, paint=True)
    if octopus:
        # Forty disconnected toy cylinders, not tentacle or client mesh copies.
        rings = [22.0, 30.7, 38.7, 45.9, 52.5]
        for angle in range(0, 360, 45):
            theta = math.radians(angle)
            for radius in rings:
                segment = trimesh.creation.cylinder(radius=2, height=6, sections=16)
                segment.apply_translation([radius * math.cos(theta), radius * math.sin(theta), 3])
                add_part(segment)
    if negative:
        void = trimesh.creation.cylinder(radius=2, height=8, sections=16)
        void.apply_translation([0, 0, 26])
        add_part(void, subtype='negative_part')
    resources.append(root)
    build = E.SubElement(model, Q('build'))
    E.SubElement(build, Q('item'), objectid=str(ROOT_ID),
                 transform=transform or '1 0 0 0 1 0 0 0 1 70 70 0', printable='1')
    for pid in range(1, plate_count + 1):
        plate = E.SubElement(config, 'plate')
        metadata(plate, 'plater_id', pid)
        metadata(plate, 'plater_name', 'Synthetic plate ' + str(pid))
        if pid == 1:
            instance = E.SubElement(plate, 'model_instance')
            for key, value in [('object_id', ROOT_ID), ('instance_id', 0), ('identify_id', 1)]:
                metadata(instance, key, value)
    settings = {'filament_colour': ['#FFD400', '#202020'], 'filament_type': ['PETG', 'PETG'],
                'printable_area': ['0x0', '270x0', '270x270', '0x270'],
                'wipe_tower_x': ['210'] * plate_count, 'wipe_tower_y': ['210'] * plate_count,
                'printer_settings_id': 'Synthetic test machine', 'support_multi_bed_types': '1'}
    return {'3D/3dmodel.model': E.tostring(model, xml_declaration=True, encoding='UTF-8'),
            'Metadata/model_settings.config': E.tostring(config, xml_declaration=True, encoding='UTF-8'),
            'Metadata/project_settings.config': json.dumps(settings).encode()}
