#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Agentic Code Reader - 智能代码理解工具

核心思想：
- Planner: 基于黑板状态规划查询动作
- Executor: 执行查询并将证据写回黑板
- Synthesizer: 基于黑板证据生成解释
"""

from __future__ import annotations

from .models import Action, PlannerOutput, SymbolDef, Evidence
from .indexer import RepoIndex
from .search import SearchEngine
from .blackboard import new_blackboard, bb_add_evidence, bb_log, bb_mark_unresolved, apply_patch
from .llm_client import LLM
from .agents import PlannerAgent, ExecutorAgent, SynthesizerAgent
from .orchestrator import run

__all__ = [
    "Action",
    "PlannerOutput",
    "SymbolDef",
    "Evidence",
    "RepoIndex",
    "SearchEngine",
    "new_blackboard",
    "bb_add_evidence",
    "bb_log",
    "bb_mark_unresolved",
    "apply_patch",
    "LLM",
    "PlannerAgent",
    "ExecutorAgent",
    "SynthesizerAgent",
    "run",
]
