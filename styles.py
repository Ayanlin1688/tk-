# -*- coding: utf-8 -*-
"""
TikTok 账号风格档案 —— 从 4 个真实带货账号的图文里提炼的"人格"。
每个风格定义：语言、钩子句式池、卖点句池、CTA 池、排版参数（字体/颜色/高亮/贴纸）。

目的：每套图文随机分配一种人格，文案从池中组合、排版按人格变化 → 每一套有自己的灵魂，不是流水线。
"""

# 人格档案
STYLES = {
    "apg": {
        "name": "APG 省钱反讽",
        "lang": "es",
        "voice": "humor_irony",
        "font": "black",            # Arial Black
        "text_color": (255, 255, 255),
        "highlight": True,
        "hl_color": (255, 235, 110, 70),   # 黄色荧光笔（淡，贴近文字）
        "cta_style": "black_bar",          # 底部黑条
        "arrow": False,
        "hooks": [
            "Aviso: no compres esto si te gusta pagar de más {emoji}",
            "¿$200 por un perfume… o $26 por este? Yo ya hice la cuenta {emoji}",
            "POV: te preguntan qué perfume usas y no quieres decir cuánto costó {emoji}",
            "Compré el caro primero. Después probé este. Devolví el caro {emoji}",
            "El precio es un 10/10… el olor es un 20/10 {emoji}",
            "Mi bolsillo dijo NO, pero mi nariz dijo SÍ {emoji}",
            "El de $200 lo compré una vez… solo para darme cuenta de que este huele igual {emoji}",
            "No soy influencer, solo una persona que dejó de pagar de más por oler rico {emoji}",
        ],
        "claims": [
            "dura 8+ horas. Sin exagerar. {emoji}",
            "huele a los de $200, cuesta $26. Matemática simple {emoji}",
            "la rosa + frutos rojos es la combinación que TODOS preguntan {emoji}",
            "19.2K reseñas no mienten {emoji}",
            "un spray y me olvido del resto del día {emoji}",
            "es el perfume que la gente SIEMPRE pregunta en el ascensor {emoji}",
        ],
        "ctas": [
            "link en mi carrito {emoji} (precio de verdad, no inflado)",
            "50% OFF ahora · link en mi carrito {emoji}",
            "link abajo antes de que vuelva a subir de precio {emoji}",
            "aprovecha que está en oferta, después lloras pagando de más {emoji}",
        ],
        "emoji_pool": ["😏", "💸", "🤡", "🙃", "🤷♀️", "😌", "🤯", "🫠"],
        "tags": ["#perfume", "#perfumes", "#tiktokshop", "#QAWAFI", "#voyagenova", "#perfumesbaratos", "#regalos", "#fragancia", "#fyp", "#parati"],
        "comment_hook": "¿Cuánto pagas de más solo por el olor? 👇",
    },
    "conmariaa": {
        "name": "ConMariaa 闺蜜悬念",
        "lang": "es",
        "voice": "warning_mystery",
        "font": "black",
        "text_color": (255, 222, 0),       # 警示黄字（她主页那种黄）
        "highlight": False,                # 黄字本身醒目，不加荧光条
        "cta_style": "black_bar",
        "arrow": True,                     # 最后张加下箭头指向产品
        "hooks": [
            "Aviso no uses esto a menos que quieras que te pregunten TODO el día {emoji}",
            "No es normal oler así de rico por 8 horas {emoji}",
            "Mi amiga me vio y me dijo: ¿qué te pusiste? {emoji}",
            "Si él no te lo ha dicho todavía, esto lo va a hacer hablar {emoji}",
            "No lo compres si no quieres que te lo pidan prestado {emoji}",
            "Para las que quieren oler a $$$ sin pagar $$$ {emoji}",
            "Si quieres oler a 'no me toques' pero rico, esto es {emoji}",
            "El secreto está en el frasco rosado y no te lo digo más {emoji}",
        ],
        "claims": [
            "yo las cuido, chicas {emoji}",
            "esto hace maravillas, te lo juro {emoji}",
            "8+ horas y todavía me lo huelo yo misma {emoji}",
            "la botella más viral por algo es {emoji}",
            "un 10/10, sin filtros {emoji}",
            "es el único perfume que mi mejor amiga me quiso robar {emoji}",
        ],
        "ctas": [
            "⬇️ esto hace maravillas · link en mi carrito {emoji}",
            "link en mi carrito {emoji} (queda poco del 50% OFF)",
            "aquí abajo, chicas {emoji}",
            "link en mi carrito, pero no se lo digas a todas {emoji}",
        ],
        "emoji_pool": ["😳", "🤭", "👀", "💕", "✨", "🥺", "😭", "💖"],
        "tags": ["#perfume", "#perfumes", "#tiktokshop", "#QAWAFI", "#voyagenova", "#regalos", "#novia", "#fragancia", "#fyp", "#parati"],
        "comment_hook": "¿Tu novio o tu novia te ha dicho que hueles rico? 👇",
    },
    "jonhy": {
        "name": "Jonhy 直白实用",
        "lang": "en",
        "voice": "direct_urgent",
        "font": "black",
        "text_color": (255, 255, 255),
        "highlight": True,
        "hl_color": (255, 255, 255, 60),   # 白荧光条（淡）
        "cta_style": "black_bar",
        "arrow": False,
        "hooks": [
            "Don't wait for the next price hike. Grab yours below {emoji}",
            "Stop overpaying for the same result {emoji}",
            "If you smell like $200 but spent $26, you win {emoji}",
            "The only warning: everyone will ask what you're wearing {emoji}",
            "This one bottle replaced my whole collection {emoji}",
            "Do yourself a favor and read the reviews {emoji}",
            "The $200 bottle? Keep it. This one gets the same result for $26 {emoji}",
            "No restocks for weeks. Don't say I didn't warn you {emoji}",
        ],
        "claims": [
            "8+ hours, no re-spray needed {emoji}",
            "rose + red fruits. The combo people ask about {emoji}",
            "4.3 stars from 19.2K reviews {emoji}",
            "best seller for a reason {emoji}",
            "works all day, smells like a dream {emoji}",
            "verified 4.3 stars, 19.2K reviews — real ones {emoji}",
        ],
        "ctas": [
            "Grab yours below. Link in my cart {emoji}",
            "Link in my cart. 50% off ends soon {emoji}",
            "Free 3-day shipping. Link in my cart {emoji}",
            "Tap the cart before the sale ends tonight {emoji}",
        ],
        "emoji_pool": ["⚡", "🔥", "✅", "💯", "🚨", "😎", "👉", "🏆"],
        "tags": ["#perfume", "#perfumes", "#tiktokshop", "#QAWAFI", "#voyagenova", "#giftideas", "#fragrance", "#fyp", "#foryou", "#tiktokmademebuyit"],
        "comment_hook": "Would you pick the $26 or the $200? 👇",
    },
    "viviana": {
        "name": "Viviana 俏皮梗",
        "lang": "es",
        "voice": "playful_meme",
        "font": "black",
        "text_color": (255, 255, 255),
        "highlight": True,
        "hl_color": (255, 150, 190, 68),  # 粉色荧光笔（淡）
        "cta_style": "black_bar",
        "arrow": True,
        "hooks": [
            "Por algo le dicen el perfume que enamora {emoji}",
            "Mi secreto no es un secreto, es un link {emoji}",
            "Dicen que los hombres no se fijan en detalles… hasta que huelen esto {emoji}",
            "POV: usas esto y tu crush no deja de olerte {emoji}",
            "Linfa, perfume, lo que sea—esto SÍ funciona {emoji}",
            "No lo compres si no quieres que te lo pidan todos los días {emoji}",
            "Cuando te preguntan '¿qué perfume usas?' y no quieres confesar el truco {emoji}",
            "POV: tu crush dice 'huele rico' y tú solo sonríes {emoji}",
        ],
        "claims": [
            "8+ horas. Te lo juro por mi vida {emoji}",
            "la rosa + frutos rojos es otra cosa {emoji}",
            "un frasco y no vuelves a usar el otro {emoji}",
            "me lo preguntan hasta en el super {emoji}",
            "así de simple {emoji}",
            "es el perfume de '¿cuánto cuesta? …no importa' {emoji}",
        ],
        "ctas": [
            "link en mi carrito {emoji} (te lo juro)",
            "⬇️ aquí abajo, sin vueltas {emoji}",
            "link en mi carrito antes de que se acabe {emoji}",
            "no te lo pierdas, que el 50% se va volando {emoji}",
        ],
        "emoji_pool": ["😏", "🙈", "😅", "✨", "💅", "🫡", "🤍", "👑"],
        "tags": ["#perfume", "#perfumes", "#tiktokshop", "#QAWAFI", "#voyagenova", "#regalos", "#fragancia", "#fyp", "#parati", "#compras"],
        "comment_hook": "¿Ya oliste este perfume? Cuéntame 👇",
    },
}

