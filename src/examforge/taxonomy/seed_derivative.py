"""导数板块预置方法种子。"""

ALL_DERIVATIVE = [
    {"name": "分离参数法", "applicability": "含参不等式/极值,且可把参数从主变量中分离出",
     "core_idea": "化为 f(a) ≥ g(x) 后求 g 的最值",
     "procedure_steps": "1. 整理 2. 分离 3. 对侧求最值",
     "pitfalls": "忘验等号;极值与端点综合;参数范围"},
    {"name": "切线放缩", "applicability": "指数/对数不等式,常见 a^x ≥ 1+ln(a)(x-1) 类",
     "core_idea": "用常见函数的切线/常用不等式逼近",
     "procedure_steps": "1. 选放缩形式 2. 作差构造函数 3. 判单调或求最值",
     "pitfalls": "选错切线方向;忘写等号条件"},
    {"name": "构造函数比较", "applicability": "两不等式或两数比较,不易直接作差时",
     "core_idea": "构 F(x)=f(x)-g(x),通过单调性比较",
     "procedure_steps": "1. 作差 2. 构函 3. 用导数判单调 4. 求最值",
     "pitfalls": "构造方向反;忽略端点"},
    {"name": "隐零点代换", "applicability": "极值点不易显式表达时",
     "core_idea": "把含极值点的表达式用 x0 替换,消去超越",
     "procedure_steps": "1. 设极值点 x0 2. 替换 3. 研究 x0 范围",
     "pitfalls": "替换后忘回代检验"},
]