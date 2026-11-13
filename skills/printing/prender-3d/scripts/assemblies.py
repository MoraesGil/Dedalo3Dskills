"""Give every figure its own multipart root, without rewriting mesh resources.

The default only separates linked instances. Additional copies and layout changes
require explicit target_count/positions and one unambiguous production plate.
"""
from __future__ import annotations
import copy,uuid
import numpy as np
from lxml import etree as E

CORE='http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
PROD='{http://schemas.microsoft.com/3dmanufacturing/production/2015/06}'
NS={'m':CORE}

def metadata(node):
    return {m.get('key'):m.get('value')for m in node.findall('metadata')}

def setmd(node,key,value):
    items=node.xpath('./metadata[@key=$key]',key=key)
    if len(items)>1:raise ValueError('Duplicate metadata')
    item=items[0]if items else E.SubElement(node,'metadata',key=key)
    item.set('value',str(value))

def matrix(value):
    a=np.fromstring(value or '1 0 0 0 1 0 0 0 1 0 0 0',sep=' ')
    if len(a)!=12 or not np.isfinite(a).all():raise ValueError('Invalid build transform')
    m=np.eye(4);m[:3,:]=a.reshape(4,3).T
    return m

def encode(m):
    return ' '.join(f'{v:.12g}'for v in m[:3,:].T.ravel())

def separate(data,root_id,*,target_count=None,positions=None):
    root_id=str(root_id)
    root=E.fromstring(data['3D/3dmodel.model']);cfg=E.fromstring(data['Metadata/model_settings.config'])
    resource=root.find('m:resources',NS);build=root.find('m:build',NS)
    obj=resource.find(f"m:object[@id='{root_id}']",NS);ocfg=cfg.find(f"object[@id='{root_id}']")
    if obj is None or ocfg is None or obj.find('m:components',NS)is None:raise ValueError('A configured multipart root is required')
    items=build.findall(f"m:item[@objectid='{root_id}']",NS)
    if not items:raise ValueError('No build instances')
    if target_count is None:target_count=len(items)
    if target_count<len(items):raise ValueError('Removing existing figures is outside this helper')
    if positions is not None and len(positions)!=target_count:raise ValueError('One XY position per figure is required')
    if target_count!=len(items)and positions is None:raise ValueError('Additional figures require an explicit layout')
    plates={}
    maxidentify=0
    for plate in cfg.findall('plate'):
        for mi in plate.findall('model_instance'):
            meta=metadata(mi);maxidentify=max(maxidentify,int(meta.get('identify_id','0')))
            if meta.get('object_id')==root_id:
                key=int(meta['instance_id'])
                if key in plates:raise ValueError('An instance belongs to multiple plates')
                plates[key]=(plate,mi)
    if set(plates)!=set(range(len(items))):raise ValueError('Incomplete plate memberships')
    if positions is not None and len({id(p)for p,mi in plates.values()})!=1:raise ValueError('Layout requires one unambiguous plate')
    if target_count==1 and positions is None:return {'source_root_id':int(root_id),'root_ids':[int(root_id)],'independent':True,'mesh_resources_rewritten':False}
    used={int(o.get('id'))for o in resource.findall('m:object',NS)}|{int(p.get('id'))for p in cfg.findall('object/part')}
    nextid=max(used,default=0)+1
    assemble=cfg.find('assemble')
    if assemble is None:assemble=E.SubElement(cfg,'assemble')
    savedposes={int(a.get('instance_id')):copy.deepcopy(a)for a in assemble.findall(f"assemble_item[@object_id='{root_id}']")}
    for a in assemble.findall(f"assemble_item[@object_id='{root_id}']"):assemble.remove(a)
    result=[]
    source_obj=copy.deepcopy(obj);source_cfg=copy.deepcopy(ocfg);source_item=copy.deepcopy(items[0])
    source_plate,source_mi=plates[0]
    for index in range(target_count):
        if index==0:oid=root_id;outobj=obj;outcfg=ocfg
        else:
            while nextid in used:nextid+=1
            oid=str(nextid);used.add(nextid);nextid+=1
            outobj=copy.deepcopy(source_obj);outobj.set('id',oid);outobj.set(PROD+'UUID',str(uuid.uuid4()))
            for component in outobj.findall('m:components/m:component',NS):component.set(PROD+'UUID',str(uuid.uuid4()))
            resource.append(outobj)
            outcfg=copy.deepcopy(source_cfg);outcfg.set('id',oid);cfg.insert(list(cfg).index(ocfg)+index,outcfg)
        if index<len(items):
            item=items[index];plate,mi=plates[index]
        else:
            item=copy.deepcopy(source_item);item.set(PROD+'UUID',str(uuid.uuid4()));build.append(item)
            plate=source_plate;mi=copy.deepcopy(source_mi);maxidentify+=1;setmd(mi,'identify_id',maxidentify);plate.append(mi)
        item.set('objectid',oid);setmd(mi,'object_id',oid);setmd(mi,'instance_id',0)
        if positions is not None:
            m=matrix(item.get('transform'));xy=np.asarray(positions[index],float)
            if xy.shape!=(2,)or not np.isfinite(xy).all():raise ValueError('Invalid XY layout')
            m[:2,3]=xy;item.set('transform',encode(m))
        if target_count>1:setmd(outcfg,'name',f"{metadata(source_cfg).get('name','Figure')} | {index+1:02d}")
        pose=copy.deepcopy(savedposes.get(index,savedposes.get(0)))
        if pose is None:pose=E.Element('assemble_item',offset='0 0 0')
        pose.set('object_id',oid);pose.set('instance_id','0')
        if positions is not None or index not in savedposes:pose.set('transform',item.get('transform'))
        assemble.append(pose)
        result.append(int(oid))
    data['3D/3dmodel.model']=E.tostring(root,encoding='UTF-8',xml_declaration=True)
    data['Metadata/model_settings.config']=E.tostring(cfg,encoding='UTF-8',xml_declaration=True)
    return {'source_root_id':int(root_id),'root_ids':result,'independent':True,'count':target_count,'layout_changed':positions is not None,'mesh_resources_rewritten':False}
