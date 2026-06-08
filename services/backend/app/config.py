"""LeaseFlow orchestrator config. Read once, treat as immutable."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _s(name: str, default: str) -> str:
    v = os.environ.get(name)
    return v if v is not None and v != "" else default


def _i(name: str, default: int) -> int:
    v = os.environ.get(name)
    return int(v) if v is not None and v != "" else default


def _f(name: str, default: float) -> float:
    v = os.environ.get(name)
    return float(v) if v is not None and v != "" else default


def _b(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None or v == "":
        return default
    return v.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Config:
    # ---- Supabase ----
    supabase_url: str = field(default_factory=lambda: _s("SUPABASE_URL", ""))
    supabase_service_key: str = field(default_factory=lambda: _s("SUPABASE_SERVICE_KEY", ""))
    supabase_anon_key: str = field(default_factory=lambda: _s("SUPABASE_ANON_KEY", ""))

    # ---- Storage ----
    storage_bucket: str = field(default_factory=lambda: _s("LEASEFLOW_BUCKET", "loan-documents"))
    signed_url_ttl_s: int = field(default_factory=lambda: _i("SIGNED_URL_TTL_S", 300))

    # ---- MiniMax LLM (OpenAI-compatible) ----
    llm_base_url: str = field(default_factory=lambda: _s("LLM_BASE_URL", "https://api.minimax.io/v1"))
    llm_api_key: str = field(default_factory=lambda: _s("MINIMAX_API_KEY", ""))
    llm_model: str = field(default_factory=lambda: _s("LLM_MODEL", "MiniMax-M2.7"))
    llm_timeout_s: int = field(default_factory=lambda: _i("LLM_TIMEOUT_S", 120))
    llm_max_retries: int = field(default_factory=lambda: _i("LLM_MAX_RETRIES", 3))
    llm_temperature: float = field(default_factory=lambda: _f("LLM_TEMPERATURE", 0.2))

    # ---- Google Maps reviews agent (Apify) ----
    apify_token: str = field(default_factory=lambda: _s("APIFY_TOKEN", ""))
    apify_base_url: str = field(default_factory=lambda: _s("APIFY_BASE_URL", "https://api.apify.com/v2"))
    apify_timeout_s: int = field(default_factory=lambda: _i("APIFY_TIMEOUT_S", 180))
    apify_places_actor_id: str = field(default_factory=lambda: _s("APIFY_PLACES_ACTOR_ID", "compass/crawler-google-places"))
    apify_reviews_actor_id: str = field(default_factory=lambda: _s("APIFY_REVIEWS_ACTOR_ID", "compass/google-maps-reviews-scraper"))
    google_reviews_location_query: str = field(default_factory=lambda: _s("GOOGLE_REVIEWS_LOCATION_QUERY", "Saudi Arabia"))
    google_reviews_country_code: str = field(default_factory=lambda: _s("GOOGLE_REVIEWS_COUNTRY_CODE", "sa"))
    google_reviews_language: str = field(default_factory=lambda: _s("GOOGLE_REVIEWS_LANGUAGE", "en"))
    google_reviews_max_places: int = field(default_factory=lambda: _i("GOOGLE_REVIEWS_MAX_PLACES", 3))
    google_reviews_max_reviews: int = field(default_factory=lambda: _i("GOOGLE_REVIEWS_MAX_REVIEWS", 20))

    # ---- Analyst service (existing POS/financial agent) ----
    analyst_api_url: str = field(default_factory=lambda: _s("ANALYST_API_URL", "http://analyst:8080"))
    analyst_api_key: str = field(default_factory=lambda: _s("ANALYST_API_KEY", ""))
    analyst_poll_interval_s: float = field(default_factory=lambda: _f("ANALYST_POLL_INTERVAL_S", 5.0))
    analyst_timeout_s: int = field(default_factory=lambda: _i("ANALYST_TIMEOUT_S", 1800))

    # ---- Orchestrator ----
    decision_mode: str = field(default_factory=lambda: _s("DECISION_MODE", "guardrail"))  # guardrail | llm_primary
    pipeline_concurrency: int = field(default_factory=lambda: _i("PIPELINE_CONCURRENCY", 4))
    dim_task_timeout_s: int = field(default_factory=lambda: _i("DIM_TASK_TIMEOUT_S", 1800))

    # ---- Risk snapshot scheduler ----
    risk_snapshot_interval_s: int = field(default_factory=lambda: _i("RISK_SNAPSHOT_INTERVAL_S", 1800))
    risk_snapshot_on_startup: bool = field(default_factory=lambda: _b("RISK_SNAPSHOT_ON_STARTUP", True))

    # ---- Dev fixtures ----
    dev_fixtures_enabled: bool = field(default_factory=lambda: _b("LEASEFLOW_DEV_FIXTURES", False))

    # ---- Demo replay mode ----
    # When true, /analyze/start short-circuits for known demo merchant emails
    # and replays a previously-computed decision (see DEMO_TEMPLATES in
    # orchestrator.py). Real upload + classification still run; only the
    # extraction + dims + synthesis phases are replaced with a paced replay
    # of cached data. Off in prod.
    demo_mode: bool = field(default_factory=lambda: _b("DEMO_MODE", False))

    # ---- Notifications ----
    resend_api_key: str = field(default_factory=lambda: _s("RESEND_API_KEY", ""))
    notifications_from: str = field(default_factory=lambda: _s("NOTIFICATIONS_FROM", "LeaseFlow <no-reply@leaseflow.demo>"))
    notifications_enabled: bool = field(default_factory=lambda: _b("NOTIFICATIONS_ENABLED", True))

    # ---- Stream Payments (stream.sa) ----
    stream_base_url: str = field(default_factory=lambda: _s("STREAM_BASE_URL", "https://stream-app-service.streampay.sa"))
    stream_api_key: str = field(default_factory=lambda: _s("STREAM_API_KEY", ""))
    stream_api_secret: str = field(default_factory=lambda: _s("STREAM_API_SECRET", ""))
    stream_x_api_key: str = field(default_factory=lambda: _s("STREAM_X_API_KEY", ""))
    stream_webhook_secret: str = field(default_factory=lambda: _s("STREAM_WEBHOOK_SECRET", ""))
    stream_timeout_s: int = field(default_factory=lambda: _i("STREAM_TIMEOUT_S", 15))
    stream_link_expiry_days: int = field(default_factory=lambda: _i("STREAM_LINK_EXPIRY_DAYS", 30))
    # Sandbox mode forces consumer phone_number to match the org-owner's phone.
    # Set this to your Stream-registered phone in sandbox; leave empty in prod.
    stream_sandbox_phone: str = field(default_factory=lambda: _s("STREAM_SANDBOX_PHONE", ""))
    # Default consumer type: INDIVIDUAL skips the address + vat_number requirement
    # Stream enforces for BUSINESS consumers. Flip to BUSINESS in production.
    stream_consumer_type: str = field(default_factory=lambda: _s("STREAM_CONSUMER_TYPE", "INDIVIDUAL"))
    stream_default_country: str = field(default_factory=lambda: _s("STREAM_DEFAULT_COUNTRY", "SA"))
    stream_default_city: str = field(default_factory=lambda: _s("STREAM_DEFAULT_CITY", "Riyadh"))

    # ---- Service ----
    bind_host: str = field(default_factory=lambda: _s("BIND_HOST", "0.0.0.0"))
    bind_port: int = field(default_factory=lambda: _i("BIND_PORT", 8000))
    cors_origins: str = field(default_factory=lambda: _s("CORS_ORIGINS", "*"))

    # ---- Logging ----
    log_level: str = field(default_factory=lambda: _s("LOG_LEVEL", "INFO"))
    env: str = field(default_factory=lambda: _s("ENV", "development"))

    def require(self) -> None:
        """Fail fast on boot if critical secrets are missing."""
        missing = []
        if not self.supabase_url:
            missing.append("SUPABASE_URL")
        if not self.supabase_service_key:
            missing.append("SUPABASE_SERVICE_KEY")
        if not self.llm_api_key:
            missing.append("MINIMAX_API_KEY")
        if missing:
            raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")


CONFIG = Config()
