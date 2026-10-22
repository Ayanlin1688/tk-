# -*- coding: utf-8 -*-
"""
content.py — TK图文工作台 双语文案素材库
目标市场：美国（英语 + 西语，拉美西语）
默认产品：QAWAFI Voyage Nova 女士香水（玫瑰+红果香调）
所有素材可被 generator.py 调用，也可在 GUI 中编辑产品信息后覆盖。
"""

# ============================================================
# 一、默认产品事实（用户可在界面中修改）
# ============================================================
DEFAULT_PRODUCT = {
    "brand": "QAWAFI",
    "name": "Voyage Nova",
    "desc": "女士香水 · 玫瑰+红果香调 · Extrait de Parfum",
    "price_50": "$25.99",
    "price_100": "$25.99",
    "sale": "50% OFF",
    "shipping": "envío gratis 3 días / free 3-day shipping",
    "rating": "4.3★ / 19.2K reviews",
    "sales": "153.7K sold · Best Seller",
    "hook_claim": "8h+ 留香 · 闻起来像 $200 大牌只花 $26",
    "refund": "Free returns · fast refund",
    "product_image": "",   # 产品图路径（用户可指定）
}

# ============================================================
# 二、五个内容角度（矩阵）
# ============================================================
ANGLES = {
    "pov":     {"name": "吸引力POV",     "langs": ["en"]},
    "rosas":   {"name": "玫瑰约会叙事",   "langs": ["es"]},
    "value":   {"name": "平价贵感",       "langs": ["es", "en"]},
    "long":    {"name": "留香实测",       "langs": ["en", "es"]},
    "flash":   {"name": "闪购紧迫",       "langs": ["es", "en"]},
}

# ============================================================
# 三、钩子叠字库（图1 顶部叠字，每行≤8词）
# 结构：{角度: {"en": [...], "es": [...]}}
# ============================================================
HOOKS = {
    "pov": {
        "en": [
            "the perfume that makes him surrender",
            "he can't stop smelling my neck",
            "every guy at the party asked what I'm wearing",
        ],
        "es": [
            "el perfume que lo hace rendirse",
            "no puede dejar de oler mi cuello",
            "todos me preguntan qué me puse",
        ],
    },
    "rosas": {
        "en": [
            "smells like the most expensive roses in the world 🌹",
            "he came with roses and said \"this smells like you\" 😭🌹",
            "one spritz and you'll smell like a $200 bouquet 🌹",
        ],
        "es": [
            "huele al ramo de rosas más caro del mundo 🌹",
            "llegó con un ramo de rosas y me dijo \"esto huele a ti\" 😭🌹",
            "un toque y hueles como un ramo de $200 🌹",
        ],
    },
    "value": {
        "en": [
            "$26 vs $200 — same vibe",
            "smells expensive. costs $26. period.",
            "the $200 dupe nobody talks about",
        ],
        "es": [
            "$26 vs $200 — el mismo vibe",
            "huele caro. cuesta $26. punto.",
            "el dupe de $200 del que nadie habla",
        ],
    },
    "long": {
        "en": [
            "sprayed at 7am… still smelling it at 3pm",
            "8+ hours later it's still there",
            "the only perfume that survives my whole workday",
        ],
        "es": [
            "me lo puse a las 7am… a las 3pm todavía huele",
            "8+ horas después todavía está ahí",
            "el único perfume que aguanta todo mi día",
        ],
    },
    "flash": {
        "en": [
            "50% OFF ends tonight ⏳",
            "this deal won't last — 50% OFF now",
            "grabbed it before the sale ends ⏳",
        ],
        "es": [
            "el 50% OFF termina esta noche ⏳",
            "esta oferta no dura — 50% OFF ahora",
            "lo agarré antes de que terminara la oferta ⏳",
        ],
    },
}

