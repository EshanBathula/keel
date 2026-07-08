from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import TxType, User
from ..schemas import ForecastResponse, Insight, KPIs, MonthlyPoint, ScenarioRequest
from ..services import analytics as svc
from ..services.forecast import forecast as run_forecast
from ..services.forecast import scenario as run_scenario
from ..services.insights import generate_insights
from ..tz import user_today

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/kpis", response_model=KPIs)
def kpis(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return svc.compute_kpis(db, user.id, today=user_today(user))


@router.get("/monthly", response_model=list[MonthlyPoint])
def monthly(
    months: int = Query(12, ge=3, le=36), db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    return svc.monthly_series(db, user.id, months=months, today=user_today(user))


@router.get("/categories", response_model=list[dict])
def categories(
    type: TxType = TxType.expense,
    months: int = Query(12, ge=1, le=36),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return svc.category_breakdown(db, user.id, type, months=months, today=user_today(user))


@router.get("/top-customers", response_model=list[dict])
def customers(
    limit: int = Query(5, ge=1, le=25), db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    return svc.top_customers(db, user.id, limit=limit)


@router.get("/forecast", response_model=ForecastResponse)
def forecast(
    horizon: int = Query(6, ge=1, le=12), db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    return run_forecast(db, user.id, horizon_months=horizon, today=user_today(user))


@router.post("/scenario", response_model=ForecastResponse)
def scenario(
    payload: ScenarioRequest,
    horizon: int = Query(6, ge=1, le=12),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return run_scenario(
        db,
        user.id,
        monthly_revenue_change_pct=payload.monthly_revenue_change_pct,
        new_monthly_expense_cents=payload.new_monthly_expense_cents,
        start_month=payload.start_month,
        horizon_months=horizon,
        today=user_today(user),
    )


@router.get("/insights", response_model=list[Insight])
def insights(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return generate_insights(db, user.id, today=user_today(user))
