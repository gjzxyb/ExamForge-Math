import pytest
from examforge.repositories import (
    init_vector_store, vector_repo, reset_vector_for_tests,
)


@pytest.fixture
def vs(tmp_data_dir):
    reset_vector_for_tests()
    init_vector_store(tmp_data_dir / "chroma")
    yield
    reset_vector_for_tests()


def test_add_and_query_returns_self_on_top(vs):
    repo = vector_repo()
    e = [1.0, 0.0, 0.0]
    vec_id = repo.add("doc-A", e)
    got = repo.get(vec_id)
    assert got == "doc-A"
    res = repo.query(e, top_k=1)
    assert res and res[0][0] == vec_id