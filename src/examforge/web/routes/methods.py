"""方法库路由(占位,Task 18 完整实现)。"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/methods")
async def methods_placeholder():
    return {"todo": "methods list"}


@router.get("/methods/{method_id}")
async def method_detail_placeholder(method_id: int):
    return {"todo": "method detail", "id": method_id}
