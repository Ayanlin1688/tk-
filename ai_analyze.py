# -*- coding: utf-8 -*-
"""
ai_analyze.py — 分析模型客户端（升级版）
用多模态模型（OpenAI 兼容 chat/completions）分析参考图，输出"排版指纹"：
  {
    "blocks":     [{"type":"title|body|cta|image","x0":0,"y0":0.1,"x1":1,"y1":0.3}, ...],   # 主区域（兼容旧版）
    "colors":     {"background":"#hex","accent":"#hex","text":"#hex"},                      # 配色（兼容旧版）
    "text_zones": [ {block, x0,y0,x1,y1, align, size_ratio, max_lines, font, text_color,
                     stroke, has_bar, bar_color, bar_alpha, emoji}, ... ],                  # 逐块文字排版细节
    "elements":   [{"type":"arrow|underline|circle|price_tag|check|hand","x0":..,"y0":..,"x1":..,"y1":..}],
    "scene":      "英文场景描述（用于生图：同场景构图、内容全新）",
    "copy_style": {"tone":"...","emoji_density":"low|medium|high","hook_lang":"es|en",
                   "hook_original":"参考图原文案","caption_lang":"es|en"}
  }
坐标均为 0-1 归一化（y 从顶部）。失败返回 None/回退规则分析。
同时提供 AI 文案模仿 generate_copy()。
"""

import base64
import json
import urllib.request
import urllib.error

# ---------------- 排版指纹分析 ----------------

SYSTEM_PROMPT = (
    "You are an expert TikTok photo-carousel designer. Given ONE reference image "
    "(one slide of a real US TikTok product photo carousel), extract a detailed "
    "\"layout fingerprint\" so a NEW image can be generated with the SAME layout "
    "but different content.\n\n"
    "Output STRICT JSON only, with exactly these fields:\n"
    '{"blocks":[{"type":"title|body|cta|image","x0":0.0,"y0":0.0,"x1":1.0,"y1":1.0},...],\n'
    ' "colors":{"background":"#hex","accent":"#hex","text":"#hex"},\n'
    ' "text_zones":[{"block":"title|body|cta","x0":0.0,"y0":0.0,"x1":1.0,"y1":0.0,\n'
    '   "align":"center|left|right","size_ratio":0.0,"max_lines":1,"font":"black|bold",\n'
    '   "text_color":"#hex","stroke":"#hex","has_bar":false,"bar_color":"#hex",\n'
    '   "bar_alpha":0.0,"emoji":false}, ...],\n'
    ' "elements":[{"type":"arrow|underline|circle|price_tag|check|hand","x0":0.0,"y0":0.0,"x1":0.0,"y1":0.0}],\n'
    ' "scene":"...",\n'
    ' "copy_style":{"tone":"...","emoji_density":"low|medium|high","hook_lang":"es|en",\n'
    '   "hook_original":"...","caption_lang":"es|en"}}\n\n'
    "Rules:\n"
    "- Coordinates are fractions 0-1 of image width/height, y starts at TOP.\n"
    "- blocks: the MAIN content zones (title text, body text, cta/pricing, image/product) in reading order.\n"
    "- text_zones: EVERY visible text block with precise position and style. "
    "Measure the zone as the bounding box of the text itself (not the whole image). "
    "size_ratio = text cap height / image height (typical 0.03-0.10). align = text alignment. "
    "font: black = extra bold (Arial Black style), bold = regular bold. "
    "text_color = text fill color, stroke = outline color (usually #000000 or #FFFFFF). "
    "has_bar = whether the text sits on a banner/bar background; give bar_color and bar_alpha (0-1). "
    "emoji = whether the text contains emoji symbols.\n"
    "- Do NOT create overlapping text zones: if two blocks of the same type touch, merge them into one.\n"
    "- elements: only OBVIOUS stickers/decorations: arrow (pointing down), underline "
    "(hand-drawn line under text), circle (drawn around a word), price_tag, check, hand. "
    "Skip faint background decorations.\n"
    "- scene: ONE short English sentence describing the real-life scene of the PHOTO part: "
    "where, who, what action, lighting, camera feel. If there is no photo, describe the visual style.\n"
    "- copy_style: tone = voice of the on-image text (humor, warning, contrast, mystery, direct, "
    "casual, sexy). emoji_density = how many emoji the text uses. "
    "hook_original = TRANSCRIBE the main hook text exactly as seen, keep original language. "
    "hook_lang = es|en. caption_lang = language of the caption.\n"
    "Output ONLY the JSON, no other text."
)


