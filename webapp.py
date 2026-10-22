# -*- coding: utf-8 -*-
"""
webapp.py — TK图文工作台 主程序（本地HTTP服务 + pywebview窗口）
架构说明：前端页面与 Python 后端通过本地 HTTP 通信（绝对可靠），
文件选择使用 HTML 标准 file input（系统对话框），不依赖任何桥接注入。
运行：python webapp.py  或  打包后的 TK图文工作台.exe
"""

import os
import sys
import io
import re
import time
import base64
import json
import socket
import zipfile
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import webview
from PIL import Image

import analysis as A
import generator as G
import content as C
import ai_image
import ai_analyze


def _is_frozen():
    return getattr(sys, "frozen", False)


if _is_frozen():
    RES_DIR = sys._MEIPASS          # 打包资源（index.html）
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    RES_DIR = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = RES_DIR

OUTPUT_DIR = os.path.join(BASE_DIR, "output")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
REFS_DIR = os.path.join(ASSETS_DIR, "refs")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(REFS_DIR, exist_ok=True)


def rgb_to_hex(c):
    return "#{:02x}{:02x}{:02x}".format(*[int(v) for v in c])


def img_to_b64(img, max_w=420, quality=84):
    """图片转 JPEG base64 缩略图（前端预览用）"""
    if img.width > max_w:
        img = img.resize((max_w, int(img.height * max_w / img.width)), Image.LANCZOS)
    if img.mode != "RGB":
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _safe_name(name):
    name = re.sub(r'[\\/:*?"<>|\r\n]+', "_", name)
    return name or "image.png"


# ---------------- 并行生图 & 文案预算 ----------------

AI_CONCURRENCY = 3          # 同时生成的 AI 画面数（接口并发安全值）
COPY_CONCURRENCY = 3        # 同时生成的 AI 文案数
AI_RETRY = 2                # 单张失败自动重试次数


def _gen_image_with_retry(cfg, prompt, retries=AI_RETRY, timeout=300, on_retry=None):
    """生成一张 AI 画面：失败自动重试，返回 PIL RGB 图或抛异常。
    timeout 给足 300s：部分中转接口排队出图要 2-4 分钟，太短会误判超时反复重试"""
    last = None
    for attempt in range(retries + 1):
        try:
            imgs = ai_image.generate_image(cfg, prompt, timeout=timeout)
            if imgs:
                return Image.open(io.BytesIO(imgs[0])).convert("RGB")
            raise RuntimeError("接口未返回图片")
        except Exception as e:
            last = e
            if on_retry and attempt < retries:
                on_retry(f"第{attempt + 1}次失败，正在重试: {e}")
            time.sleep(3)
    raise last or RuntimeError("生图失败")


def resolve_set_lang(lang_mode, analysis_list, i):
    """按语言模式解析第 i 套的语言。auto = 跟随参考图文案语言（未检测到则回退西语）"""
    if lang_mode == "both":
        return "en" if i % 2 == 0 else "es"
    if lang_mode in ("en", "es"):
        return lang_mode
    for a in analysis_list or []:
        if isinstance(a, dict):
            cs = a.get("copy_style") or {}
            l = cs.get("hook_lang") or cs.get("caption_lang")
            if l in ("en", "es"):
                return l
    return "es"


def build_copy_budget(analysis_list):
    """按参考图文字区容量估算每类文案的词数上限（hook→title区 / body→正文区 / cta→CTA区）。
    让 AI 文案“随版面应变”：区小则文案短，区大则文案可以长。"""
    budget = {"hook": None, "body": None, "cta": None}
    for a in analysis_list or []:
        if not isinstance(a, dict):
            continue
        for z in a.get("text_zones") or []:
            block = z.get("block")
            if block not in budget:
                continue
            span_w = z.get("x1", 1) - z.get("x0", 0)
            size_r = z.get("size_ratio", 0.06)
            max_lines = max(1, int(z.get("max_lines", 2) or 2))
            chars_per_line = max(4, int(span_w * 1080 / (size_r * 1920 * 0.55)))
            words = max(2, int(chars_per_line * max_lines / 6.5))
            budget[block] = max(budget[block] or 0, words)
    caps = {"hook": 14, "body": 20, "cta": 14}
    out = {}
    for k in budget:
        out[k] = min(caps[k], budget[k] or caps[k])
    return out


