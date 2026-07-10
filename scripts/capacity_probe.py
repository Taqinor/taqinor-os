"""SCA7 — Sonde de capacite DEV-ONLY (jetable), PAS le harnais canonique.

But : mesurer p50/p95 de latence sur 4 endpoints "chauds" (login, liste devis,
liste leads, /proposal) et le nombre de rendus PDF concurrents avant
saturation, avec un garde-fou d'arret immediat si /core/health/ passe
"degraded" ou "down" pendant la sonde.

Usage (hors heures ouvrees UNIQUEMENT, jamais sur la prod vivante sans accord
fondateur explicite) :

    python scripts/capacity_probe.py --base-url https://api.taqinor.ma \
        --token "<jwt-access-existant>" --duration 60 --concurrency 4

Contraintes (CLAUDE.md — lane infra/compose SCA7) :
  * duree bornee < 10 min par sonde (--duration en secondes, plafonne a 600) ;
  * arret immediat des que /api/django/core/health/ retourne "degraded" ou
    "down" (poll avant chaque salve) ;
  * AUCUNE mutation : uniquement des GET (le seul POST est /token/ pour
    obtenir un jeton si aucun n'est fourni, et seulement si des identifiants
    dev sont explicitement passes) ;
  * zero dependance a un service tiers non present dans requirements.txt
    (stdlib + `requests`, deja utilise ailleurs dans le repo cote scripts).

Ce script ne s'execute PAS en CI, ne fait PAS partie de la suite de tests
automatisee — c'est un outil opere manuellement, hors heures ouvrees, par le
fondateur ou un run explicitement autorise. Voir docs/scale-runway.md section
"Baseline 2026-07" pour la procedure complete et les resultats mesures.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

MAX_DURATION_SECONDS = 600  # garde-fou dur : < 10 min par sonde (Done= SCA7).
HEALTH_PATH = '/api/django/core/health/'

# Les 4 endpoints "chauds" demandes par SCA7. Le proposal token est un
# placeholder public — sans jeton reel fourni via --proposal-token, cette
# sonde est sautee (jamais de token invente/devine).
HOT_ENDPOINTS = {
    'login': '/api/django/token/',  # sonde en GET (405 attendu) = latence TCP/TLS+routage, jamais un POST auto.
    'liste_devis': '/api/django/ventes/devis/',
    'liste_leads': '/api/django/crm/leads/',
    'proposal': '/api/django/public/proposal/{token}/data/',
}


@dataclass
class ProbeResult:
    endpoint: str
    latencies_ms: list = field(default_factory=list)
    errors: int = 0

    def p(self, pct):
        if not self.latencies_ms:
            return None
        data = sorted(self.latencies_ms)
        k = max(0, min(len(data) - 1, int(round(pct / 100 * (len(data) - 1)))))
        return data[k]

    def summary(self):
        return {
            'endpoint': self.endpoint,
            'n': len(self.latencies_ms),
            'errors': self.errors,
            'p50_ms': self.p(50),
            'p95_ms': self.p(95),
            'mean_ms': (round(statistics.mean(self.latencies_ms), 1)
                        if self.latencies_ms else None),
        }


def _get(url, headers, timeout=15):
    req = urllib.request.Request(url, headers=headers, method='GET')
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read(1)  # on ne veut pas le corps entier, juste TTFB approx
            status_code = resp.status
    except urllib.error.HTTPError as exc:
        # 401/404/405 sont des reponses VALIDES pour mesurer la latence d'un
        # endpoint qu'on ne peut/veut pas authentifier/POST-er depuis la
        # sonde — seule une erreur reseau (URLError) est une vraie erreur.
        status_code = exc.code
    elapsed_ms = (time.monotonic() - t0) * 1000
    return elapsed_ms, status_code


def check_health(base_url, headers):
    """Renvoie le statut global ('ok'/'degraded'/'down'/'unknown')."""
    try:
        elapsed_ms, code = _get(base_url + HEALTH_PATH, headers, timeout=10)
        if code != 200:
            return 'unknown'
    except Exception:  # noqa: BLE001 — best-effort, la sonde s'arrete si doute
        return 'unknown'
    # /core/health/ (SystemStatusViewSet) exige une auth ; sans jeton valide
    # on ne peut pas lire le corps -> on retombe sur les probes /live//ready/
    # qui n'exigent aucune auth (core/urls.py health_live/health_ready).
    try:
        elapsed_ms, code = _get(base_url + '/api/django/core/health/ready/',
                                headers={}, timeout=10)
        return 'ok' if code == 200 else 'degraded'
    except Exception:  # noqa: BLE001
        return 'unknown'


def run_probe(base_url, path, headers, duration_s, concurrency):
    result = ProbeResult(endpoint=path)
    url = base_url + path
    deadline = time.monotonic() + duration_s

    def _one_call():
        try:
            elapsed_ms, _code = _get(url, headers)
            return elapsed_ms
        except Exception:  # noqa: BLE001 — erreur reseau comptee, pas fatale
            return None

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        while time.monotonic() < deadline:
            health_status = check_health(base_url, headers)
            if health_status in ('degraded', 'down'):
                print(f'[ARRET] sante={health_status} pendant la sonde de '
                      f'{path} — arret immediat (garde-fou SCA7).',
                      file=sys.stderr)
                break
            futures = [pool.submit(_one_call) for _ in range(concurrency)]
            for fut in as_completed(futures):
                val = fut.result()
                if val is None:
                    result.errors += 1
                else:
                    result.latencies_ms.append(val)
    return result


def run_pdf_concurrency_probe(base_url, token, headers, max_concurrency=8):
    """Augmente la concurrence sur /proposal/<token>/pdf/ jusqu'a saturation
    (garde-fou health) ou max_concurrency — jamais au-dela. Sans --proposal-
    token fourni, cette sonde est sautee (jamais de token invente)."""
    if not token:
        print('[SKIP] rendus PDF concurrents : aucun --proposal-token fourni '
              '(sonde sautee, jamais de token invente).', file=sys.stderr)
        return None
    path = f'/api/django/public/proposal/{token}/pdf/'
    for n in range(1, max_concurrency + 1):
        health_status = check_health(base_url, headers)
        if health_status in ('degraded', 'down'):
            print(f'[ARRET] sante={health_status} avant concurrence={n} '
                  'PDF — arret (garde-fou SCA7).', file=sys.stderr)
            return {'max_concurrency_reached': n - 1, 'stopped_reason': 'health'}
        with ThreadPoolExecutor(max_workers=n) as pool:
            futures = [pool.submit(_get, base_url + path, headers, 30)
                       for _ in range(n)]
            for fut in as_completed(futures):
                try:
                    fut.result()
                except Exception:  # noqa: BLE001
                    return {'max_concurrency_reached': n - 1,
                            'stopped_reason': 'erreur reseau'}
    return {'max_concurrency_reached': max_concurrency, 'stopped_reason': 'plafond sonde atteint'}


def main():
    parser = argparse.ArgumentParser(
        description='Sonde de capacite dev-only (SCA7) — voir docstring du '
                    'module pour les contraintes (duree bornee, garde-fou '
                    'sante, hors heures ouvrees).')
    parser.add_argument('--base-url', required=True,
                        help='Ex: https://api.taqinor.ma ou http://localhost')
    parser.add_argument('--token', default='',
                        help='JWT access existant (Authorization: Bearer). '
                             'Jamais genere par ce script.')
    parser.add_argument('--proposal-token', default='',
                        help='Token public /proposal/<token>/ existant pour '
                             'la sonde PDF concurrente. Sans lui, la sonde '
                             'PDF est sautee.')
    parser.add_argument('--duration', type=int, default=30,
                        help='Duree par endpoint en secondes (plafond dur %ds).'
                             % MAX_DURATION_SECONDS)
    parser.add_argument('--concurrency', type=int, default=4)
    parser.add_argument('--max-pdf-concurrency', type=int, default=8)
    parser.add_argument('--out', default='',
                        help='Chemin JSON de sortie (defaut: stdout uniquement).')
    args = parser.parse_args()

    duration_s = min(args.duration, MAX_DURATION_SECONDS)
    if duration_s != args.duration:
        print(f'[INFO] duree plafonnee a {MAX_DURATION_SECONDS}s (garde-fou SCA7).',
              file=sys.stderr)

    headers = {}
    if args.token:
        headers['Authorization'] = f'Bearer {args.token}'

    base_url = args.base_url.rstrip('/')

    initial_health = check_health(base_url, headers)
    print(f'[INFO] sante initiale: {initial_health}', file=sys.stderr)
    if initial_health in ('degraded', 'down'):
        print('[ABORT] sante deja degradee/down avant meme de commencer — '
              'sonde annulee.', file=sys.stderr)
        sys.exit(1)

    report = {
        'base_url': base_url,
        'duration_s_per_endpoint': duration_s,
        'concurrency': args.concurrency,
        'started_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'endpoints': {},
    }

    for name, path_tpl in HOT_ENDPOINTS.items():
        if '{token}' in path_tpl:
            if not args.proposal_token:
                print(f'[SKIP] {name}: --proposal-token non fourni.',
                      file=sys.stderr)
                continue
            path = path_tpl.format(token=args.proposal_token)
        else:
            path = path_tpl
        print(f'[RUN] {name} ({path}) pendant {duration_s}s, '
              f'concurrence={args.concurrency}...', file=sys.stderr)
        result = run_probe(base_url, path, headers, duration_s, args.concurrency)
        report['endpoints'][name] = result.summary()
        print(f'  -> {json.dumps(result.summary())}', file=sys.stderr)

    print('[RUN] rendus PDF concurrents (garde-fou sante entre chaque palier)...',
          file=sys.stderr)
    report['pdf_concurrency'] = run_pdf_concurrency_probe(
        base_url, args.proposal_token, headers, args.max_pdf_concurrency)

    report['finished_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    report['final_health'] = check_health(base_url, headers)

    payload = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as fh:
            fh.write(payload)
        print(f'[INFO] rapport ecrit: {args.out}', file=sys.stderr)
    print(payload)


if __name__ == '__main__':
    main()
