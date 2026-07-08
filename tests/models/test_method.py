from examforge.models import Method, SubjectArea, MethodStatus


def test_method_default_status_is_seed():
    m = Method(
        name="分离参数法",
        subject_area=SubjectArea.DERIVATIVE,
        applicability="含参不等式恒成立,参数可分离",
        core_idea="将不等式化为 f(a) ≥ g(x) 形式",
        procedure_steps="1. 整理不等式 2. 分离参数 3. 求最值",
    )
    assert m.status == MethodStatus.SEED
    assert m.parent_id is None