class Api:
    """后端业务逻辑（被 HTTP Handler 调用）"""

    def __init__(self):
        self.ref_paths = []
        self.analysis = None
        self.product_image = ""
        self.product_images = []
        self.latest_out_dir = ""
        self.latest_zip = ""
        self.cancel_generate = False
        self.progress = {"state": "idle", "done": 0, "total": 0, "msg": ""}

    def get_progress(self):
        return self.progress

    def request_cancel(self):
        """停止当前生成（并行任务会尽快退出，已完成的保留）"""
        self.cancel_generate = True
        self.progress = {"state": "cancelling", "done": 0, "total": 0, "msg": "正在停止…"}
        return {"ok": True}

    # ---------- 参考图 ----------
    def add_refs(self, payloads):
        """payloads: [{name, dataUrl}] 前端上传的参考图"""
        for p in payloads or []:
            try:
                b64 = str(p.get("dataUrl", "")).split(",", 1)[-1]
                data = base64.b64decode(b64)
                path = os.path.join(REFS_DIR, _safe_name(p.get("name", "ref.png")))
                with open(path, "wb") as f:
                    f.write(data)
                if path not in self.ref_paths:
                    self.ref_paths.append(path)
            except Exception:
                continue
        return self._thumbs()

    def remove_ref(self, path):
        try:
            if path in self.ref_paths:
                self.ref_paths.remove(path)
        except Exception:
            pass
        return self._thumbs()

    def _thumbs(self):
        thumbs = []
        for p in self.ref_paths:
            try:
                thumbs.append({"path": p, "name": os.path.basename(p),
                               "b64": img_to_b64(Image.open(p))})
            except Exception:
                continue
        return thumbs

    # ---------- 产品图 ----------
    def save_product_image(self, payload):
        """payload: {name, dataUrl}（多图轮换：重复上传不同图会累积）"""
        try:
            b64 = str(payload.get("dataUrl", "")).split(",", 1)[-1]
            data = base64.b64decode(b64)
            path = os.path.join(ASSETS_DIR, "product_" + _safe_name(payload.get("name", "p.png")))
            with open(path, "wb") as f:
                f.write(data)
            if path not in self.product_images:
                self.product_images.append(path)
            if not self.product_image:
                self.product_image = path
            return {"path": path, "name": os.path.basename(path),
                    "b64": img_to_b64(Image.open(path), 220),
                    "images": [os.path.basename(p) for p in self.product_images],
                    "count": len(self.product_images)}
        except Exception as e:
            return {"error": str(e)}

    def remove_product_image(self, payload):
        """删除一张已上传的产品图（多图轮换管理）"""
        try:
            path = (payload or {}).get("path", "")
            if path in self.product_images:
                self.product_images.remove(path)
            if self.product_image == path:
                self.product_image = self.product_images[0] if self.product_images else ""
            return {"ok": True, "images": [os.path.basename(p) for p in self.product_images],
                    "count": len(self.product_images)}
        except Exception as e:
            return {"error": str(e)}

    # ---------- 分析 ----------
    def analyze(self, cfg=None):
        try:
            if not self.ref_paths:
                return {"error": "请先导入参考图"}
            results = A.analyze_many(self.ref_paths)

            # AI 分析模式：用多模态模型覆盖每张的布局/配色 + 排版指纹/场景/文案风格
            ai_cfg = ai_image.load_config()
            ai_an_errors = []
            if cfg and cfg.get("ai_analyze") and ai_cfg.get("analyze_model") and ai_cfg.get("api_key"):
                for r_idx, r in enumerate(results):
                    if "error" in r:
                        continue
                    extra = None
                    last_e = None
                    for _attempt in range(2):      # AI 分析失败自动重试一次
                        try:
                            with open(r["path"], "rb") as f:
                                img_bytes = f.read()
                            extra = ai_analyze.merge_full(img_bytes, ai_cfg)
                            break
                        except Exception as e:
                            last_e = e
                            time.sleep(3)
                    if extra:
                        if extra.get("blocks"):
                            r["blocks"] = extra["blocks"]
                        if extra.get("scheme"):
                            r["scheme"] = extra["scheme"]
                        for key in ("text_zones", "elements", "scene", "copy_style"):
                            if extra and extra.get(key):
                                r[key] = extra[key]
                        if extra:
                            r["ai_analyzed"] = True
                    elif last_e is not None:
                        ai_an_errors.append(f"第{r_idx + 1}张: {last_e}")

            self.analysis = results
            summary = A.summarize(results)

            annotated = None
            for r in results:
                if "error" not in r:
                    tmp = os.path.join(ASSETS_DIR, "_annotated_tmp.png")
                    A.draw_annotation(Image.open(r["path"]), r["regions"], tmp)
                    annotated = img_to_b64(Image.open(tmp))
                    break

            schemes = []
            if results and "error" not in results[0]:
                for s in G.build_schemes(results[0]):
                    schemes.append({
                        "name": s["name"],
                        "top": rgb_to_hex(s["bg_top"]),
                        "bottom": rgb_to_hex(s["bg_bottom"]),
                        "accent": rgb_to_hex(s["accent"]),
                        "text": rgb_to_hex(s["text"]),
                    })
            resp = {"summary": summary, "annotated": annotated, "schemes": schemes}
            if ai_an_errors:
                resp["ai_analyze_errors"] = ai_an_errors
            return resp
        except Exception as e:
            return {"error": str(e), "trace": traceback.format_exc()}

    # ---------- AI生图配置 ----------
    def get_ai_config(self):
        return ai_image.load_config()

    def save_ai_config(self, cfg):
        try:
            clean = {}
            for k in ["base_url", "api_key", "model", "analyze_model"]:
                v = str(cfg.get(k, "")).strip()
                if v:
                    clean[k] = v
            if not clean.get("base_url"):
                clean["base_url"] = "https://api.kkone.vip"
            ai_image.save_config(clean)
            return {"ok": True, "config": ai_image.load_config()}
        except Exception as e:
            return {"error": str(e)}

    def test_ai(self):
        cfg = ai_image.load_config()
        ok, msg, models = ai_image.test_connection(cfg)
        return {"ok": ok, "msg": msg, "models": models,
                "image_models": filter_image_models(models),
                "analyze_models": filter_analyze_models(models)}

    # ---------- 生成 ----------
    def generate(self, cfg):
        try:
            sets = max(1, min(int(cfg.get("sets", 5)), 20))
            lang = cfg.get("lang", "auto")          # auto = 跟随参考图文案语言
            product = dict(C.DEFAULT_PRODUCT)
            for k in ["brand", "name", "price_50", "price_100", "sale",
                      "rating", "sales", "refund"]:
                v = str(cfg.get(k, "")).strip()
                if v:
                    product[k] = v
            _op = str(cfg.get("orig_price", "")).strip()
            if _op:
                product["orig_price"] = _op

            analysis = None
            if self.analysis and "error" not in self.analysis[0]:
                analysis = self.analysis[0]
            if analysis is None:
                analysis = {
                    "scheme": {"background": (40, 32, 52),
                               "accent": (212, 175, 55),
                               "text": (255, 255, 255)},
                    "layout": {"style": ["顶部标题", "中图", "底部CTA"]},
                }

            self.cancel_generate = False
            ai_images = []      # [[img,...], [img,...]] 每套一张列表，与参考图张数对应
            ai_errors = []
            self.progress = {"state": "start", "done": 0, "total": 0, "msg": ""}

            # ---- AI 裂变：每套每一张都生成全新画面（并行 + 失败自动重试） ----
            if cfg.get("ai_generate"):
                ai_cfg = ai_image.load_config()
                if not (ai_cfg.get("api_key") and ai_cfg.get("model")):
                    return {"error": "AI生图未配置：请在「AI生图设置」里填好密钥并选择模型"}
                style = cfg.get("style", "ugc")
                angles = ["pov", "rosas", "value", "long", "flash"]
                valid_an = [a for a in self.analysis if isinstance(a, dict) and "error" not in a]
                slides = max(1, len(valid_an))
                total = sets * slides
                self.progress = {"state": "generating", "done": 0, "total": total,
                                 "msg": f"并行生图中（{AI_CONCURRENCY}路并发）…"}
                lock = threading.Lock()
                done_cnt = [0]

                def _worker(i, k, prompt):
                    if self.cancel_generate:
                        return None
                    if prompt is None:
                        with lock:
                            done_cnt[0] += 1
                            self.progress = {"state": "generating", "done": done_cnt[0], "total": total,
                                             "msg": f"套{i + 1} 第{k + 1}张 · 使用上传的真实产品图"}
                        return None
                    try:
                        img = _gen_image_with_retry(ai_cfg, prompt)
                        with lock:
                            done_cnt[0] += 1
                            self.progress = {"state": "generating", "done": done_cnt[0], "total": total,
                                             "msg": f"套{i + 1} 第{k + 1}张 · 完成"}
                        return img
                    except Exception as e:
                        with lock:
                            done_cnt[0] += 1
                            ai_errors.append(f"套{i + 1}第{k + 1}张: {e}")
                            self.progress = {"state": "generating", "done": done_cnt[0], "total": total,
                                             "msg": f"套{i + 1} 第{k + 1}张 · 失败已回退本地排版"}
                        return None

                tasks = []
                for i in range(sets):
                    ang = angles[i % len(angles)]
                    # 本套产品图：多张轮换，单张则每套同一张
                    p_img = None
                    if self.product_images:
                        p_img = self.product_images[i % len(self.product_images)]
                    elif self.product_image and os.path.exists(self.product_image):
                        p_img = self.product_image
                    for k in range(slides):
                        # 每张参考图自己的场景指纹（AI 精分析）→ 画面同场景类型
                        scene_k = valid_an[k].get("scene") if k < len(valid_an) else None
                        # 最后一张（价格页）：本套已有产品图 → 不 AI 生成，直接用真实产品图
                        if k == slides - 1 and p_img and os.path.exists(p_img):
                            tasks.append((i, k, None))
                            continue
                        prompt = build_ai_prompt_for_page(ang, style, product, i, k, slides, scene_k)
                        tasks.append((i, k, prompt))

                results_map = {}
                with ThreadPoolExecutor(max_workers=AI_CONCURRENCY) as ex:
                    futs = {ex.submit(_worker, i, k, prompt): (i, k) for i, k, prompt in tasks}
                    for fut in as_completed(futs):
                        i, k = futs[fut]
                        results_map[(i, k)] = fut.result()
                        if self.cancel_generate:
                            ex.shutdown(wait=False, cancel_futures=True)
                            break

                ai_images = []
                for i in range(sets):
                    row = []
                    for k in range(slides):
                        row.append(results_map.get((i, k)))
                    ai_images.append(row)

                if self.cancel_generate:
                    self.progress = {"state": "cancelled", "done": done_cnt[0], "total": total,
                                     "msg": "已停止生成"}
                else:
                    self.progress = {"state": "rendering", "done": total, "total": total,
                                     "msg": "排版合成中…"}

            # AI 文案模仿：参考图有文案风格指纹 → 每套按该风格写新文案（失败回退人格池）
            # 文案长度按参考图文字区容量自适应 + 语言自动跟随参考图
            copy_texts = []
            copy_style = None
            for a in self.analysis:
                if isinstance(a, dict) and a.get("copy_style"):
                    copy_style = a["copy_style"]
                    break
            if copy_style and not self.cancel_generate:
                try:
                    copy_ai_cfg = ai_image.load_config()
                    budget = build_copy_budget(self.analysis)
                    lang_list_local = [resolve_set_lang(lang, self.analysis, i) for i in range(sets)]
                    copy_results = {}

                    def _copy_worker(i):
                        if self.cancel_generate:
                            return i, None
                        try:
                            item = ai_analyze.generate_copy(copy_ai_cfg, copy_style, product,
                                                            lang=lang_list_local[i], budget=budget)
                            return i, item
                        except Exception:
                            return i, None

                    with ThreadPoolExecutor(max_workers=COPY_CONCURRENCY) as ex:
                        futs = [ex.submit(_copy_worker, i) for i in range(sets)]
                        for fut in as_completed(futs):
                            i, item = fut.result()
                            copy_results[i] = item
                    copy_texts = [copy_results.get(i) for i in range(sets)]
                except Exception:
                    copy_texts = []

            if self.cancel_generate:
                self.progress = {"state": "cancelled", "done": 0, "total": 0,
                                 "msg": "已停止，未生成新内容"}

            out_dir = os.path.join(OUTPUT_DIR, "批量输出")
            per_set_langs = [resolve_set_lang(lang, self.analysis, i) for i in range(sets)]
            results = G.generate(self.analysis, product=product, lang=lang, sets=sets,
                                 product_image=self.product_image or None,
                                 out_dir=out_dir, ai_images=ai_images,
                                 style_mode=cfg.get("style_mode") or "auto",
                                 copy_texts=copy_texts or None,
                                 per_set_langs=per_set_langs,
                                 product_images=self.product_images or None)
            self.latest_out_dir = out_dir

            items = []
            for i, (name, pages, pack, scheme) in enumerate(results):
                images = []
                for fn, fp in pages:
                    images.append({"name": fn, "b64": img_to_b64(Image.open(fp))})
                items.append({
                    "folder": os.path.basename(name),
                    "angle": pack["angle_name"],
                    "lang": pack["lang"],
                    "scheme": scheme,
                    "slides": pack.get("slides", 1),
                    "images": images,
                    "pack": pack,
                })
            resp = {"items": items, "out_dir": out_dir}
            if ai_errors:
                resp["ai_errors"] = ai_errors
            if self.cancel_generate:
                resp["cancelled"] = True
            return resp
        except Exception as e:
            return {"error": str(e), "trace": traceback.format_exc()}

    # ---------- 其他 ----------
    def open_output(self):
        d = self.latest_out_dir or os.path.join(OUTPUT_DIR, "批量输出")
        if os.path.isdir(d):
            os.startfile(d)
            return True
        return False

    def open_app_dir(self):
        os.startfile(BASE_DIR)
        return True

    def export_zip(self):
        """把最新生成结果打包成 ZIP（放 output 目录），自动打开所在文件夹"""
        import datetime
        src = self.latest_out_dir or os.path.join(OUTPUT_DIR, "批量输出")
        if not os.path.isdir(src):
            return {"error": "还没有可打包的生成结果"}
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = os.path.join(OUTPUT_DIR, f"TK图文成品_{stamp}.zip")
        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, _dirs, files in os.walk(src):
                    for fn in files:
                        fp = os.path.join(root, fn)
                        arc = os.path.relpath(fp, src)
                        zf.write(fp, arc)
            self.latest_zip = zip_path
            os.startfile(OUTPUT_DIR)
            return {"ok": True, "path": zip_path, "name": os.path.basename(zip_path),
                    "size": os.path.getsize(zip_path)}
        except Exception as e:
            return {"error": str(e)}


