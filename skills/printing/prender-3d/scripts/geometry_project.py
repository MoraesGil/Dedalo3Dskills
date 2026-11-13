"""Read-only, recursive positive-mesh geometry from a 3MF project.

Measurement copies only; negative/modifier parts remain excluded, not applied as
booleans. Callers must protect functional voids and preserve original ZIP bytes.
"""
import hashlib,io,math,pathlib,posixpath,urllib.parse,zipfile
import numpy as np
import trimesh
from lxml import etree as E
CORE='http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
PROD='{http://schemas.microsoft.com/3dmanufacturing/production/2015/06}'
NS={'m':CORE};MAIN='3D/3dmodel.model';NORMAL={'normal_part','model',''}
MAX_FACES=5_000_000;MAX_COMPONENTS=2048

class GeometryError(ValueError):
    """A safe technical reason, never raw XML or user metadata."""


def conformal_blocker(body, lower_z, upper_z, *, margin_mm=.6,
                      center_xy=None, shape='auto', segments=128):
    """Describe a conservative modifier around the measured positive XY outline.

    Use a circle for a radial body, otherwise a rounded convex contour. Explicit
    cylinder mode is for a geometrically confirmed radial target, such as the
    Magic Wand octopus. The complete positive projection is used, not just an
    arbitrary bounding box or the visible top part. Functional negatives are
    intentionally not booleans here. Callers still own keepouts, neighbouring
    tower/part intersection checks, and fresh native support validation.

    Returns (shape descriptor accepted by apply_regions, measurement metadata).
    This constructs a slicing mask only; it never changes the product mesh.
    """
    from shapely.geometry import MultiPoint
    points=np.asarray(body.vertices,dtype=float)
    if points.ndim!=2 or points.shape[1:]!=(3,) or not len(points) or not np.isfinite(points).all():
        raise GeometryError('invalid_contour_measurement_vertices')
    lower_z,upper_z,margin_mm=map(float,(lower_z,upper_z,margin_mm))
    if not all(map(math.isfinite,(lower_z,upper_z,margin_mm))) or upper_z<=lower_z or margin_mm<0:
        raise GeometryError('invalid_contour_blocker_band_or_margin')
    if shape not in {'auto','cylinder','contour'}:
        raise GeometryError('choose_auto_cylinder_or_contour_blocker')
    if isinstance(segments,bool) or int(segments)!=segments or not 16<=segments<=4096:
        raise GeometryError('invalid_contour_circle_segments')
    segments=int(segments)
    xy=points[:,:2]
    hull=MultiPoint(xy).convex_hull
    if hull.geom_type!='Polygon' or hull.area<=1e-9:
        raise GeometryError('degenerate_positive_xy_outline')
    center=(xy.min(axis=0)+xy.max(axis=0))/2 if center_xy is None else np.asarray(center_xy,dtype=float)
    if center.shape!=(2,) or not np.isfinite(center).all():
        raise GeometryError('invalid_contour_center')
    # Native cylinders are inscribed polygons. Compensate the apothem so the
    # projected product and declared margin are inside every cylinder facet.
    required_radius=float(np.linalg.norm(xy-center,axis=1).max())+margin_mm
    radius=required_radius/math.cos(math.pi/segments)
    round_outline=hull.buffer(margin_mm,resolution=16) if margin_mm else hull
    circle_area=segments*radius*radius*math.sin(2*math.pi/segments)/2
    selected='cylinder' if shape=='cylinder' or (shape=='auto' and circle_area/round_outline.area<=1.15) else 'contour'
    if selected=='cylinder':
        descriptor={'shape':'cylinder','values':[radius,upper_z-lower_z,[*center,(lower_z+upper_z)/2],segments]}
        a=np.arange(segments)*2*np.pi/segments
        outline=np.c_[np.cos(a)*radius,np.sin(a)*radius]+center
        from shapely.geometry import Polygon
        polygon=Polygon(outline)
    else:
        from shapely.geometry.polygon import orient
        polygon=orient(round_outline,sign=1.)
        outline=np.asarray(polygon.exterior.coords[:-1],dtype=float)
        n=len(outline);middle=np.asarray(polygon.representative_point().coords[0])
        vertices=np.vstack([np.c_[outline,np.full(n,lower_z)],
                            np.c_[outline,np.full(n,upper_z)],
                            [[*middle,lower_z],[*middle,upper_z]]])
        faces=[]
        for i in range(n):
            j=(i+1)%n
            faces.extend([[i,j,n+j],[i,n+j,n+i],[2*n,j,i],[2*n+1,n+i,n+j]])
        descriptor={'shape':'mesh','values':[vertices.tolist(),faces]}
    # Coverage is checked independently of the chosen primitive. A too-small
    # shape must fail here, not be accepted merely because it looks rounded.
    if not polygon.buffer(1e-8).covers(round_outline):
        raise GeometryError('contour_blocker_does_not_cover_product_margin')
    measurement={'basis':'complete_positive_product_xy_projection',
                 'shape':selected,'margin_mm':margin_mm,
                 'z_bounds_local_mm':[lower_z,upper_z],
                 'xy_bounds_local_mm':list(polygon.bounds),
                 'positive_hull_area_mm2':float(hull.area),
                 'mask_area_mm2':float(polygon.area),
                 'covers_positive_projection_and_margin':True}
    if selected=='cylinder':
        measurement.update(center_xy=center.tolist(),radius_mm=radius,segments=segments)
    return descriptor,measurement


