# E2E suite (Playwright)

End-to-end browser tests that drive the **real built app** against a throwaway
stack (Postgres + Redis + MinIO + Django), never production. The CI job `e2e`
in `.github/workflows/ci.yml` is the source of truth for how the stack is
brought up; this is the short version for running it locally.

## What it covers

`E2` login · `E3` lead lifecycle · `E4` devis-from-lead (PDF preview + download)
· `E5` inline bill edit · `E6` reassignment · `E7` stage moves incl. Signé ·
`E8` employees (+ photo, password reset) · `E9` activities · `E10` attachments ·
`E11` doublons merge · `E12` avoirs · `E13` relances/balance âgée/relevé ·
`E14` paramètres · `E15` broken-image/console-error health · `E16` mobile pass.

## How it's wired

- One origin: `vite preview` serves the built app and, with `E2E_PROXY=1`,
  reverse-proxies `/api/django` to Django — so the httpOnly auth cookies behave
  exactly like they do behind nginx in production.
- `VITE_E2E=1` at build time drops the service worker (PWA shell-cache only adds
  flakiness to browser tests; app logic is unchanged).
- The suite is **serial** (`workers: 1`) over one freshly-seeded DB
  (`manage.py seed_demo`, user `demo_admin` / `Demo@2026!`), so mutating flows
  stay deterministic. `auth.setup.js` logs in once and shares the cookie jar.

## Run locally

You need the stack up first (Docker is the easiest way):

```bash
cp .env.example .env            # repo root, if not done yet
docker compose up -d            # Postgres, Redis, MinIO, Django, …
docker compose exec django_core python manage.py seed_demo

cd frontend
npm ci
npx playwright install chromium
VITE_E2E=1 npm run build        # build the app the suite serves
E2E_API_TARGET=http://127.0.0.1:8000 npm run e2e   # adjust target to your Django
npm run e2e:report              # open the HTML report
```

In CI, Django is served on `127.0.0.1:8000` and `E2E_API_TARGET` defaults to it.
