# Vast.ai Remote Compute Workflow

## Table of Contents

- Official decision rule: Docker instance vs VM
- Template-first API surface
- Offer selection heuristics
- SSH and key handling
- Docker-based instance pattern
- VM pattern
- Validation checklist
- Failure modes that matter
- Helper script usage

## Official decision rule: Docker instance vs VM

Use the documented platform boundary, not intuition:

- Standard Vast instances already run as Linux Docker containers.
- Vast explicitly does **not** support Docker-in-Docker on those instances.
- Vast VMs are the supported path for nested containerization and host-level Linux behavior.

Choose the mode this way:

1. Use a Docker-based instance when:
   - one container can run the workload directly
   - the remote process does not need `systemd`, `ptrace`, or nested container tools
   - you can express ports and env vars through the template `env` field and startup commands through `onstart`
2. Use a VM when:
   - the remote host must run Docker, Docker Compose, Kubernetes, Snap, or similar tooling
   - the workload requires `systemd` or `ptrace`
   - the deployment assumes full-machine semantics instead of container semantics

VM tradeoffs called out by Vast:

- slower creation and boot times
- higher disk overhead
- smaller selection of machines
- fewer preconfigured templates
- only SSH launch mode is currently supported

## Template-first API surface

Prefer templates over one-off instance payloads.

Key endpoints:

- `POST /bundles/`
  - search offers
- `POST /template/`
  - create a reusable template
- `PUT /template/`
  - edit a template by `hash_id`
- `DELETE /template/`
  - delete a template by numeric `template_id`
- `PUT /asks/{offer_id}/`
  - create an instance from an offer
  - use `template_hash_id` for template-driven launches
- `GET /instances/`
  - list current instances
- `GET /instances/{id}/`
  - inspect a single instance
  - treat `{"instances": null}` as stale or destroyed state
- `DELETE /instances/{id}/`
  - destroy a failed or no-longer-needed instance
- `GET /ssh/`
  - list account SSH keys
- `POST /ssh/`
  - add an account SSH public key
- `POST /instances/{id}/ssh/`
  - attach an SSH key to an existing standard instance

Template fields that matter most:

- `image`
- `tag`
- `env`
  - Docker flag string format, for example `"-e MODE=prod -p 8000:8000"`
- `onstart`
- `runtype`
  - valid values: `ssh`, `jupyter`, `args`
- `ssh_direct`
- `use_ssh`
- `extra_filters`
- `recommended_disk_space`

Important API rules:

- Create instances from templates with `template_hash_id`, not numeric `template_id`.
- Template `env` uses Docker flag string format.
- Instance creation overrides use JSON dict format for `env`.
- `runtype: "ssh"` with `ssh_direct: true` and `use_ssh: true` is the documented SSH recommendation.
- The old idea of setting `runtype` to `ssh_direct` is incorrect.

## Offer selection heuristics

Default filters that work well:

- `rentable=true`
- `rented=false`
- `type=ondemand`
- `verified=true`
- reliability threshold appropriate for the task
- enough `gpu_total_ram` or CPU RAM
- enough `direct_port_count` for SSH plus published services
- enough disk for image layers, package installs, caches, models, and logs

VM-specific filter:

- set `vms_enabled=true` when the workload needs a VM

Useful search facts from the current docs:

- `allocated_storage` can be included in offer search to estimate pricing for the disk size you plan to reserve
- disk size is fixed at creation time and cannot be changed later

Operational heuristics:

- prefer a reliable host over the absolute cheapest offer when bootstrap is expensive to retry
- kill bad instances early if they stall in `creating` or never expose usable SSH
- budget extra disk for VMs because their overhead is higher than standard container instances

## SSH and key handling

Generate the SSH keypair yourself when needed:

- PowerShell:
  - `ssh-keygen -t ed25519 -f "$HOME/.ssh/id_ed25519" -N ""`
- Bash:
  - `ssh-keygen -t ed25519 -f "$HOME/.ssh/id_ed25519" -N ""`

Current documented behavior:

- adding a key to the account applies automatically to new instances
- existing standard instances need instance-level key attachment if you want to add a key later
- VM keys cannot be changed on a running VM; recreate the VM instead
- proxy SSH works on all machines
- direct SSH is faster and preferred when available

Use these SSH priorities:

1. direct SSH details from the instance if present
2. proxy SSH details from the instance panel or API

If a controller runs inside another container and OpenSSH rejects the private key permissions, stage the key into a private temp path and lock it down before calling `ssh` or `scp`.

## Docker-based instance pattern

Treat a standard Vast instance as the runtime container, not as a host where you install Docker again.

Recommended pattern:

1. build or choose the container image that can run the service directly
2. create a template with:
   - `image`
   - `env` for ports and env vars
   - `onstart` for startup commands
   - `runtype: "ssh"` plus SSH flags when you want shell access
3. create the instance from a chosen offer with `template_hash_id`
4. wait for `running` plus SSH readiness if needed
5. verify the mapped public ports or tunnel through SSH
6. hit `/health`
7. run one real request

Important container-mode details:

- Vast says SSH and Jupyter launch modes inject setup scripts and replace the image’s original entrypoint
- if your image depends on its own entrypoint, copy that command into `onstart`
- for SSH instances, `/root/onstart.sh` runs automatically on startup
- random external port mappings are normal because many instances share the same public IP

