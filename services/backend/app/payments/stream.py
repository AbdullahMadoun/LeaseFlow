"""Stream payment-provider client (streampay.sa).

Wired against Stream App v2 API:
  Base: https://stream-app-service.streampay.sa
  Auth: `x-api-key` = base64(api_key:api_secret)
  Spec: https://stream-app-service.streampay.sa/openapi.json

Entities we touch:
  - Consumer       (= our merchant; Stream stores one per business)
  - Product        (one per loan, RECURRING, price = single installment)
  - Subscription   (one per approved loan; Stream drives the cadence,
                    bills each cycle, fires PAYMENT_SUCCEEDED webhooks)

Webhook signature (per https://docs.streampay.sa/webhooks):
  header value: "t=<unix_ts>,v1=<hex_hmac_sha256(secret, f'{ts}.{body}')>"

The client falls back to no-op stubs when `STREAM_X_API_KEY` is empty so
local dev / CI works without a Stream account.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

import httpx

from ..config import CONFIG

log = logging.getLogger(__name__)

API_PREFIX = "/api/v2"


@dataclass
class StreamConsumer:
    id: str
    name: str
    external_id: str | None = None


@dataclass
class StreamProduct:
    id: str
    name: str
    amount: str
    currency: str
    recurring_interval: str
    recurring_interval_count: int


@dataclass
class StreamSubscription:
    id: str
    status: str
    current_cycle_number: int | None
    current_period_start: str | None
    current_period_end: str | None
    latest_invoice_id: str | None


class StreamClient:
    provider_name = "stream.sa"

    def __init__(
        self,
        *,
        base_url: str,
        x_api_key: str,
        webhook_secret: str,
        timeout_s: int = 15,
    ):
        self.base_url = base_url.rstrip("/")
        self.x_api_key = x_api_key
        self.webhook_secret = webhook_secret
        self.timeout_s = timeout_s

    @property
    def is_live(self) -> bool:
        return bool(self.x_api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.x_api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _post(self, path: str, body: dict) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout_s) as c:
            r = await c.post(self.base_url + path, headers=self._headers(), json=body)
            if r.status_code >= 400:
                raise StreamAPIError(r.status_code, r.text, path=path)
            return r.json() if r.content else {}

    async def _get(self, path: str) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout_s) as c:
            r = await c.get(self.base_url + path, headers=self._headers())
            if r.status_code >= 400:
                raise StreamAPIError(r.status_code, r.text, path=path)
            return r.json() if r.content else {}

    # ---------- Consumers ----------

    async def create_consumer(
        self,
        *,
        name: str,
        external_id: str,
        phone_number: str | None = None,
        email: str | None = None,
        commercial_registration: str | None = None,
        vat_number: str | None = None,
        consumer_type: str = "INDIVIDUAL",
        address_line_1: str | None = None,
        city: str | None = None,
        country: str | None = None,
    ) -> StreamConsumer:
        """Create a Stream consumer.

        INDIVIDUAL: only name + phone + email required.
        BUSINESS  : additionally requires address + vat_number per Stream v2.
        """
        if not self.is_live:
            return StreamConsumer(id=f"stub_consumer_{external_id[:8]}",
                                  name=name, external_id=external_id)
        body: dict[str, Any] = {
            "name": name,
            "external_id": external_id,
            "consumer_type": consumer_type,
        }
        if phone_number: body["phone_number"] = phone_number
        if email: body["email"] = email
        if commercial_registration: body["commercial_registration"] = commercial_registration
        if vat_number: body["vat_number"] = vat_number
        if consumer_type == "BUSINESS":
            body["address"] = {
                "address_line_1": address_line_1 or "N/A",
                "city": city or CONFIG.stream_default_city,
                "country": country or CONFIG.stream_default_country,
            }
        data = await self._post(f"{API_PREFIX}/consumers", body)
        return StreamConsumer(
            id=str(data.get("id", "")),
            name=str(data.get("name", name)),
            external_id=data.get("external_id"),
        )

    async def find_consumer_by_external_id(self, external_id: str) -> StreamConsumer | None:
        if not self.is_live:
            return None
        try:
            data = await self._get(f"{API_PREFIX}/consumers?external_id={external_id}")
        except StreamAPIError:
            return None
        for r in _extract_list(data):
            if r.get("external_id") == external_id:
                return StreamConsumer(id=str(r["id"]), name=str(r.get("name", "")),
                                      external_id=external_id)
        return None

    async def find_consumer_by_email(self, email: str) -> StreamConsumer | None:
        if not self.is_live or not email:
            return None
        try:
            data = await self._get(f"{API_PREFIX}/consumers?email={email}")
        except StreamAPIError:
            return None
        for r in _extract_list(data):
            if (r.get("email") or "").lower() == email.lower():
                return StreamConsumer(id=str(r["id"]), name=str(r.get("name", "")),
                                      external_id=r.get("external_id"))
        return None

    async def get_or_create_consumer(
        self,
        *,
        name: str,
        external_id: str,
        phone_number: str | None = None,
        email: str | None = None,
        commercial_registration: str | None = None,
        vat_number: str | None = None,
        consumer_type: str | None = None,
    ) -> StreamConsumer:
        existing = await self.find_consumer_by_external_id(external_id)
        if existing:
            return existing
        if email:
            existing = await self.find_consumer_by_email(email)
            if existing:
                return existing
        try:
            return await self.create_consumer(
                name=name, external_id=external_id,
                phone_number=phone_number, email=email,
                commercial_registration=commercial_registration,
                vat_number=vat_number,
                consumer_type=consumer_type or CONFIG.stream_consumer_type,
            )
        except StreamAPIError as e:
            # Stream surfaces duplicate-email collisions as 400/DUPLICATE_CONSUMER.
            if email and "DUPLICATE_CONSUMER" in e.body:
                existing = await self.find_consumer_by_email(email)
                if existing:
                    return existing
            raise

    # ---------- Products ----------

    async def create_recurring_product(
        self,
        *,
        name: str,
        amount_sar: float,
        recurring_interval: str,          # WEEK | MONTH | YEAR
        recurring_interval_count: int = 1,
        description: str | None = None,
        currency: str = "SAR",
        is_price_inclusive_of_vat: bool = True,
    ) -> StreamProduct:
        if not self.is_live:
            return StreamProduct(
                id=f"stub_product_{hashlib.sha256(name.encode()).hexdigest()[:12]}",
                name=name, amount=str(amount_sar), currency=currency,
                recurring_interval=recurring_interval,
                recurring_interval_count=recurring_interval_count,
            )
        # `price` / `is_price_*` on ProductCreate are deprecated — use
        # `prices[]` with one inline price per currency.
        body: dict[str, Any] = {
            "name": name,
            "type": "RECURRING",
            "recurring_interval": recurring_interval,
            "recurring_interval_count": recurring_interval_count,
            "prices": [{
                "currency": currency,
                "amount": round(float(amount_sar), 2),
                "is_price_inclusive_of_vat": is_price_inclusive_of_vat,
            }],
        }
        if description: body["description"] = description
        data = await self._post(f"{API_PREFIX}/products", body)
        return StreamProduct(
            id=str(data["id"]),
            name=str(data.get("name", name)),
            amount=str(data.get("price", amount_sar)),
            currency=str(data.get("currency", currency)),
            recurring_interval=str(data.get("recurring_interval", recurring_interval)),
            recurring_interval_count=int(data.get("recurring_interval_count", recurring_interval_count)),
        )

    # ---------- Subscriptions ----------

    async def create_subscription(
        self,
        *,
        product_id: str,
        consumer_id: str,
        period_start: str,                 # ISO date/datetime
        until_cycle_number: int,           # total cycles (= installment count)
        description: str | None = None,
        notify_consumer: bool = True,
        quantity: int = 1,
    ) -> StreamSubscription:
        if not self.is_live:
            return StreamSubscription(
                id=f"stub_sub_{hashlib.sha256(product_id.encode()).hexdigest()[:12]}",
                status="ACTIVE", current_cycle_number=0,
                current_period_start=period_start, current_period_end=None,
                latest_invoice_id=None,
            )
        body: dict[str, Any] = {
            "items": [{"product_id": product_id, "quantity": quantity}],
            "organization_consumer_id": consumer_id,
            "period_start": period_start,
            "until_cycle_number": until_cycle_number,
            "notify_consumer": notify_consumer,
        }
        if description: body["description"] = description
        data = await self._post(f"{API_PREFIX}/subscriptions", body)
        return _subscription_from_dto(data)

    async def get_subscription(self, subscription_id: str) -> StreamSubscription:
        data = await self._get(f"{API_PREFIX}/subscriptions/{subscription_id}")
        return _subscription_from_dto(data)

    # ---------- Invoices / payments (for webhook lookups) ----------

    async def get_invoice(self, invoice_id: str) -> dict:
        return await self._get(f"{API_PREFIX}/invoices/{invoice_id}")

    async def get_payment(self, payment_id: str) -> dict:
        return await self._get(f"{API_PREFIX}/payments/{payment_id}")

    # ---------- Webhook signature verification ----------

    def verify_webhook(self, payload: bytes, signature_header: str | None) -> bool:
        """Verify a Stream webhook signature of the form
        `t=<unix_ts>,v1=<hex_hmac_sha256(secret, f'{ts}.{body}')>`.

        Falls open when no secret is configured (demo default). Tolerates
        missing parts, extra whitespace, and the raw-hex variant some
        providers use for backfills.
        """
        if not self.webhook_secret:
            log.warning("stream webhook signature NOT verified (no secret configured)")
            return True
        if not signature_header:
            return False

        parts = {}
        for seg in signature_header.split(","):
            if "=" in seg:
                k, v = seg.split("=", 1)
                parts[k.strip()] = v.strip()

        ts = parts.get("t")
        sig = parts.get("v1")
        if ts and sig:
            message = f"{ts}.{payload.decode('utf-8', errors='replace')}".encode()
            expected = hmac.new(self.webhook_secret.encode(), message, hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected, sig)

        # Fallback: header is just the raw hex digest over the body
        expected = hmac.new(self.webhook_secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature_header.strip())


class StreamAPIError(RuntimeError):
    def __init__(self, status_code: int, body: str, *, path: str = ""):
        super().__init__(f"stream {path} {status_code}: {body[:500]}")
        self.status_code = status_code
        self.body = body
        self.path = path


def _extract_list(data: Any) -> list[dict]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "items", "results"):
            v = data.get(key)
            if isinstance(v, list):
                return v
    return []


def _subscription_from_dto(data: dict) -> StreamSubscription:
    latest = data.get("latest_invoice") or {}
    return StreamSubscription(
        id=str(data.get("id", "")),
        status=str(data.get("status", "UNKNOWN")),
        current_cycle_number=_int_or_none(data.get("current_cycle_number")),
        current_period_start=data.get("current_period_start"),
        current_period_end=data.get("current_period_end"),
        latest_invoice_id=str(latest.get("id")) if latest.get("id") else data.get("latest_invoice_id"),
    )


def _int_or_none(v: Any) -> int | None:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _compute_x_api_key() -> str:
    if CONFIG.stream_x_api_key:
        return CONFIG.stream_x_api_key
    if CONFIG.stream_api_key and CONFIG.stream_api_secret:
        raw = f"{CONFIG.stream_api_key}:{CONFIG.stream_api_secret}".encode()
        return base64.b64encode(raw).decode()
    return ""


@lru_cache(maxsize=1)
def get_stream_client() -> StreamClient:
    return StreamClient(
        base_url=CONFIG.stream_base_url,
        x_api_key=_compute_x_api_key(),
        webhook_secret=CONFIG.stream_webhook_secret,
        timeout_s=CONFIG.stream_timeout_s,
    )
