#!/usr/bin/env python3
import ast
import argparse
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

@dataclass
class DefInfo:
    qualname: str
    kind: str
    start_line: int
    end_line: int

class _DefCollector(ast.NodeVisitor):

    def __init__(self) -> None:
        self.stack: List[str] = []
        self.defs: Dict[str, DefInfo] = {}

    def _push(self, name: str) -> None:
        self.stack.append(name)

    def _pop(self) -> None:
        self.stack.pop()

    def _qualname(self, name: str) -> str:
        return '.'.join(self.stack + [name]) if self.stack else name

    @staticmethod
    def _span(node: ast.AST) -> Tuple[int, int]:
        if not hasattr(node, 'lineno') or not hasattr(node, 'end_lineno'):
            raise RuntimeError('This script requires Python >= 3.8 (need lineno/end_lineno).')
        start = node.lineno
        decos = getattr(node, 'decorator_list', []) or []
        if decos:
            start = min([start] + [d.lineno for d in decos if hasattr(d, 'lineno')])
        end = node.end_lineno
        return (start, end)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._push(node.name)
        self.generic_visit(node)
        self._pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        qual = self._qualname(node.name)
        start, end = self._span(node)
        kind = 'method' if self.stack and self._is_in_class_context() else 'function'
        self.defs[qual] = DefInfo(qualname=qual, kind=kind, start_line=start, end_line=end)
        self._push(node.name)
        self.generic_visit(node)
        self._pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        qual = self._qualname(node.name)
        start, end = self._span(node)
        kind = 'async_method' if self.stack and self._is_in_class_context() else 'async_function'
        self.defs[qual] = DefInfo(qualname=qual, kind=kind, start_line=start, end_line=end)
        self._push(node.name)
        self.generic_visit(node)
        self._pop()

    def _is_in_class_context(self) -> bool:
        return len(self.stack) == 1

def build_index(py_path: str) -> Dict[str, DefInfo]:
    with open(py_path, 'r', encoding='utf-8') as f:
        src = f.read()
    tree = ast.parse(src, filename=py_path)
    collector = _DefCollector()
    collector.visit(tree)
    return collector.defs

def extract_source(py_path: str, info: DefInfo) -> str:
    with open(py_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    start = info.start_line - 1
    end = info.end_line
    return ''.join(lines[start:end])

def main():
    ap = argparse.ArgumentParser(description='List and extract Python function/class method definitions from a .py file.')
    ap.add_argument('py', help='Path to .py file')
    ap.add_argument('action', choices=['list', 'get'], help='list: show all defs, get: extract one def')
    ap.add_argument('--name', help='Qualname to extract, e.g. format_detailed_report or A.method or outer.inner')
    ap.add_argument('--contains', help='Filter: only list names containing this substring')
    args = ap.parse_args()
    defs = build_index(args.py)
    if args.action == 'list':
        names = sorted(defs.keys())
        if args.contains:
            names = [n for n in names if args.contains in n]
        for n in names:
            info = defs[n]
            print(f'{info.qualname}\t[{info.kind}]  lines {info.start_line}-{info.end_line}')
        return
    if not args.name:
        raise SystemExit('Missing --name. Example: python extract_defs.py your.py get --name format_detailed_report')
    if args.name in defs:
        print(extract_source(args.py, defs[args.name]))
        return
    cands = [k for k in defs.keys() if args.name in k]
    if not cands:
        raise SystemExit(f"No match for name='{args.name}'. Try: python extract_defs.py {args.py} list")
    if len(cands) > 1:
        print('Multiple matches, please choose one exact qualname:')
        for k in sorted(cands):
            info = defs[k]
            print(f'  - {info.qualname}\t[{info.kind}] lines {info.start_line}-{info.end_line}')
        raise SystemExit(2)
    only = cands[0]
    print(extract_source(args.py, defs[only]))
if __name__ == '__main__':
    main()