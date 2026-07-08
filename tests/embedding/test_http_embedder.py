import os
import pytest

pytestmark = pytest.mark.contract


@pytest.mark.skipif(
    not os.environ.get("EXAMFORGE_RUN_CONTRACT"),
    reason="set EXAMFORGE_RUN_CONTRACT=1 to run",
)
def test_http_embedder_live_returns_correct_shape():
    from examforge.embedding import HttpEmbedder
    e = HttpEmbedder()
    v = e.embed("测试文本")
    assert len(v) == e.dim()