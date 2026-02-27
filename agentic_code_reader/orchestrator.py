#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""主协调逻辑模块"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

from .indexer import RepoIndex
from .search import SearchEngine
from .blackboard import new_blackboard, bb_add_evidence, bb_log, bb_mark_unresolved, apply_patch
from .llm_client import LLM
from .agents import PlannerAgent, ExecutorAgent, SynthesizerAgent
from .utils import write_json, write_text, RunLogger


def run(
    repo: Path,
    target: str,
    outdir: Path,
    max_iters: int = 3,
    planner_model: str = "deepseek-chat",
    synth_model: str = "deepseek-chat",
    hint_file: Optional[str] = None,
    extra_paths: Optional[List[Path]] = None,
    explanation_prompt: Optional[str] = None,
) -> None:
    """运行主流程"""
    outdir.mkdir(parents=True, exist_ok=True)

    # 初始化运行日志
    log_path = outdir / "run.log"
    logger = RunLogger(log_path)
    extra_paths_str = [str(p) for p in (extra_paths or [])]
    logger.log(
        f"START run repo={repo} target={target} max_iters={max_iters} "
        f"planner_model={planner_model} synth_model={synth_model} hint_file={hint_file} "
        f"extra_paths={extra_paths_str} explanation_prompt={explanation_prompt}"
    )

    index = RepoIndex(repo, extra_paths=extra_paths)
    print("[init] building AST index ...")
    logger.log("[init] building AST index ...")
    if extra_paths:
        print(f"[init] indexing repo + {len(extra_paths)} extra path(s): {[str(p) for p in extra_paths]}")
        logger.log(f"[init] extra_paths: {[str(p) for p in extra_paths]}")
    index.build()
    print(f"[init] indexed symbols: {len(index.symbols)}")
    logger.log(f"[init] indexed symbols: {len(index.symbols)}")

    search = SearchEngine(repo, index, logger=logger)
    llm = LLM()
    planner = PlannerAgent(llm, planner_model, explanation_prompt=explanation_prompt)
    executor = ExecutorAgent(search)
    synthesizer = SynthesizerAgent(llm, synth_model, explanation_prompt=explanation_prompt)

    bb = new_blackboard(repo, target)

    print("[bootstrap] OPEN target symbol ...")
    logger.log("[bootstrap] OPEN target symbol ...")
    logger.log(f"[bootstrap] target={target}, hint_file={hint_file}")
    

    bootstrap_hint_file = hint_file
    if not bootstrap_hint_file and "." in target:
        first = target.split(".")[0]
        candidate = repo / f"{first}.py"
        logger.log(f"[bootstrap] 尝试推断 hint_file: first={first}, candidate={candidate}")
        if candidate.exists():
            try:
                bootstrap_hint_file = str(candidate.relative_to(repo))
                logger.log(f"[bootstrap] ✓ inferred hint_file={bootstrap_hint_file} from target={target} (file exists)")
            except ValueError:
                logger.log(f"[bootstrap] ✗ ValueError when converting to relative path")
        else:
            logger.log(f"[bootstrap] ✗ candidate hint_file={first}.py does not exist, using None")
    else:
        logger.log(f"[bootstrap] 使用用户提供的 hint_file={bootstrap_hint_file}")
    
    logger.log(f"[bootstrap] 最终使用的 hint_file={bootstrap_hint_file}")
    
    # 添加索引统计信息
    logger.log(f"[bootstrap] 索引统计: 总符号数={len(index.symbols)}")
    if bootstrap_hint_file and bootstrap_hint_file in index.import_map:
        imap = index.import_map[bootstrap_hint_file]
        logger.log(f"[bootstrap] hint_file={bootstrap_hint_file} 的 import_map 包含 {len(imap)} 个导入: {list(imap.keys())[:10]}")
    
    ev0 = search.open_symbol(target, hint_file=bootstrap_hint_file)
    if ev0 is None:
        msg = f"[fatal] cannot resolve target symbol: {target}"
        print(msg)
        logger.log(msg)
        bb_mark_unresolved(bb, target, "bootstrap OPEN_SYMBOL failed")
        write_json(outdir / "blackboard.json", bb)
        logger.log_json("blackboard_fatal", bb)
        sys.exit(2)
    bb_add_evidence(bb, ev0)
    bb["current_focus"] = ev0.symbol_ref

    write_json(outdir / "blackboard.json", bb)
    logger.log_json("blackboard_after_bootstrap", bb)

    for it in range(max_iters):
        bb["iterations"] = it + 1
        write_json(outdir / "blackboard.json", bb)

        loop_header = f"[loop] iter={it+1} focus={bb.get('current_focus')}"
        print(f"\n{loop_header}")
        logger.log(loop_header)

        # Planner 阶段：记录输入摘要 + 输出结果
        plan_out = planner.plan(bb, hint_file=hint_file)
        bb_log(bb, f"[planner] stop={plan_out.stop} reason={plan_out.reason}")
        logger.log_json(
            "planner_output",
            {
                "stop": plan_out.stop,
                "reason": plan_out.reason,
                "actions": [a.model_dump() for a in plan_out.actions],
                "blackboard_patch": plan_out.blackboard_patch,
            },
        )
        apply_patch(bb, plan_out.blackboard_patch)

        if plan_out.stop:
            msg = "[loop] planner stop=true, synthesizing ..."
            print(msg)
            logger.log(msg)
            break

        # Executor 阶段：记录 action 数量
        exec_msg = f"[loop] executor actions={len(plan_out.actions)}"
        print(exec_msg)
        logger.log(exec_msg)
        executor.execute(bb, plan_out.actions, hint_file=hint_file)

        write_json(outdir / "blackboard.json", bb)
        logger.log_json("blackboard_after_executor", bb)

    # Synthesizer 阶段：记录最终解释
    final = synthesizer.synthesize(bb)
    write_text(outdir / "final_explanation.md", final)
    write_json(outdir / "blackboard.json", bb)
    logger.log_json("final_blackboard", bb)
    logger.log("final_explanation:\n" + final)

    print("\n[done] outputs:")
    print(f"  - {outdir / 'blackboard.json'}")
    print(f"  - {outdir / 'final_explanation.md'}")
    logger.log("[done] run finished")

