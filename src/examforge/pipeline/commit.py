"""Pipeline 步骤 5:Commit(向量写入 + 计数刷新)。"""

from ..models import ReviewStatus, SolutionInstance
from ..embedding import Embedder
from ..repositories import VectorRepo, MethodRepo, SolutionRepo


def commit_solution(
    si: SolutionInstance,
    *,
    embedder: Embedder,
    vector_repo: VectorRepo,
    method_repo: MethodRepo,
    solution_repo: SolutionRepo,
) -> str:
    """仅对 confirmed 的 SI 提交向量;draft/rejected 跳过。"""
    if si.review_status != ReviewStatus.CONFIRMED:
        return si.embedding_id or ""
    # 已提交过的审核结果不要重复写入向量库，避免手工重复点击造成重复样本。
    if si.embedding_id:
        return si.embedding_id
    text = (f"{si.key_steps}\n{si.transfer_note}").strip()
    vec = embedder.embed(text)
    vec_id = vector_repo.add(text, vec)
    si.embedding_id = vec_id
    solution_repo.update(si)
    # 触发 method 的时间戳刷新
    method = method_repo.get(si.method_id)
    if method is not None:
        method_repo.update(method)
    return vec_id
