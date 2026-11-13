"""Render original, synthetic concept previews for the Dedalo3Dskills catalog.

These animations are explanatory diagrams. They are not captured application
interactions, slicer output, calibrated physics, or evidence of a printed part.
Only Pillow is required; its bundled font keeps the tool self-contained.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT, SCALE = 720, 420, 2
BG = "#101f2f"
PANEL = "#162a3c"
GRID = "#253b4d"
WHITE = "#f0f5f8"
MUTED = "#a4b7c8"
GRAY = "#8499ad"
DARK = "#2c465d"
GREEN = "#64e3a6"
BLUE = "#67b9ff"
AMBER = "#ffbf69"
RED = "#ff7c86"


class Canvas:
    def __init__(self):
        self.image = Image.new("RGB", (WIDTH * SCALE, HEIGHT * SCALE), BG)
        self.draw = ImageDraw.Draw(self.image)
        self.fonts = {}

    def xy(self, points):
        return [(round(x * SCALE), round(y * SCALE)) for x, y in points]

    def box(self, bounds):
        return tuple(round(v * SCALE) for v in bounds)

    def font(self, size):
        if size not in self.fonts:
            self.fonts[size] = ImageFont.load_default(size=size * SCALE)
        return self.fonts[size]

    def text(self, point, value, size=18, fill=WHITE, anchor=None):
        self.draw.text(self.xy([point])[0], value, font=self.font(size), fill=fill, anchor=anchor)

    def line(self, points, fill=MUTED, width=2):
        self.draw.line(self.xy(points), fill=fill, width=max(1, round(width * SCALE)), joint="curve")

    def ellipse(self, bounds, fill=None, outline=None, width=2):
        self.draw.ellipse(self.box(bounds), fill=fill, outline=outline, width=round(width * SCALE))

    def rect(self, bounds, fill=None, outline=None, width=2, radius=0):
        if radius:
            self.draw.rounded_rectangle(self.box(bounds), radius=round(radius * SCALE), fill=fill, outline=outline, width=round(width * SCALE))
        else:
            self.draw.rectangle(self.box(bounds), fill=fill, outline=outline, width=round(width * SCALE))

    def polygon(self, points, fill=None, outline=None, width=2):
        self.draw.polygon(self.xy(points), fill=fill, outline=outline, width=round(width * SCALE))

    def dashed(self, start, end, fill=MUTED, width=2, dash=6):
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        if length == 0:
            return
        n = max(1, math.ceil(length / dash))
        for k in range(0, n, 2):
            t0, t1 = k / n, min(1, (k + 1) / n)
            self.line([(start[0] + dx*t0, start[1] + dy*t0), (start[0] + dx*t1, start[1] + dy*t1)], fill, width)

    def dashed_circle(self, center, radius, fill=AMBER, width=2):
        for start in range(0, 360, 24):
            pts = [(center[0] + radius*math.cos(math.radians(a)), center[1] + radius*math.sin(math.radians(a))) for a in range(start, start+13, 3)]
            self.line(pts, fill, width)

    def arrow(self, start, end, fill=MUTED, width=2):
        self.line([start, end], fill, width)
        angle = math.atan2(end[1]-start[1], end[0]-start[0])
        pts = [end, (end[0]-9*math.cos(angle-.5), end[1]-9*math.sin(angle-.5)), (end[0]-9*math.cos(angle+.5), end[1]-9*math.sin(angle+.5))]
        self.polygon(pts, fill)

    def finish(self):
        return self.image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def base(title, subtitle, t, caption):
    c = Canvas()
    c.text((24, 18), "DEDALO3D / SKILLS", 13, GREEN)
    c.text((696, 18), "CONCEPT / SYNTHETIC", 12, MUTED, anchor="ra")
    c.text((24, 45), title, 29)
    c.text((24, 82), subtitle, 17, MUTED)
    c.rect((20, 112, 700, 354), PANEL, radius=12)
    for x in range(32, 700, 24):
        c.line([(x, 120), (x, 346)], GRID, 1)
    for y in range(130, 352, 24):
        c.line([(28, y), (692, y)], GRID, 1)
    c.line([(24, 367), (696, 367)], GRID, 3)
    c.line([(24, 367), (24 + 672*t, 367)], GREEN, 3)
    c.text((24, 377), caption, 16)
    c.text((24, 401), "Illustration only. Validate the actual saved project and native toolpaths.", 11, MUTED)
    return c


def interpolate_path(points, progress):
    if progress <= 0:
        return points[:1]
    if progress >= 1:
        return points
    n = progress * (len(points)-1)
    k = int(n)
    a, b = points[k], points[k+1]
    return points[:k+1] + [(a[0]+(b[0]-a[0])*(n-k), a[1]+(b[1]-a[1])*(n-k))]


def grip(t):
    phase = min(2, int(t*3))
    captions = ["1  Measure the fixed wall and its small bed contact", "2  Add short native braces and permitted brim lines", "3  Check contact; keep the socket and fits clear"]
    c = base("Prender3D", "Low lateral restraint for a small contact area", t, captions[phase])
    c.line([(108, 326), (610, 326)], GRAY, 2)
    c.rect((309, 153, 363, 313), GRAY, outline=WHITE, radius=2)
    c.ellipse((309, 144, 363, 162), fill=GRAY, outline=WHITE)
    c.ellipse((322, 150, 350, 158), fill=BG)
    c.ellipse((299, 306, 373, 320), outline=AMBER, width=2)
    c.text((412, 154), "protected socket", 17, BLUE)
    c.arrow((402, 163), (356, 155), BLUE)
    c.text((85, 205), "fixed surface", 17, MUTED)
    c.arrow((211, 216), (305, 244), MUTED)
    progress = max(0, min(1, (t-.27)/.38))
    if progress > 0:
        for r in (60, 70, 80):
            c.ellipse((336-r, 316-11*r/80, 336+r, 316+11*r/80), outline=GREEN, width=1)
        for points in [[(273, 318), (283, 299), (310, 286)], [(398, 318), (388, 299), (362, 286)]]:
            c.line(interpolate_path(points, progress), GREEN, 8)
        for points in [[(284, 319), (296, 300), (310, 296)], [(388, 319), (376, 300), (362, 296)]]:
            c.line(interpolate_path(points, progress), GREEN, 4)
        c.text((429, 275), "native supports", 17, GREEN)
        c.line([(420, 291), (385, 298)], GREEN, 2)
    if phase == 2:
        c.ellipse((304, 280, 316, 294), GREEN)
        c.ellipse((356, 280, 368, 294), GREEN)
        c.text((85, 275), "contact above", 16, GREEN)
        c.text((85, 295), "the first layer", 16, GREEN)
    return c.finish()


def radial_point(cx, cy, radius, angle):
    a = math.radians(angle)
    return cx+radius*math.cos(a), cy+radius*math.sin(a)


def octopus(t):
    phase = min(2, int(t*3))
    captions = ["1  Distinguish the fixed body from moving segments", "2  Place low contacts between the arms and inside", "3  Preserve the moving joint spaces"]
    c = base("PrenderPolvo3D", "A measured radial layout with protected articulation", t, captions[phase])
    cx, cy = 350, 232
    c.ellipse((cx-43, cy-43, cx+43, cy+43), DARK, WHITE, 2)
    for k in range(8):
        angle = k*45
        start = radial_point(cx, cy, 42, angle)
        end = radial_point(cx, cy, 113, angle)
        c.line([start, end], GRAY, 6)
        for radius in (56, 75, 94, 113):
            px, py = radial_point(cx, cy, radius, angle)
            c.ellipse((px-8, py-8, px+8, py+8), GRAY)
        jx, jy = radial_point(cx, cy, 65.5, angle)
        c.dashed_circle((jx, jy), 6, AMBER, 2)
    c.text((cx, cy-24), "fixed body", 12, WHITE, anchor="mm")
    contacts = round(max(0, min(1, (t-.25)/.4))*8)
    for k in range(contacts):
        angle = 22.5+k*45
        p0 = radial_point(cx, cy, 42, angle)
        p1 = radial_point(cx, cy, 53, angle)
        c.line([p0, p1], GREEN, 7)
    if contacts:
        c.ellipse((cx-10, cy-10, cx+10, cy+10), fill=GREEN)
        c.text((508, 183), "low inner contact", 16, GREEN)
        c.arrow((498, 201), (362, 232), GREEN, 1)
    c.text((55, 148), "8 moving arms", 17, AMBER)
    c.text((55, 174), "joint keepouts", 16, AMBER)
    c.text((505, 264), "upper blocker", 16, BLUE)
    c.text((505, 286), "follows the body", 15, BLUE)
    if phase == 2:
        c.dashed_circle((cx, cy), 49, BLUE, 2)
    return c.finish()


def geometry(t):
    phase = min(2, int(t*3))
    captions = ["1  Read the geometry and preserve its transforms", "2  Inspect positive-mesh sections, not just a box", "3  Report measurements, limits and unresolved keepouts"]
    c = base("Analyze 3D geometry", "A preflight before support or material changes", t, captions[phase])
    c.rect((260, 162, 380, 312), DARK, outline=GRAY, width=2)
    c.ellipse((260, 148, 380, 177), GRAY, WHITE, 2)
    c.ellipse((285, 154, 355, 171), BG, BLUE, 2)
    c.ellipse((260, 300, 380, 328), DARK, WHITE, 2)
    c.ellipse((285, 307, 355, 320), BG, BLUE, 2)
    for a,b in [((250,145),(390,145)),((390,145),(390,330)),((390,330),(250,330)),((250,330),(250,145))]:
        c.dashed(a,b,GRAY,1)
    scan = 305 - 142 * (.5-.5*math.cos(t*math.pi*2))
    c.ellipse((255, scan-15, 385, scan+15), outline=GREEN, width=3)
    c.line([(246, scan), (393, scan)], GREEN, 1)
    c.text((62, 170), "upright", 17, MUTED)
    c.text((62, 195), "hollow positive mesh", 16, BLUE)
    c.arrow((195, 199), (277, 166), BLUE)
    chips = [("bounds", GRAY), ("section area", GREEN), ("transforms", BLUE), ("functional keepouts", AMBER)]
    for i,(label,color) in enumerate(chips):
        y=157+i*39
        c.rect((466,y,650,y+29), BG, outline=color, radius=6, width=1)
        c.text((478,y+6), label, 15, color)
    if phase == 2:
        c.text((64, 280), "bounding box", 16, MUTED)
        c.text((64, 301), "is not bed contact", 16, GREEN)
    return c.finish()


def rounded_poly(cx,cy,rx,ry,mode,margin=0):
    pts=[]
    for i in range(97):
        a=i*2*math.pi/96
        if mode=="contour":
            rr=1+.12*math.cos(3*a)+.07*math.sin(5*a)
            x,y=(rx+margin)*rr*math.cos(a),(ry+margin)*rr*math.sin(a)
        elif mode=="rounded rectangle":
            exponent=.40
            x=(rx+margin)*math.copysign(abs(math.cos(a))**exponent,math.cos(a))
            y=(ry+margin)*math.copysign(abs(math.sin(a))**exponent,math.sin(a))
        else:
            x,y=(rx+margin)*math.cos(a),(ry+margin)*math.sin(a)
        pts.append((cx+x,cy+y))
    return pts


def footprint(t):
    mode_index=min(3,int(t*4))
    mode=["circle","ellipse","rounded rectangle","contour"][mode_index]
    captions = ["Choose a measured shape and an explicit margin", "Adjust the mask; preserve the original product", "Position contacts and protected regions deliberately", "Export a native mask plan, then validate the slice"]
    c=base("Custom footprint", "Parametric mask plans; no solid base is added", t, captions[mode_index])
    cx,cy=290,234
    rx,ry = ((70,70) if mode=="circle" else (108,61))
    margin=5+5*math.sin(t*math.pi*2)
    for offset in (0,5,10):
        pts=rounded_poly(cx,cy,rx,ry,mode,margin+offset)
        c.line(pts,GREEN,1 if offset else 3)
    c.ellipse((cx-35,cy-35,cx+35,cy+35),DARK,WHITE,2)
    c.text((cx,cy), "product",15,WHITE,anchor="mm")
    for angle in [20,110,200,290]:
        a=angle+5*math.sin(t*math.pi*2)
        c.line([radial_point(cx,cy,35,a),radial_point(cx,cy,47,a)],GREEN,6)
    c.dashed_circle(radial_point(cx,cy,63,65),13,AMBER,2)
    c.text((497,143),mode,20,GREEN,anchor="mm")
    for k,label in enumerate(["margin","contact angles","height limit"]):
        y=189+k*49
        c.text((461,y),label,15,MUTED)
        c.line([(461,y+27),(642,y+27)],GRAY,2)
        fraction=(.5+.3*math.sin(t*math.pi*2+k))
        x=461+181*fraction
        c.ellipse((x-5,y+22,x+5,y+32),GREEN)
    c.text((67,320),"MASK PLAN / NOT A SOLID BASE",13,BLUE)
    return c.finish()


def burj_outline(center_x, bottom, height, width):
    widths=[1,.82,.82,.65,.65,.48,.48,.30,.30,.15]
    pts=[(center_x-width/2,bottom)]
    for i,w in enumerate(widths):
        pts.append((center_x-width*w/2,bottom-height*i/(len(widths)-1)))
    pts.append((center_x,bottom-height))
    for i,w in reversed(list(enumerate(widths))):
        pts.append((center_x+width*w/2,bottom-height*i/(len(widths)-1)))
    pts.append((center_x+width/2,bottom))
    return pts


def burj(t):
    phase=min(2,int(t*3))
    captions=["1  Read the external G-code layer and material schedule", "2  Build supported nested sections for active materials", "3  Stop at the last real colour change; the model can continue"]
    c=base("Burj priming tower", "A deterministic plan inspired by the Burj Khalifa",t,captions[phase])
    floor=325
    c.line([(64,floor),(654,floor)],GRAY,2)
    for x,h,w in [(102,60,30),(160,108,34),(225,174,38)]:
        c.rect((x-w/2,floor-h,x+w/2,floor),DARK,outline=GRAY,width=2)
    current=min(1,t/.65)
    height=130*current
    if height>0:
        c.polygon(burj_outline(450,floor,height,100),fill=DARK,outline=GREEN,width=2)
        for k in range(int(height/7)):
            y=floor-k*7
            relative=k/max(1,height/7)
            half=50*(1-.85*relative)
            color=[GREEN,BLUE,AMBER][k%3]
            c.line([(450-half,y),(450+half,y)],color,3)
    for offset in (0,5,10):
        c.ellipse((385-offset,318-offset*.15,515+offset,333+offset*.15),outline=GREEN,width=1)
    last_y=floor-130
    if t>.35:
        c.dashed((274,last_y),(633,last_y),AMBER,1)
        c.text((611,last_y-20),"last change",15,AMBER,anchor="ra")
    if phase==2:
        # The taller model continues in one active colour after tower growth stops.
        top_progress=(t-2/3)*3
        c.rect((206,floor-130-44*max(0,min(1,top_progress)),244,floor-130),fill=GREEN,outline=GREEN,width=1)
    c.rect((61,130,176,160),BG,outline=BLUE,radius=5,width=1)
    c.text((119,145),"G-code prepass",13,BLUE,anchor="mm")
    c.arrow((184,146),(355,146),BLUE,2)
    c.text((265,130),"layers + materials",13,MUTED,anchor="mm")
    c.text((539,269),"PLA / PETG",16,MUTED)
    c.text((539,291),"or mixed",16,MUTED)
    return c.finish()


SCENES = {
    "prender-3d": grip,
    "prender-polvo-3d": octopus,
    "analyze-3d-geometry": geometry,
    "custom-footprint": footprint,
    "torre-burj": burj,
}


def render(output_dir, frames=36, duration_ms=120):
    if not 12 <= frames <= 180 or not 40 <= duration_ms <= 500:
        raise ValueError("Choose 12..180 frames and 40..500 ms per frame")
    output_dir.mkdir(parents=True, exist_ok=True)
    results=[]
    for slug,scene in SCENES.items():
        rgb=[scene(i/(frames-1)) for i in range(frames)]
        # One shared palette keeps unchanged diagram regions byte-stable between
        # frames, allowing GIF delta rectangles instead of full-frame redraws.
        sample=Image.new("RGB",(WIDTH,HEIGHT),BG)
        for j,index in enumerate((0,frames//3,2*frames//3,frames-1)):
            sample.paste(rgb[index].resize((WIDTH//2,HEIGHT//2),Image.Resampling.LANCZOS),
                         ((j%2)*(WIDTH//2),(j//2)*(HEIGHT//2)))
        palette=sample.quantize(colors=128)
        palettes=[frame.quantize(palette=palette,dither=Image.Dither.NONE) for frame in rgb]
        gif=output_dir/(slug+".gif")
        palettes[0].save(gif,save_all=True,append_images=palettes[1:],duration=duration_ms,loop=0,optimize=True,disposal=1)
        poster=output_dir/(slug+".png")
        rgb[round((frames-1)*.82)].save(poster,optimize=True)
        with Image.open(gif) as check:
            assert check.n_frames==frames and check.size==(WIDTH,HEIGHT)
            assert check.info["loop"]==0
            for index in range(check.n_frames):
                check.seek(index)
                check.convert("RGB").load()
            actual_duration=sum((check.seek(index) or check.info.get("duration",0)) for index in range(check.n_frames))
        results.append({"skill":slug,"gif":gif.name,"poster":poster.name,"frames":frames,
                        "duration_ms":actual_duration,"width":WIDTH,"height":HEIGHT,
                        "bytes":gif.stat().st_size,"concept_only":True})
    return results



def write_collection_hero(path):
    """Write the original collection-level static fallback banner."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="350" viewBox="0 0 1120 350" role="img" aria-labelledby="title desc">\n<title id="title">Dedalo3Dskills — a collection for 3D print preparation</title>\n<desc id="desc">Five schematic cards represent geometry analysis, a custom footprint, low native retention, protected articulation, and a Burj-inspired priming tower. The banner is a conceptual illustration, not a slicer preview or physical print result.</desc>\n<rect width="1120" height="350" rx="18" fill="#101f2f"/>\n<g font-family="Arial, Helvetica, sans-serif">\n<text x="32" y="34" fill="#64e3a6" font-size="15" letter-spacing="3">DEDALO3D / SKILLS</text>\n<text x="32" y="82" fill="#f0f5f8" font-size="34" font-weight="700">Skills and tools for 3D print preparation.</text>\n<text x="32" y="115" fill="#a4b7c8" font-size="18">Inspect geometry. Plan contact. Protect movement. Prepare material changes.</text>\n<g fill="#162a3c" stroke="#2c465d">\n<rect x="32" y="147" width="200" height="155" rx="12"/><rect x="246" y="147" width="200" height="155" rx="12"/><rect x="460" y="147" width="200" height="155" rx="12"/><rect x="674" y="147" width="200" height="155" rx="12"/><rect x="888" y="147" width="200" height="155" rx="12"/>\n</g>\n<g fill="none" stroke-width="2">\n<path d="M97 176h66v57H97z M97 190h66 M97 205h66 M97 220h66" stroke="#8499ad"/><ellipse cx="130" cy="204" rx="44" ry="10" stroke="#67b9ff"/>\n<ellipse cx="346" cy="207" rx="53" ry="28" stroke="#64e3a6"/><ellipse cx="346" cy="207" rx="43" ry="19" stroke="#64e3a6"/><circle cx="346" cy="207" r="14" stroke="#f0f5f8"/><path d="M302 179h88" stroke="#8499ad"/><circle cx="350" cy="179" r="4" fill="#64e3a6" stroke="#64e3a6"/>\n<path d="M548 172h25v64h-25z" stroke="#8499ad"/><path d="M532 239l6-13 10-7 M589 239l-6-13-10-7" stroke="#64e3a6" stroke-width="5"/><ellipse cx="560" cy="240" rx="46" ry="6" stroke="#64e3a6"/>\n<circle cx="774" cy="207" r="23" stroke="#f0f5f8"/><path d="M774 164v20 M774 230v20 M731 207h20 M797 207h20 M744 177l14 14 M790 223l14 14 M744 237l14-14 M790 191l14-14" stroke="#8499ad" stroke-width="7"/><path d="M752 197l-7-3 M785 186l3-7 M797 218l7 3 M763 228l-3 7" stroke="#64e3a6" stroke-width="5"/><circle cx="774" cy="170" r="7" stroke="#ffbf69" stroke-dasharray="3 3"/>\n<path d="M958 242v-19h8v-17h8v-16h7v-16h7v-13h8v13h7v16h7v16h8v17h8v19z" stroke="#64e3a6"/><path d="M958 237h68 M966 220h52 M974 203h36 M981 186h22" stroke="#67b9ff"/><path d="M958 230h68 M974 197h36" stroke="#ffbf69"/>\n</g>\n<g fill="#f0f5f8" font-size="20" font-weight="700" text-anchor="middle"><text x="132" y="270">Analyze</text><text x="346" y="270">Footprint</text><text x="560" y="270">Retain</text><text x="774" y="270">Articulate</text><text x="988" y="270">Prime</text></g>\n<g fill="#a4b7c8" font-size="13" text-anchor="middle"><text x="132" y="289">geometry preflight</text><text x="346" y="289">parametric mask plan</text><text x="560" y="289">native lateral braces</text><text x="774" y="289">protected joint spaces</text><text x="988" y="289">Burj-inspired layer plan</text></g>\n<text x="32" y="330" fill="#a4b7c8" font-size="13">Original agent workflows + custom tools · MIT / commercial use · Concept illustrations</text>\n</g></svg>')



