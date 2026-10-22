# -*- coding: utf-8 -*-
"""
generator.py — TK图文生成引擎
基于参考图分析结果 + 双语文案素材库，批量渲染 1080x1920 TK图文。
每套 = 图1钩子页 + 图2产品价格页 + 发布文案包。
支持多套变体（配色/布局/文案/角度组合）。
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io
import os
import re
import random
import shutil
import content as C
import styles

CANVAS = (1080, 1920)

# ---------------- 字体工具 ----------------

def _font_path(name):
    candidates = [
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", name),
        os.path.join(r"C:\Windows\Fonts", name),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

FONT_BLACK = _font_path("ariblk.ttf") or _font_path("impact.ttf")
FONT_BOLD = _font_path("arialbd.ttf") or _font_path("segoeuib.ttf")
FONT_REG = _font_path("arial.ttf") or _font_path("segoeui.ttf")

def font_black(size):
    """TikTok 原生感粗黑体（白字+超粗黑描边）"""
    return ImageFont.truetype(FONT_BLACK, size) if FONT_BLACK else ImageFont.load_default()

def font_bold(size):
    return ImageFont.truetype(FONT_BOLD, size) if FONT_BOLD else ImageFont.load_default()

def font_reg(size):
    return ImageFont.truetype(FONT_REG, size) if FONT_REG else ImageFont.load_default()

# TikTok 原生叠字：图上 emoji 转符号（PIL 画不了彩色 emoji），发布包保留原 emoji
EMOJI_MAP = {
    "🛒": "→", "💝": "♥", "🌹": "✿", "😭": "♡", "😅": ";)", "👀": "→",
    "🫡": "★", "⏳": "⌛", "🚪": "→", "📦": "▣", "💯": "100%", "🔥": "★",
    "💄": "✿", "✨": "✦", "❤️": "♥", "😍": "♥", "🤯": "★", "👃": "→",
    "🚨": "⚡", "🎁": "★", "💸": "$$", "💰": "$", "💋": "♥", "🥰": "♥",
    "😏": ";)", "🤤": "♡", "😜": ";)", "😉": ";)", "🤭": ";)", "😳": ";)",
    "🙈": "♡", "🙊": "♡", "🤣": ":D", "😂": ":D", "😱": "!!", "🫠": "~",
    "🌷": "✿", "🌸": "✿", "💐": "✿", "🌺": "✿", "🍾": "★", "🥂": "★",
}

def sanitize_emoji(s):
    s = str(s)
    for k, v in EMOJI_MAP.items():
        s = s.replace(k, v)
    # 兜底：去掉剩余 4 字节 emoji 与变体选择符，只留 BMP 可渲染字符
    return "".join(ch for ch in s if ord(ch) < 0x10000 or ch in "\u263a\u263b")


# ---------------- 彩色 emoji 贴纸渲染（TikTok 原生感关键） ----------------

EMOJI_FONT_PATH = None
_emoji_font_cache = {}

def _emoji_font(size):
    """加载 Segoe UI Emoji（Windows 自带），缓存字体对象"""
    global EMOJI_FONT_PATH, _emoji_font_cache
    if EMOJI_FONT_PATH is None:
        cands = [
            os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "seguiemj.ttf"),
            r"C:\Windows\Fonts\seguiemj.ttf",
        ]
        EMOJI_FONT_PATH = next((p for p in cands if os.path.exists(p)), "")
    if not EMOJI_FONT_PATH:
        return None
    key = size
    if key not in _emoji_font_cache:
        try:
            _emoji_font_cache[key] = ImageFont.truetype(EMOJI_FONT_PATH, size)
        except Exception:
            _emoji_font_cache[key] = None
    return _emoji_font_cache[key]


def _is_emoji_char(ch):
    o = ord(ch)
    return (
        0x1F000 <= o <= 0x1FAFF           # Emoticons ~ Symbols & pictographs
        or 0x2600 <= o <= 0x27BF          # 杂项符号/装饰
        or 0x2B00 <= o <= 0x2BFF          # 箭头等
        or 0xFE0F == o                    # 变体选择符（并入前一个 emoji）
        or 0x1F1E6 <= o <= 0x1F1FF        # 国旗
    )


def mixed_text_width(text, font, ef):
    """混合文本总宽（普通字符用 font，emoji 用 emoji 字体）"""
    total = 0.0
    for ch in text:
        if _is_emoji_char(ch) and ef:
            total += ef.getlength(ch)
        else:
            total += font.getlength(ch)
    return total


def draw_mixed_text(d, xy, text, font, fill, stroke_fill=(0, 0, 0), stroke_width=6,
                    align="center", center_x=None):
    """逐字符渲染：普通字符用 font，emoji 用 Segoe UI Emoji（同色+黑描边贴纸感）。
    align: center 需要 center_x；left 时 xy 为起点；right 时 xy 为右端"""
    if not text:
        return
    ef = _emoji_font(int(font.size * 1.02))
    x, y = xy
    if align == "center" and center_x is not None:
        total = mixed_text_width(text, font, ef)
        x = center_x - total / 2
    elif align == "right":
        total = mixed_text_width(text, font, ef)
        x = x - total
    for ch in text:
        if _is_emoji_char(ch) and ef:
            f = ef
        else:
            f = font
        d.text((x, y), ch, font=f, fill=fill,
               stroke_width=stroke_width, stroke_fill=stroke_fill)
        x += f.getlength(ch)
    return x


# ---------------- 价格高亮分段（TikTok 价格页原生感） ----------------

PRICE_TOKEN_RE = re.compile(r"(\$\d[\d.,]*|\d+% ?OFF|50% ?OFF)")
STRIKE_RE = re.compile(r"~~(.+?)~~(.*)")


def strip_strike_marks(text):
    """去掉 ~~删除线~~ 标记（用于测宽）"""
    return STRIKE_RE.sub(r"\1\2", text)


def split_price_segments(text):
    """把价格/折扣标记拆成黄色高亮段，其余保持默认色"""
    parts = PRICE_TOKEN_RE.split(text)
    segs = []
    for idx, p in enumerate(parts):
        if not p:
            continue
        segs.append((p, (255, 215, 0) if idx % 2 == 1 else None))
    return segs


def build_price_segments(text, orig_price=None):
    """价格/折扣黄色高亮 + 可选划线原价（现价前插入 ~~原价~~ 段，渲染删除线）"""
    segs = split_price_segments(text)
    if not orig_price:
        return segs
    out = []
    op = str(orig_price).strip()
    for t, col in segs:
        if col is not None and re.search(r"\$\d", t):
            out.append(("~~" + op + "~~ " + t, col))
        else:
            out.append((t, col))
    return out


def _accent_word_segments(line, kw, accent, base_segs=None):
    """把行内命中的关键词段标成 accent 色（模仿真人圈重点）"""
    if not kw:
        return base_segs or split_price_segments(line)
    out = []
    for t, col in (base_segs or split_price_segments(line)):
        if col is not None:
            out.append((t, col))
            continue
        for p in re.split(r"(\s+)", t):
            if not p:
                continue
            if p.strip().casefold() == kw.casefold():
                out.append((p, tuple(accent)))
            else:
                out.append((p, None))
    return out


def draw_segmented_line(d, xy, segs, font, default_fill, stroke_fill, stroke_width,
                        align="center", center_x=None):
    """逐段渲染一行（价格黄色高亮 + 划线原价删除线），普通段用 default_fill"""
    if not segs:
        return
    ef = _emoji_font(int(font.size * 1.02))
    full = "".join(strip_strike_marks(t) for t, _ in segs)
    x, y = xy
    if align == "center" and center_x is not None:
        x = center_x - mixed_text_width(full, font, ef) / 2
    elif align == "right":
        x = x - mixed_text_width(full, font, ef)
    asc2, _d2 = font.getmetrics()
    for text, fcolor in segs:
        fill = fcolor or default_fill
        m = STRIKE_RE.match(text)
        if m:
            st_text, rest = m.group(1), m.group(2)
            w_st = mixed_text_width(st_text, font, ef)
            draw_mixed_text(d, (x, y), st_text, font, (198, 198, 198), stroke_fill, stroke_width,
                            align="left", center_x=None)
            # 删除线：横穿原价中部的粗黑线（真实划线价）
            ly = y + asc2 // 2
            d.line([(x - 2, ly), (x + w_st + 2, ly)], fill=(30, 30, 30),
                   width=max(4, font.size // 9))
            x += w_st
            if rest:
                x = draw_mixed_text(d, (x, y), rest, font, fill, stroke_fill, stroke_width,
                                    align="left", center_x=None)
        else:
            x = draw_mixed_text(d, (x, y), text, font, fill, stroke_fill, stroke_width,
                                align="left", center_x=None)
    return x

# ---------------- 颜色工具 ----------------

def scale_color(c, f):
    """颜色加深(f<1)/变浅(f>1)"""
    return tuple(max(0, min(255, int(v * f))) for v in c)

def blend(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

def complement(c):
    """近似互补色"""
    return tuple(255 - v for v in c)

# ---------------- 基础绘制 ----------------

def vertical_gradient(size, top, bottom):
    w, h = size
    img = Image.new("RGB", size)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        d.line([(0, y), (w, y)], fill=color)
    return img


def wrap_words(text, font, max_width):
    """按词换行，每行<=max_width，返回行列表"""
    words = str(text).split()
    lines, cur = [], ""
    for w_ in words:
        trial = (cur + " " + w_).strip()
        if font.getlength(trial) <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w_
    if cur:
        lines.append(cur)
    return lines or [""]


def draw_text_block(d, lines, font, center_x, start_y, line_gap, fill, stroke_fill=(0, 0, 0), stroke_width=6,
                    align="center", highlight=False, hl_color=(255, 235, 110, 115), hl_pad=12, hl_offset=(0, 0)):
    """多行文字块：居中/贴左/贴右 + 可选荧光笔划痕（TikTok 原生感）"""
    y = start_y
    widths = [d.textlength(l, font=font) for l in lines]
    max_w = max(widths) if widths else 0
    asc, _desc = font.getmetrics()
    for i, line in enumerate(lines):
        lw = widths[i]
        if align == "center":
            x = center_x - lw / 2
        elif align == "left":
            x = center_x - max_w / 2
        else:
            x = center_x + max_w / 2 - lw
        if highlight:
            # 荧光笔划痕：两道错位叠加 + 轻微抖动，模拟真人手划（不整条铺满）
            rnd = random.Random(997 + i * 13)
            jx = rnd.randint(-4, 4)
            hr0 = (x - 6 + hl_offset[0] + jx, y + hl_offset[1] + rnd.randint(-2, 2),
                   x + lw + 6 + hl_offset[0] + jx, y + asc - 4 + hl_offset[1])
            d.rounded_rectangle(hr0, radius=5, fill=hl_color)
            if len(hl_color) > 3:
                alpha2 = hl_color[3] // 2
                hr1 = (hr0[0] + rnd.randint(-9, 7), hr0[1] + rnd.randint(1, 5),
                       hr0[2] + rnd.randint(-7, 9), hr0[3] + rnd.randint(1, 3))
                d.rounded_rectangle(hr1, radius=5, fill=hl_color[:3] + (alpha2,))
        d.text((x, y), line, font=font, fill=fill,
               stroke_width=stroke_width, stroke_fill=stroke_fill)
        y += font.size + line_gap
    return y


def rounded_card(size, radius, color, border=None, border_w=0):
    w, h = size
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=color)
    if border and border_w:
        d.rounded_rectangle([border_w // 2, border_w // 2, w - 1 - border_w // 2, h - 1 - border_w // 2],
                            radius=radius, outline=border, width=border_w)
    return img


def paste_centered(base, layer, cx, cy, max_w=None, max_h=None):
    """把 RGBA layer 居中贴到 base 指定中心，可选缩放"""
    if max_w or max_h:
        w, h = layer.size
        scale = min((max_w or w) / w, (max_h or h) / h, 1.0)
        if scale < 1.0:
            layer = layer.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    w, h = layer.size
    base.paste(layer, (int(cx - w / 2), int(cy - h / 2)), layer)
    return base


def soft_shadow(base, cx, cy, size, radius, color=(0, 0, 0, 110), offset=(0, 18), blur=18):
    """在卡片下方画柔和阴影"""
    w, h = size
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([cx - w / 2 + offset[0], cy - h / 2 + offset[1],
                          cx + w / 2 + offset[0], cy + h / 2 + offset[1]],
                         radius=radius, fill=color)
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    base.paste(shadow, (0, 0), shadow)
    return base


def decorate(base, accent, n=6, seed=7):
    """背景装饰：半透明圆环+圆点，增加设计感"""
    rnd = random.Random(seed)
    w, h = base.size
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for _ in range(n):
        r = rnd.randint(40, 130)
        x, y = rnd.randint(-r, w), rnd.randint(0, h)
        alpha = rnd.randint(18, 42)
        d.ellipse([x - r, y - r, x + r, y + r], outline=accent + (alpha,), width=3)
        if rnd.random() < 0.5:
            rr = rnd.randint(6, 18)
            d.ellipse([x + r - rr, y - rr, x + r + rr, y + rr], fill=accent + (alpha,))
    base.paste(layer, (0, 0), layer)
    return base


def draw_bottle_placeholder(size, scheme):
    """内置香水瓶占位图（无产品图时使用），粉渐变瓶身+黑盖+标签"""
    w, h = size
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 瓶身（粉渐变）
    bw, bh = int(w * 0.52), int(h * 0.62)
    bx, by = (w - bw) // 2, int(h * 0.16)
    bottle = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bottle)
    for yy in range(bh):
        t = yy / max(1, bh - 1)
        col = blend((245, 150, 200), (255, 245, 250), t)
        bd.line([(0, yy), (bw, yy)], fill=col + (235,))
    mask = Image.new("L", (bw, bh), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, bw - 1, bh - 1], radius=int(bw * 0.18), fill=255)
    img.paste(bottle, (bx, by), mask)

    # 瓶盖（黑色圆角）
    cw, ch = int(w * 0.4), int(h * 0.1)
    cx_, cy_ = (w - cw) // 2, by - ch + int(h * 0.02)
    d.rounded_rectangle([cx_, cy_, cx_ + cw, cy_ + ch], radius=int(cw * 0.25), fill=(20, 20, 24, 255))

    # 银色金属环
    ring_y = cy_ + ch
    d.rounded_rectangle([bx - 4, ring_y, bx + bw + 4, ring_y + int(h * 0.025)],
                        radius=6, fill=(210, 215, 220, 255))

    # 标签
    lw, lh = int(w * 0.4), int(h * 0.16)
    lx, ly = (w - lw) // 2, by + int(bh * 0.30)
    d.rounded_rectangle([lx, ly, lx + lw, ly + lh], radius=8, fill=(255, 255, 255, 240))
    try:
        f1 = font_bold(int(h * 0.055))
        f2 = font_reg(int(h * 0.04))
        d.text((w / 2, ly + lh * 0.32), "VOYAGE NOVA", font=f1, fill=(40, 40, 50, 255), anchor="mm")
        d.text((w / 2, ly + lh * 0.74), "QAWAFI", font=f2, fill=(120, 120, 130, 255), anchor="mm")
    except Exception:
        pass
    return img


def load_product_image(path, size):
    """加载产品图并裁成方形居中，返回 RGBA"""
    if path and os.path.exists(path):
        try:
            img = Image.open(path).convert("RGB")
            w, h = img.size
            s = min(w, h)
            img = img.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2))
            img = img.resize(size, Image.LANCZOS)
            rgba = img.convert("RGBA")
            return rgba
        except Exception:
            return None
    return None


def paste_product(base, cx, cy, max_w, max_h, scheme, product_path, radius=28, border=None):
    """产品图卡片（圆角+描边+阴影）；无图时用内置瓶占位"""
    # 阴影
    soft_shadow(base, cx, cy, (max_w, max_h), radius, color=(0, 0, 0, 120))

    real = load_product_image(product_path, (max_w, max_h)) if product_path else None
    if real:
        layer = Image.new("RGBA", (max_w + 8, max_h + 8), (0, 0, 0, 0))
        mask = Image.new("L", (max_w, max_h), 0)
        md = ImageDraw.Draw(mask)
        md.rounded_rectangle([0, 0, max_w - 1, max_h - 1], radius=radius, fill=255)
        layer.paste(real, (4, 4), mask)
        if border:
            bd = ImageDraw.Draw(layer)
            bd.rounded_rectangle([4, 4, max_w + 3, max_h + 3], radius=radius, outline=border, width=4)
        base.paste(layer, (int(cx - layer.size[0] / 2), int(cy - layer.size[1] / 2)), layer)
    else:
        ph = draw_bottle_placeholder((max_w, max_h), scheme)
        if border:
            layer = Image.new("RGBA", (max_w + 8, max_h + 8), (0, 0, 0, 0))
            layer.paste(ph, (4, 4), ph)
            bd = ImageDraw.Draw(layer)
            bd.rounded_rectangle([4, 4, max_w + 3, max_h + 3], radius=radius, outline=border, width=4)
            base.paste(layer, (int(cx - layer.size[0] / 2), int(cy - layer.size[1] / 2)), layer)
        else:
            base.paste(ph, (int(cx - max_w / 2), int(cy - max_h / 2)), ph)
    return base


# ---------------- 配色方案解析 ----------------

def build_schemes(analysis):
    """根据参考图分析结果 + 内置方案库，产出N套可用配色"""
    bg = analysis.get("scheme", {}).get("background", (40, 32, 52))
    accent = analysis.get("scheme", {}).get("accent", (212, 175, 55))
    text = analysis.get("scheme", {}).get("text", (255, 255, 255))

    schemes = []
    # 1. 参考图主色系：背景加深→变浅渐变，强调色用金色/原强调色
    schemes.append({
        "name": "参考主色系",
        "bg_top": scale_color(bg, 0.55),
        "bg_bottom": scale_color(bg, 1.25),
        "text": (255, 255, 255) if luminance_v(bg) < 150 else (25, 25, 30),
        "accent": accent if saturate_v(accent) > 0.2 else (212, 175, 55),
        "card": scale_color(bg, 0.85),
    })
    # 2. 主色+金色贵感
    schemes.append({
        "name": "主色+金色贵感",
        "bg_top": scale_color(bg, 0.4),
        "bg_bottom": scale_color(bg, 0.95),
        "text": (255, 255, 255),
        "accent": (212, 175, 55),
        "card": scale_color(bg, 0.7),
    })
    # 3. 黑金高级
    schemes.append({
        "name": "黑金高级",
        "bg_top": (12, 12, 16),
        "bg_bottom": (34, 32, 40),
        "text": (255, 255, 255),
        "accent": (218, 165, 32),
        "card": (22, 22, 28),
    })
    # 4. 粉紫浪漫（香水女性向）
    schemes.append({
        "name": "粉紫浪漫",
        "bg_top": (70, 32, 62),
        "bg_bottom": (160, 88, 138),
        "text": (255, 255, 255),
        "accent": (255, 216, 236),
        "card": (96, 44, 86),
    })
    # 5. 清爽白+主色
    schemes.append({
        "name": "清爽白+主色",
        "bg_top": (252, 250, 252),
        "bg_bottom": (238, 233, 244),
        "text": (28, 28, 38),
        "accent": accent if saturate_v(accent) > 0.25 else (212, 175, 55),
        "card": (255, 255, 255),
    })
    # 6. 互补色冲击
    comp = complement(bg)
    schemes.append({
        "name": "互补色冲击",
        "bg_top": scale_color(comp, 0.5),
        "bg_bottom": scale_color(comp, 1.15),
        "text": (255, 255, 255),
        "accent": accent if saturate_v(accent) > 0.25 else (255, 214, 170),
        "card": scale_color(comp, 0.75),
    })
    return schemes


def luminance_v(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]

def saturate_v(c):
    mx, mn = max(c) / 255, min(c) / 255
    return 0 if mx == 0 else (mx - mn) / mx

# ---------------- 页面渲染 ----------------

def cover_resize(img, size):
    """保持比例，覆盖裁剪到目标尺寸"""
    tw, th = size
    w, h = img.size
    scale = max(tw / w, th / h)
    nw, nh = int(round(w * scale)), int(round(h * scale))
    img = img.resize((nw, nh), Image.LANCZOS)
    x = (nw - tw) // 2
    y = (nh - th) // 2
    return img.crop((x, y, x + tw, y + th))


def _readoverlay(w, h):
    """顶部+底部极轻黑色渐变遮罩：只保证叠字可读，不压暗画面（实拍原生感）"""
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    top_h = int(h * 0.30)
    for y in range(top_h):
        a = int(80 * (1 - y / top_h) ** 1.6)
        od.line([(0, y), (w, y)], fill=(0, 0, 0, a))
    bot_y = int(h * 0.80)
    bot_h = max(1, h - bot_y)
    for y in range(bot_y, h):
        t = (y - bot_y) / bot_h
        od.line([(0, y), (w, y)], fill=(0, 0, 0, int(70 * t ** 1.5)))
    return overlay


def render_hook_page(scheme, hook_text, cta_text, brand_name, product_path, seed, base_image=None):
    """
    图1：钩子页
    base_image: AI 生成的画面底图（铺满+叠字）；None 时回退到渐变+内置产品卡
    """
    w, h = CANVAS
    if base_image is not None:
        img = cover_resize(base_image, (w, h))
        img = Image.alpha_composite(img.convert("RGBA"), _readoverlay(w, h)).convert("RGB")
        d = ImageDraw.Draw(img)
    else:
        img = vertical_gradient((w, h), scheme["bg_top"], scheme["bg_bottom"])
        d = ImageDraw.Draw(img)

    # 顶部品牌小标
    try:
        f_brand = font_bold(40)
        d.text((w / 2, 120), brand_name.upper(), font=f_brand, fill=scheme["accent"], anchor="mm")
        d.line([(w / 2 - 180, 168), (w / 2 + 180, 168)], fill=scheme["accent"], width=2)
    except Exception:
        pass

    # 钩子叠字（画面上1/3，白粗体+黑描边，每行<=8词）
    f_hook = font_bold(92)
    max_w = int(w * 0.82)
    lines = wrap_words(hook_text, f_hook, max_w)
    # 最多显示4行，超出则缩小字号
    while len(lines) > 4 and f_hook.size > 52:
        f_hook = font_bold(f_hook.size - 8)
        lines = wrap_words(hook_text, f_hook, max_w)
    start_y = 260
    draw_text_block(d, lines, f_hook, w / 2, start_y, line_gap=26,
                    fill=scheme["text"], stroke_fill=(0, 0, 0), stroke_width=8)

    # AI 底图模式不叠产品卡（底图本身是场景画面）；回退模式保留产品卡
    if base_image is None:
        card_max_w, card_max_h = int(w * 0.66), int(h * 0.46)
        cy = int(h * 0.62)
        paste_product(img, w / 2, cy, card_max_w, card_max_h, scheme,
                      product_path, radius=30, border=scheme["accent"])

    # 底部CTA
    f_cta = font_bold(56)
    d.text((w / 2, int(h * 0.90)), cta_text, font=f_cta, fill=scheme["accent"],
           stroke_width=5, stroke_fill=(0, 0, 0), anchor="mm")
    return img


def paste_fit(pimg, max_w, max_h):
    """产品图等比缩放适配块内（居中）"""
    w, h = pimg.size
    scale = min(max_w / w, max_h / h, 1.0)
    if scale < 1.0:
        pimg = pimg.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    return pimg


def draw_arrow_down(d, cx, y_top, size, color=(255, 255, 255), stroke=(0, 0, 0), stroke_w=6):
    """TikTok 原生感下箭头（粗白杆 + 黑描边，更接近真人贴纸）"""
    shaft = size * 1.35
    head = size * 0.95
    # 杆（白+细黑描边）
    d.line([(cx, y_top), (cx, y_top + shaft)], fill=stroke, width=stroke_w + 5)
    d.line([(cx, y_top), (cx, y_top + shaft)], fill=color, width=stroke_w + 2)
    # 箭头头部
    pts = [(cx - head, y_top + shaft), (cx + head, y_top + shaft), (cx, y_top + shaft + head * 1.15)]
    d.polygon(pts, fill=stroke)
    pts2 = [(cx - head + 3, y_top + shaft), (cx + head - 3, y_top + shaft), (cx, y_top + shaft + head * 1.05)]
    d.polygon(pts2, fill=color)
    return y_top + shaft + head


def _draw_pointing_hand(d, cx, cy, size, color=(255, 255, 255), stroke=(0, 0, 0)):
    """手指标贴：白色指向箭头（食指形，黑描边），TikTok 常用「这里」手势"""
    # 手臂：粗线（从左上指向右下）
    arm = [(cx - size * 0.55, cy + size * 0.5), (cx + size * 0.4, cy - size * 0.45)]
    d.line(arm, fill=stroke, width=int(size * 0.28) + 6, joint="curve")
    d.line(arm, fill=color, width=int(size * 0.28), joint="curve")
    # 食指头：圆角椭圆
    r = size * 0.16
    ex, ey = cx + size * 0.46, cy - size * 0.5
    d.ellipse([ex - r, ey - r, ex + r, ey + r], fill=stroke)
    d.ellipse([ex - r + 3, ey - r + 3, ex + r - 3, ey + r - 3], fill=color)


def draw_cta_tag(d, cx, y_top, text, max_lines=2, base_size=52, orig_price=None):
    """价格/CTA 黑底横条 + 白字（TikTok 底部价格条，小圆角更原生）"""
    f = font_black(base_size)
    max_w = int(CANVAS[0] * 0.9)
    lines = wrap_words(text, f, max_w)
    while len(lines) > max_lines and f.size > 30:
        f = font_black(f.size - 6)
        lines = wrap_words(text, f, max_w)
    asc, desc = f.getmetrics()
    pad_x, pad_y = int(f.size * 0.30), int(f.size * 0.14)
    tag_w = int(max([d.textlength(l, font=f) for l in lines]) + 2 * pad_x)
    tag_h = f.size + asc + 2 * pad_y
    tx0 = cx - tag_w / 2
    d.rounded_rectangle([tx0, y_top, tx0 + tag_w, y_top + tag_h],
                        radius=int(f.size * 0.20), fill=(18, 16, 20))
    # 逐行渲染：价格/折扣数字黄色高亮 + 划线原价删除线（更接近真实 TikTok 价格条）
    y0 = y_top + pad_y + asc // 2
    for line in lines:
        segs = build_price_segments(sanitize_emoji(line), orig_price)
        draw_segmented_line(d, (0, y0), segs, f, (255, 255, 255), (0, 0, 0),
                            max(6, f.size // 5), align="center", center_x=cx)
        y0 += f.size + int(f.size * 0.28)
    return y_top + tag_h


def render_layout_page(scheme, blocks, texts, base_image=None, product_image=None, seed=0,
                       style_params=None, is_last=False, is_first=False):
    """
    按参考图的布局块渲染一张新图（排版跟随参考图）。
    blocks: [{"type": "title"|"body"|"cta"|"image", x0,y0,x1,y1 (0-1)}, ...]
    texts:  {"title": str, "body": str, "cta": str}（缺省不画）
    base_image: AI 画面 —— 有则满幅铺底（参考图风格：实拍图+叠字）
    product_image: 产品图路径（无 AI 画面时贴在 image 块）
    style_params: 人格渲染参数（styles.render_params）——字体/文字颜色/高亮/CTA样式/箭头
    is_last: 最后一张（价格页），箭头贴纸只在价格页画
    is_first: 首张（钩子页），只叠一句钩子（像真实 TikTok 钩子页：一张画面+一句话）
    """
    w, h = CANVAS
    full_photo = base_image is not None
    if full_photo:
        img = cover_resize(base_image, (w, h))
    elif is_last and product_image and os.path.exists(product_image):
        # 价格页原生底：真实产品图放大模糊铺底 + 轻微压暗（TikTok 常见做法，非渐变海报）
        try:
            pimg = Image.open(product_image).convert("RGB")
            bg = cover_resize(pimg.filter(ImageFilter.GaussianBlur(70)), (w, h))
            img = Image.eval(bg, lambda v: int(v * 0.86)).convert("RGB")
        except Exception:
            img = vertical_gradient((w, h), scheme["bg_top"], scheme["bg_bottom"])
    else:
        img = vertical_gradient((w, h), scheme["bg_top"], scheme["bg_bottom"])

    sp = style_params or {}
    text_color = sp.get("text_color", (255, 255, 255))
    hl_enabled = bool(sp.get("highlight", False))
    hl_color = sp.get("hl_color", (255, 235, 110, 105))

    # 1. image 块（仅无 AI 画面时：只贴最大的图片区，产品图贴一次）
    if not full_photo:
        img_blocks = [b for b in blocks if b["type"] == "image"]
        if img_blocks:
            big = max(img_blocks, key=lambda b: (b["x1"] - b["x0"]) * (b["y1"] - b["y0"]))
            bx0, by0 = int(big["x0"] * w), int(big["y0"] * h)
            bx1, by1 = int(big["x1"] * w), int(big["y1"] * h)
            bw, bh = bx1 - bx0, by1 - by0
            if product_image and os.path.exists(product_image):
                try:
                    pimg = Image.open(product_image).convert("RGBA")
                    pimg = paste_fit(pimg, int(bw * 0.92), int(bh * 0.92))
                    img.paste(pimg, (bx0 + (bw - pimg.size[0]) // 2,
                                     by0 + (bh - pimg.size[1]) // 2), pimg)
                except Exception:
                    pass

    # 2. 文字块（顶层，带白粗体黑描边）——同类型只渲染最大块，避免碎块重复
    d = ImageDraw.Draw(img)
    text_blocks = {}
    for b in blocks:
        if b["type"] not in ("title", "body", "cta"):
            continue
        cur = text_blocks.get(b["type"])
        if cur is None or (b["y1"] - b["y0"]) > (cur["y1"] - cur["y0"]):
            text_blocks[b["type"]] = b
    # 首张（钩子页）：只留一句钩子（title），丢弃 body/cta —— 真实 TikTok 钩子页就是这样
    if is_first:
        texts = dict(texts)
        texts["body"] = None
        texts["cta"] = None
        text_blocks = {t: b for t, b in text_blocks.items() if t == "title"}
    # 无 cta 块但有 cta 文案：价格页画底部黑条；中间页叠白字黑描边（更原生）
    if texts.get("cta") and "cta" not in text_blocks:
        body_b = text_blocks.get("body")
        if body_b:
            y_top = int((body_b["y1"] + 0.02) * h)
            if is_last:
                draw_cta_tag(d, w / 2, y_top, sanitize_emoji(texts["cta"]), max_lines=2)
            else:
                f = font_black(48)
                cta_lines = wrap_words(sanitize_emoji(texts["cta"]), f, int(w * 0.85))
                draw_text_block(d, cta_lines, f, w / 2, y_top, int(f.size * 0.22),
                                fill=(255, 255, 255), stroke_width=6, stroke_fill=(0, 0, 0))
        texts["cta"] = None

    # 3. 箭头贴纸（价格页且人格带箭头时：指向图片区下方）
    if sp.get("arrow") and is_last:
        img_y = 0.62 * h if not full_photo else 0.55 * h
        draw_arrow_down(d, w / 2, int(img_y), int(w * 0.045), color=text_color)
        texts["cta"] = None
    for b in text_blocks.values():
        text = texts.get(b["type"])
        if not text:
            continue
        text = sanitize_emoji(text)
        bx0, by0 = int(b["x0"] * w), int(b["y0"] * h)
        bx1, by1 = int(b["x1"] * w), int(b["y1"] * h)
        bw, bh = bx1 - bx0, by1 - by0
        cx = (bx0 + bx1) / 2
        max_lines = 2 if b["type"] == "title" else 3
        size = max(36, min(128, int(bh / (max_lines + 0.6))))
        if b["type"] == "cta":
            size = max(32, min(70, int(bh / 1.6)))
        # 文字颜色：实拍画面/模糊产品底用人格色（白/警示黄），纯渐变才用参考配色
        fill = text_color
        if not full_photo and not is_last:
            fill = scheme["text"] if b["type"] != "cta" else scheme["accent"]
        f = font_black(size)
        max_w = int(bw * 0.9)
        lines = wrap_words(text, f, max_w)
        while len(lines) > max_lines and size > 30:
            size -= 6
            f = font_black(size)
            lines = wrap_words(text, f, max_w)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            if len(lines[-1]) > 3:
                lines[-1] = lines[-1][:-1].rstrip() + "…"
        line_gap = int(size * 0.28)
        total_h = len(lines) * (size + line_gap)
        stroke_w = max(6, size // 5)
        if b["type"] == "cta" and is_last:
            # 价格/CTA：黑底横条 + 白字（TikTok 底部价格条，仅价格页）
            draw_cta_tag(d, cx, int(by0 + bh * 0.08), text, max_lines=2,
                         base_size=min(70, max(32, int(bh / 1.6))))
        else:
            # 标题/正文：顶部贴齐块 + 高亮划痕（人格色）
            start_y = by0 + int(size * 0.12)
            if b["type"] == "title":
                start_y = by0 + int(size * 0.05)
            hl_off = (0, 3) if b["type"] == "title" else (2, 4)
            draw_text_block(d, lines, f, cx, start_y, line_gap, fill=fill,
                            stroke_width=stroke_w, stroke_fill=(0, 0, 0),
                            align="center", highlight=hl_enabled,
                            hl_color=hl_color, hl_offset=hl_off)
    return img


# ---------------- 排版指纹渲染（AI 精分析，1:1 复刻参考图） ----------------

def _draw_underline(d, x0, y, x1, color=(255, 255, 255), stroke=(0, 0, 0), width=16):
    """手绘波浪下划线：白粗线 + 黑描边 + 轻微起伏（TikTok 圈词划线，真人感）"""
    import math
    pts = []
    steps = max(5, int((x1 - x0) / 34))
    phase = (x0 * 3) % 6.28
    for s_ in range(steps + 1):
        t = s_ / steps
        px = x0 + (x1 - x0) * t
        py = y + math.sin(phase + t * math.pi * 2.1) * (width * 0.24)
        pts.append((px, py))
    d.line(pts, fill=stroke, width=width + 4, joint="curve")
    d.line(pts, fill=color, width=width - 4, joint="curve")


def _draw_circle_highlight(d, cx, cy, r, color=(255, 255, 255), stroke=(0, 0, 0)):
    """圈重点：白圈 + 黑描边"""
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=stroke, width=8)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=4)


def _draw_check(d, cx, cy, size, color=(0, 200, 90), stroke=(0, 0, 0)):
    """勾选标记：绿勾 + 黑描边（TikTok 价格页常见）"""
    pts = [(cx - size * 0.8, cy), (cx - size * 0.1, cy + size * 0.7), (cx + size * 0.9, cy - size * 0.7)]
    d.line(pts, fill=stroke, width=16, joint="curve")
    d.line(pts, fill=color, width=9, joint="curve")


def _draw_price_tag(d, cx, cy, tw, th, color=(255, 215, 0), stroke=(0, 0, 0)):
    """价格标签贴纸：黄色圆角标签 + 黑描边"""
    d.rounded_rectangle([cx - tw / 2, cy - th / 2, cx + tw / 2, cy + th / 2],
                        radius=int(th * 0.28), fill=color, outline=stroke, width=5)


def render_fp_page(fp, texts, base_image=None, product_image=None, is_first=False, is_last=False, seed=0,
                   orig_price=None):
    """
    按排版指纹 1:1 复刻渲染一张图（AI 精分析产物）。
    fp: {"scheme":..., "blocks":[...], "text_zones":[...], "elements":[...]}
    texts: {"title":..., "body":..., "cta":...}（缺省不画）
    is_first: 钩子页（只画 title 区）
    is_last: 价格页（真实产品图模糊铺底 + 只画 body/cta 区）
    """
    w, h = CANVAS
    scheme = fp.get("scheme") or {"background": (40, 32, 52), "accent": (212, 175, 55), "text": (255, 255, 255)}
    bg_c = scheme.get("background", (40, 32, 52))
    full_photo = base_image is not None

    if full_photo:
        img = cover_resize(base_image, (w, h))
        img = Image.alpha_composite(img.convert("RGBA"), _readoverlay(w, h)).convert("RGB")
    elif is_last and product_image and os.path.exists(product_image):
        # 价格页原生底：真实产品图放大模糊铺底 + 轻微压暗
        try:
            pimg = Image.open(product_image).convert("RGB")
            bg = cover_resize(pimg.filter(ImageFilter.GaussianBlur(70)), (w, h))
            img = Image.eval(bg, lambda v: int(v * 0.86)).convert("RGB")
        except Exception:
            img = vertical_gradient((w, h), scale_color(bg_c, 0.7), bg_c)
    else:
        img = vertical_gradient((w, h), scale_color(bg_c, 0.7), bg_c)
    d = ImageDraw.Draw(img)

    # 图片区：无 AI 画面时贴产品图（价格页/中间页回退；钩子页只叠字不贴图）
    if not full_photo and not is_first and product_image and os.path.exists(product_image):
        img_blocks = [b for b in fp.get("blocks", []) if b.get("type") == "image"]
        if img_blocks:
            big = max(img_blocks, key=lambda b: (b["x1"] - b["x0"]) * (b["y1"] - b["y0"]))
            bx0, by0 = int(big["x0"] * w), int(big["y0"] * h)
            bx1, by1 = int(big["x1"] * w), int(big["y1"] * h)
            bw, bh = bx1 - bx0, by1 - by0
            try:
                pimg = Image.open(product_image).convert("RGBA")
                pimg = paste_fit(pimg, int(bw * 0.92), int(bh * 0.92))
                img.paste(pimg, (bx0 + (bw - pimg.size[0]) // 2,
                                 by0 + (bh - pimg.size[1]) // 2), pimg)
            except Exception:
                pass

    # 按指纹选文字区（价格页不过滤：指纹有什么区画什么区，texts 空自动跳过）
    zones = [z for z in (fp.get("text_zones") or []) if z.get("block") in ("title", "body", "cta")]
    if is_first:
        zones = [z for z in zones if z["block"] == "title"]

    # 1. 底条（has_bar）先画，文字后画
    bar_layers = []
    for z in zones:
        text = texts.get(z["block"])
        if not text:
            continue
        bx0, by0 = int(z["x0"] * w), int(z["y0"] * h)
        bx1, by1 = int(z["x1"] * w), int(z["y1"] * h)
        bw, bh = bx1 - bx0, by1 - by0
        cx = (bx0 + bx1) / 2
        size = max(24, min(140, int(z.get("size_ratio", 0.06) * h)))
        f = font_black(size) if z.get("font") != "bold" else font_bold(size)
        max_lines = max(1, z.get("max_lines", 2))
        max_w = int(bw * 0.96)
        lines = wrap_words(text, f, max_w)
        while len(lines) > max_lines and size > 24:
            size -= 5
            f = font_black(size) if z.get("font") != "bold" else font_bold(size)
            lines = wrap_words(text, f, max_w)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
        line_gap = int(size * 0.30)
        if z.get("has_bar"):
            bar_color = tuple(z.get("bar_color", (0, 0, 0)))
            bar_alpha = z.get("bar_alpha", 0.8)
            pad_x, pad_y = int(size * 0.24), int(size * 0.16)
            ef = _emoji_font(size)
            bar_w = max([mixed_text_width(l, f, ef) for l in lines]) + 2 * pad_x
            bar_h = len(lines) * size + (len(lines) - 1) * line_gap + 2 * pad_y
            bx = cx - bar_w / 2
            by = by0
            bar = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            bd = ImageDraw.Draw(bar)
            bd.rounded_rectangle([bx, by, bx + bar_w, by + bar_h],
                                 radius=int(size * 0.26),
                                 fill=bar_color + (int(255 * bar_alpha),))
            bar_layers.append(bar)

    for bar in bar_layers:
        img.paste(bar, (0, 0), bar)

    # 2. 文字（逐字符混合 emoji）
    for z in zones:
        block = z["block"]
        text = texts.get(block)
        if not text:
            continue
        bx0, by0 = int(z["x0"] * w), int(z["y0"] * h)
        bx1, by1 = int(z["x1"] * w), int(z["y1"] * h)
        bw, bh = bx1 - bx0, by1 - by0
        cx = (bx0 + bx1) / 2
        size = max(24, min(140, int(z.get("size_ratio", 0.06) * h)))
        f = font_black(size) if z.get("font") != "bold" else font_bold(size)
        max_lines = max(1, z.get("max_lines", 2))
        max_w = int(bw * 0.96)
        lines = wrap_words(text, f, max_w)
        while len(lines) > max_lines and size > 24:
            size -= 5
            f = font_black(size) if z.get("font") != "bold" else font_bold(size)
            lines = wrap_words(text, f, max_w)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            if len(lines[-1]) > 3:
                lines[-1] = lines[-1][:-1].rstrip() + "…"
        line_gap = int(size * 0.30)
        fill = tuple(z.get("text_color", (255, 255, 255)))
        stroke = tuple(z.get("stroke", (0, 0, 0)))
        sw = max(3, int(size * 0.14))
        align = z.get("align", "center")
        accent_c = scheme.get("accent", (212, 175, 55))
        # 钩子关键词强调：从完整文案里挑一个词（种子决定，稳定不重复），用参考图强调色标出
        kw = None
        if block == "title":
            words_all = [wd for wd in text.split() if len(wd) >= 3]
            if words_all:
                kw = words_all[seed % len(words_all)]
        start_y = by0 + int(size * 0.10) + (int(size * 0.16) if z.get("has_bar") else 0)
        y = start_y
        for line in lines:
            # 价格/折扣数字黄色高亮 + 划线原价删除线 + 关键词 accent 强调
            line_s = sanitize_emoji(line)
            segs = build_price_segments(line_s, orig_price if block == "cta" else None)
            segs = _accent_word_segments(line_s, kw, accent_c, segs)
            draw_segmented_line(d, (bx0, y), segs, f, fill, stroke, sw,
                                align=align, center_x=cx)
            y += size + line_gap

    # 3. 元素贴纸（箭头/下划线/圆圈/勾选/价格标签）
    for e in fp.get("elements") or []:
        t = e.get("type", "")
        ex0, ey0 = int(e["x0"] * w), int(e["y0"] * h)
        ex1, ey1 = int(e["x1"] * w), int(e["y1"] * h)
        ecx, ecy = (ex0 + ex1) / 2, (ey0 + ey1) / 2
        ew, eh = ex1 - ex0, ey1 - ey0
        if t == "arrow":
            draw_arrow_down(d, ecx, ey0, max(30, int(ew * 0.5)), color=(255, 255, 255))
        elif t == "underline":
            _draw_underline(d, ex0, ecy, ex1)
        elif t == "circle":
            _draw_circle_highlight(d, ecx, ecy, max(30, int(max(ew, eh) * 0.6)))
        elif t == "check":
            _draw_check(d, ecx, ecy, max(24, int(min(ew, eh) * 0.8)))
        elif t == "price_tag":
            _draw_price_tag(d, ecx, ecy, max(80, int(ew * 1.2)), max(40, int(eh * 1.4)))
        elif t == "hand":
            _draw_pointing_hand(d, ecx, ecy, max(44, int(max(ew, eh) * 0.5)))
    return img


def render_price_page(scheme, product, price_text, product_path, seed):
    """图2：产品价格页（产品大图 + 价格卡 + 数据背书）"""
    w, h = CANVAS
    img = vertical_gradient((w, h), scale_color(scheme["bg_top"], 0.75), scheme["bg_bottom"])
    img = decorate(img, scheme["accent"], seed=seed + 31)

    d = ImageDraw.Draw(img)

    # 顶部品牌
    f_brand = font_bold(46)
    d.text((w / 2, 150), f"{product['brand']} {product['name']}".upper(), font=f_brand,
           fill=scheme["text"], stroke_width=4, stroke_fill=(0, 0, 0), anchor="mm")

    # 产品大图
    card_max_w, card_max_h = int(w * 0.62), int(h * 0.42)
    cy = int(h * 0.40)
    paste_product(img, w / 2, cy, card_max_w, card_max_h, scheme,
                  product_path, radius=34, border=scheme["accent"])

    # 价格卡（深色圆角横条，文字分两行防溢出）
    pw, ph = int(w * 0.88), int(h * 0.14)
    px0, py0 = (w - pw) // 2, int(h * 0.665)
    card = rounded_card((pw, ph), 26, scheme["card"], border=scheme["accent"], border_w=3)
    img.paste(card, (px0, py0), card)
    # 拆价格卡为两行
    price_parts = price_text.split(" · ")
    line1 = " · ".join(price_parts[:2])
    line2 = " · ".join(price_parts[2:])
    f_price = font_bold(52)
    d.text((w / 2, py0 + ph * 0.34), line1, font=f_price, fill=scheme["accent"],
           stroke_width=4, stroke_fill=(0, 0, 0), anchor="mm")
    f_price2 = font_bold(46)
    d.text((w / 2, py0 + ph * 0.70), line2, font=f_price2, fill=scheme["accent"],
           stroke_width=4, stroke_fill=(0, 0, 0), anchor="mm")

    # 数据背书小字（两行）
    f_meta = font_reg(36)
    meta1 = f"{product['rating']} · {product['sales']}"
    meta2 = f"{product['refund']}"
    d.text((w / 2, int(h * 0.83)), meta1, font=f_meta, fill=scheme["text"],
           stroke_width=3, stroke_fill=(0, 0, 0), anchor="mm")
    d.text((w / 2, int(h * 0.875)), meta2, font=f_meta, fill=scheme["text"],
           stroke_width=3, stroke_fill=(0, 0, 0), anchor="mm")
    return img


# ---------------- 发布包生成 ----------------

def build_pack(style_key, seed, lang, product, shot_prompt, texts_override=None):
    """按账号人格生成一套的发布文案包（与图片叠字同源，非流水线）
    texts_override: AI 模仿文案 dict（含 title/body/cta/caption/tags/comment_hook/pinned/style_name）"""
    t = texts_override or styles.build_texts(style_key, seed, lang=lang)
    price = C.price_card_text(lang)

    pack = {
        "angle": style_key,
        "angle_name": t["style_name"],
        "lang": lang,
        "hook": t["title"],
        "caption": t["caption"],
        "tags": " ".join(t["tags"]),
        "comment_hook": t["comment_hook"],
        "pinned": t["pinned"],
        "price_text": price,
        "shot_prompt": shot_prompt,
        "product_prompt": C.PRODUCT_SHOT_PROMPT,
    }
    return pack


def pack_to_text(pack, scheme_name):
    lines = [
        f"【套件：{pack['angle_name']} · {pack['lang'].upper()} · 配色:{scheme_name} · 轮播{pack.get('slides', 1)}张】",
        "",
        "◆ 图1叠字（钩子）:",
        pack["hook"],
        "",
        "◆ 图2价格卡:",
        pack["price_text"],
        "",
        "◆ 发布正文:",
        pack["caption"],
        "",
        "◆ 话题标签:",
        pack["tags"],
        "",
        "◆ 评论钩子:",
        pack["comment_hook"],
        "",
        "◆ 置顶评论:",
        pack["pinned"],
        "",
        "◆ 图1英文生图提示词（AI生成实拍素材用）:",
        pack["shot_prompt"],
        "",
        "◆ 图2产品图提示词（全批复用）:",
        pack["product_prompt"],
        "",
        "=" * 50,
        "",
    ]
    return "\n".join(lines)


# ---------------- 主生成入口 ----------------

def generate(analysis_list, product=None, lang="es", sets=5, product_image=None,
             out_dir=None, angles=None, seed_offset=0, ai_images=None, style_mode=None,
             copy_texts=None, per_set_langs=None, product_images=None):
    """
    生成多套图文（排版/张数跟随参考图文）。
    analysis_list: 逐张参考图分析结果列表（dict 或 error dict）；
                   每套张数 = 有效参考图张数，第k张按参考图k的布局/配色渲染。
                   含 text_zones 的条目走"排版指纹"1:1 复刻渲染（AI 精分析）。
    product: 产品信息 dict（缺省用 content.DEFAULT_PRODUCT）
    lang: 'es'/'en'/'both'
    sets: 套数
    product_image: 产品图路径或None
    out_dir: 输出目录（默认 ./output）
    angles: 指定角度列表（缺省按 sets 轮换5个角度）
    ai_images: 嵌套列表 [[每张AI画面...], 每套...]（第k张画面给参考图k）
    style_mode: None/'auto'=按套轮换4账号人格；或 'apg'/'conmariaa'/'jonhy'/'viviana' 固定人格
    copy_texts: 每套 AI 模仿文案 [{"hook":..,"body":..,"cta":..,"caption":..,"tags":..,...}, ...]
                缺省回退人格文案池
    返回: [(套目录, [(文件名,路径),...], pack, scheme_name), ...]
    """
    # 兼容传单张 dict
    if isinstance(analysis_list, dict):
        analysis_list = [analysis_list]
    valid = [a for a in analysis_list if isinstance(a, dict) and "error" not in a]
    if not valid:
        valid = [{
            "scheme": {"background": (40, 32, 52), "accent": (212, 175, 55), "text": (255, 255, 255)},
            "blocks": [
                {"type": "title", "x0": 0.0, "y0": 0.10, "x1": 1.0, "y1": 0.30},
                {"type": "image", "x0": 0.0, "y0": 0.32, "x1": 1.0, "y1": 0.74},
                {"type": "cta", "x0": 0.0, "y0": 0.80, "x1": 1.0, "y1": 0.92},
            ],
        }]
    slides = len(valid)  # 每套张数 = 参考图张数

    product = product or C.DEFAULT_PRODUCT
    out_dir = out_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

    # 每张参考图各自的配色（取各自主色系）
    schemes = [build_schemes(a)[0] for a in valid]

    # 角度轮换
    if angles is None:
        angles = ["pov", "rosas", "value", "long", "flash"]
    angle_list = []
    for i in range(sets):
        angle_list.append(angles[i % len(angles)])

    # 语言分配（支持逐套指定；否则按 lang 模式分配）
    if per_set_langs:
        lang_list = list(per_set_langs)
    else:
        lang_list = []
        for i in range(sets):
            if lang == "both":
                lang_list.append("en" if i % 2 == 0 else "es")
            else:
                lang_list.append(lang)

    results = []
    for i in range(sets):
        ang = angle_list[i]
        lg = lang_list[i]
        seed = seed_offset + i * 17
        # 本套产品图：多张轮换（product_images[i % n]），无则用单张/内置素材
        p_img = product_image
        if product_images:
            p_img = product_images[i % len(product_images)]

        # 人格分配：auto/None=按套轮换4账号人格；指定key=固定该人格
        if style_mode and style_mode in styles.STYLES:
            style_key = style_mode
        else:
            style_key = styles.STYLE_KEYS[i % len(styles.STYLE_KEYS)]
        sp = styles.render_params(style_key)
        # 文案来源：AI 模仿文案（copy_texts）优先；否则人格池
        if copy_texts and i < len(copy_texts) and copy_texts[i]:
            ct = copy_texts[i]
            hook_t = ct.get("hook") or ""
            body_t = ct.get("body") or ""
            cta_t = ct.get("cta") or ""
            t1 = {
                "title": hook_t, "body": body_t, "cta": cta_t,
                "caption": ct.get("caption", ""), "tags": ct.get("tags", ""),
                "comment_hook": ct.get("comment_hook", ""), "pinned": ct.get("pinned", ""),
                "style_name": styles.STYLES[style_key]["name"],
            }
            t2 = dict(t1)
        else:
            t1 = styles.build_texts(style_key, seed, lang=lg)
            t2 = styles.build_texts(style_key, seed + 3, lang=lg)

        # 图1提示词：换人物/场景/情节槽，保证套间不重复
        p_i, s_i, pl_i = seed_offset + i, seed_offset + i * 2 + 1, seed_offset + i * 3 + 2
        shot_prompt = C.build_shot_prompt(p_i, s_i, pl_i)

        brand_name = f"{product['brand']} {product['name']}"
        price = C.price_card_text(lg)

        # 每套的 AI 画面列表（与参考图张数对应；ai_images[i] 可为 None 或缺省）
        ai_set = None
        if ai_images and i < len(ai_images):
            ai_set = ai_images[i] or []

        # 逐张渲染（排版跟随参考图）
        set_dir = os.path.join(out_dir, f"套{i + 1}_{C.ANGLES[ang]['name']}_{lg.upper()}")
        os.makedirs(set_dir, exist_ok=True)
        pages = []
        for k in range(slides):
            scheme_k = schemes[k % len(schemes)]
            blocks_k = valid[k].get("blocks") or []
            brand_name = f"{product['brand']} {product['name']}"
            is_first = (k == 0)
            if k == 0:
                # 钩子页只放一句钩子（参考图即：一张实拍+一句大字）
                texts = {"title": t1["title"], "body": "", "cta": ""}
            elif k == slides - 1 and slides > 1:
                # 价格页：本套产品图（多张轮换）→ 不 AI 画瓶，直接用真实产品图
                if p_img and os.path.exists(p_img):
                    if ai_set:
                        ai_set = list(ai_set)
                        ai_set[k] = None
                # 价格页文本按参考图指纹的 zone 结构分配（参考图什么样就放哪）
                fp_k = valid[k] if valid[k].get("text_zones") else None
                zone_blocks = [z.get("block") for z in (fp_k.get("text_zones") or [])]
                has_t, has_b, has_c = "title" in zone_blocks, "body" in zone_blocks, "cta" in zone_blocks
                texts = {"title": "", "body": "", "cta": ""}
                if has_c:
                    # cta 区小（max_lines<=2 或高度<0.08）用短价格，否则完整价格
                    cz = next((z for z in (fp_k.get("text_zones") or []) if z.get("block") == "cta"), None)
                    if cz and (cz.get("max_lines", 2) <= 2 or (cz.get("y1", 0) - cz.get("y0", 0)) < 0.08):
                        texts["cta"] = C.price_card_short(lg)
                    else:
                        texts["cta"] = price
                if has_b:
                    texts["body"] = t2["body"]
                    if has_t:
                        texts["title"] = t2["caption"] or ""
                elif has_t:
                    texts["title"] = t2["body"]
            else:
                # 中间页（卖点页）：title 区放短评价引语（caption 第一句），body 区放卖点句
                cap_first = t2["caption"] or ""
                for sep in [". ", ".", "! ", "? ", "…"]:
                    idx = cap_first.find(sep)
                    if 0 < idx < 90:
                        cap_first = cap_first[:idx + 1].strip()
                        break
                else:
                    cap_first = cap_first[:70].strip()
                texts = {"title": cap_first or t2["body"], "body": t2["body"], "cta": ""}
            base_image = None
            if ai_set and k < len(ai_set) and ai_set[k] is not None:
                base_image = ai_set[k]
            # AI 精分析指纹：有 text_zones 走 1:1 复刻渲染；否则旧排版
            fp_k = valid[k] if valid[k].get("text_zones") else None
            if fp_k is not None:
                page = render_fp_page(fp_k, texts,
                                      base_image=base_image,
                                      product_image=p_img,
                                      is_first=is_first,
                                      is_last=(k == slides - 1),
                                      seed=seed + k,
                                      orig_price=product.get("orig_price") or None)
            else:
                page = render_layout_page(scheme_k, blocks_k, texts,
                                          base_image=base_image,
                                          product_image=p_img,
                                          seed=seed + k,
                                          style_params=sp,
                                          is_last=(k == slides - 1),
                                          is_first=is_first)
            if k == 0:
                fname = "图1_钩子页.png"
            elif k == slides - 1 and slides > 1:
                fname = f"图{k + 1}_价格页.png"
            else:
                fname = f"图{k + 1}_卖点页.png"
            fpath = os.path.join(set_dir, fname)
            page.save(fpath)
            pages.append((fname, fpath))

        pack = build_pack(style_key, seed, lg, product, shot_prompt, texts_override=t1)
        pack["slides"] = slides
        with open(os.path.join(set_dir, "发布包.txt"), "w", encoding="utf-8") as f:
            f.write(pack_to_text(pack, schemes[0]["name"]))

        results.append((set_dir, pages, pack, schemes[0]["name"]))

    return results


if __name__ == "__main__":
    # 自检：用分析结果生成示例（排版跟随参考图）
    import analysis as A
    ref = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "_selftest_ref.png")
    res = A.analyze_image(ref)
    out = generate([res], lang="both", sets=2, out_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "自检输出"))
    for name, pages, pack, scheme in out:
        print(name, "|", pack["angle_name"], pack["lang"], "| 张数:", pack.get("slides", 1),
              "|", "; ".join(fn for fn, _ in pages))
    print("生成完成")