# ---------------- AI 生图提示词构建 ----------------

IMAGE_MODEL_KEYWORDS = ("image", "imagine", "banana", "dall-e", "dalle",
                        "flux", "midjourney", "mj", "sdxl", "seedream",
                        "diffusion", "draw")


def filter_image_models(models):
    """从 /v1/models 全量列表里筛出真正的生图模型（排除视频/文本模型）"""
    out = []
    for m in models or []:
        low = (m or "").lower()
        if any(k in low for k in IMAGE_MODEL_KEYWORDS):
            out.append(m)
    return out


ANALYZE_MODEL_DEFAULT = ["gemini-3.8-flash", "gpt-5.6-sol", "gpt-6-astra", "grok-4.6", "grok-4.7"]

def filter_analyze_models(models):
    """分析模型下拉候选：优先推荐池；再从全量模型里补充 gemini/gpt/grok（排除生图模型）"""
    out = list(ANALYZE_MODEL_DEFAULT)
    for m in models or []:
        low = (m or "").lower()
        if any(k in low for k in IMAGE_MODEL_KEYWORDS):
            continue
        if ("gemini" in low or "gpt" in low or "grok" in low) and m not in out:
            out.append(m)
    return out

ANGLE_PLOTS = {
    "pov": [
        "her boyfriend casually burying his face in her neck while she laughs, candid unposed moment",
        "her boyfriend pulling her wrist up to smell it, both laughing naturally",
        "a couple close together, his nose in her hair, cozy casual moment at home",
    ],
    "rosas": [
        "her boyfriend handing her a bouquet of fresh red roses at home, casual moment",
        "she holding a single red rose near her face with eyes closed, smelling it",
        "fresh red roses lying on her bed beside her, everyday bedroom",
    ],
    "value": [
        "she holding the perfume bottle up to the light at home, curious everyday moment",
        "the perfume bottle standing on her real bathroom counter, casual product moment",
        "two perfume bottles side by side, she picking one up, real home setting",
    ],
    "long": [
        "she spraying perfume on her wrist in soft morning light, everyday routine",
        "she smelling her own wrist at her office desk, checking the time",
        "she smelling her scarf in the afternoon, perfume still lingering, real moment",
    ],
    "flash": [
        "a shopping cart with a perfume bottle inside, excited real sale moment",
        "she holding her phone with a countdown, perfume bottle beside her, casual",
        "her grabbing a perfume bottle quickly, bright everyday sale mood",
    ],
}

