# Infrastructure & demo plan

Single source of truth for how the hackathon stack is wired. Updated as decisions land.

## Current state (2026-04-16)

| Thing | Status | Details |
|---|---|---|
| Domain `imdad.website` | ✅ Owned | Bought from GoDaddy (AED 3.64 first year). Auto-renew should be turned OFF to dodge the ~AED 147 renewal. |
| Cloudflare account | ✅ Created | `Ghazal.abdulrazzak@gmail.com`, free plan |
| Domain on Cloudflare | ✅ Connected | Zone added, default GoDaddy records imported |
| Nameservers | ✅ Pointed at Cloudflare | `selah.ns.cloudflare.com`, `walt.ns.cloudflare.com` — GoDaddy updated, awaiting propagation (5–30 min typical) |
| Cloudflare SSL mode | ⏳ Set to "Full (strict)" | One-click after CF becomes active |
| Frontend on Replit | ✅ Existing | Keep as-is; don't migrate |
| POS analyst backend | ✅ Code ready on `feat/pos-analyst` branch | Not yet deployed anywhere |
| Vast.ai VM | ❌ Not yet rented | Bandwidth-first offer ready via `deploy_vast.py scout` |
| Cloudflare Tunnel | ❌ Not yet created | Needed before backend becomes reachable on `api.imdad.website` |
| CF Access auth | ⏳ Deferred | Using `POS_API_KEY` for MVP; migrate to Access Service Tokens before real customers |

## Target architecture

```
  ┌───────────────────────────────┐
  │ Judge's browser               │
  └──────────────┬────────────────┘
                 │ HTTPS
       ┌─────────┴──────────┐
       │                    │
  imdad.website       api.imdad.website
       │                    │
       ▼                    ▼
  ┌─────────────┐    ┌──────────────────┐
  │ Cloudflare  │    │ Cloudflare edge  │
  │ CNAME →     │    │ (TLS terminates) │
  │ Replit      │    │     │            │
  └──────┬──────┘    │     │ tunnel     │
         │           │     ▼            │
         ▼           │  cloudflared     │
  ┌─────────────┐    │  (outbound only) │
  │ Replit app  │    └──────┬───────────┘
  │ (frontend)  │           │
  └──────┬──────┘           │
         │ fetch()          │
         └──────────────────┘  ← CORS allowlists the Replit origin
                              (request now reaches Vast VM)
                              ┌──────────────┐
                              │ Vast.ai VM   │
                              │  ┌────────┐  │
                              │  │ FastAPI│  │  pos-analyst-api:8080
                              │  └────────┘  │
                              │  ┌────────┐  │
                              │  │ future │  │  other services
                              │  │ APIs   │  │  (on same tunnel,
                              │  └────────┘  │   own hostnames)
                              └──────────────┘
```

## Subdomain plan

