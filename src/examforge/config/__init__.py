"""全局可配置阈值与开关。"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PipelineConfig:
    # 相似度闸门
    similarity_high: float = 0.85
    similarity_low: float = 0.55
    # 一题最多允许的方法数
    max_methods_per_problem: int = 3
    # 自动确认最低置信度
    auto_confirm_min_confidence: float = 0.7
    # 后端选择
    embed_backend: str = os.environ.get("EXAMFORGE_EMBED_BACKEND", "mock")
    llm_backend: str = os.environ.get("EXAMFORGE_LLM_BACKEND", "mock")


def get_config() -> PipelineConfig:
    return PipelineConfig()