STYLE_WORDS = {
    "ugc": "iPhone snapshot, casual amateur photo taken by a friend, everyday realism, slightly imperfect framing, natural lighting, no studio, no photoshoot",
    "ads": "High-end commercial product photography, studio soft lighting, luxurious, 8K detail",
    "mix": "Candid photorealistic lifestyle photography, natural everyday moments",
}


def build_ai_prompt(angle, style, product, i, scene=None):
    """按 角度×人物×场景×情节 组合英文生图提示词，每套不重样。
    scene: AI 精分析出的参考图场景描述 → 画面同场景类型、内容全新"""
    person = C.PERSONS[i % len(C.PERSONS)]
    scene_txt = scene or C.SCENES[(i * 2 + 1) % len(C.SCENES)]
    plot = ANGLE_PLOTS[angle][(i * 3 + 2) % len(ANGLE_PLOTS[angle])]
    style_txt = STYLE_WORDS.get(style, STYLE_WORDS["ugc"])
    brand = f"{product.get('brand', 'QAWAFI')} {product.get('name', 'Voyage Nova')}"
    fresh = FRESH_VARIANTS[i % len(FRESH_VARIANTS)]
    if scene:
        scene_txt = f"a scene similar to this: {scene_txt} (same type of place and mood, but brand-new people and details, {fresh})"
    return (
        f"{style_txt}: {person}, {scene_txt}, {plot}, near a {brand} perfume bottle "
        f"with transparent glass and soft pink liquid, natural everyday lighting, "
        f"realistic skin texture, casual unposed moment, vertical 9:16 composition, "
        f"slight film grain, no text, no letters, no watermark, no captions"
    )


