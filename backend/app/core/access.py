"""Small prototype boundaries adapted from the old verified implementation."""
import hashlib
import re
import secrets
from fastapi import Header,HTTPException
from app.core.config import settings


def visitor_owner(x_visitor_key: str | None = Header(None)) -> str:
    if not x_visitor_key or not re.fullmatch(r'[a-f0-9]{32,128}',x_visitor_key):
        raise HTTPException(401,'缺少游客访问凭据')
    return hashlib.sha256(x_visitor_key.encode()).hexdigest()


def require_admin(value):
    if not settings.ADMIN_API_KEY:
        raise HTTPException(503,'管理员接口未配置')
    if not value or not secrets.compare_digest(value.encode(),settings.ADMIN_API_KEY.encode()):
        raise HTTPException(401,'管理员凭据无效')


def admin_route(path,method):
    return path.startswith('/api/knowledge') or path.startswith('/api/avatar') and method not in ('GET','HEAD') or path.startswith('/api/analytics') and path not in ('/api/analytics/rate','/api/analytics/checkin','/api/analytics/my-visits')
