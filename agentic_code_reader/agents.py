#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""代理模块：Planner, Executor, Synthesizer"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .models import Action, PlannerOutput
from .search import SearchEngine
from .blackboard import bb_add_evidence, bb_log, bb_mark_unresolved
from .llm_client import LLM
from .utils import contains_forbidden_words


PLANNER_SYSTEM = """你是 Planner，一个证据驱动的代码理解规划代理。
输入：blackboard_summary（黑板摘要）与 current_focus 上下文。
输出：必须符合 schema（actions/stop/reason/blackboard_patch）。

目标：
- 产出“最小充分证据集合”，让 Synthesizer 能无含糊地解释 current_focus 的关键逻辑。
- 不追求解析所有调用；只解析会影响解释结论或关键语义的依赖。

硬约束：
1) 只能依据 blackboard 中已存在的证据做判断；blackboard 没有定义证据的符号视为信息缺口。
2) 你必须先基于 current_focus 的 snippet/注释/控制流做出明确的“初步解释草案”（写在 reason 里）。
3) 只有当某个未解析符号满足【必要展开条件】时，才产生查询 action。
4) 查询优先级：OPEN_SYMBOL > HYBRID_SEARCH > FIND_USAGES。
5) 一次性规划所有“必要展开”的 actions（最多 10 个），不要只规划一个；必要的才并行。
6) **去重硬约束（必须严格遵守，违反会导致重复查询）**：
   - **重要理解**：blackboard_summary 中的 `resolved_symbols` 列表包含所有已经解析过的符号，这些符号已经有完整的定义证据（包括代码片段snippet、extracted_calls等），不需要再次查询
   - **在规划任何 OPEN_SYMBOL 之前，必须先完整检查 resolved_symbols 列表（包含所有已解析符号）和 resolved_short_names 列表**
   - 若符号的完整名（qualname）已在 resolved_symbols 列表中，**绝对禁止**为它规划 OPEN_SYMBOL（因为已经有完整定义，再次查询是重复且无效的）
   - 若符号的短名已在 resolved_short_names 列表中，**绝对禁止**为它规划 OPEN_SYMBOL
   - 同一轮内对同一 symbol_ref 最多一个 OPEN_SYMBOL
   - **关键**：如果某个符号已经在 resolved_symbols 中，说明已经有足够的信息来解释它；如果需要展开它的依赖，应该查看它的 extracted_calls，而不是再次 OPEN_SYMBOL 这个符号本身
7) stop=true 的条件（必须满足以下任一条件）：
   - 你判断现有证据已足以解释 current_focus 的关键语义与关键路径
   - **硬约束**：如果在去重约束下（检查 resolved_symbols 和 resolved_short_names）没有任何可新增的 actions，则必须 stop=true
   - all_unresolved_calls 不需要清空，但如果所有未解析调用都已满足去重约束，必须 stop=true

必要展开条件（满足任一条 => 必须查询）：
A. 语义决定性：该调用决定 current_focus 的核心输出/副作用/状态更新/关键计算。
B. 控制流决定性：该调用的返回值或异常改变 current_focus 的分支走向（if/try/raise/early return）。
C. 数据流不透明：current_focus 把关键数据交给该调用处理，而 snippet 无法推出处理规则。
D. 问题驱动：用户问题明确指向该调用语义。
E. 多处出现且关键：在关键链路中多次使用并影响主结论。

默认忽略（除非命中 D 或 B）：
- 内置函数与明显的简单工具（len/sum/zip/range/...）
- 日志/告警/字符串拼接/参数转发
- 异常类型本身（除非问题在解释报错条件）

关于 all_unresolved_calls：
- 它是“候选缺口池”，不是待办清单。
- 只从中挑选满足【必要展开条件】且会影响 current_focus 解释的符号。

输出要求：
- reason：写清 current_focus 初步解释草案 + 哪些缺口会影响解释 + 为什么这些 actions 足够。
"""


