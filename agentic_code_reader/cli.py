#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""命令行入口模块"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 支持直接运行和作为模块运行
try:
    from .orchestrator import run
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    import os
    # 添加父目录到路径
    current_dir = Path(__file__).parent
    parent_dir = current_dir.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    from agentic_code_reader.orchestrator import run


def main():
    ap = argparse.ArgumentParser(
        description="Agentic Code Reader - 智能代码理解工具"
    )
    ap.add_argument("--repo", required=True, help="Path to repo root")
    ap.add_argument("--target", required=True, help="Target qualname, e.g. pkg.mod.func")
    ap.add_argument("--outdir", default="./_agent_out", help="Output directory")
    ap.add_argument("--max-iters", type=int, default=3, help="Maximum iterations")
    ap.add_argument("--planner-model", default="deepseek-chat", help="Planner model name")
    ap.add_argument("--synth-model", default="deepseek-chat", help="Synthesizer model name")
    ap.add_argument("--hint-file", default="", help="Relative file path for disambiguation (optional)")
    ap.add_argument("--extra-paths", nargs="*", default=[], help="Extra paths to index (e.g., site-packages/sklearn)")
    ap.add_argument("--explanation-prompt", default="", help="Custom prompt to control explanation depth/focus (e.g., '深入展开所有验证函数' or '只关注核心逻辑，忽略工具函数')")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    outdir = Path(args.outdir).resolve()
    hint_file = args.hint_file.strip() or None
    extra_paths = [Path(p).resolve() for p in (args.extra_paths or [])]
    explanation_prompt = args.explanation_prompt.strip() or None

    run(
        repo=repo,
        target=args.target,
        outdir=outdir,
        max_iters=args.max_iters,
        planner_model=args.planner_model,
        synth_model=args.synth_model,
        hint_file=hint_file,
        extra_paths=extra_paths,
        explanation_prompt=explanation_prompt,
    )


if __name__ == "__main__":
    main()