def analyze_full(cfg, img_bytes, model=None, timeout=120):
    """调用多模态模型分析一张参考图，返回完整排版指纹 dict 或 None"""
    base = (cfg.get("base_url") or "https://api.kkone.vip").rstrip("/")
    key = cfg.get("api_key") or ""
    model = model or cfg.get("analyze_model") or "gemini-3.8-flash"

    b64 = base64.b64encode(img_bytes).decode("ascii")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": "Analyze this carousel slide image and return the layout fingerprint JSON."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ]},
        ],
        "temperature": 0,
        "max_tokens": 6000,
    }
    req = urllib.request.Request(
        base + "/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "ignore")[:300]
        except Exception:
            pass
        raise RuntimeError(f"分析接口返回 {e.code}: {body}")
    content = data["choices"][0]["message"]["content"]
    return _parse_json(content)


def _parse_json(content):
    """从模型输出里提取 JSON（兼容 markdown 包裹/前后杂文本）"""
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except Exception:
        pass
    s, e = text.find("{"), text.rfind("}")
    if s >= 0 and e > s:
        try:
            return json.loads(text[s : e + 1])
        except Exception:
            return None
    return None


def hex_to_rgb(h):
    h = str(h or "").strip().lstrip("#")
    if len(h) != 6:
        return None
    try:
        return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return None


def _f(v, lo=0.0, hi=1.0, default=0.0):
    try:
        return max(lo, min(hi, float(v)))
    except Exception:
        return default


def _clean_text_zones(res):
    """解析 text_zones：过滤非法、补默认字段"""
    zones = []
    for z in res.get("text_zones") or []:
        block = str(z.get("block", "")).strip().lower()
        if block not in ("title", "body", "cta"):
            continue
        zone = {
            "block": block,
            "x0": _f(z.get("x0", 0)),
            "y0": _f(z.get("y0", 0)),
            "x1": _f(z.get("x1", 1)),
            "y1": _f(z.get("y1", 0.1)),
            "align": str(z.get("align", "center")).strip().lower() if str(z.get("align", "center")).strip().lower() in ("center", "left", "right") else "center",
            "size_ratio": max(0.02, min(0.14, _f(z.get("size_ratio", 0.06), 0.0, 0.5, 0.06))),
            "max_lines": max(1, min(6, int(z.get("max_lines", 2) or 2))),
            "font": "black" if str(z.get("font", "black")).strip().lower() != "bold" else "bold",
            "text_color": hex_to_rgb(z.get("text_color", "")) or (255, 255, 255),
            "stroke": hex_to_rgb(z.get("stroke", "")) or (0, 0, 0),
            "has_bar": bool(z.get("has_bar", False)),
            "bar_color": hex_to_rgb(z.get("bar_color", "")) or (0, 0, 0),
            "bar_alpha": max(0.0, min(1.0, _f(z.get("bar_alpha", 0.75), 0.0, 1.0, 0.75))),
            "emoji": bool(z.get("emoji", False)),
        }
        if zone["x1"] - zone["x0"] < 0.01 or zone["y1"] - zone["y0"] < 0.005:
            continue
        zones.append(zone)
    return zones


def _clean_elements(res):
    """解析 elements：箭头/下划线/圆圈/价格标签/勾选/手指"""
    allowed = ("arrow", "underline", "circle", "price_tag", "check", "hand")
    els = []
    for e in res.get("elements") or []:
        t = str(e.get("type", "")).strip().lower()
        if t not in allowed:
            continue
        els.append({
            "type": t,
            "x0": _f(e.get("x0", 0)),
            "y0": _f(e.get("y0", 0)),
            "x1": _f(e.get("x1", 1)),
            "y1": _f(e.get("y1", 1)),
        })
    return els


def merge_full(img_bytes, model_cfg):
    """分析一张图，返回与 analysis.analyze_image 兼容的补充字段（含指纹）"""
    res = analyze_full(model_cfg, img_bytes)
    if not res:
        return None
    out = {"ai_analyzed": True}
    # blocks（兼容旧渲染）
    blocks = []
    for b in res.get("blocks", []):
        t = str(b.get("type", "")).strip().lower()
        if t not in ("title", "body", "cta", "image"):
            continue
        try:
            x0 = max(0.0, min(1.0, float(b.get("x0", 0))))
            y0 = max(0.0, min(1.0, float(b.get("y0", 0))))
            x1 = max(0.0, min(1.0, float(b.get("x1", 1))))
            y1 = max(0.0, min(1.0, float(b.get("y1", 1))))
        except Exception:
            continue
        if x1 - x0 < 0.01 or y1 - y0 < 0.01:
            continue
        blocks.append({"type": t, "x0": x0, "y0": y0, "x1": x1, "y1": y1})
    if blocks:
        out["blocks"] = blocks
    # 配色
    colors = res.get("colors") or {}
    bg = hex_to_rgb(colors.get("background", ""))
    ac = hex_to_rgb(colors.get("accent", ""))
    tx = hex_to_rgb(colors.get("text", ""))
    if bg and ac and tx:
        out["scheme"] = {"background": bg, "accent": ac, "text": tx}
    # 指纹
    zones = _clean_text_zones(res)
    if zones:
        out["text_zones"] = zones
    els = _clean_elements(res)
    if els:
        out["elements"] = els
    if res.get("scene"):
        out["scene"] = str(res["scene"]).strip()[:400]
    cs = res.get("copy_style") or {}
    copy_style = {}
    if cs.get("tone"):
        copy_style["tone"] = str(cs["tone"]).strip()[:60]
    if cs.get("emoji_density") in ("low", "medium", "high"):
        copy_style["emoji_density"] = cs["emoji_density"]
    if cs.get("hook_original"):
        copy_style["hook_original"] = str(cs["hook_original"]).strip()[:300]
    hook_lang = str(cs.get("hook_lang", "")).strip().lower()
    caption_lang = str(cs.get("caption_lang", "")).strip().lower()
    if hook_lang in ("en", "es"):
        copy_style["hook_lang"] = hook_lang
    if caption_lang in ("en", "es"):
        copy_style["caption_lang"] = caption_lang
    if copy_style:
        out["copy_style"] = copy_style
    return out


def merge_into_analysis(img_bytes, model_cfg):
    """兼容旧接口：只返回 blocks/scheme（供无指纹能力的旧流程使用）"""
    res = analyze_full(model_cfg, img_bytes)
    if not res:
        return None
    blocks = []
    for b in res.get("blocks", []):
        t = str(b.get("type", "")).strip().lower()
        if t not in ("title", "body", "cta", "image"):
            continue
        try:
            x0 = max(0.0, min(1.0, float(b.get("x0", 0))))
            y0 = max(0.0, min(1.0, float(b.get("y0", 0))))
            x1 = max(0.0, min(1.0, float(b.get("x1", 1))))
            y1 = max(0.0, min(1.0, float(b.get("y1", 1))))
        except Exception:
            continue
        if x1 - x0 < 0.01 or y1 - y0 < 0.01:
            continue
        blocks.append({"type": t, "x0": x0, "y0": y0, "x1": x1, "y1": y1})
    scheme = None
    colors = res.get("colors") or {}
    bg = hex_to_rgb(colors.get("background", ""))
    ac = hex_to_rgb(colors.get("accent", ""))
    tx = hex_to_rgb(colors.get("text", ""))
    if bg and ac and tx:
        scheme = {"background": bg, "accent": ac, "text": tx}
    return {"blocks": blocks, "scheme": scheme}


# ---------------- AI 文案模仿 ----------------

COPY_SYSTEM_PROMPT = (
    "You are a native US TikTok copywriter who writes EXACTLY like a real account. "
    "A reference account's on-image style is given. Write a FRESH set of captions for a "
    "product, keeping the SAME voice, tone and emoji habits, but brand-new wording "
    "(do NOT copy the reference text).\n\n"
    "Write like a real person actually posting on TikTok: vary sentence structure, "
    "use casual native phrasing, never open with template phrases like \"Introducing\", "
    "\"Are you ready\", \"Get ready for\". One hook must sound like it was typed fast on a phone.\n\n"
    "Length budget (MUST fit the reference layout exactly):\n"
    "- hook: max {hook} words (this is what gets overlaid big on image 1)\n"
    "- body: max {body} words (one short selling line on the middle slide)\n"
    "- cta: max {cta} words (price/call-to-action line)\n"
    "Keep each field comfortably UNDER its budget — short and punchy beats long.\n\n"
    "Reference style:\n"
    "- on-image hook: \"{hook_original}\"\n"
    "- tone: {tone}\n"
    "- emoji density: {emoji_density}\n"
    "- language: {lang}\n\n"
    "Product: {brand} {name} — {desc}\n"
    "Facts: price {price}, {sale} off, {rating} rating, {sales} sold, 8+ hours lasting, "
    "smells like a $200 perfume but costs $26, rose + red fruits scent.\n\n"
    "Output STRICT JSON only:\n"
    '{"hook":"one-line hook for image 1, max {hook} words, {lang}",\n'
    ' "body":"one selling sentence, max {body} words, {lang}",\n'
    ' "cta":"call to action like \'link in my cart\', max {cta} words, {lang}",\n'
    ' "caption":"1-2 sentence post caption, {lang}",\n'
    ' "tags":"8-10 hashtags separated by spaces",\n'
    ' "comment_hook":"one comment question, {lang}",\n'
    ' "pinned":"pinned comment text, {lang}"}\n'
    "Output ONLY the JSON."
)


def generate_copy(cfg, copy_style, product, lang=None, timeout=120, budget=None):
    """按参考图文案风格为新图文生成全套文案（长度按版面容量自适应）。
    budget: {"hook": int, "body": int, "cta": int} 词数上限；缺省用自然长度。失败返回 None"""
    base = (cfg.get("base_url") or "https://api.kkone.vip").rstrip("/")
    key = cfg.get("api_key") or ""
    model = cfg.get("analyze_model") or "gemini-3.8-flash"
    cs = copy_style or {}
    target_lang = lang or cs.get("hook_lang") or cs.get("caption_lang") or "es"
    if target_lang not in ("en", "es"):
        target_lang = "es"
    lang_txt = "Spanish (es, casual Latin American)" if target_lang == "es" else "English (en, casual US)"
    hook = cs.get("hook_original") or ""
    tone = cs.get("tone") or "casual"
    density = cs.get("emoji_density") or "medium"
    b = budget or {}
    b_hook = max(3, min(14, int(b.get("hook") or 9)))
    b_body = max(3, min(20, int(b.get("body") or 12)))
    b_cta = max(2, min(14, int(b.get("cta") or 8)))
    p = product or {}
    system = (COPY_SYSTEM_PROMPT
              .replace("{hook}", str(b_hook))
              .replace("{body}", str(b_body))
              .replace("{cta}", str(b_cta))
              .replace("{hook_original}", hook[:200])
              .replace("{tone}", tone[:60])
              .replace("{emoji_density}", density)
              .replace("{lang}", lang_txt)
              .replace("{brand}", p.get("brand", "QAWAFI"))
              .replace("{name}", p.get("name", "Voyage Nova"))
              .replace("{desc}", p.get("desc", "perfume, rose + red fruits scent"))
              .replace("{price}", p.get("price_50", "$25.99"))
              .replace("{sale}", p.get("sale", "50% OFF"))
              .replace("{rating}", p.get("rating", "4.3 stars"))
              .replace("{sales}", p.get("sales", "153.7K sold")))
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": "Write the captions now."},
        ],
        "temperature": 0.8,
        "max_tokens": 2000,
    }
    req = urllib.request.Request(
        base + "/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        return None
    content = data["choices"][0]["message"]["content"]
    res = _parse_json(content)
    if not res:
        return None
    out = {}
    for k in ("hook", "body", "cta", "caption", "tags", "comment_hook", "pinned"):
        v = res.get(k)
        if v and isinstance(v, str):
            out[k] = v.strip()
    return out or None
