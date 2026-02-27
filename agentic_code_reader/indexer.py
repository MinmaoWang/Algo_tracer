#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""代码索引模块"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .models import SymbolDef
from .utils import read_text, safe_relpath

EXCLUDE_DIRS = {".git", "__pycache__", ".venv", "venv", ".mypy_cache", ".pytest_cache", "build", "dist"}


def is_python_file(p: Path) -> bool:
    return p.is_file() and p.suffix == ".py"


def iter_py_files(repo: Path) -> Iterable[Path]:
    for p in repo.rglob("*.py"):
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        yield p


def module_name_from_path(root: Path, file_path: Path) -> str:
    rel = file_path.relative_to(root)
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]
    return ".".join(parts)


class RepoIndex:
    def __init__(self, repo: Path, extra_paths: Optional[List[Path]] = None):
        self.repo = repo
        self.extra_paths = extra_paths or []
        self.symbols: Dict[str, SymbolDef] = {}
        self.shortname_map: Dict[str, list[SymbolDef]] = {}
        self.import_map: Dict[str, Dict[str, str]] = {}
        self.file_ast_ok: Dict[str, bool] = {}
        # 映射：file_rel -> source_root (用于知道文件属于哪个根目录)
        self.file_to_root: Dict[str, Path] = {}

    def build(self) -> None:
        """构建索引：先遍历 repo，再遍历 extra_paths（repo 内的符号优先）"""
        # 先索引主 repo
        self._build_from_root(self.repo, is_primary=True)
        
        # 再索引额外路径（如果存在同名符号，repo 内的已优先，不会覆盖）
        for extra_root in self.extra_paths:
            self._build_from_root(extra_root, is_primary=False)

    def _build_from_root(self, root: Path, is_primary: bool) -> None:
        """从指定根目录构建索引"""
        for py in iter_py_files(root):
            rel = safe_relpath(py, root)
            src = read_text(py)
            try:
                tree = ast.parse(src)
                self.file_ast_ok[rel] = True
            except Exception:
                self.file_ast_ok[rel] = False
                continue

            mod = module_name_from_path(root, py)
            # 如果 is_primary=False 且符号已存在（来自 repo），跳过（repo 优先）
            if not is_primary:
                # 检查是否已有同名符号，如果有则跳过（不覆盖）
                skip = False
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        q = f"{mod}.{node.name}"
                        if q in self.symbols:
                            skip = True
                            break
                if skip:
                    continue

            self.import_map[rel] = self._extract_imports(tree, mod)
            self.file_to_root[rel] = root

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    q = f"{mod}.{node.name}"
                    # 如果符号已存在且当前不是 primary，跳过（不覆盖）
                    if not is_primary and q in self.symbols:
                        continue
                    sd = SymbolDef(q, "function", rel, node.lineno, getattr(node, "end_lineno", node.lineno))
                    self._add_symbol(sd, short=node.name)
                elif isinstance(node, ast.ClassDef):
                    q = f"{mod}.{node.name}"
                    # 如果符号已存在且当前不是 primary，跳过（不覆盖）
                    if not is_primary and q in self.symbols:
                        continue
                    sd = SymbolDef(q, "class", rel, node.lineno, getattr(node, "end_lineno", node.lineno))
                    self._add_symbol(sd, short=node.name)
                    for body_node in node.body:
                        if isinstance(body_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            mq = f"{mod}.{node.name}.{body_node.name}"
                            # 如果符号已存在且当前不是 primary，跳过（不覆盖）
                            if not is_primary and mq in self.symbols:
                                continue
                            msd = SymbolDef(mq, "method", rel, body_node.lineno, getattr(body_node, "end_lineno", body_node.lineno))
                            self._add_symbol(msd, short=body_node.name)

    def get_file_root(self, file_rel: str) -> Path:
        """获取文件所属的根目录"""
        return self.file_to_root.get(file_rel, self.repo)

    def _add_symbol(self, sd: SymbolDef, short: str) -> None:
        self.symbols[sd.qualname] = sd
        self.shortname_map.setdefault(short, []).append(sd)

    def _extract_imports(self, tree: ast.AST, modname: str) -> Dict[str, str]:
        alias_map: Dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    asname = a.asname or a.name.split(".")[-1]
                    alias_map[asname] = a.name
            elif isinstance(node, ast.ImportFrom):
                if node.module is None:
                    continue
                base = node.module
                if node.level and node.level > 0:
                    cur_parts = modname.split(".")
                    up = max(0, len(cur_parts) - node.level)
                    base = ".".join(cur_parts[:up] + [base]) if base else ".".join(cur_parts[:up])
                for a in node.names:
                    asname = a.asname or a.name
                    alias_map[asname] = f"{base}.{a.name}"
        return alias_map
