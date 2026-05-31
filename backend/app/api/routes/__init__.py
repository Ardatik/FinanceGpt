from fastapi import APIRouter

from app.api.routes import auth, challenges, coach, cushion, dashboard, mail, payments, profile, transactions


api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(profile.router, prefix="/profile", tags=["profile"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(cushion.router, prefix="/cushion", tags=["cushion"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(challenges.router, prefix="/challenges", tags=["challenges"])
api_router.include_router(mail.router, prefix="/mail", tags=["mail"])
api_router.include_router(coach.router, prefix="/coach", tags=["coach"])
