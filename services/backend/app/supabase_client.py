"""Supabase client — service_role singleton. Bypasses RLS."""
from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from .config import CONFIG


@lru_cache(maxsize=1)
def get_client() -> Client:
    """Service-role client. Do NOT expose this beyond the backend."""
    return create_client(CONFIG.supabase_url, CONFIG.supabase_service_key)


def signed_url(storage_path: str, ttl_s: int | None = None) -> str:
    """Return a short-lived signed download URL for a private object."""
    ttl = ttl_s if ttl_s is not None else CONFIG.signed_url_ttl_s
    resp = get_client().storage.from_(CONFIG.storage_bucket).create_signed_url(storage_path, ttl)
    url = resp.get("signedURL") or resp.get("signed_url") or resp.get("signedUrl")
    if not url:
        raise RuntimeError(f"No signed URL in response: {resp!r}")
    return url
