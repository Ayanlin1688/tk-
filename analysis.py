# -*- coding: utf-8 -*-
"""
analysis.py — 参考图文分析引擎（纯本地，无需API）
功能：
1. 主色提取（背景色/强调色/文字色推断）
2. 文字区域检测（亮度方差聚类）
3. 布局结构识别（标题区/图片区/卖点区/CTA区）
4. 生成标注图（可视化分析结果，供 GUI 展示）
"""

from PIL import Image, ImageDraw, ImageFont
import os

# ---------------- 基础颜色工具 ----------------

def luminance(rgb):
    """计算感知亮度 0-255"""
    r, g, b = rgb
    return 0.299 * r + 0.587 * g + 0.114 * b


def color_dist(c1, c2):
    return sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5


def saturate(rgb):
    """饱和度 0-1（HSV）"""
    r, g, b = [v / 255.0 for v in rgb]
    mx, mn = max(r, g, b), min(r, g, b)
    if mx == 0:
        return 0.0
    return (mx - mn) / mx


def is_near_white(rgb, thresh=235):
    return all(v >= thresh for v in rgb)


def is_near_black(rgb, thresh=18):
    return all(v <= thresh for v in rgb)


# ---------------- 主色提取 ----------------

def extract_main_colors(image, n=6):
    """缩小图片后量化，返回按占比排序的主色列表 [(rgb, ratio), ...]"""
    small = image.resize((80, 80))
    q = small.convert("RGB").quantize(colors=n, method=Image.MEDIANCUT)
    palette = q.getpalette()[: n * 3]
    counts = {}
    for px in q.getdata():
        counts[px] = counts.get(px, 0) + 1
    total = sum(counts.values())
    result = []
    for idx, cnt in sorted(counts.items(), key=lambda kv: -kv[1]):
        r, g, b = palette[idx * 3 : idx * 3 + 3]
        result.append(((r, g, b), cnt / total))
    return result


def infer_scheme(main_colors):
    """
    从主色推断：背景色、强调色、文字色
    - background: 占比最大且非极端纯黑白的色（或面积最大）
    - accent: 饱和度最高且占比>5% 的色
    - text: 与背景对比度最大的色（白/黑）
    """
    colors = [c for c, _ in main_colors]
    ratios = [r for _, r in main_colors]

    # 背景：占比最大的非纯白/纯黑
    bg = colors[0]
    for (c, r) in main_colors:
        if not is_near_white(c) and not is_near_black(c):
            bg = c
            break

    # 强调色：饱和度最高且占比>=0.04 的色；否则取非背景的次主色
    accent = None
    for (c, r) in main_colors[1:]:
        if r >= 0.04 and saturate(c) > 0.35:
            accent = c
            break
    if accent is None:
        for (c, r) in main_colors[1:]:
            if not is_near_white(c) and not is_near_black(c):
                accent = c
                break
    if accent is None:
        accent = bg

    # 文字色：与背景对比度大的那一个
    lum_bg = luminance(bg)
    text = (255, 255, 255) if lum_bg < 140 else (25, 25, 30)

    return {"background": bg, "accent": accent, "text": text}


# ---------------- 结构分析 ----------------

def _row_stats(gray):
    """每行像素的 (均值, 标准差)，用于找文字/边界"""
    w, h = gray.size
    px = gray.load()
    means, stds = [], []
    for y in range(h):
        vals = [px[x, y] for x in range(w)]
        m = sum(vals) / w
        var = sum((v - m) ** 2 for v in vals) / w
        stds.append(var ** 0.5)
        means.append(m)
    return means, stds