# ============================================================
# 四、正文文案库（发布正文，英西双语，可组合出多条变体）
# 每条 = 首句 + 主体 + 结尾CTA
# ============================================================
CAPTIONS = {
    "pov": {
        "en": [
            "He literally said \"what are you wearing?\" before I even said hi. {claim} {cta}",
            "Wore this on a date and he kept pulling me closer. {claim} {cta}",
            "POV: he can't stop thinking about how you smell. {claim} {cta}",
        ],
        "es": [
            "Literal me dijo \"¿qué te pusiste?\" antes de saludarme. {claim} {cta}",
            "Lo usé en una cita y no dejaba de acercarse. {claim} {cta}",
            "POV: él no puede dejar de pensar en cómo hueles. {claim} {cta}",
        ],
    },
    "rosas": {
        "en": [
            "Me dijo que huelo a las rosas más caras del mundo… y el frasco costó $26 🌹 {claim} {cta}",
            "He said I smell like the most expensive roses… and the bottle was $26 🌹 {claim} {cta}",
            "Got complimented twice in one day wearing this. {claim} {cta}",
        ],
        "es": [
            "Me dijo que huelo a las rosas más caras del mundo… y el frasco costó $26 🌹 {claim} {cta}",
            "Me halagaron dos veces en un día usándolo. {claim} {cta}",
            "Es el perfume que me regalaría a mí misma 😌 {claim} {cta}",
        ],
    },
    "value": {
        "en": [
            "Smells like a $200 luxury perfume. Costs $26. Math checks out. {claim} {cta}",
            "I compared it side by side with my expensive bottle… honestly can't tell. {claim} {cta}",
            "Luxury smell, drugstore price. {claim} {cta}",
        ],
        "es": [
            "Huele como un perfume de lujo de $200. Cuesta $26. La matemática cuadra. {claim} {cta}",
            "Lo comparé con mi frasco caro… honestamente no noté la diferencia. {claim} {cta}",
            "Olor de lujo, precio de farmacia. {claim} {cta}",
        ],
    },
    "long": {
        "en": [
            "Sprayed it at 7am for work. By 3pm my coworker asked what I was wearing. {claim} {cta}",
            "8+ hours later and it's still there. This is the one. {claim} {cta}",
            "I own 20 perfumes. This is the only one that lasts my full shift. {claim} {cta}",
        ],
        "es": [
            "Me lo puse a las 7am para trabajar. A las 3pm mi compañera me preguntó qué usaba. {claim} {cta}",
            "8+ horas después y todavía está ahí. Este es el bueno. {claim} {cta}",
            "Tengo 20 perfumes. Este es el único que aguanta todo mi turno. {claim} {cta}",
        ],
    },
    "flash": {
        "en": [
            "Just grabbed this at 50% OFF before it ends tonight ⏳ {claim} {cta}",
            "The 50% OFF sale is ending — don't say I didn't warn you. {claim} {cta}",
            "Cart's been ready all week. Finally pulled the trigger at 50% OFF. {claim} {cta}",
        ],
        "es": [
            "Acabo de agarrarlo con 50% OFF antes de que termine esta noche ⏳ {claim} {cta}",
            "La oferta del 50% OFF está terminando — no digas que no te avisé. {claim} {cta}",
            "Tenía el carrito listo toda la semana. Al final le di click con el 50% OFF. {claim} {cta}",
        ],
    },
}

# ============================================================
# 五、CTA（结尾引导）
# ============================================================
CTAS = {
    "en": [
        "link in my cart 💝",
        "grab it before the sale ends ⏳",
        "link in bio 💌",
        "50% OFF — link in my cart ✨",
    ],
    "es": [
        "link en mi carrito 💝",
        "cógelo antes de que termine la oferta ⏳",
        "link en mi bio 💌",
        "50% OFF — link en mi carrito ✨",
    ],
}

# 主体（卖点/背书）句，可插入正文
CLAIMS = {
    "en": [
        "The rose + red fruits scent lasts 8+ hours.",
        "4.3 stars with 19.2K reviews and 153.7K sold.",
        "Extrait de parfum — the strongest concentration out there.",
        "Smells like a $200 niche perfume for only $26.",
    ],
    "es": [
        "El aroma de rosa + frutos rojos dura 8+ horas.",
        "4.3 estrellas con 19.2K reseñas y 153.7K vendidos.",
        "Extrait de parfum — la concentración más fuerte que hay.",
        "Huele como un perfume nicho de $200 por solo $26.",
    ],
}

