from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.dashboard import DashboardOut
from app.services.finance import dashboard_for_user, financial_portrait_for_user


router = APIRouter()


@router.get("", response_model=DashboardOut)
async def dashboard(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await dashboard_for_user(session, current_user)


@router.get("/portrait")
async def financial_portrait(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await financial_portrait_for_user(session, current_user)
