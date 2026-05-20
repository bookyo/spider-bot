"""CDN 上传工具。"""

from __future__ import annotations

import asyncio
import mimetypes
import os
import re
from typing import Optional

import requests

DEFAULT_CDN_UPLOAD_BASE_URL = 'https://cdn.wmdb.tv'


def cdn_upload_base_url() -> str:
    return (os.environ.get('CDN_UPLOAD_BASE_URL') or DEFAULT_CDN_UPLOAD_BASE_URL).rstrip('/')


def is_cdn_public_url(url: str | None) -> bool:
    value = str(url or '').strip()
    if not value:
        return False
    return value.startswith(f'{cdn_upload_base_url()}/api/processed/public/file/')


def cdn_auth_headers() -> dict[str, str]:
    api_key = str(os.environ.get('CDN_UPLOAD_API_KEY') or '').strip()
    api_secret = str(os.environ.get('CDN_UPLOAD_API_SECRET') or '').strip()
    if not api_key or not api_secret:
        raise ValueError('CDN upload credentials are not configured')
    return {
        'X-API-Key': api_key,
        'X-API-Secret': api_secret,
    }


def build_cdn_url(path_or_url: str) -> str:
    value = str(path_or_url or '').strip()
    if re.match(r'^https?://', value):
        return value
    if not value:
        raise ValueError('CDN path/url is empty')
    return f"{cdn_upload_base_url()}{value if value.startswith('/') else f'/{value}'}"


def poster_content_type(content_type: str | None, source_url: str) -> str:
    cleaned = str(content_type or '').strip()
    if cleaned:
        return cleaned.split(';', 1)[0].strip().lower()
    guessed, _ = mimetypes.guess_type(source_url)
    return guessed or 'application/octet-stream'


def poster_extension(source_url: str, content_type: str) -> str:
    guessed, _ = mimetypes.guess_type(source_url)
    if guessed:
        ext = mimetypes.guess_extension(guessed) or ''
        if ext:
            return ext
    ext = mimetypes.guess_extension(content_type or '') or ''
    return ext or '.jpg'


def build_poster_filename(dedup_key: str, source_url: str, content_type: str) -> str:
    safe_key = re.sub(r'[^a-zA-Z0-9._-]+', '-', str(dedup_key or 'poster')).strip('-') or 'poster'
    ext = poster_extension(source_url, content_type)
    return f'{safe_key}{ext}'


def upload_bytes_to_cdn(filename: str, content: bytes, content_type: str, timeout: int = 20) -> str:
    signed_response = requests.post(
        f'{cdn_upload_base_url()}/api/upload/generate-signed-url',
        headers={**cdn_auth_headers(), 'X-Public-Access': 'true'},
        json={
            'filename': filename,
            'contentType': content_type,
            'expiresIn': 3600,
        },
        timeout=timeout,
    )
    signed_response.raise_for_status()
    signed_payload = signed_response.json()

    upload_url = build_cdn_url(str(signed_payload['uploadUrl']))
    upload_response = requests.post(
        upload_url,
        headers={**cdn_auth_headers(), 'X-Public-Access': 'true'},
        files={'file': (filename, content, content_type)},
        timeout=timeout,
    )
    upload_response.raise_for_status()
    upload_payload = upload_response.json()

    public_url = str(upload_payload.get('publicUrl') or '').strip()
    if public_url:
        return public_url
    protected_url = str(upload_payload.get('url') or '').strip()
    if protected_url:
        return protected_url
    raise ValueError(f'CDN upload missing publicUrl/url for {filename}')


async def upload_poster_to_cdn(
    content: bytes,
    source_url: str,
    dedup_key: str,
    content_type: Optional[str] = None,
    timeout: int = 20,
) -> str:
    resolved_type = poster_content_type(content_type, source_url)
    filename = build_poster_filename(dedup_key, source_url, resolved_type)
    return await asyncio.to_thread(
        upload_bytes_to_cdn,
        filename,
        content,
        resolved_type,
        timeout,
    )
