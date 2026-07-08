from sqlmodel import Session, SQLModel, create_engine
from examforge.models import Method, SubjectArea, MethodStatus
from examforge.taxonomy import load_seed_methods, seed_methods


def _engine():
    eng = create_engine("sqlite:///:memory:", future=True)
    SQLModel.metadata.create_all(eng)
    return eng


def test_seed_methods_covers_derivative_and_conic():
    items = seed_methods()
    areas = {m.subject_area for m in items}
    assert SubjectArea.DERIVATIVE in areas
    assert SubjectArea.CONIC in areas


def test_load_seed_methods_idempotent():
    eng = _engine()
    s1 = Session(eng)
    a = load_seed_methods(s1)
    s2 = Session(eng)
    b = load_seed_methods(s2)
    assert len(a) > 0
    assert len(b) == 0  # 第二次不应再插入


def test_loaded_seeds_have_required_fields():
    eng = _engine()
    s = Session(eng)
    methods = load_seed_methods(s)
    m = methods[0]
    assert m.status == MethodStatus.SEED
    assert m.applicability
    assert m.core_idea
    assert m.procedure_steps
    assert m.pitfalls