# ============================================================
# 六、话题标签（8-10个一组，按语言）
# ============================================================
TAGS = {
    "en": [
        "#perfume #perfumes #tiktokshop #fragrance #perfumereview #perfumetok #fyp #foryou #giftideas #luxuryperfume #perfumedupe #ootd",
        "#perfume #fragrance #tiktokshop #tiktokfinds #perfumetok #review #fyp #foryoupage #giftguide #date night #selfcare #beauty",
    ],
    "es": [
        "#perfume #perfumes #tiktokshop #QAWAFI #voyagenova #regalos #novia #perfumesbaratos #fyp #parati #fragancia #compras",
        "#perfume #perfumes #tiktokshop #ofertas #perfumesbaratos #QAWAFI #voyagenova #regalos #fyp #parati #fragancia #primeramor",
    ],
}
BRAND_TAGS = ["#QAWAFI", "#voyagenova", "#tiktokshop"]

# ============================================================
# 七、评论钩子 + 置顶评论
# ============================================================
COMMENT_HOOKS = {
    "en": [
        "Has someone ever told you that you smell amazing? 👇",
        "What's your go-to date night perfume? 💬",
        "Would you try a $26 dupe of a $200 perfume? 👇",
        "How long does YOUR perfume usually last? 💬",
    ],
    "es": [
        "¿Tu novio o tu novia te ha dicho que hueles rico? 👇",
        "¿Cuál es tu perfume favorito para citas? 💬",
        "¿Probarías un dupe de $26 de un perfume de $200? 👇",
        "¿Cuánto dura tu perfume normalmente? 💬",
    ],
}
PINNED = {
    "en": "link to buy in my cart 💝 (50% OFF almost gone ⏳)",
    "es": "link para comprarlo en mi carrito 💝 (queda poco del 50% OFF ⏳)",
}

# ============================================================
# 八、生图提示词素材（英文，供 AI 生成实拍素材图）
# 结构：人物池 × 场景池 × 情节池
# ============================================================
PERSONS = [
    "a young Latina woman (mid-20s) with long dark brown hair, everyday look, wearing a plain white t-shirt, natural no-makeup face",
    "a young Latina woman with dark curly hair, relaxed weekend look, wearing an oversized hoodie",
    "a young Latina woman with a shoulder-length bob, casual outfit, wearing a denim jacket over a tank top",
    "a young Latina woman with a high ponytail, athletic look, wearing a simple sports top",
    "a young Latina woman with long straight black hair, cozy home look, wearing a soft cardigan",
    "a young Latina woman with golden-brown waves, casual errands look, wearing a knit sweater",
]
SCENES = [
    "in her real bedroom with an unmade bed and morning light through the window",
    "in a normal bathroom with everyday toiletries visible, natural window light",
    "in the passenger seat of a car, bright daylight",
    "in a small kitchen with everyday items in the background, soft daylight",
    "standing in her hallway by the front door, getting ready to leave",
    "in a gym locker room with fluorescent lighting",
    "at her office desk with a water bottle and notebook around",
    "on a rooftop with city buildings around, daylight",
    "on a park bench with soft sunlight",
    "at the mall, casual shopping moment, store lighting",
]
PLOTS = [
    "her boyfriend casually burying his face in her neck while she laughs, candid unposed moment",
    "her boyfriend handing her a bouquet of red roses at home, casual moment",
    "her friend leaning in to smell her wrist and asking what she's wearing",
    "a stranger stopping her on the street to ask what perfume she's wearing",
    "her smelling her own wrist and smiling to herself, everyday moment",
    "her boyfriend pulling her wrist up to smell it, both laughing naturally",
]

PROMPT_TEMPLATE = (
    "iPhone snapshot, casual amateur photo taken by a friend: {person}, {scene}, {plot}, "
    "natural everyday lighting, slightly imperfect framing, realistic skin texture, "
    "everyday realism, candid unposed moment, slight grain and soft focus, "
    "no studio lighting, no photoshoot, no fashion editorial style, no text, no letters"
)

PRODUCT_SHOT_PROMPT = (
    "Handheld iPhone photo taken in a real bathroom: a perfume bottle with transparent "
    "glass in a soft pink gradient, glossy black cap, standing on a bathroom counter "
    "next to everyday objects, natural bathroom lighting, slightly cluttered realistic "
    "background, casual product shot, no studio, no staging, photorealistic, no text"
)

