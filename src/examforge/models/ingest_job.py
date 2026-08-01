"""可跨 Web worker 查询的题目录入后台任务。"""

from sqlmodel import Field, SQLModel


class IngestJobRecord(SQLModel, table=True):
    __tablename__ = "ingest_jobs"

    id: str = Field(primary_key=True)
    problem_id: int = Field(index=True)
    status: str = "queued"
    stage: str = "题目已保存，等待后台管线"
    error: str = ""
    warning: str = ""
    queued_count: int = 0
    llm_backend: str = ""
    answer_backend: str = ""
    used_fallback: bool = False
    created_at: str = ""
    finished_at: str = ""
