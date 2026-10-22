"""Small prototype boundary: admin secret and per-browser visitor capability."""
import hashlib
import re
import secrets

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db


def require_admin(x_admin_key: str | None = Header(default=None)):
    expected = get_settings().admin_api_key
    if not expected:
        raise HTTPException(503, "管理员接口未配置")
    if not x_admin_key or not secrets.compare_digest(x_admin_key.encode(), expected.encode()):
        raise HTTPException(401, "管理员凭据无效")


def visitor_fingerprint(x_visitor_key: str | None = Header(default=None)) -> str:
    if not x_visitor_key or not re.fullmatch(r"[a-f0-9]{32,128}", x_visitor_key):
        raise HTTPException(401, "缺少游客访问凭据")
    return hashlib.sha256(x_visitor_key.encode()).hexdigest()


def get_visitor_db(owner: str = Depends(visitor_fingerprint), db: Session = Depends(get_db)):
    db.info["visitor"] = owner
    return db
