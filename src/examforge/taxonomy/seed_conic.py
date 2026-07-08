"""圆锥曲线板块预置方法种子。"""

ALL_CONIC = [
    {"name": "设而不求联立", "applicability": "直线与圆锥曲线交点问题",
     "core_idea": "设交点参数但不直接求解,利用韦达定理",
     "procedure_steps": "1. 设线参数 2. 联立 3. 韦达 4. 代入目标式",
     "pitfalls": "判别式忽略;零点遗漏"},
    {"name": "硬解点差法", "applicability": "涉及弦中点或垂直弦时",
     "core_idea": "用两端点坐标差的韦达表达",
     "procedure_steps": "1. 设两端点 2. 韦达差 3. 整理",
     "pitfalls": "忽略斜率不存在情形"},
    {"name": "齐次化与平移", "applicability": "斜率为定值、与非标准位置曲线交汇",
     "core_idea": "把非标准型经平移旋转化为标准",
     "procedure_steps": "1. 配标准型 2. 平移 3. 套标准模板",
     "pitfalls": "平移后方程对应错位"},
]