import pytest
from examforge.repositories import init_db, method_repo, reset_db_engine_for_tests
from examforge.models import Method, SubjectArea, MethodStatus


@pytest.fixture
def db(tmp_data_dir):
    reset_db_engine_for_tests()
    init_db(tmp_data_dir)
    yield
    reset_db_engine_for_tests()


def _m(name, area=SubjectArea.DERIVATIVE, status=MethodStatus.SEED):
    m = Method(name=name, subject_area=area, applicability="", status=status)
    method_repo().add(m)
    return m


def test_find_by_name_and_list_confirmed(db):
    _m("A")
    _m("B", status=MethodStatus.CONFIRMED)
    repo = method_repo()
    a = repo.find_by_name("A", SubjectArea.DERIVATIVE)
    assert a is not None
    confirmed = repo.list_confirmed_by_area(SubjectArea.DERIVATIVE)
    assert {m.name for m in confirmed} == {"B"}