def _matrix(value):
    if not value:return np.eye(4)
    a=np.fromstring(value,sep=' ')
    if len(a)!=12 or not np.isfinite(a).all():raise GeometryError('invalid_component_transform')
    m=np.eye(4);m[:3,:]=a.reshape(4,3).T
    if abs(np.linalg.det(m[:3,:3]))<1e-12:raise GeometryError('singular_component_transform')
    return m


def _metadata(element):
    return {x.get('key'):x.get('value')for x in element.findall('metadata')}



class Project:
    def __init__(self,path):
        self.source_bytes=bytes(path) if isinstance(path,(bytes,bytearray)) else pathlib.Path(path).read_bytes()
        self.sha256=hashlib.sha256(self.source_bytes).hexdigest()
        self.filename_exempt=False
        self.zip=zipfile.ZipFile(io.BytesIO(self.source_bytes))
        self.docs={};self.meshes={};self.splits={};self.excluded=set()
        self.xml_parser=E.XMLParser(resolve_entities=False,no_network=True,huge_tree=True)
        self.root=self.doc(MAIN)[0]
        unit=self.root.get('unit','millimeter')
        factors={'micron':.001,'millimeter':1.,'centimeter':10.,'meter':1000.,'inch':25.4,'foot':304.8}
        if unit not in factors:raise GeometryError('unsupported_model_unit')
        self.unit=unit;self.unit_mm=factors[unit]
        self.config={};self.plates={}
        if 'Metadata/model_settings.config' in self.zip.namelist():
            cfg=E.fromstring(self.zip.read('Metadata/model_settings.config'),self.xml_parser)
            for o in cfg.findall('object'):
                self.config[int(o.get('id'))]={'name':_metadata(o).get('name',''),'types':{int(p.get('id')):p.get('subtype','normal_part')for p in o.findall('part')}}
            for ordinal,plate in enumerate(cfg.findall('plate'),1):
                pid=int(_metadata(plate).get('plater_id',ordinal))
                for instance in plate.findall('model_instance'):
                    d=_metadata(instance)
                    if 'object_id'in d and 'instance_id'in d:self.plates.setdefault((int(d['object_id']),int(d['instance_id'])),[]).append(pid)
        self.instances={}
        counts={}
        for index,item in enumerate(self.root.findall('m:build/m:item',NS)):
            oid=int(item.get('objectid'));n=counts.get(oid,0);counts[oid]=n+1
            self.instances.setdefault(oid,[]).append({'build_index':index,'instance_id':n,'build_uuid':item.get(PROD+'UUID'),'printable':item.get('printable','1')!='0','transform_4x4':_matrix(item.get('transform')).tolist(),'plate_ids':sorted(set(self.plates.get((oid,n),[])))})

    @classmethod
    def from_members(cls,data):
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED)as archive:
            for name,blob in data.items():archive.writestr(name,blob)
        return cls(stream.getvalue())

    def doc(self,path):
        if path not in self.docs:
            if path not in self.zip.namelist():raise GeometryError('missing_mesh_resource')
            info=self.zip.getinfo(path)
            if info.file_size>512*1024*1024:raise GeometryError('xml_resource_size_limit')
            root=E.fromstring(self.zip.read(path),self.xml_parser)
            objects={int(o.get('id')):o for o in root.findall('m:resources/m:object',NS)}
            self.docs[path]=(root,objects)
        return self.docs[path]

    def resource(self,current,reference):
        if not reference:return current
        ref=urllib.parse.urlsplit(reference)
        if ref.scheme or ref.netloc or ref.query or ref.fragment:raise GeometryError('external_resource_reference_rejected')
        target=urllib.parse.unquote(ref.path)
        target=posixpath.normpath(target.lstrip('/')if target.startswith('/')else posixpath.join(posixpath.dirname(current),target))
        if target.startswith('../')or target in ('','.'):raise GeometryError('unsafe_resource_reference')
        return target

    def mesh_components(self,path,oid,obj):
        key=(path,oid)
        if key not in self.meshes:
            vertices=obj.findall('m:mesh/m:vertices/m:vertex',NS);triangles=obj.findall('m:mesh/m:triangles/m:triangle',NS)
            if len(triangles)>MAX_FACES:raise GeometryError('mesh_face_limit')
            v=np.array([[float(x.get(k))for k in ('x','y','z')]for x in vertices],dtype=float)
            f=np.array([[int(x.get(k))for k in ('v1','v2','v3')]for x in triangles],dtype=np.int64)
            if v.ndim!=2 or v.shape[1:]!=(3,)or len(v)==0 or f.ndim!=2 or f.shape[1:]!=(3,)or len(f)==0:raise GeometryError('empty_or_invalid_mesh')
            if not np.isfinite(v).all()or f.min()<0 or f.max()>=len(v):raise GeometryError('invalid_mesh_indices_or_vertices')
            mesh=trimesh.Trimesh(v,f,process=False)
            # Welding only this measurement copy also supports unwelded STL-derived 3MFs.
            mesh.merge_vertices(digits_vertex=8)
            self.meshes[key]=mesh
        if key not in self.splits:
            components=self.meshes[key].split(only_watertight=False)
            if len(components)>MAX_COMPONENTS:raise GeometryError('component_count_limit')
            self.splits[key]=components
        return self.splits[key]

    def components(self,root_id):
        self.excluded=set();result=[]
        def visit(path,oid,matrix,trail,active):
            key=(path,oid)
            if key in active:raise GeometryError('component_cycle')
            if len(active)>32:raise GeometryError('component_depth_limit')
            obj=self.doc(path)[1].get(oid)
            if obj is None:raise GeometryError('unresolved_object_id')
            if obj.find('m:mesh',NS)is not None:
                for number,source in enumerate(self.mesh_components(path,oid,obj)):
                    mesh=source.copy();mesh.apply_transform(matrix);mesh.vertices*=self.unit_mm
                    result.append((mesh,{'mesh_object_id':oid,'component_path_ids':trail,'connected_component_index':number}))
                return
            children=obj.find('m:components',NS)
            if children is None:raise GeometryError('object_without_mesh_or_components')
            types=self.config.get(oid,{}).get('types',{})
            for index,component in enumerate(children):
                cid=int(component.get('objectid'));subtype=types.get(cid,'normal_part')
                if subtype not in NORMAL:self.excluded.add(cid);continue
                visit(self.resource(path,component.get(PROD+'path')),cid,matrix@_matrix(component.get('transform')),trail+[cid],active|{key})
                if len(result)>MAX_COMPONENTS:raise GeometryError('root_component_count_limit')
        visit(MAIN,root_id,np.eye(4),[root_id],set())
        return result