def format_blackboard_summary(bb: Dict[str, Any], max_snippet_lines: int = 40) -> str:
    target = bb.get("target")
    focus = bb.get("current_focus")
    frontier = bb.get("frontier", [])[:25]
    resolved = [k for k, v in bb.get("symbols", {}).items() if v.get("status") == "resolved"]
    unresolved = [k for k, v in bb.get("symbols", {}).items() if v.get("status") == "unresolved"]
    ignored_symbols = []
    ignored_short_names = set()
    for sym_name, sym_data in bb.get("symbols", {}).items():
        if sym_data.get("ignore_unresolved"):
            ignored_symbols.append({
                "qualname": sym_name,
                "reason": sym_data.get("reason", ""),
                "note": sym_data.get("note", "")
            })
            parts = sym_name.split(".")
            if len(parts) > 0:
                ignored_short_names.add(parts[-1])
            ignored_short_names.add(sym_name)  
    
    # 清理 frontier：移除已解析的符号和已忽略的符号
    cleaned_frontier = []
    for f in frontier:
        # 检查是否已解析（完整路径或短名称匹配）
        is_resolved = False
        for sym_name in resolved:
            if sym_name == f or sym_name.endswith(f".{f}"):
                is_resolved = True
                break
        # 检查是否已忽略
        is_ignored = f in ignored_short_names
        if not is_resolved and not is_ignored and f not in unresolved:
            cleaned_frontier.append(f)
    
    focus_ev = bb.get("symbols", {}).get(focus, {})
    snippet = ""
    extracted_calls = []
    if focus_ev.get("status") == "resolved":
        lines = focus_ev.get("snippet", "").splitlines()
        snippet = "\n".join(lines[:max_snippet_lines])
        extracted_calls = focus_ev.get("extracted_calls", [])
    
    short_to_full = {}
    # 构建 resolved_set 用于快速检查完整符号名是否已解析
    resolved_set = set(resolved)
    for full_name in resolved:
        parts = full_name.split(".")
        if len(parts) > 0:
            short_name = parts[-1]
            if short_name not in short_to_full:
                short_to_full[short_name] = full_name
    
    # 检查 current_focus 的调用
    focus_resolved_calls = []
    focus_unresolved_calls = []
    for call in extracted_calls:
        if call in {"len", "sum", "zip", "range", "print", "min", "max", "set", "list", "dict", "tuple", 
                   "all", "isinstance", "get", "str", "int", "float", "bool"}:
            continue
        if "." in call:
            continue
        # 如果这个调用对应的符号已经被标记为 ignore_unresolved，则直接跳过
        for sym_name, sym_data in bb.get("symbols", {}).items():
            if sym_data.get("ignore_unresolved") and (sym_name == call or sym_name.endswith(f".{call}")):
                break
        else:
            # 只有在没有被 ignore_unresolved 标记时，才纳入 resolved/unresolved 判断
            if call in short_to_full:
                focus_resolved_calls.append(f"{call} -> {short_to_full[call]}")
            else:
                focus_unresolved_calls.append(call)
    
    # 检查所有已解析符号的未解析调用
    # 同时记录每个未解析调用来自哪个已解析符号，帮助 Planner 推断位置
    all_unresolved_calls = {}  # call -> [source_symbols]
    for sym_name, sym_data in bb.get("symbols", {}).items():
        if sym_data.get("status") == "resolved":
            calls = sym_data.get("extracted_calls", [])
            sym_source_kind = sym_data.get("source", "main_repo")
            defined_in = sym_data.get("defined_in", "")
            for call in calls:
                if call in {"len", "sum", "zip", "range", "print", "min", "max", "set", "list", "dict", "tuple", 
                           "all", "isinstance", "get", "str", "int", "float", "bool"}:
                    continue
                if "." in call:
                    continue
                # 如果这个调用对应的符号已经被标记为 ignore_unresolved，则直接跳过
                ignored = False
                for name, data in bb.get("symbols", {}).items():
                    if data.get("ignore_unresolved") and (name == call or name.endswith(f".{call}")):
                        ignored = True
                        break
                if ignored:
                    continue
                # 检查是否已解析：不仅要检查短名映射，还要检查是否有完整符号名已解析
                is_already_resolved = False
                # 方法1：检查短名是否在 short_to_full 中
                if call in short_to_full:
                    is_already_resolved = True
                # 方法2：检查是否有任何已解析符号的完整名以这个 call 结尾
                if not is_already_resolved:
                    for resolved_sym in resolved_set:
                        if resolved_sym.endswith(f".{call}") or resolved_sym == call:
                            is_already_resolved = True
                            break
                
                if not is_already_resolved:
                    if call not in all_unresolved_calls:
                        all_unresolved_calls[call] = []
                    all_unresolved_calls[call].append({
                        "source": sym_name,
                        "file": defined_in,
                        "source_kind": sym_source_kind,
                    })
    
    # 转换为列表格式，包含上下文信息
    all_unresolved_list = []
    for call, sources in sorted(all_unresolved_calls.items()):
        # 尝试推断可能的模块路径
        possible_modules = set()
        for src in sources:
            file_path = src["file"]
            if file_path:
                # 从文件路径推断可能的模块
                parts = file_path.replace(".py", "").split("/")
                if len(parts) > 0:
                    possible_modules.add(".".join(parts))
        
        all_unresolved_list.append({
            "call": call,
            "sources": sources[:3],  
            "possible_modules": sorted(list(possible_modules))[:2] 
        })

    # 构建已解析符号的短名集合，方便 Planner 快速检查
    resolved_short_names = set()
    for full_name in resolved:
        parts = full_name.split(".")
        if len(parts) > 0:
            resolved_short_names.add(parts[-1])
    

    # 为每个已解析符号构建摘要证据（包含 defined_in, span, snippet_head, extracted_calls）
    resolved_evidence_summary = []
    for sym_name in resolved[:50]:  # 最多显示50个已解析符号的证据摘要
        sym_data = bb.get("symbols", {}).get(sym_name, {})
        if sym_data.get("status") == "resolved":
            snippet_lines = sym_data.get("snippet", "").splitlines()
            snippet_head = "\n".join(snippet_lines[:40])  # 前40行
            extracted_calls_list = sym_data.get("extracted_calls", [])
            resolved_evidence_summary.append({
                "qualname": sym_name,
                "defined_in": sym_data.get("defined_in", ""),
                "span": sym_data.get("span", []),
                "source": sym_data.get("source", "main_repo"),
                "snippet_head": snippet_head[:2000],  
                "extracted_calls": extracted_calls_list  
            })
    
    return json.dumps({
        "target": target,
        "current_focus": focus,
        "frontier_top": cleaned_frontier[:20],
        "resolved_count": len(resolved),
        "unresolved_count": len(unresolved),
        "resolved_symbols": resolved, 
        "resolved_short_names": sorted(list(resolved_short_names)),  
        "resolved_evidence_summary": resolved_evidence_summary,  
        "ignored_symbols": ignored_symbols,  
        "ignored_short_names": sorted(list(ignored_short_names)),  
        "unresolved": unresolved[:30],
        "focus_evidence": {
            "defined_in": focus_ev.get("defined_in"),
            "span": focus_ev.get("span"),
            "source": focus_ev.get("source", "main_repo"),
            "snippet_head": snippet,
            "extracted_calls": extracted_calls[:15],
            "resolved_calls": focus_resolved_calls,
            "unresolved_calls": focus_unresolved_calls
        },
        "all_unresolved_calls": all_unresolved_list[:30]  
    }, ensure_ascii=False, indent=2)


