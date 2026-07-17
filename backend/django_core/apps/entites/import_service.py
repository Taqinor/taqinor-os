"""NTADM43 — Import CSV en masse du référentiel Entités (bootstrap initial).

Self-contained (ne touche pas `apps.dataimport` — app hors périmètre) mais
reprend son esprit : dry-run + commit, résolution des parents par `code` en
2 passes (un enfant peut apparaître avant son parent dans le CSV), erreurs de
ligne remontées avec le numéro de ligne.

Colonnes attendues : `code`, `nom`, `code_parent` (optionnel).
"""
from __future__ import annotations

import csv
import io

from django.db import transaction

from .models import Entite


def _parse_csv(file_bytes, filename):
    text = file_bytes.decode('utf-8-sig') if isinstance(file_bytes, bytes) else file_bytes
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for i, raw in enumerate(reader, start=2):  # ligne 1 = en-têtes
        rows.append((i, {(k or '').strip().lower(): (v or '').strip()
                         for k, v in raw.items()}))
    return rows


def _valider(rows):
    """Renvoie (valides, erreurs) sans écrire. `erreurs` = liste
    {ligne, motif}. Vérifie code présent, unicité intra-fichier, et que tout
    `code_parent` existe (dans le fichier OU déjà en base — vérifié au commit)."""
    erreurs = []
    codes_fichier = set()
    valides = []
    for ligne, row in rows:
        code = row.get('code', '')
        nom = row.get('nom', '')
        if not code:
            erreurs.append({'ligne': ligne, 'motif': 'Code manquant.'})
            continue
        if not nom:
            erreurs.append({'ligne': ligne, 'motif': 'Nom manquant.'})
            continue
        if code in codes_fichier:
            erreurs.append({'ligne': ligne, 'motif': f'Code dupliqué dans le fichier : {code}.'})
            continue
        codes_fichier.add(code)
        valides.append((ligne, row))
    return valides, erreurs


def dry_run(file_bytes, filename, company):
    """NTADM43 — aperçu sans écriture : valide les lignes + vérifie que chaque
    `code_parent` existe (fichier ∪ base)."""
    rows = _parse_csv(file_bytes, filename)
    valides, erreurs = _valider(rows)
    codes_fichier = {row.get('code') for _, row in valides}
    codes_base = set(Entite.objects.filter(company=company).values_list('code', flat=True))
    for ligne, row in valides:
        parent = row.get('code_parent', '')
        if parent and parent not in codes_fichier and parent not in codes_base:
            erreurs.append({'ligne': ligne, 'motif': f'Parent inconnu : {parent}.'})
    return {
        'total': len(rows),
        'valides': len(valides) - sum(
            1 for e in erreurs if any(v[0] == e['ligne'] for v in valides)),
        'erreurs': erreurs,
    }


def commit(file_bytes, filename, company):
    """NTADM43 — importe en 2 passes : (1) crée/actualise toutes les entités
    sans parent, (2) résout les `code_parent` par code. Atomique : toute
    erreur de parent inexistant annule le lot."""
    rows = _parse_csv(file_bytes, filename)
    valides, erreurs = _valider(rows)
    if erreurs:
        return {'created': 0, 'updated': 0, 'erreurs': erreurs, 'total': len(rows)}

    created = updated = 0
    with transaction.atomic():
        # Passe 1 : upsert par (company, code), sans parent.
        for _ligne, row in valides:
            obj, was_created = Entite.objects.update_or_create(
                company=company, code=row['code'],
                defaults={'nom': row['nom']})
            created += 1 if was_created else 0
            updated += 0 if was_created else 1
        # Passe 2 : rattachement des parents par code.
        by_code = {e.code: e for e in Entite.objects.filter(company=company)}
        for ligne, row in valides:
            parent_code = row.get('code_parent', '')
            if not parent_code:
                continue
            parent = by_code.get(parent_code)
            if parent is None:
                raise ValueError(f'Ligne {ligne}: parent inconnu {parent_code}.')
            enfant = by_code[row['code']]
            if enfant.parent_id != parent.id:
                enfant.parent = parent
                enfant.full_clean(exclude=['id'])
                enfant.save(update_fields=['parent', 'updated_at'])
    return {'created': created, 'updated': updated, 'erreurs': [], 'total': len(rows)}