SCENE_VARIANTS = [
    "the perfume bottle standing on a real vanity with everyday makeup products around, natural light",
    "her hand holding the perfume bottle up near her face, casual bedroom background with messy blankets",
    "the perfume bottle peeking out of a shopping bag on a bed, excited unboxing moment, real home",
    "the perfume bottle on a bedside table next to a lamp, a phone charger and a book",
    "she spraying the perfume on her neck in front of a bathroom mirror, natural window light",
    "the perfume bottle on an office desk next to a coffee cup and papers",
]

FRESH_VARIANTS = [
    "slightly different camera angle, brand-new people and surroundings",
    "a fresh angle with different people and slightly different room layout",
    "another camera angle, new people, different props and mood",
    "a different angle and brand-new people, some new details around",
]


def build_scene_prompt(style, product, i, k, scene=None):
    """卖点页：产品在场景中（满幅实拍）"""
    scene_txt = SCENE_VARIANTS[(i * 3 + k) % len(SCENE_VARIANTS)]
    style_txt = STYLE_WORDS.get(style, STYLE_WORDS["ugc"])
    brand = f"{product.get('brand', 'QAWAFI')} {product.get('name', 'Voyage Nova')}"
    fresh = FRESH_VARIANTS[(i + k) % len(FRESH_VARIANTS)]
    if scene:
        scene_txt = f"a scene similar to this: {scene_txt} (same type of place and mood, but brand-new details, {fresh})"
    return (
        f"{style_txt}: {scene_txt}, with a {brand} perfume bottle (transparent glass, soft pink "
        f"gradient, glossy black cap), natural everyday lighting, realistic textures, "
        f"vertical 9:16 composition, candid product moment, slight grain, "
        f"no text, no letters, no watermark"
    )