def planner_user_prompt(bb: Dict[str, Any], hint_file: Optional[str], explanation_prompt: Optional[str] = None) -> str:
    summary = format_blackboard_summary(bb)
    hint = hint_file or ""
    custom_instruction = ""
    if explanation_prompt:
        custom_instruction = f"\n\n用户自定义解释要求：\n{explanation_prompt}\n\n请根据上述要求调整你的规划策略：决定哪些依赖需要展开、展开到多深。"
    return f"""blackboard_summary:
{summary}

hint_file (relative path, may be empty):
{hint}{custom_instruction}

任务：
- 先基于 focus_evidence.snippet_head 对 current_focus 写出“明确的初步解释草案”（放在 reason 开头）。
- 然后判断：为了让解释完整且无含糊，是否缺少必要依赖定义。
  - 优先检查 focus_evidence.unresolved_calls（直接缺口）
  - 再从 all_unresolved_calls 中挑选“会影响 current_focus 解释”的必要缺口（不是清空列表）

去重硬约束（必须遵守，违反会导致重复查询）：
- **重要理解**：blackboard_summary 中的 `resolved_symbols` 列表包含所有已经解析过的符号，这些符号已经有完整的定义证据（包括代码片段snippet、extracted_calls等），不需要再次查询
- **在规划任何 OPEN_SYMBOL 之前，必须先完整检查 resolved_symbols 列表（包含所有已解析符号）和 resolved_short_names 列表**：
  - 如果某个符号的完整名（qualname）已经在 resolved_symbols 列表中，**绝对禁止**为它规划 OPEN_SYMBOL（因为已经有完整定义，再次查询是重复且无效的）
  - 如果某个 call 的短名已经在 resolved_short_names 列表中，**绝对禁止**为它规划 OPEN_SYMBOL
- **关键**：如果某个符号已经在 resolved_symbols 中，说明已经有足够的信息来解释它；如果需要展开它的依赖，应该查看它的 extracted_calls（在 focus_evidence 或 all_unresolved_calls 中），而不是再次 OPEN_SYMBOL 这个符号本身
- **忽略符号约束**：`ignored_symbols` 列表包含所有被标记为 `ignore_unresolved` 的符号（通常是内置/外部库函数，无法在当前仓库中解析）
  - 如果某个符号的完整名或短名在 `ignored_symbols` 或 `ignored_short_names` 列表中，**绝对禁止**为它规划 OPEN_SYMBOL
  - 这些符号已经被 resolver 明确标记为"无法解析，应该按内置/外部方法理解"，不需要再次尝试查询

行动规划：
- 只为“必要缺口”规划 actions（最多 10 个），必要的才并行。
- 能通过 possible_modules/来源文件推断 qualname => OPEN_SYMBOL(symbol_ref=完整路径)
- 否则 => HYBRID_SEARCH(query=call + 关键上下文)

stop 条件（必须满足以下任一条件）：
- 如果你判断现有证据已经足以解释 current_focus 的关键语义与关键路径：stop=true，actions=[]
- **硬约束**：如果在去重约束下（检查 resolved_symbols 和 resolved_short_names）没有任何可新增的 actions，则必须 stop=true（避免空转）
- 否则 stop=false，并给出必要 actions

blackboard_patch 可用于：add_frontier / mark_unresolved /（必要时）切换 current_focus
"""



