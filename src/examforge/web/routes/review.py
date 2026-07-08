"""审核队列路由(占位,Task 19 完整实现)。"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/review")
async def review_placeholder():
    return {"todo": "review queue"}


@router.post("/review/{si_id}/confirm")
async def confirm_placeholder(si_id: int):
    return {"todo": "confirm", "id": si_id}


@router.post("/review/{si_id}/reject")
async def reject_placeholder(si_id: int):
    return {"todo": "reject", "id": si_id}


@router.post("/review/{si_id}/revise")
async def revise_placeholder(si_id: int):
    return {"todo": "revise", "id": si_id}
