#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Small OpenAI-compatible clients used by this repo."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
import requests

load_dotenv()


def _model_list(raw: str | None, default: str) -> list[str]:
    models = [m.strip() for m in (raw or "").split(",") if m.strip()]
    return models or [default]


def _mime_type(path: str) -> str:
    ext = Path(path).suffix.lower()
    return {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
        ".webm": "video/webm",
        ".mkv": "video/x-matroska",
    }.get(ext, "video/mp4")


def _timeout(env_name: str, default: str) -> float:
    try:
        return float(os.getenv(env_name, default))
    except ValueError:
        return float(default)


def _parse_video_response(text: str, video_path: str) -> dict[str, Any]:
    """Return JSON responses when present; otherwise keep markdown content."""
    import re

    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            parsed = json.loads(match.group(0))
            parsed["success"] = True
            parsed["video_path"] = video_path
            return parsed
        except json.JSONDecodeError:
            pass
    return {"success": True, "content": text, "video_path": video_path}


def call_text_llm(messages: list[dict[str, Any]]) -> str:
    """Call the Stage 3 distillation model."""
    api_key = os.getenv("LINEAGE_TEXT_API_KEY")
    base_url = os.getenv("LINEAGE_TEXT_BASE_URL") or None
    models = _model_list(os.getenv("LINEAGE_TEXT_MODEL"), "gpt-4o")
    max_tokens = int(os.getenv("LINEAGE_TEXT_MAX_TOKENS", "4096"))
    timeout = _timeout("LINEAGE_TEXT_TIMEOUT", "300")

    if not api_key:
        raise ValueError("未设置 LINEAGE_TEXT_API_KEY")

    if base_url:
        url = base_url.rstrip("/") + "/chat/completions"
    else:
        url = "https://api.openai.com/v1/chat/completions"

    last_error: Exception | None = None
    for model in models:
        try:
            response = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0.8,
                    "max_tokens": max_tokens,
                },
                timeout=(20, timeout),
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"].get("content") or ""
        except Exception as exc:
            last_error = exc
            print(f"  模型 {model} 调用失败: {type(exc).__name__}: {exc}")
    raise last_error or RuntimeError("所有文本模型均失败")


def analyze_video_with_vision_model(video_path: str, prompt: str) -> dict[str, Any]:
    """Analyze a video with the configured OpenAI-compatible vision endpoint."""
    api_key = os.getenv("LINEAGE_VISION_API_KEY")
    base_url = os.getenv("LINEAGE_VISION_BASE_URL") or None
    models = _model_list(os.getenv("LINEAGE_VISION_MODEL"), "gpt-4o")
    timeout = _timeout("LINEAGE_VISION_TIMEOUT", "600")

    if not api_key:
        raise ValueError("未设置 LINEAGE_VISION_API_KEY")
    if not Path(video_path).exists():
        raise FileNotFoundError(video_path)

    video_bytes = Path(video_path).read_bytes()
    video_base64 = base64.b64encode(video_bytes).decode("utf-8")
    mime_type = _mime_type(video_path)

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
    last_error: Exception | None = None
    for model in models:
        try:
            print(f"  🚀 视觉模型: {model}, base64={len(video_base64) / 1024 / 1024:.1f}MB")
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime_type};base64,{video_base64}"},
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
                max_tokens=4096,
            )
            text = (response.choices[0].message.content or "").strip()
            if not text:
                raise ValueError("模型返回空内容")
            return _parse_video_response(text, video_path)
        except Exception as exc:
            last_error = exc
            print(f"  ⚠️ 视觉模型 {model} 失败: {exc}")

    return {
        "success": False,
        "error": str(last_error or "所有视觉模型均失败"),
        "content": "",
        "video_path": video_path,
    }


def analyze_images_with_vision_model(image_paths: list[str], prompt: str) -> dict[str, Any]:
    """Analyze one or more images with the configured OpenAI-compatible vision endpoint."""
    api_key = os.getenv("LINEAGE_VISION_API_KEY")
    base_url = os.getenv("LINEAGE_VISION_BASE_URL") or None
    models = _model_list(os.getenv("LINEAGE_VISION_MODEL"), "gpt-4o")
    timeout = _timeout("LINEAGE_VISION_TIMEOUT", "600")

    if not api_key:
        raise ValueError("未设置 LINEAGE_VISION_API_KEY")
    if not image_paths:
        raise ValueError("image_paths 不能为空")

    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for image_path in image_paths:
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(image_path)
        suffix = path.suffix.lower().lstrip(".") or "jpeg"
        mime = "image/png" if suffix == "png" else "image/jpeg"
        encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{encoded}"},
            }
        )

    url = (base_url.rstrip("/") if base_url else "https://api.openai.com/v1") + "/chat/completions"
    last_error: Exception | None = None
    for model in models:
        try:
            print(f"  🚀 图像模型: {model}, images={len(image_paths)}", flush=True)
            response = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": content}],
                    "max_tokens": 4096,
                },
                timeout=(20, timeout),
            )
            response.raise_for_status()
            data = response.json()
            text = (data["choices"][0]["message"].get("content") or "").strip()
            if not text:
                raise ValueError("模型返回空内容")
            return {"success": True, "content": text, "image_paths": image_paths}
        except Exception as exc:
            last_error = exc
            print(f"  ⚠️ 图像模型 {model} 失败: {exc}", flush=True)

    return {
        "success": False,
        "error": str(last_error or "所有图像模型均失败"),
        "content": "",
        "image_paths": image_paths,
    }

