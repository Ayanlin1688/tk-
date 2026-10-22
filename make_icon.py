# -*- coding: utf-8 -*-
"""生成应用图标 icon.ico（深底+金色香水瓶+金色描边）"""
from PIL import Image, ImageDraw, ImageFont
import os

SIZE = 256
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# 圆角深色底
mask = Image.new("L", (SIZE, SIZE), 0)
md = ImageDraw.Draw(mask)
md.rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=56, fill=255)
base = Image.new("RGBA", (SIZE, SIZE), (18, 14, 26, 255))
img.paste(base, (0, 0), mask)

# 金色渐变瓶身
bw, bh = 96, 150
bx, by = (SIZE - bw) // 2, (SIZE - bh) // 2 - 26
bottle = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
bd = ImageDraw.Draw(bottle)
for yy in range(bh):
    t = yy / max(1, bh - 1)
    col = (int(212 + (238 - 212) * t), int(175 + (199 - 175) * t), int(55 + (102 - 55) * t))
    bd.line([(0, yy), (bw, yy)], fill=col + (255,))
bmask = Image.new("L", (bw, bh), 0)
bmd = ImageDraw.Draw(bmask)
bmd.rounded_rectangle([0, 0, bw - 1, bh - 1], radius=26, fill=255)
img.paste(bottle, (bx, by), bmask)

# 瓶盖（深色圆角）
cw, ch = 72, 26
cx, cy = (SIZE - cw) // 2, by - ch + 4
d.rounded_rectangle([cx, cy, cx + cw, cy + ch], radius=10, fill=(12, 10, 16, 255))

# 标签
lw, lh = 64, 52
lx, ly = (SIZE - lw) // 2, by + 46
d.rounded_rectangle([lx, ly, lx + lw, ly + lh], radius=8, fill=(255, 255, 255, 245))
try:
    f = ImageFont.truetype("arialbd.ttf", 20)
    d.text((SIZE // 2, ly + 15), "TK", font=f, fill=(30, 26, 44, 255), anchor="mm")
    f2 = ImageFont.truetype("arial.ttf", 13)
    d.text((SIZE // 2, ly + 38), "WORKBENCH", font=f2, fill=(150, 140, 170, 255), anchor="mm")
except Exception:
    pass

# 底部金色弧线
d.arc([SIZE // 2 - 70, SIZE - 84, SIZE // 2 + 70, SIZE - 34], start=200, end=340, fill=(212, 175, 55, 255), width=5)

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
img.save(out, sizes=[(256, 256), (64, 64), (48, 48), (32, 32), (16, 16)])
print("图标已生成:", out)
