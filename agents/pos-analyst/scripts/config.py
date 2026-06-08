"""Centralised configuration. Read once, treat as immutable."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env_str(name: str, default: str) -> str:
    v = os.environ.get(name)
    return v if v is not None and v != "" else default


def _env_int(name: str, default: int) -> int:
    v = os.environ.get(name)
    return int(v) if v is not None and v != "" else default


def _env_float(name: str, default: float) -> float:
    v = os.environ.get(name)
    return float(v) if v is not None and v != "" else default


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None or v == "":
        return default
    return v.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Config:
    # ---- model ----
    model_id: str = field(default_factory=lambda: _env_str("POS_MODEL_ID", "MiniMax-M2.7"))
    report_model_id: str = field(default_factory=lambda: _env_str("POS_REPORT_MODEL_ID", "MiniMax-M2.7"))
    api_base: str = field(default_factory=lambda: _env_str("POS_LLM_BASE_URL", "https://api.minimax.io/v1"))
    api_key: str = field(default_factory=lambda: _env_str("MINIMAX_API_KEY", ""))
    request_timeout_s: int = field(default_factory=lambda: _env_int("POS_LLM_TIMEOUT", 180))
    max_retries: int = field(default_factory=lambda: _env_int("POS_LLM_RETRIES", 4))
    temperature: float = field(default_factory=lambda: _env_float("POS_LLM_TEMP", 0.2))

    # ---- agent loop ----
    max_code_steps: int = field(default_factory=lambda: _env_int("POS_MAX_CODE_STEPS", 80))
    max_validation_rounds: int = field(default_factory=lambda: _env_int("POS_MAX_VALIDATION_ROUNDS", 2))
    findings_window: int = field(default_factory=lambda: _env_int("POS_FINDINGS_WINDOW", 20))
    trace_window: int = field(default_factory=lambda: _env_int("POS_TRACE_WINDOW", 10))
    default_target_minutes: int = field(default_factory=lambda: _env_int("POS_DEFAULT_TARGET_MINUTES", 5))
    default_hard_cap_minutes: int = field(default_factory=lambda: _env_int("POS_DEFAULT_HARD_CAP_MINUTES", 30))

    # ---- sandbox ----
    sandbox_image: str = field(default_factory=lambda: _env_str("POS_SANDBOX_IMAGE", "pos-analyst-sandbox:latest"))
    sandbox_cpu: float = field(default_factory=lambda: _env_float("POS_SANDBOX_CPUS", 2.0))
    sandbox_mem: str = field(default_factory=lambda: _env_str("POS_SANDBOX_MEM", "2g"))
    sandbox_pids: int = field(default_factory=lambda: _env_int("POS_SANDBOX_PIDS", 256))
    sandbox_timeout_s: int = field(default_factory=lambda: _env_int("POS_SANDBOX_TIMEOUT", 90))
    sandbox_output_limit_kb: int = field(default_factory=lambda: _env_int("POS_SANDBOX_OUTPUT_LIMIT_KB", 256))
    sandbox_output_head_kb: int = field(default_factory=lambda: _env_int("POS_SANDBOX_OUTPUT_HEAD_KB", 8))
    sandbox_output_tail_kb: int = field(default_factory=lambda: _env_int("POS_SANDBOX_OUTPUT_TAIL_KB", 8))
    sandbox_tmpfs_mb: int = field(default_factory=lambda: _env_int("POS_SANDBOX_TMPFS_MB", 256))

    # ---- paths ----
    work_dir: Path = field(default_factory=lambda: Path(_env_str("POS_WORK_DIR", "/var/pos-analyst")))

    # ---- service ----
    api_key_required: str = field(default_factory=lambda: _env_str("POS_API_KEY", ""))
    bind_host: str = field(default_factory=lambda: _env_str("POS_BIND_HOST", "0.0.0.0"))
    bind_port: int = field(default_factory=lambda: _env_int("POS_BIND_PORT", 8080))
    worker_concurrency: int = field(default_factory=lambda: _env_int("POS_WORKER_CONCURRENCY", 1))

    # ---- web search ----
    web_search_enabled: bool = field(default_factory=lambda: _env_bool("POS_WEB_SEARCH_ENABLED", False))
    web_search_provider: str = field(default_factory=lambda: _env_str("POS_WEB_SEARCH_PROVIDER", "tavily"))
    web_search_api_key: str = field(default_factory=lambda: _env_str("TAVILY_API_KEY", ""))
    web_search_max_per_job: int = field(default_factory=lambda: _env_int("POS_WEB_SEARCH_MAX_PER_JOB", 6))

    # ---- logging ----
    log_level: str = field(default_factory=lambda: _env_str("POS_LOG_LEVEL", "INFO"))

    @property
    def jobs_dir(self) -> Path:
        return self.work_dir / "jobs"

    def job_dir(self, job_id: str) -> Path:
        return self.jobs_dir / job_id


CONFIG = Config()


def ensure_dirs() -> None:
    """Create top-level directories on first boot."""
    CONFIG.jobs_dir.mkdir(parents=True, exist_ok=True)