def build_closeup_prompt(style, product, i, scene=None):
    """价格页：产品特写（满幅实拍）"""
    style_txt = STYLE_WORDS.get(style, STYLE_WORDS["ugc"])
    brand = f"{product.get('brand', 'QAWAFI')} {product.get('name', 'Voyage Nova')}"
    scene_txt = ""
    fresh = FRESH_VARIANTS[(i + 2) % len(FRESH_VARIANTS)]
    if scene:
        scene_txt = f" in a setting similar to this: {scene}, {fresh}"
    return (
        f"{style_txt}: close-up of a {brand} perfume bottle with transparent glass in a soft "
        f"pink gradient and glossy black cap, standing on a real bathroom counter next to "
        f"everyday objects{scene_txt}, natural window light, slightly cluttered realistic background, "
        f"handheld casual product shot, vertical 9:16 composition, slight grain, "
        f"no text, no letters, no watermark"
    )


def build_ai_prompt_for_page(angle, style, product, i, k, slides, scene=None):
    """按参考图页码选择画面类型：第1张=钩子场景，最后张=产品特写，中间=产品+场景"""
    if k == 0:
        return build_ai_prompt(angle, style, product, i, scene)
    if k == slides - 1 and slides > 1:
        return build_closeup_prompt(style, product, i, scene)
    return build_scene_prompt(style, product, i, k, scene)


