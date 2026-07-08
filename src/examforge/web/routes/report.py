"""报告路由(占位,Task 20 完整实现)。"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/report")
async def report_placeholder():
    return {"todo": "report"}
