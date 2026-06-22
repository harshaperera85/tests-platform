# SETUP — Tests Platform (AWS EC2 development)

Development runs on an **AWS EC2 Ubuntu instance with native Docker** — not the local Windows
machine. The instance mirrors the CAT platform's environment; your laptop is used only for light
editing + git, while the conda env, Claude Code, and the full `docker compose` stack all run on the
instance. This is a run-once setup guide; do it top to bottom.

## 1. Prerequisites
- **An AWS account** with permission to launch EC2 instances.
- **An SSH client** on your laptop (built into Windows 10/11, macOS, and Linux).
- **A Claude Code-eligible account** (Claude subscription or API access) to run Claude Code on the
  instance.
- **Use the same AWS region as the CAT platform** — keeps the mirtCAT R service and neural services
  close (low latency) and simplifies networking.

## 2. Launch the instance
In the EC2 console, launch an instance with:
- **AMI:** Ubuntu Server **24.04 LTS** (x86_64).
- **Instance type:** **t3.xlarge** recommended (4 vCPU / 16 GB), **t3.large** minimum
  (2 vCPU / 8 GB). The full compose stack (postgres, redis, backend, frontend, scoring-r) plus
  Claude Code is comfortable at xlarge.
- **Key pair:** create or select one; download the `.pem` and keep it safe — you SSH with it.
- **Security group:** allow **SSH (port 22) from My IP only**. Do not open it to the world. The app
  ports are reached via SSH tunnels (§9), so they need not be opened in the security group.
- **Storage:** **50 GB gp3** (Docker images + conda env + repo need headroom).
- **Elastic IP (optional but recommended):** associate one so the public IP survives stop/start. See
  cost/lifecycle notes (§10).

## 3. Connect
From your laptop:
```bash
ssh -i <key.pem> ubuntu@<PUBLIC_IP>
```
(`chmod 400 <key.pem>` first on macOS/Linux if SSH complains about key permissions.)

## 4. Provision the instance
Run these on the instance over SSH.

Base packages:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git build-essential
```

Docker (native — the engine runs on Linux directly, no Docker Desktop):
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```
Log out and back in (or `newgrp docker`) so the group change takes effect, then verify with
`docker run hello-world`.

Miniconda:
```bash
curl -fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -o ~/miniconda.sh
bash ~/miniconda.sh -b -p ~/miniconda
~/miniconda/bin/conda init bash
```
Re-open the shell so `conda` is on PATH.

Claude Code:
```bash
curl -fsSL https://claude.ai/install.sh | bash
```
Ensure `~/.local/bin` is on PATH (add `export PATH="$HOME/.local/bin:$PATH"` to `~/.bashrc` if
needed), then run `claude` once to authenticate.

## 5. Clone the repo (SSH deploy key)
Generate a deploy key on the instance and add its public half to the GitHub repo
(**Settings → Deploy keys**):
```bash
ssh-keygen -t ed25519 -C "ec2-tests-platform" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub   # paste this into GitHub → Deploy keys
```
Then clone over SSH:
```bash
git clone git@github.com:<you>/tests-platform.git
cd tests-platform
```

## 6. Create the conda environment
```bash
conda env create -f environment.yml
conda activate tests-platform
```

## 7. Run Phase 0 in Claude Code
From the repo root on the instance, launch Claude Code and paste the Phase 0 kickoff prompt below.
Docker is **native** here, so run the **full Phase 0** — including `docker compose up`. There is no
step to skip; the full stack comes up on the instance, never on your laptop.

## 8. Access the running app from your laptop
The app ports are not exposed publicly; reach them through SSH tunnels:
```bash
ssh -i <key.pem> -L 5173:localhost:5173 -L 8000:localhost:8000 ubuntu@<PUBLIC_IP>
```
Then open `http://localhost:5173` (frontend) and `http://localhost:8000` (backend) in your laptop
browser — the traffic is forwarded to the instance.

## 9. Cost & lifecycle hygiene
- **Stop the instance when idle.** You pay for compute while it is running; stopped instances cost
  only for EBS storage.
- **The public IP changes on stop/start** unless you attached an **Elastic IP** (§2). With an
  Elastic IP your `ssh`/tunnel commands stay constant.
- **Resize** by stop → change instance type → start (e.g. t3.large ↔ t3.xlarge). The instance must
  be stopped to change its type.

---

## Phase 0 kickoff prompt (paste into Claude Code)

> You are building the Tests Platform. **Read `CLAUDE.md` and
> `docs/tests_module_architecture_and_build_plan.md` first and follow them exactly** — especially the
> golden rules (strategy-contract extensibility, OR-Tools owns assembly with R packages as oracles
> only, CAT-as-adapter, one canonical θ metric, contract-first OpenAPI→Orval).
>
> **Phase 0 — scaffolding only. Do not implement Linear, CAT, or any assembly logic yet.** Deliver:
> 1. The monorepo skeleton exactly per the layout in the plan (`backend/`, `engines/scoring-r/`,
>    `frontend/`, `infra/`, `docs/`).
> 2. A FastAPI app (`backend/app/main.py`) with a health endpoint and versioned `/api/v1` router
>    mount; settings via `core/config.py` (pydantic-settings, reads `.env`); db/redis wiring in
>    `core/`.
> 3. SQLAlchemy 2 base + an Alembic baseline migration (empty/initial).
> 4. The engine foundation: `engine/contract.py` (the `AdministrationStrategy` ABC + `NextAction`,
>    `Navigation`, `TerminationDecision`, and the session-state types) and `engine/registry.py`
>    (`register` decorator + `get_strategy`). No concrete strategies yet — just the contract and an
>    empty registry, with a unit test proving registration/lookup works.
> 5. A Pydantic `TestConfig` discriminated union skeleton keyed by `administration_model` with stub
>    `LinearConfig` and `CatConfig` branches (fields can be minimal placeholders for now).
> 6. `infra/docker-compose.yml` with services: `postgres`, `redis`, `backend`, `frontend`,
>    `scoring-r` (stub R/plumber service that returns a health response). `.env.example` for config.
> 7. Frontend skeleton: Vite + React + TypeScript + Tailwind, with the Orval config wired to read the
>    backend OpenAPI (client generation can be a no-op until endpoints exist).
> 8. Tooling: ruff + mypy configs, a `pytest` setup with the test-tier folders
>    (`tests/{unit,integration,contract,regression}`), and a GitHub Actions CI workflow that runs
>    lint, type-check, and tests.
>
> Make it run: `docker compose up` should bring the stack up and the backend health endpoint should
> respond. Keep everything minimal but real — no business logic. After scaffolding, summarize what
> you created and confirm the health check passes. Then stop for review before Phase 1.
