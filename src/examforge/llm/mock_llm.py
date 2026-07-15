"""Mock LLM:不调真实 API,基于规则/固定返回驱动整套管线可在测试里跑通。"""

from .schemas import ExtractedSolution, ProposedMethodUse, ReportedSections, QAResult, GeneratedAnswer


def _looks_like_parametric(stem: str) -> bool:
    return ("任意" in stem or "恒成立" in stem) and "a" in stem


class MockLLM:
    def extract_solution(self, *, stem_latex, reference_solution,
                         taxonomy_hint, subject_area) -> ExtractedSolution:
        # 简单启发式,用于驱动测试。
        if _looks_like_parametric(stem_latex):
            name = "分离参数法" if "分离参数法" in taxonomy_hint else "未命名方法"
        else:
            name = "切线放缩" if "切线放缩" in taxonomy_hint else "未命名方法"
        m = ProposedMethodUse(
            method_name=name,
            subject_area=subject_area,
            key_steps="(占位)此方法在本题的关键步骤",
            transfer_note="(占位)可迁移套路",
            applicability="(占位)适用特征",
            confidence=0.85,
        )
        return ExtractedSolution(
            summary="(占位)思路综述",
            methods=[m],
            overall_confidence=0.85,
        )

    def generate_answer(self, *, stem_latex, subject_area, reference_solution=None, web_context=None) -> GeneratedAnswer:
        """缺失答案时的本地占位生成,保证录入流程可 fail-open。"""
        stem = stem_latex or ""
        search_note = ""
        if web_context:
            search_note = "\n5. 全网搜索参考:已接收搜索摘要,但 mock 后端不会据此做真实数学推导,仅标记流程已接入搜索上下文。"
        if _looks_like_parametric(stem):
            answer = "(自动生成占位答案) a=2"
            steps = (
                "1. 审题:题干含“任意/恒成立”和参数 a,可先按含参恒成立模型处理。\n"
                "2. 转化:把不等式整理为参数与关于 x 的函数最值之间的比较关系。\n"
                "3. 计算:mock 后端不做真实符号运算,沿用内置样例推断最值对应参数为 2。\n"
                "4. 验证:真实使用时仍需检查等号是否可取、参数定义域和端点条件;当前答案为占位草稿。"
                f"{search_note}"
            )
        elif "选择" in stem or "A" in stem and "B" in stem:
            answer = "(自动生成占位答案) 请以真实 LLM/API 结果为准"
            steps = (
                "1. 审题:识别到可能是选择题或含选项题。\n"
                "2. 条件整理:需要完整选项、图形或题干约束才能排除干扰项。\n"
                "3. 计算策略:应逐项代入或按题型建立方程/不等式验证。\n"
                "4. 结论:mock 后端无法可靠判断选项,这里只给出占位结果并降低置信度。"
                f"{search_note}"
            )
        else:
            answer = "(自动生成占位答案) 待真实 LLM/API 补全"
            steps = (
                "1. 审题:已收到题干,但 mock 后端无法完成通用数学推导。\n"
                "2. 条件整理:应先列出已知量、目标量和所属模块常用公式。\n"
                "3. 计算路径:根据题型选择代数化简、函数最值、几何关系或概率模型。\n"
                "4. 验证:最终答案需回代题干并检查定义域、单位、取值范围和特殊情形。"
                f"{search_note}"
            )
        return GeneratedAnswer(answer=answer, analysis_steps=steps, confidence=0.6)

    def render_report(self, *, method_name, applicability, core_idea,
                      procedure, pitfalls, examples) -> ReportedSections:
        return ReportedSections(
            intro=f"关于 {method_name} 的解法专题报告。",
            core_idea=core_idea,
            procedure=procedure,
            applicability=applicability,
            pitfalls=pitfalls,
            examples_markdown="(占位)Markdown 表格",
        )

    def answer_question(self, *, question, method_doc, examples) -> QAResult:
        return QAResult(
            answer=f"(占位)基于 {method_doc[:20]} ... 的回答",
            cited_method_names=[],
            cited_problem_ids=[],
        )
