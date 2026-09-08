"""Génère ``backend/django_core/apps/parametres/data/lieux_maroc.tsv.gz`` (lieux-dits).

Source : le MÊME export GeoNames du Maroc que ``build_villes_maroc.py``
(https://download.geonames.org/export/dump/MA.zip, licence CC-BY 4.0). Usage ::

    python scripts/build_lieux_maroc.py chemin/vers/MA.txt

VREF-LIEUX (fondateur 08/09/2026, cas « Sidi Hashass ») : le gazetier des
VILLES (409 entrées, population >= 5 000 + chefs-lieux) ignore les douars par
construction, et Nominatim (OpenStreetMap) n'en connaît qu'une minorité —
Google, lui, les place. GeoNames recense pourtant ~47 000 lieux habités du
Maroc (classe ``P`` : douars, quartiers, hameaux). Ce script les écrit TOUS,
sans filtre de population, dans un TSV compressé lu paresseusement par
``apps/parametres/lieux_maroc.py``.

Colonnes : nom GeoNames, latitude, longitude, code admin1 (région),
orthographes alternatives latines (séparées par des virgules). Coordonnées
recopiées VERBATIM (des FAITS, jamais une estimation) — règle « zéro chiffre
inventé ». Le fichier est trié et compressé sans horodatage : deux
générations sur le même export donnent des octets identiques.
"""
from __future__ import annotations

import gzip
import io
import sys
import unicodedata
from datetime import date
from pathlib import Path

SORTIE = (Path(__file__).resolve().parent.parent / 'backend' / 'django_core'
          / 'apps' / 'parametres' / 'data' / 'lieux_maroc.tsv.gz')

CLASSE_LIEU_HABITE = 'P'


def _normaliser(texte: str) -> str:
    txt = str(texte or '').strip().lower()
    txt = txt.replace('-', ' ').replace("'", ' ').replace('’', ' ')
    txt = unicodedata.normalize('NFKD', txt)
    txt = ''.join(c for c in txt if not unicodedata.combining(c))
    return ' '.join(txt.split())


def _alternates_latins(brut, nom):
    """Orthographes alternatives latines (ASCII a-z, 1 à 4 mots), distinctes
    du nom principal une fois normalisées. Les écritures arabes/tifinagh et
    les codes courts (< 4 caractères) sont écartés."""
    vus = {_normaliser(nom)}
    for alt in (brut or '').split(','):
        cle = _normaliser(alt)
        if not cle or len(cle) < 4 or len(cle.split()) > 4 or cle in vus:
            continue
        if not all(c == ' ' or 'a' <= c <= 'z' for c in cle):
            continue
        vus.add(cle)
        yield alt.strip()


def lire_lieux(chemin):
    lieux = []
    with open(chemin, encoding='utf-8') as fh:
        for ligne in fh:
            cols = ligne.rstrip('\n').split('\t')
            if len(cols) < 15 or cols[6] != CLASSE_LIEU_HABITE:
                continue
            nom = cols[1].strip()
            if not nom or '\t' in nom:
                continue
            try:
                float(cols[4]), float(cols[5])  # coordonnées lisibles, sinon ligne ignorée
            except ValueError:
                continue
            alternates = ','.join(_alternates_latins(cols[3], nom))
            lieux.append((nom, cols[4], cols[5], cols[10].strip(), alternates))
    lieux.sort(key=lambda lieu: (_normaliser(lieu[0]), lieu[1], lieu[2]))
    return lieux


def ecrire(lieux, sortie=SORTIE):
    entete = (f'# GeoNames MA (download.geonames.org/export/dump/MA.zip, CC-BY 4.0) '
              f'— classe P (lieux habités), {len(lieux)} lieux, généré le '
              f'{date.today().isoformat()} par scripts/build_lieux_maroc.py. '
              f'Colonnes : nom, lat, lng, admin1, alternates.\n')
    tampon = io.BytesIO()
    with gzip.GzipFile(filename='', mode='wb', fileobj=tampon, mtime=0,
                       compresslevel=9) as gz:
        gz.write(entete.encode('utf-8'))
        for lieu in lieux:
            gz.write(('\t'.join(lieu) + '\n').encode('utf-8'))
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_bytes(tampon.getvalue())
    return len(tampon.getvalue())


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    lieux = lire_lieux(sys.argv[1])
    octets = ecrire(lieux)
    print(f'{len(lieux)} lieux habités écrits dans {SORTIE} ({octets} octets)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