def write_preview_docs(output_dir, rows):
    """Write relative, publication-safe captions and metadata with the assets."""
    import json
    catalog = {"schema":1, "kind":"synthetic_concept_previews", "concept_only":True,
               "hero":"../dedalo3d-collection.svg", "renderer":"../../tools/render_previews.py",
               "pillow_version":Image.__version__, "previews":[]}
    labels = {'prender-3d': {'title': 'Prender3D', 'caption_en': 'Low native supports touch measured fixed walls while the socket remains clear.', 'caption_pt_br': 'Apoios nativos baixos tocam a parede fixa medida e preservam o encaixe.', 'alt': 'Synthetic concept diagram: Low native supports touch measured fixed walls while the socket remains clear.'}, 'prender-polvo-3d': {'title': 'PrenderPolvo3D', 'caption_en': 'Eight low side contacts and a small inner contact avoid the articulated joint spaces.', 'caption_pt_br': 'Oito contatos laterais baixos e um apoio interno preservam os espaços das articulações.', 'alt': 'Synthetic concept diagram: Eight low side contacts and a small inner contact avoid the articulated joint spaces.'}, 'analyze-3d-geometry': {'title': 'Analyze 3D geometry', 'caption_en': 'Inspect positive-mesh sections, transforms and unresolved functional keepouts before modifying the project.', 'caption_pt_br': 'Inspecione seções da malha positiva, transforms e regiões funcionais ainda não resolvidas antes de alterar o projeto.', 'alt': 'Synthetic concept diagram: Inspect positive-mesh sections, transforms and unresolved functional keepouts before modifying the project.'}, 'custom-footprint': {'title': 'Custom footprint', 'caption_en': 'Choose a measured contour, contact layout and height limit for native masks; no solid base is added.', 'caption_pt_br': 'Escolha contorno, contatos e limite de altura para máscaras nativas; nenhuma base sólida é adicionada.', 'alt': 'Synthetic concept diagram: Choose a measured contour, contact layout and height limit for native masks; no solid base is added.'}, 'torre-burj': {'title': 'Burj priming tower', 'caption_en': 'The prepass G-code determines layer/material needs. The tower stops at the last real colour change while taller models can continue.', 'caption_pt_br': 'O G-code de pré-fatiamento determina camadas e materiais. A torre termina na última troca real de cor, enquanto modelos mais altos podem continuar.', 'alt': 'Synthetic concept diagram: The prepass G-code determines layer/material needs. The tower stops at the last real colour change while taller models can continue.'}}
    lines = ["# Skill previews", "",
             "These are original synthetic concept diagrams. They are not application recordings, native slicer previews, calibrated physics, or physical print results.", "",
             "Regenerate the assets from the repository root:", "",
             "    python -m pip install -r tools/requirements-previews.txt",
             "    python tools/render_previews.py", "",
             "The renderer uses Pillow's bundled font and no customer models. It also writes the collection banner. PNG posters provide a static fallback. Pixel output can change when the renderer dependency changes.", ""]
    for row in rows:
        entry = dict(row, **labels[row["skill"]])
        catalog["previews"].append(entry)
        lines += ["## "+entry["title"], "",
                  "!["+entry["alt"]+"]("+entry["gif"]+")", "",
                  entry["caption_en"], "", entry["caption_pt_br"], "",
                  "[Static PNG]("+entry["poster"]+")", ""]
    (output_dir/"catalog.json").write_text(json.dumps(catalog,indent=2,ensure_ascii=False)+"\n")
    (output_dir/"README.md").write_text("\n".join(lines)+"\n")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",type=Path,default=Path(__file__).resolve().parents[1]/"assets/previews")
    parser.add_argument("--frames",type=int,default=36)
    parser.add_argument("--duration-ms",type=int,default=120)
    args=parser.parse_args()
    import json
    previews = render(args.output_dir,args.frames,args.duration_ms)
    hero = args.output_dir.parent / "dedalo3d-collection.svg"
    write_collection_hero(hero)
    write_preview_docs(args.output_dir, previews)
    print(json.dumps({"hero":str(hero), "previews":previews},indent=2))


if __name__=="__main__":
    main()
