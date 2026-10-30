"""ENF11 — inventaire des ids RÉELS pour les paramètres de chemin du fuzz.

1 273 opérations du nocturne ne recevaient que des 404 (« Missing valid test
data ») : seuls les FK du corps avaient des ids connus. Ce script tourne
APRÈS le démarrage de gunicorn et la génération du schéma : il se connecte
en ``fuzz_admin``, lit la première page de chaque liste ``GET /x/`` (celles
qui ont un détail ``/x/{id}/`` au schéma) et écrit ``{préfixe: [ids]}`` dans
``FUZZ_IDS_FILE`` ; ``schemathesis_hooks.py`` s'en sert dans ``before_call``.

Lancé par ``api-fuzz-full`` (16 tranches) ET par ``api-fuzz-pr`` (8 tranches,
même étape) : les cas positifs du job PR reçoivent les mêmes ids réels que le
nocturne. Les listes sont lues par ``--workers`` fils (3 = les 3 workers
gunicorn du serveur de fuzz) — lectures seules, faites AVANT le fuzz, donc sans
effet sur l'ordre des écritures ; la durée est imprimée pour la mesurer.

Usage : python inventorier_ids_chemin.py --schema openapi-schema.json --out ids.json
Env   : FUZZ_BASE_URL, FUZZ_USERNAME, FUZZ_PASSWORD
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

MAX_IDS = 25
_PARAM_ID = re.compile(r'^(.*/)\{(?:id|pk)\}/')


def parser_ids(charge) -> list:
    """Ids d'une réponse de liste DRF (paginée ``results`` ou nue)."""
    lignes = charge.get('results') if isinstance(charge, dict) else charge
    if not isinstance(lignes, list):
        return []
    ids = []
    for ligne in lignes:
        if not isinstance(ligne, dict):
            continue
        valeur = ligne.get('id', ligne.get('pk'))
        if isinstance(valeur, bool) or not isinstance(valeur, (int, str)):
            continue
        if valeur != '' and valeur not in ids:
            ids.append(valeur)
    return ids[:MAX_IDS]


def collections_du_schema(doc: dict) -> list:
    """Chemins de liste ``GET`` dont un détail ``{id}``/``{pk}`` existe."""
    chemins = doc.get('paths') or {}
    prefixes = set()
    for gabarit in chemins:
        m = _PARAM_ID.match(gabarit)
        if m:
            prefixes.add(m.group(1))
    return sorted(
        p for p in prefixes
        if 'get' in (chemins.get(p) or {}) and '{' not in p)


def inventorier(doc: dict, lire, workers: int = 1) -> dict:
    """``lire(chemin) -> charge JSON ou None`` ; renvoie {préfixe: ids}.

    ``workers`` > 1 lit les listes en parallèle ; la table produite est
    identique (même ordre, mêmes ids) quel que soit le nombre de fils.
    """
    prefixes = collections_du_schema(doc)
    if workers > 1 and len(prefixes) > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            charges = list(pool.map(lire, prefixes))
    else:
        charges = [lire(p) for p in prefixes]
    table = {}
    for prefixe, charge in zip(prefixes, charges):
        ids = parser_ids(charge)
        if ids:
            table[prefixe] = ids
    return table


def main(argv=None) -> int:
    import requests

    ap = argparse.ArgumentParser()
    ap.add_argument('--schema', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--workers', type=int, default=3)
    args = ap.parse_args(argv)
    debut = time.monotonic()
    base = os.environ.get('FUZZ_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
    session = requests.Session()
    rep = session.post(
        f'{base}/api/django/token/',
        json={'username': os.environ.get('FUZZ_USERNAME', 'fuzz_admin'),
              'password': os.environ.get('FUZZ_PASSWORD', '')}, timeout=120)
    if rep.status_code != 200:
        print(f'connexion refusée : HTTP {rep.status_code}', file=sys.stderr)
        return 1
    with open(args.schema, encoding='utf-8') as fh:
        doc = json.load(fh)

    # Une session par fil (requests.Session n'est pas garantie thread-safe),
    # chacune avec les cookies de la connexion ci-dessus.
    local = threading.local()

    def lire(chemin):
        s = getattr(local, 'session', None)
        if s is None:
            s = local.session = requests.Session()
            s.cookies.update(session.cookies)
        try:
            r = s.get(base + chemin, timeout=60)
            return r.json() if r.status_code == 200 else None
        except (requests.RequestException, ValueError):
            return None

    table = inventorier(doc, lire, workers=max(1, args.workers))
    with open(args.out, 'w', encoding='utf-8') as fh:
        json.dump(table, fh, ensure_ascii=False, indent=1, sort_keys=True)
    total = len(collections_du_schema(doc))
    print(f'ids de chemin : {len(table)}/{total} collections avec ids réels '
          f'en {time.monotonic() - debut:.1f} s ({max(1, args.workers)} fils)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