# ============================================================
# 九、生成图排版配色方案（多套变体的颜色来源）
# 结构：{方案名: {bg_top, bg_bottom, text, accent, card}}
# ============================================================
COLOR_SCHEMES = [
    {"name": "主色同系（深→浅）",  "bg_top": None, "bg_bottom": None, "text": None, "accent": None, "card": None},  # 占位：运行时用参考图主色
    {"name": "主色+金色贵感",     "bg_top": (18, 15, 20), "bg_bottom": (45, 38, 55), "text": (255, 255, 255), "accent": (212, 175, 55), "card": (28, 24, 33)},
    {"name": "黑金高级",         "bg_top": (10, 10, 12), "bg_bottom": (30, 30, 36), "text": (255, 255, 255), "accent": (218, 165, 32), "card": (20, 20, 26)},
    {"name": "粉紫浪漫",         "bg_top": (70, 30, 60), "bg_bottom": (150, 80, 130), "text": (255, 255, 255), "accent": (255, 215, 235), "card": (90, 40, 80)},
    {"name": "清爽白+主色",      "bg_top": (250, 250, 252), "bg_bottom": (240, 235, 245), "text": (30, 30, 40), "accent": None, "card": (255, 255, 255)},
    {"name": "互补色冲击",       "bg_top": None, "bg_bottom": None, "text": None, "accent": None, "card": None},  # 运行时按主色互补计算
]

# ============================================================
# 十、工具函数
# ============================================================

def build_claim(product, lang):
    """根据产品信息生成背书句。lang: 'en'/'es'"""
    p = product or DEFAULT_PRODUCT
    if lang == "es":
        return (
            f"El aroma de rosa + frutos rojos de {p['name']} de {p['brand']} "
            f"dura 8+ horas. {p['rating']} · {p['sales']}. {p['sale']} esta semana."
        )
    return (
        f"The rose + red fruits scent of {p['brand']} {p['name']} lasts 8+ hours. "
        f"{p['rating']} · {p['sales']}. {p['sale']} this week."
    )


def build_caption(angle, lang, product=None, variant=0):
    """按角度+语言+变体组合出一条完整发布正文"""
    import random
    p = product or DEFAULT_PRODUCT
    tmpl = CAPTIONS[angle][lang][variant % len(CAPTIONS[angle][lang])]
    claim = random.choice(CLAIMS[lang])
    cta = random.choice(CTAS[lang])
    return tmpl.format(claim=claim, cta=cta)


def build_tags(lang, variant=0):
    """返回一组话题标签"""
    tags = TAGS[lang][variant % len(TAGS[lang])]
    return tags


def build_comment_hook(lang, variant=0):
    return COMMENT_HOOKS[lang][variant % len(COMMENT_HOOKS[lang])]


def build_pinned(lang):
    return PINNED[lang]


def build_shot_prompt(p_i, s_i, pl_i):
    """生成图1英文生图提示词（人物×场景×情节）"""
    return PROMPT_TEMPLATE.format(
        person=PERSONS[p_i % len(PERSONS)],
        scene=SCENES[s_i % len(SCENES)],
        plot=PLOTS[pl_i % len(PLOTS)],
    )


def price_card_text(lang):
    """价格卡叠字（图2）"""
    p = DEFAULT_PRODUCT
    if lang == "es":
        return f"{p['sale']} · {p['price_50']} · envío gratis 3 días · link en mi carrito"
    return f"{p['sale']} · {p['price_50']} · free 3-day shipping · link in my cart"


def price_card_short(lang):
    """短价格卡叠字（参考图 cta 区小时用）"""
    p = DEFAULT_PRODUCT
    if lang == "es":
        return f"{p['sale']} · {p['price_50']} · link en mi carrito"
    return f"{p['sale']} · {p['price_50']} · link in my cart"


if __name__ == "__main__":
    # 自检
    for lang in ["en", "es"]:
        print(f"--- {lang} ---")
        print(build_caption("rosas", lang))
        print(build_tags(lang))
        print(build_comment_hook(lang))
        print(build_pinned(lang))
        print(price_card_text(lang))
    print(build_shot_prompt(0, 1, 2))
