#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""工具函数模块"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, List

FORBIDDEN_WORDS = [
    "可能", "也许", "大概", "或许", "应该", "推测", "猜", "不确定", "似乎"
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def write_text(path: Path, s: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(s, encoding="utf-8")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def clip_lines(s: str, max_lines: int = 140) -> str:
    lines = s.splitlines()
    if len(lines) <= max_lines:
        return s
    return "\n".join(lines[:max_lines] + ["... <clipped> ..."])


def contains_forbidden_words(s: str) -> List[str]:
    hits = []
    for w in FORBIDDEN_WORDS:
        if w in s:
            hits.append(w)
    return hits


def safe_relpath(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except Exception:
        return str(path)


class RunLogger:
    """
    简单的运行日志工具。
    - 每条日志带时间戳
    - 追加写入到同一个 .log 文件
    """

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, msg: str) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {msg}"
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def log_json(self, label: str, obj: Any) -> None:
        payload = {
            "label": label,
            "data": obj,
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        self.log(text)

