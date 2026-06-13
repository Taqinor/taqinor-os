# TAQINOR Solar Quote Simulator

Rescued from the old ADK cPanel server (was served via Passenger at
`taqinor.ma/simulator` until the June 2026 domain cutover). Now rehosted on the
Hetzner server at **https://simulateur.taqinor.ma**.

This folder is the **canonical source** (code + config templates only). Client
data and runtime state live on the server and are git-ignored — see below.

## What it is

- **FastAPI (ASGI)** app. Entry point: `main.py` → `app`. Run with **uvicorn**.
  (The `passenger_wsgi.py` / `app_wsgi.py` files are inert cPanel/WSGI shims,
  kept for fidelity; they are not used here.)
- Self-contained **login** (`users.db`, SQLite) with JWT + bcrypt
  (`auth_router.py`, `auth_utils.py`, `db.py`). The team's accounts live in
  `users.db`.
- Generates solar quote PDFs (two engines: `pdf_generator.py` via reportlab,
  `generate_devis_premium.py` via WeasyPrint). Quote history in
  `devis_history.json`; the running quote number in `config.json`; generated
  PDFs in `devis_client/`.
- Frontend is static (`static/`), **hardcoded to the `/simulator` path prefix**
  (`API_BASE = '/simulator'`), matching `root_path="/simulator"` in `main.py`.
  This is why the public URL keeps the `/simulator` segment.

## URL & login

- Team URL: **https://simulateur.taqinor.ma/** (redirects to `/simulator/`).
- Login page: `https://simulateur.taqinor.ma/simulator/login`.
- Existing accounts in `users.db` are preserved unchanged. Nothing about how the
  team uses the app changed except the domain (was `taqinor.ma/simulator`).

## Data files — SERVER-ONLY, never committed (loi 09-08)

Git-ignored (`.gitignore`); they exist only at `/opt/taqinor-simulator/`:
`users.db`, `devis_history.json`, `config.json`, `devis_client/` (PDFs whose
filenames contain real client names), `factures_client/`.

## Secrets

The JWT signing key is **not** in the source. The app reads
`SIMULATOR_SECRET_KEY` from the environment at startup (and refuses to start if
it is missing). On the server it lives only in `/opt/taqinor-simulator/secret.env`
(chmod 600, owned by `simulator`, git-ignored), loaded by the systemd unit's
`EnvironmentFile=`. To rotate: write a new random value there and
`systemctl restart taqinor-simulator` (this logs everyone out once; same
credentials). Generate one with `openssl rand -hex 48`.

## Server layout

- App + venv + data: `/opt/taqinor-simulator/` owned by the unprivileged
  `simulator` user.
- Runs via systemd: `deploy/taqinor-simulator.service` (installed at
  `/etc/systemd/system/`). uvicorn binds `172.18.0.1:8090` (the docker bridge
  gateway = host, reachable only by the Caddy container, never the public
  internet). `Restart=always`, enabled at boot.
- Fronted by the shared Caddy container (`backend/caddy/Caddyfile`,
  `simulateur.taqinor.ma` block): automatic Let's Encrypt cert, HTTP→HTTPS. The
  app keeps `root_path="/simulator"` and serves at the full `/simulator/…`
  paths, so Caddy relays the path **unstripped**; the bare domain `/` redirects
  to `/simulator/`.

## Deploy / update

Code lives in this repo; the running copy at `/opt/taqinor-simulator` is an
independent deployed copy (decoupled from the OS docker deploy). To update code:

```bash
# on the server, as root
rsync -a --delete --exclude users.db --exclude devis_history.json \
  --exclude config.json --exclude devis_client/ --exclude factures_client/ \
  --exclude secret.env --exclude venv/ \
  /path/to/repo/services/simulator/ /opt/taqinor-simulator/
chown -R simulator:simulator /opt/taqinor-simulator
systemctl restart taqinor-simulator
```

Caddyfile changes flow through the OS git checkout
(`/opt/taqinor-os/backend/caddy/Caddyfile`) + `caddy reload`.

## Security notes

- JWT signing key: moved out of the source into a server-only secret (see
  **Secrets** above) and rotated. No secret is committed.
- Public API docs (`/docs`, `/redoc`, `/openapi.json`) are disabled in `main.py`.
- `main.py` seeds default users/passwords only if `users.db` is empty; with the
  restored DB this never fires.
