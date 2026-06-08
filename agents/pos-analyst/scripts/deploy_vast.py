"""End-to-end Vast.ai VM deploy for the POS Financial Analyst stack.

Wraps `vast_probe.py` with a single command that:
  1. Picks (or accepts) a VM-capable offer.
  2. Creates a VM template (KVM ubuntu_terminal) if needed.
  3. Rents the instance.
  4. Waits for SSH.
  5. rsyncs the scripts/ directory to the VM.
  6. Installs Docker on the VM (if missing).
  7. Builds the sandbox image and brings up docker-compose.
  8. Verifies /health.

Usage:
    python deploy_vast.py up \\
        --api-key $VAST_API_KEY \\
        --minimax-key $MINIMAX_API_KEY \\
        --pos-api-key $POS_API_KEY \\
        --gpu-not-required \\
        --offer-id 1234567

If --offer-id is omitted, the script uses vast_probe to surface candidates and
pick the cheapest verified VM-capable host above the reliability threshold.

Why a VM and not a standard Vast container: the workload runs Docker on the
host (api container + per-step sibling sandbox containers). Standard Vast
instances are themselves containers and explicitly do not support DinD; the
documented path for this is a VM. See references/vast-workflow.md.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import shlex
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBE = HERE / "vast_probe.py"
VAST_API_BASE = "https://console.vast.ai/api/v0"


def _bundles_search(api_key: str, payload: dict) -> list[dict]:
    """Direct POST /bundles/ so we can filter on fields the probe CLI doesn't expose
    (inet_up, inet_down, reliability2)."""
    req = urllib.request.Request(
        f"{VAST_API_BASE}/bundles/",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Vast /bundles/ failed: HTTP {e.code}\n{e.read().decode()[:500]}") from e
    return data.get("offers") or []


def _rank_for_backend(offers: list[dict]) -> list[dict]:
    """Score: symmetric bandwidth first, then price. A backend API box cares
    about the slower direction (the floor), not peak one-way throughput."""
    def worst(o: dict) -> float:
        return min(float(o.get("inet_up") or 0), float(o.get("inet_down") or 0))

    # Keep only offers whose weaker leg is at least 1 Gbps; sort cheapest-first
    # within that pool so we don't pay $5/hr when $0.10/hr buys 3 Gbps.
    filtered = [o for o in offers if worst(o) >= 1000]
    filtered.sort(key=lambda o: (o.get("dph_total") or 1e9))
    return filtered


def _probe(args: list[str]):
    """Invoke vast_probe.py and parse its JSON output. Returns dict OR list."""
    if not args:
        cmd = [sys.executable, str(PROBE)]
    else:
        subcommand = args[0]
        remainder = args[1:]
        globals_first: list[str] = []
        sub_args: list[str] = []
        i = 0
        while i < len(remainder):
            token = remainder[i]
            if token in {"--api-key", "--base-url", "--timeout"} and i + 1 < len(remainder):
                globals_first.extend([token, remainder[i + 1]])
                i += 2
                continue
            globals_first.append(token) if token.startswith("--") and "=" in token and token.split("=", 1)[0] in {"--api-key", "--base-url", "--timeout"} else sub_args.append(token)
            i += 1
        cmd = [sys.executable, str(PROBE), *globals_first, subcommand, *sub_args]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"vast_probe failed: {' '.join(cmd)}")
    out = proc.stdout.strip()
    if not out:
        return {}
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {"raw": out}


def _dig(obj, *keys):
    """Look for the first present key in a nested dict; returns None if absent."""
    if not isinstance(obj, dict):
        return None
    for k in keys:
        if k in obj and obj[k] is not None:
            return obj[k]
    for v in obj.values():
        if isinstance(v, dict):
            found = _dig(v, *keys)
            if found is not None:
                return found
    return None


def _ssh(host: str, port: int, key: Path, command: str, *, check: bool = True) -> subprocess.CompletedProcess:
    cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ConnectTimeout=15",
        "-i", str(key),
        "-p", str(port),
        f"root@{host}",
        command,
    ]
    print(f"[ssh] {command}")
    return subprocess.run(cmd, check=check)


def _scp_dir(host: str, port: int, key: Path, local: Path, remote: str) -> None:
    rsync_bin = shutil.which("rsync")
    if rsync_bin:
        cmd = [
            rsync_bin, "-az", "--delete",
            "-e", f"ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p {port} -i {key}",
            f"{local}/",
            f"root@{host}:{remote}/",
        ]
        print(f"[rsync] {' '.join(shlex.quote(c) for c in cmd)}")
        subprocess.run(cmd, check=True)
        return

    scp_bin = shutil.which("scp")
    if not scp_bin:
        raise SystemExit("Neither rsync nor scp is available locally; cannot upload deployment files")

    with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tmp:
        archive_path = Path(tmp.name)
    try:
        with tarfile.open(archive_path, "w") as tar:
            for item in local.iterdir():
                tar.add(item, arcname=item.name)
        remote_tar = f"/tmp/{archive_path.name}"
        scp_cmd = [
            scp_bin,
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-i", str(key),
            "-P", str(port),
            str(archive_path),
            f"root@{host}:{remote_tar}",
        ]
        print(f"[scp] {' '.join(shlex.quote(c) for c in scp_cmd)}")
        subprocess.run(scp_cmd, check=True)
        _ssh(host, port, key, f"mkdir -p {remote} && tar -xf {remote_tar} -C {remote} && rm -f {remote_tar}")
    finally:
        archive_path.unlink(missing_ok=True)


def cmd_up(args: argparse.Namespace) -> None:
    api_key = args.api_key or os.environ.get("VAST_API_KEY", "")
    if not api_key:
        raise SystemExit("VAST_API_KEY is required")
    minimax_key = args.minimax_key or os.environ.get("MINIMAX_API_KEY", "")
    if not minimax_key:
        raise SystemExit("MINIMAX_API_KEY is required")
    pos_api_key = args.pos_api_key or os.environ.get("POS_API_KEY", "")

    ssh_key = Path(args.ssh_key).expanduser()
    pub_key = ssh_key.with_suffix(ssh_key.suffix + ".pub") if ssh_key.suffix else Path(str(ssh_key) + ".pub")

    if not ssh_key.exists() or not pub_key.exists():
        raise SystemExit(
            f"SSH key not found at {ssh_key}.\n"
            f"Generate one with: ssh-keygen -t ed25519 -f {ssh_key} -N ''"
        )

    # ---- 1. register ssh key if missing ----
    public_key_text = pub_key.read_text(encoding="utf-8").strip()
    existing_keys = _probe(["ssh-keys", "--api-key", api_key])
    key_exists = any(
        isinstance(item, dict) and str(item.get("public_key", "")).strip() == public_key_text
        for item in (existing_keys if isinstance(existing_keys, list) else [])
    )
    if key_exists:
        print("[ssh] public key already registered on Vast account")
    else:
        _probe(["register-ssh-key", "--api-key", api_key, "--public-key-file", str(pub_key)])

    # ---- 2. create or reuse template ----
    template_hash = args.template_hash
    if not template_hash:
        tpl = _probe([
            "create-template",
            "--api-key", api_key,
            "--name", args.template_name,
            "--image", "docker.io/vastai/kvm",
            "--tag", "ubuntu_terminal",
            "--runtype", "ssh",
            "--ssh-direct",
            "--use-ssh",
            "--recommended-disk-space", str(args.disk_gb),
            "--extra-filter-json", '{"vms_enabled":{"eq":true}}',
        ])
        template_hash = _dig(tpl, "hash_id", "template_hash_id")
        if not template_hash:
            raise SystemExit(f"create-template did not return a hash_id: {tpl}")
        print(f"[template] hash_id={template_hash}")

    # ---- 3. pick offer (bandwidth-first) ----
    offer_id = args.offer_id
    if not offer_id:
        payload: dict = {
            "rentable": {"eq": True},
            "rented": {"eq": False},
            "vms_enabled": {"eq": True},
            "reliability2": {"gte": args.min_reliability},
            "cpu_ram": {"gte": args.min_cpu_ram_mb},
            "cpu_cores": {"gte": args.min_cpu_cores},
            "disk_space": {"gte": args.disk_gb},
            "inet_up": {"gte": args.min_net_up_mbps},
            "inet_down": {"gte": args.min_net_down_mbps},
            "type": "ondemand",
            "limit": 80,
        }
        if args.verified_only:
            payload["verified"] = {"eq": True}
        if args.num_gpus > 0:
            payload["num_gpus"] = {"gte": args.num_gpus}

        offers = _bundles_search(api_key, payload)
        offers = _rank_for_backend(offers)
        if not offers:
            raise SystemExit(
                f"no VM-capable offers matched: ≥{args.min_net_up_mbps} Mbps ↑, "
                f"≥{args.min_net_down_mbps} Mbps ↓, rel≥{args.min_reliability}. "
                f"Relax --min-net-up-mbps / --min-net-down-mbps or --min-reliability."
            )
        top = offers[:5]
        print(f"[offer] {len(offers)} candidates. top 5 by price-given-bandwidth:")
        for o in top:
            print(f"        id={o['id']:<10} ${o.get('dph_total'):.4f}/hr  "
                  f"↑{int(o.get('inet_up') or 0)}↓{int(o.get('inet_down') or 0)} Mbps  "
                  f"rel={(o.get('reliability2') or 0):.3f}  "
                  f"{o.get('cpu_cores')}c/{(o.get('cpu_ram') or 0)//1024}GB  "
                  f"storage=${o.get('storage_cost') or 0:.2f}/GB-mo  "
                  f"bw=${o.get('inet_up_cost') or 0:.4f}/GB")
        offer_id = top[0]["id"]
        print(f"[offer] picked id={offer_id}")

    # ---- 4. rent ----
    inst = _probe([
        "create-instance",
        "--api-key", api_key,
        "--offer-id", str(offer_id),
        "--template-hash-id", template_hash,
        "--disk-gb", str(args.disk_gb),
    ])
    instance_id = _dig(inst, "new_contract", "instance_id", "id")
    if not instance_id:
        raise SystemExit(f"create-instance did not return an id: {inst}")
    print(f"[instance] id={instance_id}")

    # ---- 5. wait ----
    waited = _probe([
        "wait-instance",
        "--api-key", api_key,
        "--instance-id", str(instance_id),
        "--timeout-seconds", str(args.boot_timeout),
        "--require-ssh",
    ])
    host = waited.get("ssh_host") or waited.get("public_ipaddr") if isinstance(waited, dict) else None
    port_raw = (waited.get("ssh_port") if isinstance(waited, dict) else None) \
        or (waited.get("ssh_direct_port") if isinstance(waited, dict) else None) \
        or 22
    port = int(port_raw)
    if not host:
        raise SystemExit(f"wait-instance returned no SSH host: {waited}")
    print(f"[ssh] host={host} port={port}")

    # Small extra grace period for sshd to fully accept commands.
    time.sleep(5)

    # ---- 6. ensure docker on VM ----
    _ssh(host, port, ssh_key, "command -v docker >/dev/null 2>&1 || "
                              "(curl -fsSL https://get.docker.com | sh)")
    _ssh(host, port, ssh_key, "systemctl enable --now docker")

    # ---- 7. push code ----
    remote_dir = "/opt/pos-analyst"
    _ssh(host, port, ssh_key, f"mkdir -p {remote_dir}")
    _scp_dir(host, port, ssh_key, HERE, remote_dir)
    _ssh(host, port, ssh_key, "mkdir -p /var/pos-analyst/jobs")

    # ---- 8. write env file ----
    env_lines = [
        f"MINIMAX_API_KEY={minimax_key}",
        f"POS_API_KEY={pos_api_key}",
        f"POS_MODEL_ID={args.model_id}",
        f"POS_REPORT_MODEL_ID={args.report_model_id or args.model_id}",
        f"POS_HOST_WORK_DIR=/var/pos-analyst",
        f"POS_BIND_PORT={args.api_port}",
        f"POS_WORKER_CONCURRENCY={args.workers}",
    ]
    env_blob = "\n".join(env_lines).replace("'", "'\\''")
    _ssh(host, port, ssh_key, f"cat > {remote_dir}/.env <<'EOF'\n{env_blob}\nEOF")

    # ---- 9. build sandbox image + bring up compose ----
    _ssh(host, port, ssh_key, f"cd {remote_dir} && docker build -f Dockerfile.sandbox -t pos-analyst-sandbox:latest .")
    _ssh(host, port, ssh_key, f"cd {remote_dir} && docker compose --env-file .env up -d --build")

    # ---- 10. verify ----
    print("[verify] polling /health ...")
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        rc = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
             "-i", str(ssh_key), "-p", str(port), f"root@{host}",
             f"curl -fsS http://127.0.0.1:{args.api_port}/health"],
            capture_output=True, text=True,
        )
        if rc.returncode == 0:
            print(f"[verify] OK: {rc.stdout}")
            break
        time.sleep(5)
    else:
        raise SystemExit("api never became healthy on the VM")

    print()
    print("=== DEPLOYED ===")
    print(f"instance_id    : {instance_id}")
    print(f"ssh            : ssh -i {ssh_key} -p {port} root@{host}")
    print(f"api (on host)  : http://{host}:{args.api_port}")
    print("Submit a job:")
    print(f"  curl -H 'X-API-Key: {pos_api_key or '<no-auth>'}' -F 'context=...' \\")
    print(f"       -F 'files=@my_data.csv' http://{host}:{args.api_port}/jobs")


def cmd_scout(args: argparse.Namespace) -> None:
    """Preview offers that match the bandwidth/backend profile without renting."""
    api_key = args.api_key or os.environ.get("VAST_API_KEY", "")
    if not api_key:
        key_file = Path("~/.config/vastai/vast_api_key").expanduser()
        if key_file.exists():
            api_key = key_file.read_text().strip()
    if not api_key:
        raise SystemExit("VAST_API_KEY is required (or ~/.config/vastai/vast_api_key)")

    payload: dict = {
        "rentable": {"eq": True}, "rented": {"eq": False},
        "vms_enabled": {"eq": True},
        "reliability2": {"gte": args.min_reliability},
        "cpu_ram": {"gte": args.min_cpu_ram_mb},
        "cpu_cores": {"gte": args.min_cpu_cores},
        "disk_space": {"gte": args.disk_gb},
        "inet_up": {"gte": args.min_net_up_mbps},
        "inet_down": {"gte": args.min_net_down_mbps},
        "type": "ondemand",
        "limit": 80,
    }
    if args.verified_only:
        payload["verified"] = {"eq": True}
    offers = _rank_for_backend(_bundles_search(api_key, payload))
    print(f"Found {len(offers)} matching offers (ranked by price-given-bandwidth).\n")
    print(f"{'id':<10} {'$/hr':<8} {'↑Mbps':<7} {'↓Mbps':<7} {'rel':<6} {'cpu':<5} {'ram':<6} {'disk':<7} {'storage':<8} {'bw↑$/GB'}")
    print("-" * 95)
    for o in offers[:args.limit]:
        print(f"{o.get('id'):<10} "
              f"${o.get('dph_total'):.4f} "
              f"{int(o.get('inet_up') or 0):<7} "
              f"{int(o.get('inet_down') or 0):<7} "
              f"{(o.get('reliability2') or 0):.3f}  "
              f"{o.get('cpu_cores')}c  "
              f"{(o.get('cpu_ram') or 0)//1024}GB  "
              f"{int(o.get('disk_space') or 0)}GB  "
              f"${o.get('storage_cost') or 0:.3f}  "
              f"${o.get('inet_up_cost') or 0:.5f}")


def cmd_down(args: argparse.Namespace) -> None:
    api_key = args.api_key or os.environ.get("VAST_API_KEY", "")
    if not api_key:
        raise SystemExit("VAST_API_KEY is required")
    if not args.instance_id:
        raise SystemExit("--instance-id is required")
    _probe(["destroy-instance", "--api-key", api_key, "--instance-id", str(args.instance_id)])
    print(f"[destroyed] instance {args.instance_id}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    up = sub.add_parser("up", help="provision a VM and bring up the stack")
    up.add_argument("--api-key", help="Vast.ai API key (or $VAST_API_KEY)")
    up.add_argument("--minimax-key", help="MiniMax API key (or $MINIMAX_API_KEY)")
    up.add_argument("--pos-api-key", default="", help="API key clients must present (or $POS_API_KEY)")
    up.add_argument("--ssh-key", default="~/.ssh/id_ed25519", help="path to your private SSH key")
    up.add_argument("--template-name", default="pos-analyst-vm")
    up.add_argument("--template-hash", default="", help="reuse an existing template hash")
    up.add_argument("--offer-id", default="", help="skip search and use this offer id")
    up.add_argument("--min-reliability", type=float, default=0.98)
    up.add_argument("--num-gpus", type=int, default=0,
                    help="Minimum GPUs on the host. The analyst itself is CPU-only; raise this only if you plan to colocate GPU workloads on the same VM.")
    up.add_argument("--verified-only", action=argparse.BooleanOptionalAction, default=True,
                    help="Require host to be Vast-verified. Disable only for dev/test.")
    up.add_argument("--min-net-up-mbps", type=int, default=1000,
                    help="Minimum upstream bandwidth floor (default 1 Gbps). This VM is a backend API — don't skimp.")
    up.add_argument("--min-net-down-mbps", type=int, default=1000,
                    help="Minimum downstream bandwidth floor (default 1 Gbps).")
    up.add_argument("--min-cpu-cores", type=int, default=16,
                    help="Minimum CPU cores (default 16 — enough for concurrent jobs + colocated APIs).")
    up.add_argument("--min-cpu-ram-mb", type=int, default=32000,
                    help="Minimum host RAM in MB (default 32 GB).")
    up.add_argument("--disk-gb", type=int, default=80)
    up.add_argument("--boot-timeout", type=int, default=900)
    up.add_argument("--model-id", default="MiniMax-M2.7")
    up.add_argument("--report-model-id", default="")
    up.add_argument("--api-port", type=int, default=8080)
    up.add_argument("--workers", type=int, default=2)
    up.set_defaults(func=cmd_up)

    scout = sub.add_parser("scout", help="preview bandwidth-ranked offers without renting")
    scout.add_argument("--api-key", help="Vast.ai API key (or $VAST_API_KEY)")
    scout.add_argument("--min-reliability", type=float, default=0.98)
    scout.add_argument("--min-net-up-mbps", type=int, default=1000)
    scout.add_argument("--min-net-down-mbps", type=int, default=1000)
    scout.add_argument("--min-cpu-cores", type=int, default=16)
    scout.add_argument("--min-cpu-ram-mb", type=int, default=32000)
    scout.add_argument("--disk-gb", type=int, default=80)
    scout.add_argument("--verified-only", action=argparse.BooleanOptionalAction, default=True)
    scout.add_argument("--limit", type=int, default=15)
    scout.set_defaults(func=cmd_scout)

    down = sub.add_parser("down", help="destroy a VM by id")
    down.add_argument("--api-key", help="Vast.ai API key (or $VAST_API_KEY)")
    down.add_argument("--instance-id", required=True)
    down.set_defaults(func=cmd_down)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
