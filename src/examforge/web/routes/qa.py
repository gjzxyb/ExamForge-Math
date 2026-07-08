"""QA 路由(占位,Task 21 完整实现)。"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/qa")
async def qa_placeholder():
    return {"todo": "qa"}


@router.post("/qa")
async def qa_post_placeholder():
    return {"todo": "qa post"}
