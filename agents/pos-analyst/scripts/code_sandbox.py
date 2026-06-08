"""Spawn isolated sibling Docker containers to run agent-authored Python.

We mount the host docker socket into the API container and shell out to
`docker run` for each step. This is "sibling containers" — NOT
Docker-in-Docker — and is the supported isolation pattern when the host runs
a real Docker daemon (which is why we deploy on a Vast.ai VM, not a standard
Vast container).

Each step:
  - read-only root fs
  - --network none   (no exfiltration, no surprise egress)
  - --user 65534:65534 (nobody) inside the container
  - --cap-drop ALL, --security-opt no-new-privileges, --pids-limit
  - cpu + memory + tmpfs limits
  - input mounted read-only at /in
  - private scratch mount at /scratch
  - kill on wall-clock timeout
  - stdout/stderr captured (truncated for the LLM, full bytes archived to disk)
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import CONFIG
from memory import JobMemory
from models import CodeStepMeta, utcnow_iso

log = logging.getLogger("pos.sandbox")


@dataclass
class SandboxResult:
    step_id: int
    exit_code: int
    stdout: bytes
    stderr: bytes
    stdout_truncated: bool
    stderr_truncated: bool
    wall_seconds: float
    killed_for_timeout: bool
    purpose: str

    def head_tail(self, head_kb: int, tail_kb: int) -> tuple[str, str]:
        return (
            _head_tail_str(self.stdout, head_kb, tail_kb),
            _head_tail_str(self.stderr, head_kb, tail_kb),
        )


def _head_tail_str(data: bytes, head_kb: int, tail_kb: int) -> str:
    head = head_kb * 1024
    tail = tail_kb * 1024
    if len(data) <= head + tail:
        return data.decode("utf-8", errors="replace")
    h = data[:head].decode("utf-8", errors="replace")
    t = data[-tail:].decode("utf-8", errors="replace")
    omitted = len(data) - head - tail
    return f"{h}\n... [{omitted:,} bytes omitted; full output on disk] ...\n{t}"


def _truncate_tail(data: bytes, max_kb: int) -> tuple[bytes, bool]:
    cap = max_kb * 1024
    if len(data) <= cap:
        return data, False
    return data[-cap:], True


class CodeSandbox:
    """Per-job sandbox runner. Hold a reference for the duration of the execute phase."""

    def __init__(self, mem: JobMemory) -> None:
        self.mem = mem
        # Resolve absolute host paths because docker runs on the host's path namespace.
        # When running inside the API container, POS_HOST_WORK_DIR is the host-side path
        # of the same volume mounted at POS_WORK_DIR inside this container.
        api_work = CONFIG.work_dir
        host_work_str = os.environ.get("POS_HOST_WORK_DIR", str(api_work))
        host_work = Path(host_work_str)
        # Map the in-container job dir to its host equivalent.
        rel = mem.job_dir.relative_to(api_work)
        self.host_job_dir = host_work / rel
        self.host_data_dir = self.host_job_dir / "input" / "data"
        self.host_code_steps_dir = self.host_job_dir / "memory" / "code_steps"
        self.docker_bin = shutil.which("docker") or "/usr/bin/docker"

    # -- public ----
    def run(self, step_id: int, code: str, purpose: str) -> SandboxResult:
        # Write the code file first so the container can mount and execute it.
        paths = self.mem.code_step_paths(step_id)
        paths["code"].parent.mkdir(parents=True, exist_ok=True)
        paths["code"].write_text(code, encoding="utf-8")

        # Per-step scratch dir (writable mount).
        scratch_in_container = self.mem.code_steps_dir / f"scratch_{step_id:04d}"
        scratch_in_container.mkdir(parents=True, exist_ok=True)
        host_scratch = self.host_code_steps_dir / f"scratch_{step_id:04d}"

        host_code_path = self.host_code_steps_dir / paths["code"].name
        container_name = f"pos-sbx-{self.mem.job_dir.name}-{step_id:04d}-{uuid.uuid4().hex[:6]}"

        cmd = [
            self.docker_bin, "run",
            "--rm",
            "--name", container_name,
            "--network", "none",
            "--read-only",
            "--user", "65534:65534",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--pids-limit", str(CONFIG.sandbox_pids),
            "--cpus", str(CONFIG.sandbox_cpu),
            "--memory", CONFIG.sandbox_mem,
            "--memory-swap", CONFIG.sandbox_mem,  # disable swap escape
            "--tmpfs", f"/tmp:rw,size={CONFIG.sandbox_tmpfs_mb}m,mode=1777",
            "--tmpfs", "/home/nobody:rw,size=64m,mode=0700,uid=65534,gid=65534",
            "--workdir", "/scratch",
            "-e", "PYTHONUNBUFFERED=1",
            "-e", "MPLBACKEND=Agg",
            "-e", "HOME=/home/nobody",
            "-v", f"{self.host_data_dir}:/in:ro",
            "-v", f"{host_scratch}:/scratch:rw",
            "-v", f"{host_code_path}:/code/step.py:ro",
            CONFIG.sandbox_image,
            "python", "-I", "/code/step.py",
        ]

        log.info("sandbox.run job=%s step=%d image=%s timeout=%ds",
                 self.mem.job_dir.name, step_id, CONFIG.sandbox_image, CONFIG.sandbox_timeout_s)
        started_at = utcnow_iso()
        t0 = time.monotonic()
        killed = False
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=CONFIG.sandbox_timeout_s,
                check=False,
            )
            stdout, stderr, rc = proc.stdout, proc.stderr, proc.returncode
        except subprocess.TimeoutExpired as e:
            killed = True
            # Best-effort kill of the container in case docker run hasn't reaped it.
            subprocess.run([self.docker_bin, "kill", container_name],
                           capture_output=True, check=False)
            stdout = e.stdout or b""
            stderr = (e.stderr or b"") + f"\n[sandbox] killed after {CONFIG.sandbox_timeout_s}s timeout\n".encode()
            rc = 124  # conventional timeout exit code
        wall = time.monotonic() - t0
        ended_at = utcnow_iso()

        stdout_capped, stdout_trunc = _truncate_tail(stdout, CONFIG.sandbox_output_limit_kb)
        stderr_capped, stderr_trunc = _truncate_tail(stderr, CONFIG.sandbox_output_limit_kb)

        meta = CodeStepMeta(
            step_id=step_id,
            started_at=started_at,
            ended_at=ended_at,
            exit_code=rc,
            wall_seconds=round(wall, 3),
            killed_for_timeout=killed,
            stdout_bytes=len(stdout),
            stderr_bytes=len(stderr),
            purpose=purpose,
        )
        # Persist everything for audit / resume.
        self.mem.write_code_step(step_id, code, stdout_capped, stderr_capped, meta)
        # Best-effort scratch cleanup (it lives on the volume; not deleted to
        # preserve any artifact the agent might want to reference).
        return SandboxResult(
            step_id=step_id,
            exit_code=rc,
            stdout=stdout_capped,
            stderr=stderr_capped,
            stdout_truncated=stdout_trunc,
            stderr_truncated=stderr_trunc,
            wall_seconds=round(wall, 3),
            killed_for_timeout=killed,
            purpose=purpose,
        )

    def preflight(self) -> None:
        """Check the sandbox image is present and the docker socket is usable."""
        try:
            r = subprocess.run(
                [self.docker_bin, "image", "inspect", CONFIG.sandbox_image],
                capture_output=True, check=False, timeout=10,
            )
            if r.returncode != 0:
                raise RuntimeError(
                    f"Sandbox image '{CONFIG.sandbox_image}' is not available. "
                    f"Build it with `docker build -f scripts/Dockerfile.sandbox -t {CONFIG.sandbox_image} scripts/`."
                )
        except FileNotFoundError as e:
            raise RuntimeError(f"Docker CLI not found at {self.docker_bin}") from e
        except subprocess.TimeoutExpired as e:
            raise RuntimeError("Docker CLI timed out — is the docker socket mounted?") from e