## VM pattern

Use a VM only when the remote machine itself must behave like a full Linux host.

Documented VM setup:

- VM images come from `docker.io/vastai/kvm`
- VM templates must use a fully qualified KVM image such as `docker.io/vastai/kvm:ubuntu_terminal`
- add `vms_enabled=true` to the template extra filters so the offer search only returns VM-capable machines
- SSH is the only supported launch mode
- VM environment variables are written to `/etc/environment`

Recommended VM rollout:

1. create a VM template with a `docker.io/vastai/kvm:*` image
2. set `extra_filters` to require VM-capable hosts
3. choose enough disk for the guest OS plus your workload
4. launch from the template
5. wait for the VM to finish booting and expose SSH
6. SSH in and install Docker, Docker Compose, services, or other host-level tooling there
7. validate `/health` and one real request before keeping the VM running

One inference worth making explicit:

- The docs say to add `vms_enabled=true` in the template Extra Filters field and separately define `extra_filters` as a normal template object. The API form that matches both docs is `{"extra_filters": {"vms_enabled": {"eq": true}}}`.
- The template API exposes `image` and `tag` as separate fields, so the helper script can either take a fully tagged image string or the split form `--image docker.io/vastai/kvm --tag ubuntu_terminal`.

## Validation checklist

Do not keep a paid machine running until all of these are true:

- the instance is `running`
- SSH or the required remote control path works
- the remote service `/health` returns `200`
- one real workload request succeeds
- the frontend or controller sees the same endpoint it will use in steady state
- repeated status polls stay in the ready state without re-running full bootstrap

## Failure modes that matter

- assuming a standard instance can run Docker-in-Docker
  - Vast explicitly says no
  - fix: use a direct container image or switch to a VM
- using `runtype=ssh_direct`
  - not a documented runtype
  - fix: use `runtype="ssh"` and set `ssh_direct=true`
- stale persisted instance id
  - symptom: polling a destroyed machine returns `{"instances": null}`
  - fix: clear saved state and stop polling that id
- disk too small
  - symptom: image pulls or package installs fail mid-bootstrap
  - fix: create a new instance with a larger disk; resize is not supported
- treating direct ports as stable or sequential
  - symptom: service URL is wrong even though the process is healthy
  - fix: inspect the actual mapped ports or tunnel through SSH
- changing SSH keys on a running VM
  - symptom: new key never works
  - fix: recreate the VM with the correct account key already present

## Helper script usage

Search Docker-instance candidates:

```bash
python scripts/vast_probe.py offers \
  --api-key "$VAST_API_KEY" \
  --offer-type ondemand \
  --verified \
  --min-reliability 0.995 \
  --min-gpu-ram-gb 24 \
  --min-direct-ports 2 \
  --gpu-name "RTX 5090" \
  --gpu-name "L40S" \
  --allocated-storage-gb 64 \
  --limit 20
```

Search VM-capable candidates:

```bash
python scripts/vast_probe.py offers \
  --api-key "$VAST_API_KEY" \
  --offer-type ondemand \
  --verified \
  --vm-capable \
  --min-reliability 0.995 \
  --allocated-storage-gb 96 \
  --limit 20
```

Register an SSH public key:

```bash
python scripts/vast_probe.py register-ssh-key \
  --api-key "$VAST_API_KEY" \
  --public-key-file "$HOME/.ssh/id_ed25519.pub"
```

Create a Docker-instance template:

```bash
python scripts/vast_probe.py create-template \
  --api-key "$VAST_API_KEY" \
  --name my-service-ssh \
  --image vllm/vllm-openai \
  --env "-e MODEL_ID=deepseek-ai/DeepSeek-R1-Distill-Llama-8B -p 8000:8000" \
  --onstart "vllm serve \$MODEL_ID --port 8000" \
  --runtype ssh \
  --recommended-disk-space 64
```

Create a VM template:

```bash
python scripts/vast_probe.py create-template \
  --api-key "$VAST_API_KEY" \
  --name ubuntu-vm-docker-host \
  --image docker.io/vastai/kvm \
  --tag ubuntu_terminal \
  --runtype ssh \
  --recommended-disk-space 96 \
  --extra-filter-json "{\"vms_enabled\":{\"eq\":true}}"
```

Create an instance from a template:

```bash
python scripts/vast_probe.py create-instance \
  --api-key "$VAST_API_KEY" \
  --offer-id 123456 \
  --template-hash-id 4e17788f74f075dd9aab7d0d4427968f \
  --disk-gb 96
```

Attach an SSH key to an existing standard instance:

```bash
python scripts/vast_probe.py attach-ssh-key \
  --api-key "$VAST_API_KEY" \
  --instance-id 123456 \
  --public-key-file "$HOME/.ssh/id_ed25519.pub"
```

Wait until the instance is usable:

```bash
python scripts/vast_probe.py wait-instance \
  --api-key "$VAST_API_KEY" \
  --instance-id 123456 \
  --timeout-seconds 900 \
  --require-ssh
```

Destroy a failed instance:

```bash
python scripts/vast_probe.py destroy-instance \
  --api-key "$VAST_API_KEY" \
  --instance-id 123456
```