class Handler(BaseHTTPRequestHandler):
    api = None          # 由 main() 注入
    index_html = None   # 由 main() 注入

    # ---------- 静态页面 ----------
    def do_GET(self):
        try:
            html = self.index_html
            data = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception:
            self.send_response(500)
            self.end_headers()

    # ---------- API ----------
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            req = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            req = {}
        method = req.get("method")
        args = req.get("args") or {}
        fn = getattr(self.api, method, None)
        if fn is None or method.startswith("_"):
            self._send({"error": "未知操作: " + str(method)})
            return
        try:
            result = fn(**args) if isinstance(args, dict) else fn(args)
            self._send(result)
        except Exception as e:
            self._send({"error": str(e), "trace": traceback.format_exc()})

    def _send(self, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def main():
    api = Api()

    # 找空闲端口
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    index_path = os.path.join(RES_DIR, "index.html")
    try:
        with open(index_path, encoding="utf-8") as f:
            Handler.index_html = f.read()
    except Exception as e:
        Handler.index_html = "<html><body><h2>缺少界面文件: %s</h2></body></html>" % e
    Handler.api = api

    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    url = f"http://127.0.0.1:{port}/"
    window = webview.create_window(
        "TK图文工作台 · 参考图文分析批量生成器",
        url,
        width=1280, height=960, min_size=(1120, 880),
    )
    try:
        webview.start(gui="edgechromium")
    except Exception:
        webview.start()
    httpd.shutdown()
    httpd.server_close()


if __name__ == "__main__":
    main()
