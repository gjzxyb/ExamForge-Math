from examforge.embedding import get_embedder, MockEmbedder, HttpEmbedder


def test_default_is_mock(monkeypatch):
    monkeypatch.delenv("EXAMFORGE_EMBED_BACKEND", raising=False)
    e = get_embedder()
    assert isinstance(e, MockEmbedder)


def test_explicit_http():
    e = get_embedder("http")
    assert isinstance(e, HttpEmbedder)


def test_unknown_backend_raises():
    import pytest
    with pytest.raises(ValueError):
        get_embedder("does-not-exist")