STYLE_KEYS = list(STYLES.keys())

# 画面类型文案（叠字用，按风格生成时从 hooks/claims/ctas 取）

def emoji_for(style, seed=0):
    pool = STYLES[style]["emoji_pool"]
    return pool[seed % len(pool)]

def build_texts(style, seed, lang=None):
    """按人格+种子组合 标题/卖点/CTA/正文/标签/评论钩子 全套文案（发布包与叠字同源）"""
    s = STYLES[style]
    e = emoji_for(style, seed)
    e2 = emoji_for(style, seed + 1)
    # 文案池语言优先：语言与人格不一致时换目标语言的人格池（排版参数仍按原人格）
    pool_src = style
    if lang and lang != s["lang"]:
        pool_src = "jonhy" if lang == "en" else "conmariaa"
    p = STYLES[pool_src]
    hooks, claims, ctas = p["hooks"], p["claims"], p["ctas"]
    h = hooks[seed % len(hooks)].format(emoji=e)
    c = claims[(seed + 1) % len(claims)].format(emoji=e2)
    ct = ctas[(seed + 2) % len(ctas)].format(emoji=e2)
    caption = f"{h} {c} {ct}"
    tags = p["tags"]
    # 标签随种子轻微轮换（去尾2个再按种子补回，保持8-10个）
    shift = seed % 3
    if shift:
        tags = tags[shift:] + tags[:shift]
    comment_hook = p["comment_hook"]
    pinned = ("link para comprarlo en mi carrito 💝 (queda poco del 50% OFF ⏳)"
              if lang != "en" else "Link in my cart 💝 (50% off won't last ⏳)")
    return {"title": h, "body": c, "cta": ct, "caption": caption, "tags": tags,
            "comment_hook": comment_hook, "pinned": pinned, "style_name": s["name"]}

def render_params(style):
    """渲染参数：字体/颜色/高亮/CTA 样式/箭头"""
    s = STYLES[style]
    return {
        "font": s.get("font", "black"),
        "text_color": s.get("text_color", (255, 255, 255)),
        "highlight": s.get("highlight", True),
        "hl_color": s.get("hl_color", (255, 235, 110, 105)),
        "cta_style": s.get("cta_style", "black_bar"),
        "arrow": s.get("arrow", False),
    }
