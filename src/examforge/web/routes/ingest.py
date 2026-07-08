"""题目录入路由(占位,Task 17 完整实现)。"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/ingest")
async def ingest_placeholder():
    return {"todo": "ingest"}


@router.post("/ingest")
async def ingest_post_placeholder():
    return {"todo": "ingest POST"}