class PlannerAgent:
    def __init__(self, llm: LLM, model: str, explanation_prompt: Optional[str] = None):
        self.llm = llm
        self.model = model
        self.explanation_prompt = explanation_prompt

    def plan(self, bb: Dict[str, Any], hint_file: Optional[str]) -> PlannerOutput:
        user = planner_user_prompt(bb, hint_file, self.explanation_prompt)
        system_prompt = PLANNER_SYSTEM
        if self.explanation_prompt:
            system_prompt += f"\n\n用户自定义解释要求：\n{self.explanation_prompt}\n\n请根据上述要求调整你的规划策略和深度。"
        out: PlannerOutput = self.llm.parse(self.model, system_prompt, user, PlannerOutput)
        
        # 收集已解析符号和短名集合
        resolved_symbols = {
            name
            for name, data in bb.get("symbols", {}).items()
            if isinstance(data, dict) and data.get("status") == "resolved"
        }
        resolved_short_names = set()
        for full_name in resolved_symbols:
            parts = full_name.split(".")
            if len(parts) > 0:
                resolved_short_names.add(parts[-1])
        
        # 收集被忽略的符号和短名集合
        ignored_symbols = {
            name
            for name, data in bb.get("symbols", {}).items()
            if isinstance(data, dict) and data.get("ignore_unresolved")
        }
        ignored_short_names = set()
        for full_name in ignored_symbols:
            parts = full_name.split(".")
            if len(parts) > 0:
                ignored_short_names.add(parts[-1])
            ignored_short_names.add(full_name)  # 也添加完整名
        
        # 过滤掉已解析和被忽略的 OPEN_SYMBOL actions
        filtered_actions = []
        for act in out.actions:
            if act.type == "OPEN_SYMBOL":
                sym = act.symbol_ref or ""
                if not sym:
                    continue
                # 检查完整名是否已解析
                if sym in resolved_symbols:
                    continue
                # 检查短名是否已解析
                sym_short = sym.split(".")[-1] if "." in sym else sym
                if sym_short in resolved_short_names:
                    continue
                # 检查是否有任何已解析符号的完整名以这个符号结尾
                is_resolved = False
                for resolved_sym in resolved_symbols:
                    if resolved_sym.endswith(f".{sym}") or resolved_sym == sym:
                        is_resolved = True
                        break
                if is_resolved:
                    continue
                # 检查是否被忽略
                if sym in ignored_symbols or sym in ignored_short_names:
                    continue
                if sym_short in ignored_short_names:
                    continue
                # 检查是否有任何被忽略符号的完整名以这个符号结尾
                is_ignored = False
                for ignored_sym in ignored_symbols:
                    if ignored_sym.endswith(f".{sym}") or ignored_sym == sym:
                        is_ignored = True
                        break
                if is_ignored:
                    continue
            # 保留其他类型的 action 和未解析的 OPEN_SYMBOL
            filtered_actions.append(act)
        
        # 如果过滤后 actions 为空，自动设置 stop=True
        if len(filtered_actions) == 0:
            out.stop = True
            out.reason = out.reason + "\n\n[自动停止] 所有规划的 actions 都指向已解析符号，无需继续查询。"
        
        # 更新 actions 列表
        out.actions = filtered_actions
        
        return out


