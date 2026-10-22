"""Numbered markers on an illustration, drawn by the app (Pillow only): the image model draws the picture with no text at all, a vision
model says where each named part is, and the app puts the numbers there, so a number can never be misspelt or sit on the wrong part."""
import os
from PIL import ImageDraw, ImageFont

FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'fonts', 'Poppins-Bold.ttf')
PURPLE, GOLD, WHITE = (77, 42, 135, 255), (217, 164, 0, 255), (255, 255, 255, 255)


def clean(marks, n):
    """n marks from whatever the model gave: {"x", "y"} with both between 0 and 1, or None for a part that is not shown."""
    out = []
    for m in (marks if isinstance(marks, list) else [])[:n]:
        try: x, y = float(m['x']), float(m['y'])
        except (KeyError, TypeError, ValueError): out.append(None); continue
        out.append({'x': x, 'y': y} if 0 <= x <= 1 and 0 <= y <= 1 else None)
    return out + [None] * (n - len(out))


def mark_parts(im, marks):
    """The picture with a numbered circle on each part that has a mark (the number is the part's place in the list)."""
    im = im.convert('RGBA')
    draw = ImageDraw.Draw(im)
    r = max(13, im.width // 44)
    font = ImageFont.truetype(FONT, int(r * 1.1))
    for k, m in enumerate(marks or [], 1):
        if not m: continue
        cx, cy = m['x'] * im.width, m['y'] * im.height
        draw.ellipse([cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3], fill=WHITE)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=PURPLE, outline=GOLD, width=3)
        draw.text((cx, cy), str(k), fill=WHITE, font=font, anchor='mm')
    return im
