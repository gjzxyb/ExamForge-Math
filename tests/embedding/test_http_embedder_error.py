import httpx
import pytest


def test_http_embedder_does_not_retry_permanent_4xx():
    from examforge.embedding import HttpEmbedder

    calls = 0

    class FakeResponse:
        status_code = 401

        def raise_for_status(self):
            request = httpx.Request("POST", "https://embed.test/embeddings")
            response = httpx.Response(401, request=request)
            raise httpx.HTTPStatusError(
                "unauthorized", request=request, response=response,
            )

    class FakeClient:
        def post(self, *args, **kwargs):
            nonlocal calls
            calls += 1
            return FakeResponse()

    embedder = HttpEmbedder(base_url="https://embed.test", api_key="bad")
    embedder._client = FakeClient()
    with pytest.raises(httpx.HTTPStatusError):
        embedder.embed("hello")
    assert calls == 1
