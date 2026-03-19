from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.dashboard import DashboardOverviewRead
from app.services.dashboard_service import get_dashboard_overview

router = APIRouter(prefix="/dashboards", tags=["dashboards"])


@router.get("/", response_model=DashboardOverviewRead)
def get_dashboard(db: Session = Depends(get_db)):
    return get_dashboard_overview(db)
