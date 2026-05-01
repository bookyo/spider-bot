"""Admin API Key 认证"""

import os

from fastapi import Header, HTTPException


def get_admin_api_key() -> str:
    return os.environ.get('ADMIN_API_KEY', '').strip()


async def require_admin_api_key(x_api_key: str | None = Header(default=None)) -> str:
    expected = get_admin_api_key()
    if not expected:
        raise HTTPException(status_code=503, detail='服务端未配置 ADMIN_API_KEY')
    if not x_api_key or x_api_key != expected:
        raise HTTPException(status_code=401, detail='无效的 API Key')
    return x_api_key
