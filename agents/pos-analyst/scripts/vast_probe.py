#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://console.vast.ai/api/v0"


def _fail(message: str, *, payload: Any | None = None, exit_code: int = 1) -> int:
    print(message, file=sys.stderr)
    if payload is not None:
        print(json.dumps(payload, ensure_ascii=True, indent=2), file=sys.stderr)
    return exit_code


def _read_api_key(value: str | None) -> str:
    api_key = (value or os.getenv("VAST_API_KEY") or os.getenv("SKYLINK_VAST_API_KEY") or "").strip()
    if not api_key:
        raise SystemExit(_fail("Missing Vast API key. Pass --api-key or set VAST_API_KEY."))
    return api_key


def _request(
    *,
    api_key: str,
    method: str,
    base_url: str,
    path: str,
    payload: Any | None,
    timeout: float,
) -> Any:
    data = None
    headers = {"Authorization": f"Bearer {api_key}"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        headers=headers,
        method=method.upper(),
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(
            _fail(
                f"Vast API request failed: {method.upper()} {path} returned {exc.code}.",
                payload={"body": body},
            )
        ) from exc
    except urllib.error.URLError as exc:
        raise SystemExit(_fail(f"Vast API request failed: {exc}")) from exc

    if not text.strip():
        return {}
    return json.loads(text)


def _parse_json_arg(value: str | None, *, option_name: str, require_object: bool = False) -> Any | None:
    if value is None:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise SystemExit(_fail(f"Invalid JSON for {option_name}: {exc}")) from exc
    if require_object and not isinstance(parsed, dict):
        raise SystemExit(_fail(f"{option_name} must decode to a JSON object."))
    return parsed


def _read_text_arg(*, inline_value: str | None, file_path: str | None, option_name: str) -> str | None:
    if inline_value and file_path:
        raise SystemExit(_fail(f"Pass only one of inline text or file for {option_name}."))
    if file_path:
        return Path(file_path).read_text(encoding="utf-8").strip()
    if inline_value is None:
        return None
    return inline_value.strip()


def _normalize_offer_type(value: str) -> str:
    normalized = value.replace("-", "").lower()
    if normalized == "ondemand":
        return "ondemand"
    return value.lower()


def _extract_offers(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        raw = payload.get("offers") or payload.get("results") or payload.get("bundles") or payload.get("rows") or []
        return [item for item in raw if isinstance(item, dict)]
    return []


def _extract_instances(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        raw = payload.get("instances") or []
        return [item for item in raw if isinstance(item, dict)]
    return []


def _normalize_instance(instance: dict[str, Any]) -> dict[str, Any]:
    actual_status = str(instance.get("actual_status") or instance.get("cur_state") or "").strip().lower()
    return {
        "id": instance.get("id"),
        "label": instance.get("label"),
        "status": actual_status or "unknown",
        "gpu_name": instance.get("gpu_name"),
        "ssh_host": instance.get("ssh_host"),
        "ssh_port": instance.get("ssh_port"),
        "public_ipaddr": instance.get("public_ipaddr"),
        "status_msg": instance.get("status_msg"),
    }


def _trim_offer(offer: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": offer.get("id"),
        "gpu_name": offer.get("gpu_name"),
        "num_gpus": offer.get("num_gpus"),
        "dph_total": offer.get("dph_total_adj") or offer.get("dph_total"),
        "reliability": offer.get("reliability2") or offer.get("reliability"),
        "verified": offer.get("verified") or offer.get("verification"),
        "vms_enabled": offer.get("vms_enabled"),
        "direct_port_count": offer.get("direct_port_count"),
        "gpu_total_ram": offer.get("gpu_total_ram"),
        "disk_space": offer.get("disk_space"),
        "cpu_ram": offer.get("cpu_ram"),
        "dlperf": offer.get("dlperf"),
        "driver_version": offer.get("driver_version"),
        "cuda_max_good": offer.get("cuda_max_good"),
        "public_ipaddr": offer.get("public_ipaddr"),
    }


def _instance_or_fail(result: Any, *, instance_id: int) -> dict[str, Any]:
    instance = result.get("instances") if isinstance(result, dict) else result
    if isinstance(instance, dict):
        return instance
    if instance is None:
        raise SystemExit(_fail(f"Instance {instance_id} was not found. Treat this as stale or destroyed state."))
    raise SystemExit(_fail(f"Unexpected instance payload for {instance_id}.", payload={"instance": instance}))


def cmd_offers(args: argparse.Namespace) -> int:
    api_key = _read_api_key(args.api_key)
    payload: dict[str, Any] = {
        "rentable": {"eq": True},
        "rented": {"eq": False},
        "num_gpus": {"gte": args.num_gpus},
        "limit": args.limit,
        "type": _normalize_offer_type(args.offer_type),
    }
    if args.verified:
        payload["verified"] = {"eq": True}
    if args.min_reliability > 0:
        payload["reliability"] = {"gte": args.min_reliability}
    if args.min_gpu_ram_gb > 0:
        payload["gpu_total_ram"] = {"gte": int(args.min_gpu_ram_gb * 1024)}
    if args.gpu_name:
        payload["gpu_name"] = {"in": args.gpu_name}
    if args.vm_capable:
        payload["vms_enabled"] = {"eq": True}
    if args.min_direct_ports > 0:
        payload["direct_port_count"] = {"gte": args.min_direct_ports}
    if args.allocated_storage_gb > 0:
        payload["allocated_storage"] = args.allocated_storage_gb

    result = _request(
        api_key=api_key,
        method="POST",
        base_url=args.base_url,
        path="/bundles/",
        payload=payload,
        timeout=args.timeout,
    )
    offers = _extract_offers(result)
    if not args.raw:
        offers = [_trim_offer(offer) for offer in offers]
    print(json.dumps(offers, ensure_ascii=True, indent=2))
    return 0


def cmd_instances(args: argparse.Namespace) -> int:
    api_key = _read_api_key(args.api_key)
    result = _request(
        api_key=api_key,
        method="GET",
        base_url=args.base_url,
        path="/instances/",
        payload=None,
        timeout=args.timeout,
    )
    instances = [_normalize_instance(item) for item in _extract_instances(result)]
    print(json.dumps(instances, ensure_ascii=True, indent=2))
    return 0


def cmd_show_instance(args: argparse.Namespace) -> int:
    api_key = _read_api_key(args.api_key)
    result = _request(
        api_key=api_key,
        method="GET",
        base_url=args.base_url,
        path=f"/instances/{args.instance_id}/",
        payload=None,
        timeout=args.timeout,
    )
    print(json.dumps(_normalize_instance(_instance_or_fail(result, instance_id=args.instance_id)), ensure_ascii=True, indent=2))
    return 0


def cmd_wait_instance(args: argparse.Namespace) -> int:
    api_key = _read_api_key(args.api_key)
    deadline = time.time() + args.timeout_seconds
    last_seen: Any = None
    while time.time() < deadline:
        result = _request(
            api_key=api_key,
            method="GET",
            base_url=args.base_url,
            path=f"/instances/{args.instance_id}/",
            payload=None,
            timeout=args.timeout,
        )
        instance = _instance_or_fail(result, instance_id=args.instance_id)
        last_seen = instance
        normalized = _normalize_instance(instance)
        ready = normalized["status"] == "running"
        if args.require_ssh:
            ready = ready and bool(normalized["ssh_host"]) and bool(normalized["ssh_port"])
        if ready:
            print(json.dumps(normalized, ensure_ascii=True, indent=2))
            return 0
        time.sleep(args.poll_seconds)

    return _fail(
        f"Timed out waiting for instance {args.instance_id}.",
        payload={"last_seen": last_seen},
    )


def cmd_ssh_keys(args: argparse.Namespace) -> int:
    api_key = _read_api_key(args.api_key)
    result = _request(
        api_key=api_key,
        method="GET",
        base_url=args.base_url,
        path="/ssh/",
        payload=None,
        timeout=args.timeout,
    )
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


def cmd_register_ssh_key(args: argparse.Namespace) -> int:
    api_key = _read_api_key(args.api_key)
    public_key = Path(args.public_key_file).read_text(encoding="utf-8").strip()
    result = _request(
        api_key=api_key,
        method="POST",
        base_url=args.base_url,
        path="/ssh/",
        payload={"ssh_key": public_key},
        timeout=args.timeout,
    )
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


def cmd_attach_ssh_key(args: argparse.Namespace) -> int:
    api_key = _read_api_key(args.api_key)
    public_key = Path(args.public_key_file).read_text(encoding="utf-8").strip()
    result = _request(
        api_key=api_key,
        method="POST",
        base_url=args.base_url,
        path=f"/instances/{args.instance_id}/ssh/",
        payload={"ssh_key": public_key},
        timeout=args.timeout,
    )
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


def cmd_create_template(args: argparse.Namespace) -> int:
    api_key = _read_api_key(args.api_key)
    extra_filters = _parse_json_arg(args.extra_filter_json, option_name="--extra-filter-json", require_object=True)
    onstart = _read_text_arg(inline_value=args.onstart, file_path=args.onstart_file, option_name="--onstart")

    use_ssh = args.use_ssh
    ssh_direct = args.ssh_direct
    jup_direct = args.jup_direct
    if args.runtype == "ssh":
        if use_ssh is None:
            use_ssh = True
        if ssh_direct is None:
            ssh_direct = True
    if args.runtype == "jupyter" and jup_direct is None:
        jup_direct = True

    payload: dict[str, Any] = {
        "name": args.name,
        "image": args.image,
        "env": args.env or "",
        "onstart": onstart or "",
        "runtype": args.runtype,
        "docker_login_repo": args.docker_login_repo or "",
        "docker_login_user": args.docker_login_user or "",
        "docker_login_pass": args.docker_login_pass or "",
        "recommended_disk_space": args.recommended_disk_space,
        "private": args.private,
    }
    if args.tag:
        payload["tag"] = args.tag
    if args.description:
        payload["desc"] = args.description
    if args.args_str:
        payload["args_str"] = args.args_str
    if use_ssh is not None:
        payload["use_ssh"] = use_ssh
    if ssh_direct is not None:
        payload["ssh_direct"] = ssh_direct
    if jup_direct is not None:
        payload["jup_direct"] = jup_direct
    if args.jupyter_dir:
        payload["jupyter_dir"] = args.jupyter_dir
    if args.use_jupyter_lab:
        payload["use_jupyter_lab"] = True
    if extra_filters:
        payload["extra_filters"] = extra_filters

    result = _request(
        api_key=api_key,
        method="POST",
        base_url=args.base_url,
        path="/template/",
        payload=payload,
        timeout=args.timeout,
    )
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


def cmd_create_instance(args: argparse.Namespace) -> int:
    api_key = _read_api_key(args.api_key)
    if not args.template_hash_id and not args.image:
        raise SystemExit(_fail("Pass either --template-hash-id or --image."))

    payload: dict[str, Any] = {
        "target_state": args.target_state,
        "cancel_unavail": args.cancel_unavail,
    }
    if args.template_hash_id:
        payload["template_hash_id"] = args.template_hash_id
    if args.image:
        payload["image"] = args.image
    if args.label:
        payload["label"] = args.label
    if args.disk_gb is not None:
        payload["disk"] = args.disk_gb
    if args.runtype:
        payload["runtype"] = args.runtype
    elif args.image and not args.template_hash_id:
        payload["runtype"] = "ssh"

    env_payload = _parse_json_arg(args.env_json, option_name="--env-json", require_object=True)
    if env_payload:
        payload["env"] = env_payload

    volume_payload = _parse_json_arg(args.volume_info_json, option_name="--volume-info-json", require_object=True)
    if volume_payload:
        payload["volume_info"] = volume_payload

    result = _request(
        api_key=api_key,
        method="PUT",
        base_url=args.base_url,
        path=f"/asks/{args.offer_id}/",
        payload=payload,
        timeout=args.timeout,
    )
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


def cmd_destroy_instance(args: argparse.Namespace) -> int:
    api_key = _read_api_key(args.api_key)
    result = _request(
        api_key=api_key,
        method="DELETE",
        base_url=args.base_url,
        path=f"/instances/{args.instance_id}/",
        payload=None,
        timeout=args.timeout,
    )
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Minimal Vast.ai API helper for templates, instances, and VM-capable remote workflows."
    )
    parser.add_argument("--api-key", help="Vast API key. Falls back to VAST_API_KEY or SKYLINK_VAST_API_KEY.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Vast API base URL.")
    parser.add_argument("--timeout", type=float, default=60.0, help="HTTP timeout in seconds.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    offers = subparsers.add_parser("offers", help="Search offer candidates.")
    offers.add_argument("--offer-type", default="ondemand", choices=["ondemand", "on-demand", "bid", "reserved"])
    offers.add_argument("--limit", type=int, default=20)
    offers.add_argument("--num-gpus", type=int, default=1)
    offers.add_argument("--verified", action="store_true")
    offers.add_argument("--vm-capable", action="store_true", help="Require VM-capable hosts.")
    offers.add_argument("--min-direct-ports", type=int, default=0)
    offers.add_argument("--allocated-storage-gb", type=float, default=0.0)
    offers.add_argument("--min-reliability", type=float, default=0.0)
    offers.add_argument("--min-gpu-ram-gb", type=float, default=0.0)
    offers.add_argument("--gpu-name", action="append", default=[])
    offers.add_argument("--raw", action="store_true", help="Print raw offer payloads.")
    offers.set_defaults(func=cmd_offers)

    instances = subparsers.add_parser("instances", help="List current instances.")
    instances.set_defaults(func=cmd_instances)

    show_instance = subparsers.add_parser("show-instance", help="Inspect one instance.")
    show_instance.add_argument("--instance-id", type=int, required=True)
    show_instance.set_defaults(func=cmd_show_instance)

    wait_instance = subparsers.add_parser("wait-instance", help="Poll until an instance is ready.")
    wait_instance.add_argument("--instance-id", type=int, required=True)
    wait_instance.add_argument("--timeout-seconds", type=int, default=900)
    wait_instance.add_argument("--poll-seconds", type=int, default=10)
    wait_instance.add_argument("--require-ssh", action="store_true")
    wait_instance.set_defaults(func=cmd_wait_instance)

    ssh_keys = subparsers.add_parser("ssh-keys", help="List account SSH keys.")
    ssh_keys.set_defaults(func=cmd_ssh_keys)

    register_ssh_key = subparsers.add_parser("register-ssh-key", help="Register a public SSH key on the account.")
    register_ssh_key.add_argument("--public-key-file", required=True)
    register_ssh_key.set_defaults(func=cmd_register_ssh_key)

    attach_ssh_key = subparsers.add_parser("attach-ssh-key", help="Attach an SSH key to an existing standard instance.")
    attach_ssh_key.add_argument("--instance-id", type=int, required=True)
    attach_ssh_key.add_argument("--public-key-file", required=True)
    attach_ssh_key.set_defaults(func=cmd_attach_ssh_key)

    create_template = subparsers.add_parser("create-template", help="Create a reusable Vast template.")
    create_template.add_argument("--name", required=True)
    create_template.add_argument("--image", required=True)
    create_template.add_argument("--tag", help="Optional image tag. Omit to use the API default or a fully tagged image.")
    create_template.add_argument("--description")
    create_template.add_argument("--env", help="Template env in Docker flag format, e.g. '-e MODE=prod -p 8000:8000'.")
    create_template.add_argument("--onstart", help="Inline onstart shell commands.")
    create_template.add_argument("--onstart-file", help="Read onstart shell commands from a file.")
    create_template.add_argument("--runtype", choices=["ssh", "jupyter", "args"], default="ssh")
    create_template.add_argument("--args-str")
    create_template.add_argument("--ssh-direct", action=argparse.BooleanOptionalAction, default=None)
    create_template.add_argument("--use-ssh", action=argparse.BooleanOptionalAction, default=None)
    create_template.add_argument("--jup-direct", action=argparse.BooleanOptionalAction, default=None)
    create_template.add_argument("--jupyter-dir")
    create_template.add_argument("--use-jupyter-lab", action=argparse.BooleanOptionalAction, default=False)
    create_template.add_argument("--docker-login-repo")
    create_template.add_argument("--docker-login-user")
    create_template.add_argument("--docker-login-pass")
    create_template.add_argument("--extra-filter-json", help="JSON object for template extra_filters.")
    create_template.add_argument("--recommended-disk-space", type=float, default=8.0)
    create_template.add_argument("--private", action=argparse.BooleanOptionalAction, default=True)
    create_template.set_defaults(func=cmd_create_template)

    create_instance = subparsers.add_parser("create-instance", help="Create an instance from an offer id.")
    create_instance.add_argument("--offer-id", type=int, required=True)
    create_instance.add_argument("--template-hash-id")
    create_instance.add_argument("--image", help="Optional raw image or template override image.")
    create_instance.add_argument("--label")
    create_instance.add_argument("--disk-gb", type=float)
    create_instance.add_argument("--runtype", choices=["ssh", "jupyter", "args"])
    create_instance.add_argument("--target-state", default="running")
    create_instance.add_argument("--cancel-unavail", action=argparse.BooleanOptionalAction, default=True)
    create_instance.add_argument("--env-json", help="JSON object of env overrides for instance creation.")
    create_instance.add_argument("--volume-info-json", help="JSON object for volume_info.")
    create_instance.set_defaults(func=cmd_create_instance)

    destroy_instance = subparsers.add_parser("destroy-instance", help="Destroy an instance.")
    destroy_instance.add_argument("--instance-id", type=int, required=True)
    destroy_instance.set_defaults(func=cmd_destroy_instance)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
