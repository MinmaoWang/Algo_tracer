#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""LLM 客户端模块"""

from __future__ import annotations

import os
import json
import re
from typing import Any

try:
    from openai import OpenAI
except ImportError:
    raise ImportError("Missing dependency: openai. Install with: pip install openai")


class LLM:
    def __init__(self):
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError(
                "DeepSeek API key 未配置，请先在环境变量中设置 DEEPSEEK_API_KEY"
            )

        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )

    def parse(self, model: str, system: str, user: str, schema_model: Any) -> Any:
        schema_json = schema_model.model_json_schema()
        enhanced_user = f"""{user}

请严格按照以下 JSON schema 格式返回结果，只返回 JSON 对象，不要包含任何其他文本：

{schema_model.__name__} schema:
{json.dumps(schema_json, ensure_ascii=False, indent=2)}
"""
        
        try:
            resp = self.client.responses.parse(
                model=model,
                input=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                text_format=schema_model,
            )
            return resp.output_parsed
        except (AttributeError, Exception):
            pass
        
        try:
            try:
                resp = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": enhanced_user},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )
            except Exception:
                resp = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": enhanced_user},
                    ],
                    temperature=0.1,
                )
            
            content = resp.choices[0].message.content
            if not content:
                raise ValueError("Empty response from LLM")
            
            try:
                json_obj = json.loads(content.strip())
                return schema_model.model_validate(json_obj)
            except json.JSONDecodeError:
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
                if json_match:
                    json_obj = json.loads(json_match.group(1))
                    return schema_model.model_validate(json_obj)
                else:
                    json_match = re.search(r'(\{.*\})', content, re.DOTALL)
                    if json_match:
                        json_obj = json.loads(json_match.group(1))
                        return schema_model.model_validate(json_obj)
                    raise ValueError(f"Failed to parse JSON from response. First 300 chars: {content[:300]}")
                    
        except Exception as e:
            raise RuntimeError(f"Failed to parse structured output: {e}") from e

    def create_text(self, model: str, system: str, user: str) -> str:
        try:
            resp = self.client.responses.create(
                model=model,
                input=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            return resp.output_text
        except (AttributeError, Exception):
            pass
        
        try:
            resp = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.2,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            raise RuntimeError(f"Failed to create text: {e}") from e
