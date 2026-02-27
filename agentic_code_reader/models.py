#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""数据模型模块"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Literal

from pydantic import BaseModel, Field


class Action(BaseModel):
    type: Literal["OPEN_SYMBOL", "HYBRID_SEARCH", "FIND_USAGES"]
    symbol_ref: Optional[str] = None
    hint_file: Optional[str] = None
    query: Optional[str] = None
    top_k: int = 5
    needle: Optional[str] = None
    purpose: str = ""


class PlannerOutput(BaseModel):
    actions: List[Action] = Field(default_factory=list)
    stop: bool
    reason: str
    blackboard_patch: Dict[str, Any] = Field(default_factory=dict)


@dataclass
class SymbolDef:
    qualname: str
    kind: str
    file: str
    lineno: int
    end_lineno: int


@dataclass
class Evidence:
    symbol_ref: str
    kind: str
    defined_in: str
    span: Tuple[int, int]
    snippet: str
    extracted_calls: List[str]
    source: str = "main_repo"
