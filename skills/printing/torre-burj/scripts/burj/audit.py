"""Independent commanded G-code gates; digital evidence is not physical proof."""
from .gcode import audit_tower, Footprint

def phases(result): return [(round(p.z,6),p.tool,p.changed) for p in result.phases]
def temperatures(result):
    return {(round(p.z,6),p.tool):set().union(*(b.temperatures for b in p.blocks if not result.is_tower(b.name))) for p in result.phases}

def audit(before,after,plan,options,*,initial_speed_limit=None,center_xy=None,bed=None):
    out=audit_tower(after,targets={t:options.target(t) for t in options.tools});fail=set(out['failures'])
    if before.schedule()!=after.schedule():fail.add('external_material_schedule_changed')
    if phases(before)!=phases(after):fail.add('native_phases_changed')
    if temperatures(before)!=temperatures(after):fail.add('external_deposition_temperature_changed')
    if before.fallback_width_depositions or after.fallback_width_depositions:fail.add('missing_native_commanded_width')
    rows={round(r['z'],6):r for r in plan['rows']};structural=[]
    last_change=max((p.z for p in before.phases if p.changed),default=0.)
    tower_top=0.
    for p in after.phases:
        blocks=[b for b in p.blocks if after.is_tower(b.name)]
        if not blocks:continue
        tower_top=max(tower_top,max(b.top_z for b in blocks))
        row=rows.get(round(p.z,6))
        if not row or p.tool not in before.schedule().get(round(p.z,6),[]):fail.add('unscheduled_tower_material');continue
        regions=[r for r in row['regions'] if r['tool']==p.tool]
        if len(regions)!=1:fail.add('missing_planned_material_region');continue
        region=regions[0]
        if p.changed!=(region['purpose']=='prime_after_change'):fail.add('preparation_not_bound_to_change')
        if not p.changed:
            if region['target_mm3']!=0 or region['density']!=options.structural_infill_percent:fail.add('preparation_before_change')
            structural.append({'z':p.z,'tool':p.tool,'density_percent':region['density'],
                               'measured_mm3':sum(b.volume_mm3 for b in blocks),'preparation_target_mm3':0})
        limit=initial_speed_limit if p.z==after.layers[0].z and initial_speed_limit is not None else options.speed_mm_s
        if any(speed>limit+.05 for b in blocks for speed in b.speeds):fail.add('tower_speed_exceeded')
    if abs(plan['height_mm']-last_change)>.002 or abs(tower_top-last_change)>.002:fail.add('tower_not_cut_at_last_real_change')
    for layer in after.layers:
        towers=[b for p in layer.phases for b in p.blocks if after.is_tower(b.name)]
        products=[b for p in layer.phases for b in p.blocks if not after.is_tower(b.name)]
        for a in towers:
            for b in products:
                if a.volume_mm3>0 and not a.footprint.rows or b.volume_mm3>0 and not b.footprint.rows:fail.add('missing_deposition_occupancy')
                elif a.footprint.intersects(b.footprint):fail.add('native_deposition_footprint_conflict')
    expected={(round(row['z'],6),r['tool']):r for row in plan['rows'] for r in row['regions']}
    visits={}
    for phase in after.phases:
        blocks=[b for b in phase.blocks if after.is_tower(b.name) and b.features!={'brim'} and b.volume_mm3>0]
        if blocks:visits[(round(phase.z,6),phase.tool)]=blocks
    for key,region in expected.items():
        blocks=visits.get(key,[])
        if not blocks:
            fail.add('missing_planned_structural_region' if region['purpose']=='structure' else 'missing_planned_priming_region')
            continue
        features=set().union(*(b.features for b in blocks))
        if not any('wall' in f or 'perimeter' in f for f in features):fail.add('missing_planned_region_contour')
        if not any('infill' in f or 'solid' in f or 'bridge' in f for f in features):fail.add('missing_planned_region_infill')
    if set(visits)-set(expected):fail.add('unexpected_tower_region')
    if center_xy is not None and bed is not None:
        from .geometry import profile
        cx,cy=center_xy
        for layer in after.layers:
            row=rows.get(round(layer.z,6))
            if row is None: continue
            pp=profile(row['width_mm']);pad=options.line_width_mm
            if layer.z==after.layers[0].z:pad+=options.brim_mm
            expected=[cx+min(x for x,y in pp)-pad,cy+min(y for x,y in pp)-pad,
                      cx+max(x for x,y in pp)+pad,cy+max(y for x,y in pp)+pad]
            for block in [b for p in layer.phases for b in p.blocks if after.is_tower(b.name)]:
                actual=block.footprint.bounds
                if actual[0]<expected[0]-.01 or actual[1]<expected[1]-.01 or actual[2]>expected[2]+.01 or actual[3]>expected[3]+.01:
                    fail.add('tower_deposition_outside_planned_footprint')
                if actual[0]<bed[0] or actual[1]<bed[1] or actual[2]>bed[2] or actual[3]>bed[3]:fail.add('tower_deposition_outside_bed')
    commanded_passed=not fail
    active=getattr(after,'active_macros',[])
    if active:fail.add('firmware_semantics_unverified')
    return {**out,'passed':not fail,'commanded_gcode_passed':commanded_passed,
            'firmware_semantics_verified':not active,'unverified_active_macros':active,
            'firmware_macros_simulated':False,'status':('firmware_unverified' if commanded_passed and active else 'digitally_validated' if not fail else 'failed'),'failures':sorted(fail),'mode':'deterministic_priming',
            'native_flush_active':False,'native_flush_effective':False,'custom_priming_effective':(commanded_passed if not active else None),'custom_commanded_priming_passed':commanded_passed,'physical_cleaning_validated':False,
            'last_real_toolchange_z_mm':last_change,'tower_top_z_mm':tower_top,'structural_passes':structural,
            'external_schedule':after.schedule(),'deposition_targets':after.temperatures,
            'occupancy':{'conservative':True,'strip_height_mm':Footprint.pitch,'arc_sagitta_margin_mm':Footprint.sagitta}}