class ExecutorAgent:
    def __init__(self, search: SearchEngine):
        self.search = search

    def execute(self, bb: Dict[str, Any], actions: List[Action], hint_file: Optional[str]) -> None:
        # 预先收集已经解析过的符号，避免对同一符号重复 OPEN_SYMBOL
        resolved_symbols = {
            name
            for name, data in bb.get("symbols", {}).items()
            if isinstance(data, dict) and data.get("status") == "resolved"
        }
        # 同一轮中已经尝试过的 OPEN_SYMBOL 目标（无论成功与否），也不再重复尝试
        opened_this_iter: set[str] = set()

        for act in actions:
            if act.type == "OPEN_SYMBOL":
                sym = act.symbol_ref or ""
                if not sym:
                    continue
                # 如果符号已经解析过，或者本轮已经尝试过，则跳过，避免重复日志和无效调用
                if sym in resolved_symbols or sym in opened_this_iter:
                    bb_log(
                        bb,
                        f"[executor] OPEN_SYMBOL skip duplicate: {sym} "
                        f"(already_resolved={sym in resolved_symbols}, opened_this_iter={sym in opened_this_iter})"
                    )
                    continue

                opened_this_iter.add(sym)
                ev = self.search.open_symbol(sym, hint_file=act.hint_file or hint_file)
                if ev is None:
                    bb_mark_unresolved(bb, sym, f"OPEN_SYMBOL failed: {sym}")
                    bb_log(bb, f"[executor] OPEN_SYMBOL miss: {sym}")
                else:
                    # 只做“可解析性”统计，不再丢弃未解析调用：
                    # - 之前的实现会把无法在索引中 resolve 的调用全部丢弃，导致像 validate_data
                    #   这类来自外部库但对语义很重要的函数根本进不了 blackboard/frontier。
                    # - 现在保留所有 extracted_calls，让 Planner 根据 source/source_kind 决定是否展开。
                    hint = ev.defined_in
                    resolvable: List[str] = []
                    not_resolvable: List[str] = []
                    for c in ev.extracted_calls:
                        if self.search.resolve_symbol(c, hint_file=hint):
                            resolvable.append(c)
                        else:
                            not_resolvable.append(c)

                    bb_add_evidence(bb, ev)
                    bb_log(
                        bb,
                        f"[executor] OPEN_SYMBOL ok: {ev.symbol_ref} @ {ev.defined_in}:{ev.span} "
                        f"(calls total={len(ev.extracted_calls)}, resolvable={resolvable}, "
                        f"not_resolvable={not_resolvable[:10]})",
                    )
            elif act.type == "HYBRID_SEARCH":
                q = act.query or ""
                if not q:
                    continue
                res = self.search.hybrid_search(q, hint_file=act.hint_file or hint_file, top_k=act.top_k)
                bb_log(bb, f"[executor] HYBRID_SEARCH query={q} defs={len(res['defs'])} usages={len(res['usages'])}")
                if res["defs"]:
                    top = res["defs"][0]
                    cand_qn = top.get("qualname")
                    if cand_qn:
                        ev = self.search.open_symbol(cand_qn, hint_file=act.hint_file or hint_file)
                        if ev:
                            bb_add_evidence(bb, ev)
                else:
                    bb_mark_unresolved(bb, q, "HYBRID_SEARCH found no defs")
            elif act.type == "FIND_USAGES":
                needle = act.needle or ""
                if not needle:
                    continue
                hits = self.search.find_usages(needle, top_k=act.top_k)
                bb_log(bb, f"[executor] FIND_USAGES needle={needle} hits={len(hits)}")
                bb["symbols"].setdefault(needle, {})
                bb["symbols"][needle].setdefault("usages", [])
                bb["symbols"][needle]["usages"] = hits


