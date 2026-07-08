"""枚举定义。集中放这里便于复用与测试。"""

from enum import Enum


class SubjectArea(str, Enum):
    """数学板块。"""
    DERIVATIVE = "导数"
    CONIC = "圆锥曲线"
    SEQUENCE = "数列"
    INEQUALITY = "不等式"
    PROBABILITY = "概率统计"
    SOLID_GEOMETRY = "立体几何"
    PLANE_GEOMETRY = "平面几何"
    FUNCTION = "函数"
    OTHER = "其他"


class MethodStatus(str, Enum):
    SEED = "seed"            # 教研预置
    CANDIDATE = "candidate"  # 由系统发现的新方法候选
    CONFIRMED = "confirmed"  # 已审核


class ReviewStatus(str, Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
