"""Render the precise Flare Tools vector mark at Windows icon resolutions."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).parent / 'assets'
ROOT.mkdir(exist_ok=True)
svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
<rect x="20" y="20" width="472" height="472" rx="112" fill="#101010"/>
<path d="M284 90 C310 168 216 182 248 251 C207 232 192 207 199 176 C121 244 132 340 207 375 C287 414 378 350 351 275 C340 235 313 203 314 158 C305 181 291 201 275 212 C295 169 300 127 284 90Z" fill="#CC2027"/>
<path d="M255 244 C278 280 238 297 232 325 C226 355 274 369 293 339 C311 310 278 279 255 244Z" fill="#101010"/>
<rect x="136" y="420" width="240" height="16" rx="8" fill="#99CC00"/>
</svg>'''
(ROOT / 'FlareTools.svg').write_text(svg, 'utf-8')
scale = 3
image = Image.new('RGBA', (512 * scale, 512 * scale))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((20*scale,20*scale,492*scale,492*scale),radius=112*scale,fill='#101010')

def curve(start, segments):
    points = [start]
    for c1,c2,end in segments:
        x0,y0 = points[-1]
        for step in range(1,61):
            t=step/60
            u=1-t
            points.append((u**3*x0+3*u*u*t*c1[0]+3*u*t*t*c2[0]+t**3*end[0],
                           u**3*y0+3*u*u*t*c1[1]+3*u*t*t*c2[1]+t**3*end[1]))
    return [(round(x*scale),round(y*scale)) for x,y in points]

draw.polygon(curve((284,90), [((310,168),(216,182),(248,251)), ((207,232),(192,207),(199,176)),
    ((121,244),(132,340),(207,375)), ((287,414),(378,350),(351,275)), ((340,235),(313,203),(314,158)),
    ((305,181),(291,201),(275,212)), ((295,169),(300,127),(284,90))]), fill='#CC2027')
draw.polygon(curve((255,244), [((278,280),(238,297),(232,325)), ((226,355),(274,369),(293,339)),
    ((311,310),(278,279),(255,244))]), fill='#101010')
draw.rounded_rectangle((136*scale,420*scale,376*scale,436*scale),radius=8*scale,fill='#99CC00')
image=image.resize((512,512),Image.Resampling.LANCZOS)
image.save(ROOT/'FlareTools.png')
image.save(ROOT/'FlareTools.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])