| Hostname | Points to | Purpose |
|---|---|---|
| `imdad.website` (apex) | Replit (A/CNAME per Replit's custom domain instructions) | Frontend / landing page |
| `www.imdad.website` | CNAME → apex | Vanity redirect |
| `api.imdad.website` | Cloudflare Tunnel → `pos-analyst-api:8080` on Vast VM | POS analyst backend |
| `<service>.api.imdad.website` | Same tunnel, different ingress rule | Future services on the same VM |

All SSL certs are auto-issued by Cloudflare. We never touch certs manually.

## Auth plan

**Phase 1 — MVP / hackathon demo (now)**
- Clients send `X-API-Key: $POS_API_KEY` header
- FastAPI checks it; reject 401 otherwise
- Key lives in: GitHub secret `POS_API_KEY`, VM `.env`, Replit frontend code (exposed in browser — acceptable for demo)
- CORS middleware in FastAPI allowlists the Replit origin explicitly

**Phase 2 — before any real customer touches it**
- Drop `POS_API_KEY` from the app
- Cloudflare **Zero Trust → Access** with a wildcard policy on `*.api.imdad.website`
- Auth = Cloudflare Access **Service Tokens** (`CF-Access-Client-Id` + `CF-Access-Client-Secret` header pair)
- FastAPI middleware validates `Cf-Access-Jwt-Assertion` against Cloudflare's public keys for defense-in-depth
- One pair of tokens covers every service behind the wildcard. Rotate / revoke per client from the CF dashboard.

Cost: Phase 1 and Phase 2 are both free.

## Frontend: Replit (confirmed keep)

**Why Replit stays:**
- Frontend already builds/runs there
- Migrating to Cloudflare Pages mid-hackathon burns time that should go into the demo
- With a custom domain pointed at Replit, the user-facing URL is `imdad.website` regardless

**Gotchas we'll handle:**
1. **CORS.** Backend (FastAPI) must allowlist the Replit origin explicitly. Added as `CORSMiddleware` with origin from `POS_CORS_ALLOWED_ORIGINS` env var.
2. **Sleeping server.** Replit free tier sleeps ~30s–60s after idle. Before the pitch: either Replit Core (~$20/mo) "Always On", or use [cron-job.org](https://cron-job.org) to ping the frontend URL every 4 minutes (free).
3. **API key in browser.** `POS_API_KEY` sits in client-side code → visible in Network tab. Fine for the demo, not for production. Phase 2 Access tokens fix this because the frontend can call a same-origin proxy.

## Backend: Vast.ai VM + Cloudflare Tunnel

**Provisioning** (`pos-analyst/scripts/deploy_vast.py`):
- Scout: `python3 deploy_vast.py scout` — ranks VM-capable verified offers with ≥1 Gbps symmetric, picks cheapest
- Rent: `deploy_vast.py up --pos-api-key ...` — rents, installs Docker, rsyncs code, builds sandbox image, brings up compose
- Redeploys after the first: via GitHub Actions `pos-analyst deploy` workflow

**Tunnel wiring (to do once CF domain is active):**
1. Cloudflare dashboard → Zero Trust → Networks → Tunnels → Create tunnel `vast-backend` → copy TUNNEL_TOKEN
2. Add public hostname: subdomain `api`, domain `imdad.website`, service `HTTP → pos-analyst-api:8080`
3. Save TUNNEL_TOKEN as GitHub secret `CLOUDFLARE_TUNNEL_TOKEN`
4. Land the PR that adds `cloudflared` container to `scripts/docker-compose.yml`
5. Redeploy — backend now reachable at `https://api.imdad.website`

## What's left (ordered checklist)

- [ ] Wait for Cloudflare to confirm nameservers (email or dashboard badge turns green)
- [ ] Set SSL/TLS encryption mode to "Full (strict)" in CF dashboard
- [ ] Turn OFF auto-renew on GoDaddy for `imdad.website`
- [ ] **Frontend path:** in Replit → Custom Domains → add `imdad.website` → paste the A/CNAME Replit gives you into CF DNS
- [ ] **Backend path:**
   - [ ] `deploy_vast.py scout` → pick offer
   - [ ] `deploy_vast.py up --minimax-key $MINIMAX_API_KEY --pos-api-key $(openssl rand -hex 24)`
   - [ ] Create CF Tunnel + hostname `api.imdad.website`
   - [ ] Land second PR: add `cloudflared` container + `CLOUDFLARE_TUNNEL_TOKEN` secret + CORS middleware for Replit origin
   - [ ] Redeploy via GitHub Actions
- [ ] Set up cron-job.org ping on the Replit frontend URL (every 4 min) to keep it warm during demos
- [ ] End-to-end test: open `https://imdad.website` on a fresh device → frontend hits `https://api.imdad.website/jobs` → report returns
- [ ] Schedule the demo, stop touching things the night before

## Decisions log (for future-us)

| Decision | Why |
|---|---|
| Domain on GoDaddy, not Cloudflare Registrar | User was mid-cart; AED 3.64 for 1 year is fine as long as auto-renew is off |
| `.website` TLD | Cheap first year, judges won't care |
| Cloudflare free plan | Tunnel + Access + DNS + SSL all free at the volumes we need |
| MiniMax-M2.7 for analyst | Purpose-built for agentic tool calling, cheap ($0.30/$1.20 per M), 200K context |
| VM not standard Vast container | Workload runs Docker on the host (API + sibling sandbox containers); DinD is not supported on Vast standard instances |
| Keep Replit for frontend | Already working; hackathon mandate is ship > refactor |
| Shared `POS_API_KEY` for MVP, Access Service Tokens for production | Simplest path to a working demo; proper auth is a 1-PR swap after |
| Skip CF Pages for now | Replit already hosts the frontend; revisit post-hackathon if desired |
