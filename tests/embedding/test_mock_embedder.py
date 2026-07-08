from examforge.embedding import MockEmbedder


def test_dim_is_64():
    assert MockEmbedder().dim() == 64


def test_embed_is_deterministic():
    e = MockEmbedder()
    a = e.embed("分离参数法")
    b = e.embed("分离参数法")
    assert a == b


def test_embed_batch_returns_same_as_loop():
    e = MockEmbedder()
    inputs = ["a", "b", "c"]
    batch = e.embed_batch(inputs)
    assert len(batch) == 3
    assert batch[0] == e.embed("a")


def test_similarity_related_texts_score_higher():
    import math
    e = MockEmbedder()
    v1 = e.embed("使用分离参数法")
    v2 = e.embed("分离参数法求解")
    v3 = e.embed("切线放缩技巧")

    def cos(a, b):
        return sum(x * y for x, y in zip(a, b))

    related = cos(v1, v2)
    unrelated = cos(v1, v3)
    assert related >= unrelated