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

    @property
    def embed_backend(self) -> str:
        from .settings import get_settings
        return get_settings().embedder.backend

    @property
    def llm_backend(self) -> str:
        from .settings import get_settings
        return get_settings().llm.backend


def get_config() -> PipelineConfig:
    return PipelineConfig()