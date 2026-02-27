#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""搜索引擎模块"""

from __future__ import annotations

import ast
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import Evidence, SymbolDef
from .indexer import RepoIndex, iter_py_files, module_name_from_path
from .utils import read_text, clip_lines, safe_relpath


def read_snippet_by_span(file_root: Path, file_rel: str, span: Tuple[int, int], context: int = 0) -> str:
    p = file_root / file_rel
    lines = read_text(p).splitlines()
    start, end = span
    start = max(1, start - context)
    end = min(len(lines), end + context)
    return "\n".join(lines[start-1:end])


def grep_repo(repo: Path, pattern: str, max_hits: int = 30, extra_roots: Optional[List[Path]] = None) -> List[Tuple[str, int, str]]:
    hits: List[Tuple[str, int, str]] = []
    rx = re.compile(pattern)
    roots = [repo]
    if extra_roots:
        roots.extend(extra_roots)
    for root in roots:
        for py in iter_py_files(root):
            rel = safe_relpath(py, root)
            try:
                lines = read_text(py).splitlines()
            except Exception:
                continue
            for i, line in enumerate(lines, start=1):
                if rx.search(line):
                    hits.append((rel, i, line[:300]))
                    if len(hits) >= max_hits:
                        return hits
    return hits


def extract_calls_from_def(src: str, logger=None) -> List[str]:
    calls: List[str] = []
    try:
        # 使用 textwrap.dedent 去除缩进，避免类方法片段以缩进开头导致 ast.parse 失败
        import textwrap
        tree = ast.parse(textwrap.dedent(src))
    except Exception as e:
        if logger:
            logger.log(f"[extract_calls] ✗ AST 解析失败: {e}")
        return calls

    class V(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> Any:
            """
            只抽取“有机会解析到仓库符号”的调用：
            - Name: foo(...)
            - Attribute 且 base 是 Name: alias.func(...)
              （例如 utils.foo, validators.create_context）
            对于更复杂的 Attribute（如 obj.method()），不再退化成裸 method 名，
            避免大量 append/join/split 之类方法名污染 frontier。
            """
            f = node.func
            if isinstance(f, ast.Name):
                # 简单函数名或短名，后续由 resolve_symbol 决定是否真能解析
                calls.append(f.id)
                if logger:
                    logger.log(f"[extract_calls] 提取 Name 调用: {f.id}")
            elif isinstance(f, ast.Attribute):
                base = f.value
                if isinstance(base, ast.Name):
                    # 只保留 alias.func 这种，交给 resolve_symbol 结合 import_map 处理
                    call_str = f"{base.id}.{f.attr}"
                    calls.append(call_str)
                    if logger:
                        logger.log(f"[extract_calls] 提取 Attribute(Name) 调用: {call_str}")
                elif isinstance(base, ast.Call) and isinstance(base.func, ast.Name):
                    # ClassName().method(...)  -> "ClassName.method"
                    cls = base.func.id
                    if cls and cls[0].isupper():
                        call_str = f"{cls}.{f.attr}"
                        calls.append(call_str)
                        if logger:
                            logger.log(f"[extract_calls] ✓ 提取 ClassName().method 调用: {call_str} (cls={cls}, method={f.attr})")
                    else:
                        if logger:
                            logger.log(f"[extract_calls] ✗ 跳过小写类名: {cls}.{f.attr}")
                else:
                    # 复杂对象方法调用（obj.method），不再退化为裸 method 名，避免噪声
                    if logger:
                        base_type = type(base).__name__
                        logger.log(f"[extract_calls] ✗ 跳过复杂 Attribute: base_type={base_type}, attr={f.attr}")
            self.generic_visit(node)

    V().visit(tree)
    seen = set()
    out = []
    for c in calls:
        if c not in seen:
            out.append(c)
            seen.add(c)
    if logger:
        logger.log(f"[extract_calls] 最终提取的调用列表: {out}")
    return out


class SearchEngine:
    def __init__(self, repo: Path, index: RepoIndex, logger=None):
        self.repo = repo
        self.index = index
        self.extra_roots = getattr(index, 'extra_paths', [])
        self.logger = logger  # 用于调试日志

    def resolve_symbol(self, symbol_ref: str, hint_file: Optional[str] = None) -> Optional[SymbolDef]:
        if self.logger:
            self.logger.log(f"[resolve_symbol] START symbol_ref={symbol_ref} hint_file={hint_file}")
        
        # 精确匹配
        if symbol_ref in self.index.symbols:
            if self.logger:
                self.logger.log(f"[resolve_symbol] ✓ 精确匹配成功: {symbol_ref}")
            return self.index.symbols[symbol_ref]

        # 类名.方法名 的后缀精确匹配（不依赖 hint_file）
        parts = symbol_ref.split(".")
        if len(parts) >= 2:
            cls = parts[-2]  # XGBRegressor
            meth = parts[-1]  # fit
            suffix = f".{cls}.{meth}"
            if self.logger:
                self.logger.log(f"[resolve_symbol] 尝试后缀匹配: suffix={suffix} (cls={cls}, meth={meth})")
            hits = []
            exact_suffix_matches = []
            sample_matches = []
            for qn, sd in self.index.symbols.items():
                if qn.endswith(suffix):
                    hits.append(sd)
                    exact_suffix_matches.append(qn)
                # 调试：记录一些包含类名和方法名的符号
                if cls in qn and meth in qn and len(sample_matches) < 10:
                    sample_matches.append(qn)
            if self.logger:
                self.logger.log(f"[resolve_symbol] 后缀匹配找到 {len(hits)} 个候选: {exact_suffix_matches[:5]}")
                if len(hits) == 0:
                    self.logger.log(f"[resolve_symbol] ✗ 后缀匹配失败: 没有找到以 '{suffix}' 结尾的符号")
                    if sample_matches:
                        self.logger.log(f"[resolve_symbol] 调试：找到包含 '{cls}' 和 '{meth}' 的符号示例（前10个）: {sample_matches}")
                    # 额外调试：查找所有包含类名和方法名的符号
                    if cls == "XGBRegressor":
                        xgb_fit_matches = [qn for qn in self.index.symbols.keys() if "XGBRegressor" in qn and "fit" in qn]
                        if xgb_fit_matches:
                            self.logger.log(f"[resolve_symbol] 调试：找到包含 'XGBRegressor' 和 'fit' 的符号: {xgb_fit_matches[:10]}")
            if len(hits) == 1:
                if self.logger:
                    self.logger.log(f"[resolve_symbol] ✓ 后缀匹配唯一命中: {hits[0].qualname}")
                return hits[0]
            elif len(hits) > 1:
                # 有多个同名类同名方法（少见但可能），优先外部库/主库可自行加权
                hits.sort(key=lambda sd: (0 if "sklearn" in sd.qualname else 1, 0 if "xgboost" in sd.qualname.lower() else 1, len(sd.qualname)))
                if self.logger:
                    self.logger.log(f"[resolve_symbol] ✓ 后缀匹配多候选，选择: {hits[0].qualname} (排序后)")
                return hits[0]

        # 如果有 hint_file，优先使用 import_map 进行匹配
        if hint_file and "." in symbol_ref:
            parts = symbol_ref.split(".")
            imap = self.index.import_map.get(hint_file, {})
            if self.logger:
                self.logger.log(f"[resolve_symbol] hint_file={hint_file} import_map keys={list(imap.keys())[:10]}")
            
            # 新增：Class.method 直接用 import_map 映射 Class，再拼 method
            # 例如：XGBRegressor.fit -> xgboost.sklearn.XGBRegressor.fit
            # 支持两段式（Class.method）和三段式（module.Class.method）的情况
            if len(parts) >= 2:
                # 尝试最后两段作为 Class.method
                cls, meth = parts[-2], parts[-1]
                if self.logger:
                    self.logger.log(f"[resolve_symbol] 尝试两段式匹配（提取最后两段）: cls={cls}, meth={meth}")
                if cls in imap:
                    imported_full = imap[cls]
                    full = f"{imported_full}.{meth}"   # e.g. xgboost.sklearn.XGBRegressor.fit
                    if self.logger:
                        self.logger.log(f"[resolve_symbol] import_map[{cls}]={imported_full}, 拼接后 full={full}")
                    if full in self.index.symbols:
                        if self.logger:
                            self.logger.log(f"[resolve_symbol] ✓ 两段式精确匹配成功: {full}")
                        return self.index.symbols[full]
                    # 兼容索引里带前缀的情况：scikit-learn-main.sklearn....
                    suffix_matches = []
                    for sym_name, sym_def in self.index.symbols.items():
                        if sym_name.endswith(f".{full}") or sym_name == full:
                            suffix_matches.append((sym_name, sym_def))
                    if suffix_matches:
                        if self.logger:
                            self.logger.log(f"[resolve_symbol] ✓ 两段式后缀匹配成功: {suffix_matches[0][0]}")
                        return suffix_matches[0][1]
                    
                    # 尝试在索引中直接查找包含该类名和方法名的符号
                    if self.logger:
                        self.logger.log(f"[resolve_symbol] import_map 路径不在索引中，尝试在索引中查找 {cls}.{meth}")
                    fallback_matches = []
                    for sym_name, sym_def in self.index.symbols.items():
                        # 查找包含类名和方法名的符号
                        if sym_name.endswith(f".{cls}.{meth}"):
                            fallback_matches.append((sym_name, sym_def))
                    if fallback_matches:
                        # 优先选择包含 xgboost/xgb 的，或者更长的路径（更具体）
                        fallback_matches.sort(key=lambda x: (
                            0 if "xgboost" in x[0].lower() or "xgb" in x[0].lower() else 1,  # xgboost/xgb 优先
                            -len(x[0])  # 更长的路径优先
                        ))
                        if self.logger:
                            self.logger.log(f"[resolve_symbol] ✓ 通过类名+方法名找到匹配: {fallback_matches[0][0]}")
                        return fallback_matches[0][1]
                    
                    # 如果精确匹配失败，尝试模糊匹配（包含类名和方法名，但不要求完全匹配）
                    if self.logger:
                        self.logger.log(f"[resolve_symbol] 尝试模糊匹配：查找包含 '{cls}' 和 '{meth}' 的符号")
                    fuzzy_matches = []
                    for sym_name, sym_def in self.index.symbols.items():
                        # 查找包含类名和方法名的符号（不要求完全匹配）
                        if cls in sym_name and meth in sym_name:
                            fuzzy_matches.append((sym_name, sym_def))
                    if fuzzy_matches:
                        # 优先选择包含 xgboost/xgb 的，或者更长的路径（更具体）
                        fuzzy_matches.sort(key=lambda x: (
                            0 if "xgboost" in x[0].lower() or "xgb" in x[0].lower() else 1,  # xgboost/xgb 优先
                            -len(x[0])  # 更长的路径优先
                        ))
                        if self.logger:
                            self.logger.log(f"[resolve_symbol] ✓ 通过模糊匹配找到: {fuzzy_matches[0][0]}")
                        return fuzzy_matches[0][1]
                    
                    if self.logger:
                        self.logger.log(f"[resolve_symbol] ✗ 两段式匹配失败: {full} 不在索引中，且未找到 {cls}.{meth} 的匹配")
                else:
                    if self.logger:
                        self.logger.log(f"[resolve_symbol] ✗ 两段式匹配失败: cls={cls} 不在 import_map 中")
            
            # 原有的三段式匹配逻辑（保留向后兼容）
            if len(parts) >= 2:
                first, rest = ".".join(parts[:-1]), parts[-1]
                if self.logger:
                    self.logger.log(f"[resolve_symbol] 尝试三段式匹配: first={first}, rest={rest}")
                if first in imap:
                    full = f"{imap[first]}.{rest}"
                    if self.logger:
                        self.logger.log(f"[resolve_symbol] import_map[{first}]={imap[first]}, 拼接后 full={full}")
                    if full in self.index.symbols:
                        if self.logger:
                            self.logger.log(f"[resolve_symbol] ✓ 三段式精确匹配成功: {full}")
                        return self.index.symbols[full]
                # 也尝试只匹配第一部分
                first_part = parts[0]
                if first_part in imap:
                    full = f"{imap[first_part]}.{'.'.join(parts[1:])}"
                    if self.logger:
                        self.logger.log(f"[resolve_symbol] 尝试第一部分匹配: first_part={first_part}, 拼接后 full={full}")
                    if full in self.index.symbols:
                        if self.logger:
                            self.logger.log(f"[resolve_symbol] ✓ 第一部分匹配成功: {full}")
                        return self.index.symbols[full]

        # Fallback 到短名匹配
        short = symbol_ref.split(".")[-1]
        cands = self.index.shortname_map.get(short, [])
        if self.logger:
            self.logger.log(f"[resolve_symbol] ✗ 所有策略失败，fallback 到短名匹配: short={short}, 候选数={len(cands)}")
            if cands:
                self.logger.log(f"[resolve_symbol] 短名候选前10个: {[c.qualname for c in cands[:10]]}")
        
        if not cands:
            if self.logger:
                self.logger.log(f"[resolve_symbol] ✗ 短名匹配失败: 无候选")
            return None

        if not hint_file:
            if self.logger:
                self.logger.log(f"[resolve_symbol] ✗ 无 hint_file，返回第一个候选: {cands[0].qualname}")
            return cands[0]

        imap = self.index.import_map.get(hint_file, {})
        scored: List[Tuple[int, SymbolDef]] = []
        for sd in cands:
            score = 0
            if sd.file == hint_file:
                score += 50
            for alias, full in imap.items():
                if sd.qualname.startswith(full + ".") or sd.qualname.startswith(full):
                    score += 30
            hint_mod = module_name_from_path(self.repo, self.repo / hint_file)
            if sd.qualname.split(".")[0:2] == hint_mod.split(".")[0:2]:
                score += 5
            scored.append((score, sd))
        scored.sort(key=lambda x: x[0], reverse=True)
        if self.logger:
            self.logger.log(f"[resolve_symbol] 短名打分完成，最高分={scored[0][0] if scored else 0}, 选择: {scored[0][1].qualname if scored else None}")
        return scored[0][1]

    def open_symbol(self, symbol_ref: str, hint_file: Optional[str] = None) -> Optional[Evidence]:
        if self.logger:
            self.logger.log(f"[open_symbol] START symbol_ref={symbol_ref} hint_file={hint_file}")
        sd = self.resolve_symbol(symbol_ref, hint_file=hint_file)
        if not sd:
            if self.logger:
                self.logger.log(f"[open_symbol] ✗ resolve_symbol 返回 None")
            return None
        if self.logger:
            self.logger.log(f"[open_symbol] ✓ resolve_symbol 成功: {sd.qualname} (file={sd.file}, span={sd.lineno}-{sd.end_lineno})")
        file_root = self.index.get_file_root(sd.file)
        snippet = read_snippet_by_span(file_root, sd.file, (sd.lineno, sd.end_lineno), context=0)
        if self.logger:
            self.logger.log(f"[open_symbol] 读取代码片段: file_root={file_root}, file={sd.file}, snippet前50字符={snippet[:50]}")
        calls = extract_calls_from_def(snippet, logger=self.logger)
        # 确定 source_kind
        source_kind = "main_repo" if file_root == self.repo else "extra_lib"
        if self.logger:
            self.logger.log(f"[open_symbol] ✓ 完成: symbol={sd.qualname}, source={source_kind}, extracted_calls={calls}")
        return Evidence(
            symbol_ref=sd.qualname,
            kind=sd.kind,
            defined_in=sd.file,
            span=(sd.lineno, sd.end_lineno),
            snippet=clip_lines(snippet, 160),
            extracted_calls=calls,
            source=source_kind,
        )

    def find_usages(self, needle: str, top_k: int = 10) -> List[Tuple[str, int, str]]:
        pat = re.escape(needle).replace("\\.", "\\.")
        return grep_repo(self.repo, pat, max_hits=top_k, extra_roots=self.extra_roots)

    def hybrid_search(self, query: str, hint_file: Optional[str] = None, top_k: int = 5) -> Dict[str, Any]:
        defs: List[Dict[str, Any]] = []
        sd = self.resolve_symbol(query, hint_file=hint_file)
        if sd:
            defs.append(asdict(sd))
        else:
            short = query.split(".")[-1]
            for cand in (self.index.shortname_map.get(short, [])[:top_k]):
                defs.append(asdict(cand))

        usages = self.find_usages(query, top_k=max(10, top_k * 4))
        return {"defs": defs[:top_k], "usages": usages[:max(10, top_k * 4)]}
