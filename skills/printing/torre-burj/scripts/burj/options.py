"""Finite, strict, dependency-free inputs; physical tools are zero based."""
from dataclasses import asdict, dataclass, field
import math

@dataclass
class Options:
    model_tools: list[int]
    primary_object_ids: list[int]
    interface_tool: int | None = None
    minimum_width_mm: float = 24.
    maximum_width_mm: float = 48.
    brim_mm: float = 6.
    center_xy: list[float] | None = None
    clearance_mm: float = 2.
    line_width_mm: float = .5
    structural_infill_percent: int = 10
    speed_mm_s: float = 40.
    purge_volume_mm3: dict[int, float] = field(default_factory=dict)
    foundation_height_mm: float | None = None
    envelope_taper_power: float = 1.
    plate: int = 1

    @classmethod
    def parse(cls, value):
        if not isinstance(value, dict):
            raise ValueError('Options must be a JSON object')
        args = dict(value)
        if 'purge_volume_mm3' in args:
            values = args['purge_volume_mm3']
            if not isinstance(values, dict): raise ValueError('purge_volume_mm3 must map tools to volumes')
            args['purge_volume_mm3'] = {int(k): v for k, v in values.items() if str(k) in {'0','1','2','3'}}
            if len(args['purge_volume_mm3']) != len(values): raise ValueError('Invalid physical tool in volume map')
        try: result = cls(**args)
        except TypeError as exc: raise ValueError(str(exc)) from exc
        result.validate()
        return result

    @property
    def tools(self): return self.model_tools + ([] if self.interface_tool is None else [self.interface_tool])

    def validate(self):
        if (not isinstance(self.model_tools,list) or not self.model_tools or
                len(self.model_tools)>4 or len(set(self.model_tools))!=len(self.model_tools)):
            raise ValueError('Use one to four distinct model tools')
        if any(type(t) is not int or not 0<=t<=3 for t in self.tools) or len(set(self.tools))!=len(self.tools):
            raise ValueError('Physical tools must be distinct integers 0..3')
        if (not isinstance(self.primary_object_ids,list) or not self.primary_object_ids or
                any(type(x) is not int or x<=0 for x in self.primary_object_ids) or
                len(set(self.primary_object_ids))!=len(self.primary_object_ids)):
            raise ValueError('primary_object_ids must be distinct positive root IDs')
        ranges={'minimum_width_mm':(12,50),'maximum_width_mm':(24,100),'brim_mm':(0,20),
                'clearance_mm':(1,20),'line_width_mm':(.3,.8),'speed_mm_s':(5,100),
                'envelope_taper_power':(1,4)}
        for key,(low,high) in ranges.items():
            v=getattr(self,key)
            if type(v) not in (int,float) or not math.isfinite(v) or not low<=v<=high:
                raise ValueError(f'{key} must be finite in [{low}, {high}]')
        if abs(self.maximum_width_mm-2*self.minimum_width_mm)>1e-6:
            raise ValueError('Maximum width must be twice minimum width; brim is additional')
        if type(self.structural_infill_percent) is not int or not 5<=self.structural_infill_percent<=25:
            raise ValueError('Structural infill must be an integer 5..25')
        if type(self.plate) is not int or self.plate<1: raise ValueError('Plate must be a positive integer')
        if self.foundation_height_mm is not None:
            if type(self.foundation_height_mm) not in (int,float) or not math.isfinite(self.foundation_height_mm) or not 0<self.foundation_height_mm<=50:
                raise ValueError('Foundation height must be finite in (0,50]')
        if self.center_xy is not None and (not isinstance(self.center_xy,(list,tuple)) or len(self.center_xy)!=2 or
                any(type(v) not in (int,float) or not math.isfinite(v) for v in self.center_xy)):
            raise ValueError('center_xy requires two finite coordinates')
        if set(self.purge_volume_mm3)-set(self.tools): raise ValueError('Volume map references undeclared tools')
        if any(type(v) not in (int,float) or not math.isfinite(v) or not 0<v<=200 for v in self.purge_volume_mm3.values()):
            raise ValueError('Comparison volumes must be finite in (0,200] mm3')

    def target(self, tool): return self.purge_volume_mm3.get(tool, 12.)
    def to_dict(self): return asdict(self)
