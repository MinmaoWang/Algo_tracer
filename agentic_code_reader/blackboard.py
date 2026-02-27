#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""黑板数据结构模块"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .models import Evidence


def new_blackboard(repo: Path, target: str) -> Dict[str, Any]:
    return {
        "repo_root": str(repo),
        "target": target,
        "current_focus": target,
        "symbols": {},
        "frontier": [],
        "iterations": 0,
        "logs": [],
    }


def bb_log(bb: Dict[str, Any], msg: str) -> None:
    bb["logs"].append(msg)


def bb_mark_unresolved(bb: Dict[str, Any], sym: str, reason: str) -> None:
    """
    标记符号为未解析。
    - 维护 fail_count
    - 如果连续两次都无法解析，认为它不是当前仓库中的自定义方法
    """
    bb["symbols"].setdefault(sym, {})
    entry = bb["symbols"][sym]
    entry["status"] = "unresolved"
    entry["reason"] = reason
    entry["fail_count"] = int(entry.get("fail_count", 0)) + 1

    # 如果两次都解析失败，认为它不是自定义方法/本仓库符号
    if entry["fail_count"] >= 2:
        entry["ignore_unresolved"] = True
        note = f"{sym} 看起来不是当前仓库中的自定义方法，多次解析失败，请在解释中按内置/外部方法理解。"
        entry["note"] = note
        bb_log(bb, f"[resolver] ignore_unresolved sym={sym} reason={note}")
        
        # 一旦标记为 ignore_unresolved，从 frontier 中清理掉（避免 Planner 继续惦记）
        sym_short = sym.split(".")[-1] if "." in sym else sym
        bb["frontier"] = [f for f in bb["frontier"] if f != sym_short and f != sym]


def bb_add_evidence(bb: Dict[str, Any], ev: Evidence) -> None:
    bb["symbols"].setdefault(ev.symbol_ref, {})
    bb["symbols"][ev.symbol_ref].update({
        "status": "resolved",
        "kind": ev.kind,
        # 记录来源类别，供 Planner 区分主仓库符号 vs 外部库符号
        "source": getattr(ev, "source", "main_repo"),
        "defined_in": ev.defined_in,
        "span": list(ev.span),
        "snippet": ev.snippet,
        "extracted_calls": ev.extracted_calls,
    })
    BUILTINS = {
        "len", "sum", "zip", "range", "print", "min", "max", "set", "list", "dict", "tuple",
        "all", "isinstance", "get", "str", "int", "float", "bool", "type", "hasattr", "getattr",
        "enumerate", "iter", "next", "sorted", "reversed", "any", "abs", "round","join"
    }
    
    # 清理 frontier：移除已解析的符号和已忽略的符号（避免重复）
    resolved_short_names = set()
    ignored_short_names = set()
    for sym_name, sym_data in bb["symbols"].items():
        if sym_data.get("status") == "resolved":
            parts = sym_name.split(".")
            if len(parts) > 0:
                resolved_short_names.add(parts[-1])
        if sym_data.get("ignore_unresolved"):
            parts = sym_name.split(".")
            if len(parts) > 0:
                ignored_short_names.add(parts[-1])
            ignored_short_names.add(sym_name)  # 也添加完整名
    
    # 移除 frontier 中已解析的符号和已忽略的符号
    bb["frontier"] = [f for f in bb["frontier"] if f not in resolved_short_names and f not in ignored_short_names]
    
    # 添加新的未解析调用到 frontier
    for c in ev.extracted_calls:
        if c in BUILTINS:
            continue
        if "." in c:
            continue
        # 检查是否已解析
        if c in bb["symbols"]:
            continue
        # 检查是否在已解析符号的短名称中
        if c in resolved_short_names:
            continue
        # 检查是否重复
        is_duplicate = False
        for sym_name in bb["symbols"]:
            if sym_name.endswith(f".{c}") or sym_name == c:
                is_duplicate = True
                break
        if not is_duplicate and c not in bb["frontier"]:
            bb["frontier"].append(c)


def apply_patch(bb: Dict[str, Any], patch: Dict[str, Any]) -> None:
    if not patch:
        return
    if "current_focus" in patch and isinstance(patch["current_focus"], str):
        bb["current_focus"] = patch["current_focus"]
    if "add_frontier" in patch and isinstance(patch["add_frontier"], list):
        for s in patch["add_frontier"]:
            if isinstance(s, str) and s not in bb["frontier"] and s not in bb["symbols"]:
                bb["frontier"].append(s)
    if "mark_unresolved" in patch and isinstance(patch["mark_unresolved"], list):
        for item in patch["mark_unresolved"]:
            if isinstance(item, dict) and "symbol" in item:
                bb_mark_unresolved(bb, item["symbol"], item.get("reason", ""))