SYNTH_SYSTEM = """你是 Synthesizer，一个资深工程师。
你必须严格依据 blackboard 中的定义证据讲解调用链与逻辑。
硬约束：
1) 解释中涉及的函数/类/方法都必须在 blackboard.symbols 中 status=resolved，并给出来源（文件:行号范围）。
2) 不允许出现含糊措辞与不确定表达。
3) 输出结构：
   - 概览（current_focus 做什么）
   - 关键数据流/控制流（分步骤）
   - 依赖符号逐个解释（按 blackboard 的证据顺序，附来源）
   - 调用链总结（简短）

来源格式统一写为：
[relative/path.py:Lstart-Lend]
"""


def synthesizer_prompt(bb: Dict[str, Any], explanation_prompt: Optional[str] = None) -> str:
    focus = bb.get("current_focus")
    target = bb.get("target")
    symbols = bb.get("symbols", {})
    resolved_items = []
    for k, v in symbols.items():
        if v.get("status") == "resolved":
            resolved_items.append({
                "symbol_ref": k,
                "kind": v.get("kind"),
                "defined_in": v.get("defined_in"),
                "span": v.get("span"),
                "snippet": v.get("snippet"),
                "extracted_calls": v.get("extracted_calls", []),
            })
    payload = {
        "target": target,
        "current_focus": focus,
        "resolved": resolved_items,
        "frontier_remaining": bb.get("frontier", []),
    }
    prompt_text = "blackboard_evidence:\n" + json.dumps(payload, ensure_ascii=False, indent=2)
    if explanation_prompt:
        prompt_text += f"\n\n用户自定义解释要求：\n{explanation_prompt}\n\n请根据上述要求调整你的解释深度、重点和详细程度。"
    return prompt_text


class SynthesizerAgent:
    def __init__(self, llm: LLM, model: str, explanation_prompt: Optional[str] = None):
        self.llm = llm
        self.model = model
        self.explanation_prompt = explanation_prompt

    def synthesize(self, bb: Dict[str, Any]) -> str:
        user = synthesizer_prompt(bb, self.explanation_prompt)
        system_prompt = SYNTH_SYSTEM
        if self.explanation_prompt:
            system_prompt += f"\n\n用户自定义解释要求：\n{self.explanation_prompt}\n\n请根据上述要求调整你的解释深度、重点和详细程度。"
        text = self.llm.create_text(self.model, system_prompt, user)
        bad = contains_forbidden_words(text)
        if bad:
            rewrite_sys = system_prompt + "\n\n额外硬约束：禁止出现这些词：" + ",".join(bad)
            text = self.llm.create_text(self.model, rewrite_sys, user)
        return text
