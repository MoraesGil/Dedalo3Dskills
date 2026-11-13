"""Portable prepare/build/audit CLI. Never rewrites G-code or contacts a printer."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from .options import Options
from .project import Project,add_tower,placement,digest,encoded,RECEIPT
from .geometry import make_plan
from .gcode import trace
from .audit import audit

def read_trace(path,project,names=(),brim_boxes=None):
    ds=[float(v) for v in (project.config['filament_diameter'] if isinstance(project.config['filament_diameter'],list) else str(project.config['filament_diameter']).split(','))]
    result=trace(Path(path).read_text(encoding='utf-8-sig'),diameters=ds,tower_names=set(names),brim_boxes=brim_boxes)
    if result.fallback_width_depositions:raise ValueError('Fresh native G-code must declare ;WIDTH for all deposition')
    if result.auxiliary_on:raise ValueError('Auxiliary fan is enabled in G-code')
    return result

def output_json(path,value):
    with Path(path).open('xb') as f:f.write(encoded(value))

def build(args):
    project=Project(args.prepass_3mf)
    expected=args.expected_prepass_sha256.lower()
    if len(expected)!=64 or project.sha256!=expected:raise ValueError('Prepared 3MF hash does not match expected_prepass_sha256')
    options=Options.parse(json.loads(Path(args.options).read_text()))
    project.check_materials(options);project.names(options.plate,options.primary_object_ids)
    if not project.native_off(options.plate):raise ValueError('Prepared project must disable native tower')
    before=read_trace(args.prepass_gcode,project)
    names=project.names(options.plate,options.primary_object_ids)
    actual={b.name for p in before.phases for b in p.blocks}
    if not names<=actual:raise ValueError('Prepass G-code lacks selected model labels')
    if any(name.startswith('__SYNTH_TOWER') for name in actual):raise ValueError('Prepass still contains an auxiliary tower')
    plan=make_plan(before,options,names,density_boost=args.density_boost)
    center=placement(before,options,project.bed())
    bindings={'prepass_3mf_sha256':project.sha256,'prepass_gcode_sha256':digest(Path(args.prepass_gcode).read_bytes()),
              'engine_executable_sha256':digest(Path(args.engine_executable).read_bytes()) if args.engine_executable else None,
              'engine_source_commit':args.engine_source_commit,
              'prepass_source_attestation':'caller supplied; hash binding does not prove how the prepass was generated'}
    record=add_tower(project,options,before,plan,center,bindings)
    sha=project.publish(args.output)
    result={'status':'native_slicing_required','output_3mf_sha256':sha,'tower_object_id':record['tower_object_id'],
            'mode':record['mode'],'native_flush_active':False,'last_real_toolchange_z_mm':plan['height_mm'],
            'center_xy':center,'bindings':bindings,'physical_cleaning_validated':False}
    if args.receipt:output_json(args.receipt,result)
    return result

def check(args):
    project=Project(args.project); record=project.signed_record()
    if record is None:raise ValueError('Input lacks a valid hash-bound Burj tower')
    options=Options.parse(record['options']);project.check_materials(options)
    if record.get('external_project_sha256')!=project.external_hash(record['tower_object_id'],record['part_ids']):
        raise ValueError('Product geometry, painting, transforms, layout or process changed; regenerate the tower')
    if not project.native_off(options.plate):raise ValueError('Native tower flags changed after generation')
    before_project=Project(args.prepass_3mf)
    if before_project.sha256!=record['bindings']['prepass_3mf_sha256'] or digest(Path(args.prepass_gcode).read_bytes())!=record['bindings']['prepass_gcode_sha256']:
        raise ValueError('Prepass provenance does not match signed plan')
    before=read_trace(args.prepass_gcode,before_project)
    from .geometry import profile
    pp=profile(options.maximum_width_mm);cx,cy=record['center_xy'];pad=options.brim_mm+options.line_width_mm
    box=[cx+min(x for x,y in pp)-pad,cy+min(y for x,y in pp)-pad,cx+max(x for x,y in pp)+pad,cy+max(y for x,y in pp)+pad]
    after=read_trace(args.gcode,project,[record['tower_name']],{record['tower_name']:box})
    initial=project.config.get('initial_layer_speed')
    initial=float(initial[0] if isinstance(initial,list) else str(initial).split(',')[0]) if initial is not None else options.speed_mm_s
    report=audit(before,after,record['plan'],options,initial_speed_limit=initial,center_xy=record['center_xy'],bed=project.bed())
    report.update(project_3mf_sha256=project.sha256,gcode_sha256=digest(Path(args.gcode).read_bytes()),bindings=record['bindings'])
    if args.output:output_json(args.output,report)
    return report

def parser():
    p=argparse.ArgumentParser(description='Burj Khalifa inspired deterministic priming tower: native 3MF + fresh G-code in, hash-bound 3MF + audit out.')
    sub=p.add_subparsers(dest='command',required=True)
    prep=sub.add_parser('prepare',help='Write a new tower-free native-off 3MF; preserve original')
    prep.add_argument('--input',required=True);prep.add_argument('--plate',type=int,default=1);prep.add_argument('--output',required=True)
    b=sub.add_parser('build',help='Use fresh prepass to generate a hash-bound tower; slice the result next')
    b.add_argument('--prepass-3mf',required=True);b.add_argument('--prepass-gcode',required=True);b.add_argument('--options',required=True)
    b.add_argument('--expected-prepass-sha256',required=True);b.add_argument('--output',required=True);b.add_argument('--receipt')
    b.add_argument('--density-boost',type=int,choices=range(0,31,5),default=0)
    b.add_argument('--engine-executable');b.add_argument('--engine-source-commit',default='unverified')
    a=sub.add_parser('audit',help='Audit fresh final native G-code against the bound prepass and plan')
    a.add_argument('--project',required=True);a.add_argument('--gcode',required=True);a.add_argument('--prepass-3mf',required=True);a.add_argument('--prepass-gcode',required=True);a.add_argument('--output')
    return p

def main(argv=None):
    args=parser().parse_args(argv)
    try:
        if args.command=='prepare':
            project=Project(args.input);removed=project.prepare(args.plate);sha=project.publish(args.output)
            result={'status':'fresh_prepass_required','source_sha256':project.sha256,'prepass_3mf_sha256':sha,'plate':args.plate,'removed_owned_ids':removed}
        elif args.command=='build':result=build(args)
        else:result=check(args)
        print(json.dumps(result,sort_keys=True,allow_nan=False))
        return 0 if result.get('passed',True) else 2
    except (ValueError,KeyError,OSError,json.JSONDecodeError) as exc:
        print(json.dumps({'error':str(exc)}),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
