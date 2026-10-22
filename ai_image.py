# -*- coding: utf-8 -*-
"""
ai_image.py — OpenAI 兼容接口生图客户端
- 生成图像: POST {base}/v1/images/generations (model, prompt, size, n, response_format=b64_json)
- 模型列表: GET  {base}/v1/models
- 配置保存: 本地 ai_config.json（不发送给任何第三方）
"""

import os
import io
import json
import time
import base64
import urllib.request
import urllib.error

DEFAULT_CONFIG = {
    "base_url": "https://api.kkone.vip",
    "api_key": "",
    "model": "",
    "analyze_model": "",
}


def config_path():
    if getattr(__import__("sys"), "frozen", False):
        base = os.path.dirname(os.path.abspath(__import__("sys").executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "ai_config.json")


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(config_path(), encoding="utf-8") as f:
            saved = json.load(f)
        for k in cfg:
            if k in saved and saved[k]:
                cfg[k] = saved[k]
    except Exception:
        pass
    return cfg


def save_config(cfg):
    with open(config_path(), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return cfg


def _api_url(cfg, path):
    base = (cfg.get("base_url") or "").strip().rstrip("/")
    if not base:
        raise ValueError("未配置接口地址 base_url")
    if base.endswith("/v1"):
        return base + path
    return base + "/v1" + path


def _request_json(cfg, method, path, payload=None, timeout=180):
    url = _api_url(cfg, path)
    headers = {"Authorization": "Bearer " + (cfg.get("api_key") or "").strip()}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def list_models(cfg=None, timeout=60):
    """查询接口支持的模型列表，返回 [model_id, ...]"""
    cfg = cfg or load_config()
    data = _request_json(cfg, "GET", "/models", timeout=timeout)
    return [m.get("id") for m in data.get("data", [])]


def generate_image(cfg, prompt, size="1024x1792", n=1, timeout=300):
    """
    调用图像生成接口。
    返回: 成功 → [PNG bytes, ...]；失败 → 抛异常（带可读错误信息）
    """
    cfg = cfg or load_config()
    model = (cfg.get("model") or "").strip()
    if not model:
        raise ValueError("未配置生图模型 model（可在设置里从模型列表中选择）")
    payload = {
        "model": model,
        "prompt": prompt,
        "n": int(n),
        "size": size,
        "response_format": "b64_json",
    }
    try:
        data = _request_json(cfg, "POST", "/images/generations", payload, timeout=timeout)
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "ignore")[:500]
        except Exception:
            pass
        raise RuntimeError(f"生图接口返回 {e.code}: {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"无法连接生图接口: {e.reason}")

    images = []
    for item in data.get("data", []):
        if item.get("b64_json"):
            images.append(base64.b64decode(item["b64_json"]))
        elif item.get("url"):
            with urllib.request.urlopen(item["url"], timeout=120) as r:
                images.append(r.read())
    if not images:
        raise RuntimeError("生图接口未返回图像数据: " + json.dumps(data, ensure_ascii=False)[:300])
    return images


def test_connection(cfg=None):
    """测试连通性：查模型列表。返回 (ok, message, models)"""
    cfg = cfg or load_config()
    try:
        models = list_models(cfg)
        if not models:
            return False, "接口连通，但未返回任何模型（请检查密钥权限）", []
        return True, f"接口连通，发现 {len(models)} 个模型", models
    except urllib.error.HTTPError as e:
        return False, f"接口返回 {e.code}（密钥无效或无权访问）", []
    except Exception as e:
        return False, f"连接失败: {e}", []


if __name__ == "__main__":
    c = load_config()
    print("当前配置:", c["base_url"], "| key:", ("***" + c["api_key"][-4:] if c["api_key"] else "未设置"),
          "| model:", c["model"] or "未设置")
    ok, msg, models = test_connection(c)
    print("测试:", msg)
    if models:
        print("可用模型:", models[:20])
