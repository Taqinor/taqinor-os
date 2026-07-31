"""NTADM43 — Import CSV en masse du référentiel Entités (bootstrap initial).

Dry-run + commit, résolution des parents par `code` en 2 passes (un enfant
peut apparaître avant son parent dans le CSV), erreurs de ligne remontées
avec le numéro de ligne.

Colonnes attendues : `code`, `nom`, `code_parent` (optionnel).

GARDE-FOU ÉCRASEMENT (audit ARC/NTADM) — une entité DÉJÀ EN BASE (rapprochée
par `(company, code)`) est une fiche RÉELLE, potentiellement corrigée à la
main après l'import initial. `commit()` ne réécrit donc plus jamais `nom`/
`parent` en silence : chaque écriture sur une fiche EXISTANTE passe par la
primitive plateforme `apps.dataimport.services.appliquer_maj_import`
(remplissage seul par défaut — `ecraser=True` = opt-in explicite qui applique
aussi les remplacements) — jamais un diff/journal maison (dette #1 mesurée du
dépôt). `dry_run()` prévisualise les mêmes écrasements champ par champ via la
primitive `diff_import` (lecture seule), SANS RIEN écrire. Une cellule vide
(`nom` toujours requis par `_valider`, `code_parent` optionnel — une ligne
sans parent ne touche jamais un rattachement existant) ne remplace ni ne vide
jamais un champ déjà rempli. Une CRÉATION (code absent de la base) n'a rien à
écraser et s'écrit directement.
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
    """NTADM43 — aperçu sans écriture : valide les lignes, vérifie que chaque
    `code_parent` existe (fichier ∪ base), et — garde-fou écrasement —
    signale champ par champ (`conflits`) ce qu'une fiche EXISTANTE (`code`
    déjà en base) verrait remplacer : `nom`, et `parent` quand le nouveau
    parent est lui-même déjà en base (un parent qui n'apparaît que plus loin
    dans le même fichier n'est pas encore comparable, il ne peut donc pas
    encore être annoncé comme un écrasement).

    Réutilise la primitive plateforme LECTURE SEULE
    `apps.dataimport.services.diff_import` — jamais un diff maison. N'écrit
    rien, quel que soit le contenu du fichier."""
    from apps.dataimport.services import diff_import

    rows = _parse_csv(file_bytes, filename)
    valides, erreurs = _valider(rows)
    codes_fichier = {row.get('code') for _, row in valides}
    codes_base = set(Entite.objects.filter(company=company).values_list('code', flat=True))
    existantes = {
        e.code: e for e in Entite.objects.filter(company=company, code__in=codes_fichier)
    }
    conflits = []
    for ligne, row in valides:
        parent_code = row.get('code_parent', '')
        if parent_code and parent_code not in codes_fichier and parent_code not in codes_base:
            erreurs.append({'ligne': ligne, 'motif': f'Parent inconnu : {parent_code}.'})
            continue
        instance = existantes.get(row['code'])
        if instance is None:
            continue  # nouvelle entité : rien à écraser
        fields = {'nom': row['nom']}
        if parent_code:
            parent_obj = existantes.get(parent_code) or Entite.objects.filter(
                company=company, code=parent_code).first()
            if parent_obj is not None:
                fields['parent'] = parent_obj
        ecrasements, _remplissages = diff_import(
            instance, fields, skip_keys=('company', 'code'))
        if ecrasements:
            conflits.append({'ligne': ligne, 'code': row['code'], 'ecrasements': ecrasements})
    return {
        'total': len(rows),
        'valides': len(valides) - sum(
            1 for e in erreurs if any(v[0] == e['ligne'] for v in valides)),
        'erreurs': erreurs,
        # NTADM43 + garde-fou : ce qu'un `commit()` de ce même fichier
        # remplacerait réellement sur des fiches existantes (voir docstring).
        'conflits': conflits,
    }


def commit(file_bytes, filename, company, user=None, ecraser=False):
    """NTADM43 — importe en 2 passes : (1) crée les entités absentes / rapproche
    celles déjà en base par `(company, code)`, (2) résout les `code_parent`
    par code. Atomique : toute erreur de parent inexistant annule le lot.

    GARDE-FOU ÉCRASEMENT — une fiche déjà en base (rapprochée par code) n'est
    jamais réécrite en silence : `nom` (passe 1) et `parent` (passe 2)
    passent chacun par la primitive plateforme
    `apps.dataimport.services.appliquer_maj_import`. `ecraser=False`
    (défaut) = remplissage seul : un champ déjà rempli est laissé intact, la
    valeur du fichier repart dans `refuses` de la ligne concernée.
    `ecraser=True` = opt-in explicite de l'appelant qui applique aussi ces
    remplacements. Une création (code absent de la base) n'a rien à écraser
    et s'écrit directement.

    Chaque fiche modifiée par un rapprochement laisse sa valeur PRÉCÉDENTE
    (retour `ecrasements`/`refuses`, et une ligne d'audit via
    `appliquer_maj_import`) ; le lot entier est en plus journalisé dans
    `ImportJob`/`ImportJobRow` via `enregistrer_job` — même journal que les
    autres importeurs de la plateforme, jamais un journal maison.
    """
    from apps.dataimport.services import appliquer_maj_import, enregistrer_job

    rows = _parse_csv(file_bytes, filename)
    valides, erreurs = _valider(rows)
    if erreurs:
        return {'created': 0, 'updated': 0, 'erreurs': erreurs, 'total': len(rows),
                'ecrasements': [], 'refuses': []}

    created = updated = 0
    instances = {}  # ligne -> Entite (créée ou rapprochée par code)
    maj = {}        # ligne -> {'modifications': [...], 'refuses': [...]}

    def _fusionner(ligne, modifications, refuses):
        entry = maj.setdefault(ligne, {'modifications': [], 'refuses': []})
        entry['modifications'].extend(modifications)
        entry['refuses'].extend(refuses)

    with transaction.atomic():
        # Passe 1 : crée les entités absentes ; celles déjà en base ne voient
        # leur `nom` réécrit qu'à travers le garde-fou (remplissage seul par
        # défaut, `ecraser=True` = opt-in).
        for ligne, row in valides:
            instance = Entite.objects.filter(company=company, code=row['code']).first()
            if instance is None:
                instance = Entite.objects.create(
                    company=company, code=row['code'], nom=row['nom'])
                created += 1
            else:
                updated += 1
                _changed, modifications, refuses = appliquer_maj_import(
                    instance, {'nom': row['nom']}, company, user=user,
                    filename=filename, skip_keys=('company', 'code'), ecraser=ecraser)
                _fusionner(ligne, modifications, refuses)
            instances[ligne] = instance

        # Passe 2 : rattachement des parents par code — même garde-fou (un
        # rattachement déjà en place n'est jamais remplacé sans ecraser=True).
        by_code = {e.code: e for e in Entite.objects.filter(company=company)}
        for ligne, row in valides:
            parent_code = row.get('code_parent', '')
            if not parent_code:
                continue
            parent = by_code.get(parent_code)
            if parent is None:
                raise ValueError(f'Ligne {ligne}: parent inconnu {parent_code}.')
            enfant = by_code[row['code']]
            _changed, modifications, refuses = appliquer_maj_import(
                enfant, {'parent': parent}, company, user=user, filename=filename,
                skip_keys=('company', 'code'), ecraser=ecraser)
            _fusionner(ligne, modifications, refuses)

    lignes_job = []
    for ligne, row in valides:
        detail = maj.get(ligne, {'modifications': [], 'refuses': []})
        lignes_job.append({
            'ligne': ligne, 'statut': 'ok', 'motif': None, 'donnees': dict(row),
            'cible': 'entites.entite', 'cible_id': instances[ligne].pk,
            'modifications': detail['modifications'], 'refuses': detail['refuses'],
        })
    enregistrer_job(
        company, 'entites', filename, user=user, mode='maj', ecraser=ecraser,
        total_lignes=len(rows), created=created, updated=updated, lignes=lignes_job)

    ecrasements = [dict(m, ligne=ligne) for ligne, detail in maj.items()
                   for m in detail['modifications'] if m['ecrasement']]
    refuses = [dict(r, ligne=ligne) for ligne, detail in maj.items()
               for r in detail['refuses']]
    return {'created': created, 'updated': updated, 'erreurs': [], 'total': len(rows),
            'ecrasements': ecrasements, 'refuses': refuses}
