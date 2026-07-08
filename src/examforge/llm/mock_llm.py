"""Mock LLM:不调真实 API,基于规则/固定返回驱动整套管线可在测试里跑通。"""

from .schemas import ExtractedSolution, ProposedMethodUse, ReportedSections, QAResult


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
            confidence=0.6,
        )
        return ExtractedSolution(
            summary="(占位)思路综述",
            methods=[m],
            overall_confidence=0.6,
        )

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