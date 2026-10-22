from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.access import require_admin
from app.core.config import get_settings
from app.schemas.response import success
from app.services import demo_service

router = APIRouter(prefix='/api/demo', tags=['offline-demo'])


class FaultRequest(BaseModel):
    fault: Literal['none', 'empty', 'timeout', 'partial']


@router.post('/fault', dependencies=[Depends(require_admin)])
def inject_fault(payload: FaultRequest):
    if not get_settings().demo_mode:
        raise HTTPException(404, '仅演示模式支持故障注入')
    demo_service.fault = payload.fault
    return success({'fault': payload.fault, 'simulated': True, 'scope': 'single-worker'})