def detect_text_rows(stds, band=12):
    """
    把图片按行聚类成「文字密集行带」。
    文字行通常标准差大；返回 [(y0, y1, intensity), ...]
    """
    h = len(stds)
    bands = []
    for start in range(0, h, band):
        seg = stds[start : start + band]
        bands.append((start, min(start + band, h), sum(seg) / len(seg)))

    # 按强度阈值找出显著带，合并相邻
    top = sorted(bands, key=lambda b: -b[2])[:max(4, len(bands) // 3)]
    threshold = top[-1][2] if top else 5
    threshold = max(threshold, 6.0)

    active = [(s, e, v) for (s, e, v) in bands if v >= threshold]
    merged = []
    for s, e, v in active:
        if merged and s - merged[-1][1] <= band * 1.5:
            ms, me, mv = merged[-1]
            merged[-1] = (ms, max(me, e), max(mv, v))
        else:
            merged.append((s, e, v))

    # 过滤：太窄的带（可能是细线）保留但标记弱；太宽(超过1/3画布)可能是整幅图案
    result = []
    for s, e, v in merged:
        if e - s < 8:
            continue
        result.append((s, e, v))
    return result


def classify_regions(image, text_rows):
    """
    把画布按 y 划分为互斥区域，给出类型。
    类型：text（文字区）/ image（大图区）/ bg（纯背景）
    """
    w, h = image.size
    regions = []
    cursor = 0
    for s, e, v in sorted(text_rows, key=lambda r: r[0]):
        if s > cursor + h * 0.04:
            # cursor..s 之间：判断是图片区还是背景区
            regions.append({"type": "gap", "y0": cursor, "y1": s, "x0": 0, "x1": w})
        regions.append({"type": "text", "y0": s, "y1": e, "x0": 0, "x1": w, "intensity": v})
        cursor = e
    if cursor < h - 2:
        regions.append({"type": "gap", "y0": cursor, "y1": h, "x0": 0, "x1": w})

    # 将 gap 区分为 image / bg：用色彩丰富度判断
    small = image.convert("RGB").resize((40, 80))
    px = small.load()
    sw, sh = small.size
    for reg in regions:
        if reg["type"] != "gap":
            continue
        y0 = int(reg["y0"] / h * sh)
        y1 = max(y0 + 1, int(reg["y1"] / h * sh))
        vals = []
        for y in range(y0, y1):
            for x in range(sw):
                v = px[x, y]
                if isinstance(v, int):
                    v = (v, v, v)
                elif len(v) > 3:
                    v = tuple(v[:3])
                vals.append(v)
        uniq = len(set(vals))
        rich = len(vals) and (uniq / len(vals))
        avg_rgb = tuple(sum(c[i] for c in vals) // max(1, len(vals)) for i in range(3))
        lum_var = sum((luminance(v) - luminance(avg_rgb)) ** 2 for v in vals) / max(1, len(vals))
        if rich > 0.25 or lum_var > 900:
            reg["type"] = "image"
        else:
            reg["type"] = "bg"

    return regions


def detect_layout(regions, h):
    """
    依据区域分布识别布局模板：
    - top_text: 顶部有文字区（标题）
    - mid_image: 中部有图片区
    - bottom_text: 底部有文字区（卖点/CTA）
    返回布局描述与锚点位置。
    """
    layout = {
        "title_y": None,    # 标题区中心y比例
        "image_y": None,    # 图片区中心y比例
        "body_y": None,     # 正文/卖点区中心y比例
        "cta_y": None,      # CTA区中心y比例
        "style": [],
    }
    text_regs = [r for r in regions if r["type"] == "text"]
    img_regs = [r for r in regions if r["type"] == "image"]

    for r in text_regs:
        center = (r["y0"] + r["y1"]) / 2 / h
        if center < 0.30:
            layout["title_y"] = center
        elif center < 0.70:
            layout["body_y"] = center
        else:
            layout["cta_y"] = center

    if img_regs:
        biggest = max(img_regs, key=lambda r: r["y1"] - r["y0"])
        layout["image_y"] = (biggest["y0"] + biggest["y1"]) / 2 / h

    style = []
    if layout["title_y"] is not None:
        style.append("顶部标题")
    if layout["image_y"] is not None:
        style.append("中图")
    if layout["body_y"] is not None:
        style.append("中部卖点")
    if layout["cta_y"] is not None:
        style.append("底部CTA")
    layout["style"] = style if style else ["纯图无字（钩子视觉页）"]
    return layout


def to_blocks(regions, w, h):
    """
    把区域转为归一化渲染块（生成器按块排版）。
    块类型：title（顶部文字）/ body（中部文字）/ cta（底部文字）/ image（图片区）
    """
    blocks = []
    for r in regions:
        if r["type"] == "text":
            y0n, y1n = r["y0"] / h, r["y1"] / h
            c = (y0n + y1n) / 2
            t = "title" if c < 0.30 else ("cta" if c > 0.75 else "body")
            blocks.append({"type": t, "x0": 0.0, "y0": y0n, "x1": 1.0, "y1": y1n,
                           "intensity": r.get("intensity", 20)})
        elif r["type"] == "image":
            blocks.append({"type": "image", "x0": 0.0, "y0": r["y0"] / h,
                           "x1": 1.0, "y1": r["y1"] / h})
    # 同类型相邻块合并（避免碎块导致文字重复渲染）
    merged = []
    for b in blocks:
        if merged and merged[-1]["type"] == b["type"] and abs(b["y0"] - merged[-1]["y1"]) < 0.05:
            merged[-1]["y1"] = max(merged[-1]["y1"], b["y1"])
            merged[-1]["intensity"] = max(merged[-1].get("intensity", 0), b.get("intensity", 0))
        else:
            merged.append(dict(b))
    return merged


def draw_annotation(image, regions, out_path):
    """把分析结果画到参考图上（文字区=绿框，图片区=蓝框），用于GUI展示"""
    img = image.convert("RGB").copy()
    draw = ImageDraw.Draw(img)
    w, h = img.size
    try:
        font = ImageFont.truetype("arialbd.ttf", max(14, int(h * 0.025)))
    except Exception:
        font = ImageFont.load_default()
    for r in regions:
        y0, y1 = int(r["y0"]), int(r["y1"])
        if r["type"] == "text":
            color = (0, 200, 80)
            label = "文字区"
        elif r["type"] == "image":
            color = (60, 120, 255)
            label = "图片区"
        else:
            color = (150, 150, 150)
            label = "背景"
        draw.rectangle([4, y0, w - 4, y1], outline=color, width=4)
        draw.text((10, y0 + 2), label, fill=color, font=font)
    img.save(out_path)
    return out_path


# ---------------- 主入口 ----------------

def analyze_image(image_path):
    """
    分析单张参考图，返回结构化结果 dict
    """
    img = Image.open(image_path).convert("RGB")
    w, h = img.size

    main_colors = extract_main_colors(img)
    scheme = infer_scheme(main_colors)
    gray = img.convert("L")
    _, stds = _row_stats(gray)
    text_rows = detect_text_rows(stds)
    regions = classify_regions(img, text_rows)
    layout = detect_layout(regions, h)
    blocks = to_blocks(regions, w, h)

    # 是否为竖版
    vertical = h > w

    return {
        "path": image_path,
        "size": (w, h),
        "vertical": vertical,
        "main_colors": main_colors,
        "scheme": scheme,
        "text_rows": text_rows,
        "regions": regions,
        "layout": layout,
        "blocks": blocks,
    }


def analyze_many(paths):
    """分析多张参考图（一个图文帖可能多张）"""
    results = []
    for p in paths:
        try:
            results.append(analyze_image(p))
        except Exception as e:
            results.append({"path": p, "error": str(e)})
    return results


def summarize(results):
    """把多图分析汇总为一份可读摘要（中文），供 GUI 展示"""
    lines = []
    for i, r in enumerate(results, 1):
        if "error" in r:
            lines.append(f"第{i}张：解析失败（{r['error']}）")
            continue
        sch = r["scheme"]
        lines.append(
            f"第{i}张 {r['size'][0]}x{r['size'][1]}{'（竖版✓）' if r['vertical'] else '（横版）'}"
        )
        lines.append(
            f"  背景色 RGB{sch['background']} | 强调色 RGB{sch['accent']} | 文字色 RGB{sch['text']}"
        )
        lines.append(f"  布局：{' → '.join(r['layout']['style'])}")
    return "\n".join(lines)


if __name__ == "__main__":
    # 自检：生成一张测试图并分析
    import random
    test = Image.new("RGB", (1080, 1920), (40, 32, 52))
    d = ImageDraw.Draw(test)
    d.rectangle([80, 300, 1000, 600], fill=(250, 250, 250))
    d.rectangle([200, 750, 880, 1500], fill=(220, 180, 210))
    d.rectangle([80, 1680, 1000, 1800], fill=(255, 214, 170))
    test.save(os.path.join(os.path.dirname(__file__), "assets", "_selftest_ref.png"))
    res = analyze_image(os.path.join(os.path.dirname(__file__), "assets", "_selftest_ref.png"))
    print(summarize([res]))
    print(res["scheme"])
    print(res["layout"])
    out = os.path.join(os.path.dirname(__file__), "assets", "_selftest_annotated.png")
    draw_annotation(Image.open(res["path"]), res["regions"], out)
    print("标注图:", out)
