"""NTI18N45 — Export/import CSV du calendrier de jours fériés multi-pays
(``notifications.Holiday``, NTI18N13/HOLIDAY-PAYS).

``apps.notifications`` n'est PAS une app de fondation exemptée (contrairement
à ``apps.parametres`` — voir ``translations_i18n.py``) : ce module ne
touche jamais ``notifications.models`` directement, il passe par les deux
fonctions minces ajoutées à ``apps.notifications.selectors``
(``holidays_for_export``/``upsert_holiday``).

Permet à une société multi-pays de préparer son calendrier RH hors-ligne
dans un tableur (colonnes ``pays | date | libellé | recurrent_annuel``) et
de l'importer en masse. ``date`` est TOUJOURS au format ISO (``AAAA-MM-JJ``)
— celui produit par l'export, donc un aller-retour export→import fonctionne
toujours ; une autre notation est journalisée en erreur, jamais devinée.

IDEMPOTENT PAR CLÉ ``pays+date`` (critère d'acceptation NTI18N45) — jamais
``date+libellé`` : rejouer le même import deux fois ne crée aucun doublon,
même si le libellé a légèrement changé entre deux imports. ``Holiday``
porte par ailleurs une contrainte d'unicité ``(company, date, nom)``
(antérieure à ce module) : un très rare conflit entre deux pays partageant
EXACTEMENT le même libellé à la même date est journalisé en erreur pour
CETTE ligne seulement, jamais un import qui plante en entier.

Réutilise ``dataimport.ImportJob``/``ImportJobRow`` (``enregistrer_job``)
pour le journal — même patron que ``translations_i18n.py`` (NTI18N29)."""
from __future__ import annotations

import csv
import datetime
import io

from django.db import IntegrityError

from .parsing import iter_rows, normalize_header

FIELDNAMES = ['pays', 'date', 'libelle', 'recurrent_annuel']

TARGET = 'feries'

_VALEURS_VRAIES = ('1', 'true', 'oui', 'vrai', 'yes', 'on')


def _bool_export(valeur):
    return 'oui' if valeur else 'non'


def _bool_import(valeur):
    return str(valeur or '').strip().lower() in _VALEURS_VRAIES


def lignes_export(company):
    """Une ligne par jour férié de la société, triée par pays puis date."""
    from apps.notifications.selectors import holidays_for_export

    lignes = []
    for row in holidays_for_export(company):
        date_valeur = row.get('date')
        lignes.append({
            'pays': row.get('pays') or '',
            'date': date_valeur.isoformat() if date_valeur else '',
            'libelle': row.get('nom') or '',
            'recurrent_annuel': _bool_export(row.get('recurrent_annuel')),
        })
    return lignes


def exporter_feries_csv(company):
    """Le CSV (bytes UTF-8) du calendrier de jours fériés de la société."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=FIELDNAMES)
    writer.writeheader()
    for ligne in lignes_export(company):
        writer.writerow(ligne)
    return buf.getvalue().encode('utf-8')


def importer_feries_csv(file_bytes, filename, company, user=None):
    """Réimporte un CSV de jours fériés : upsert IDEMPOTENT par
    ``(pays, date)`` — voir la docstring de tête du module. ``pays`` absent/
    vide retombe sur ``'MA'`` (même défaut que le modèle ``Holiday``).

    Journalise un ``dataimport.ImportJob`` (``target='feries'``). Renvoie le
    job créé."""
    from apps.notifications.selectors import upsert_holiday

    from .services import enregistrer_job

    headers, rows = iter_rows(file_bytes, filename)
    normalises = {normalize_header(h): h for h in headers}
    col_pays = normalises.get('pays')
    col_date = normalises.get('date')
    col_libelle = normalises.get('libelle')
    col_recurrent = normalises.get('recurrent_annuel')

    lignes_job = []
    created = 0
    updated = 0
    for i, row in enumerate(rows, 1):
        libelle = (
            str(row.get(col_libelle) or '').strip() if col_libelle else '')
        date_brute = (
            str(row.get(col_date) or '').strip() if col_date else '')
        pays = (
            (str(row.get(col_pays) or '').strip().upper() if col_pays
             else '') or 'MA')
        recurrent = (
            _bool_import(row.get(col_recurrent)) if col_recurrent else False)

        if not libelle or not date_brute:
            lignes_job.append({
                'ligne': i, 'statut': 'erreur',
                'motif': 'libellé ou date manquant(e)',
                'donnees': dict(row),
            })
            continue
        try:
            date_valeur = datetime.date.fromisoformat(date_brute)
        except ValueError:
            lignes_job.append({
                'ligne': i, 'statut': 'erreur',
                'motif': (f'date invalide : {date_brute!r} '
                          '(attendu AAAA-MM-JJ)'),
                'donnees': dict(row),
            })
            continue

        try:
            _holiday, cree = upsert_holiday(
                company, pays=pays, date=date_valeur, nom=libelle,
                recurrent_annuel=recurrent)
        except IntegrityError:
            lignes_job.append({
                'ligne': i, 'statut': 'erreur',
                'motif': ('conflit : un autre jour férié porte déjà ce '
                          'libellé à cette date'),
                'donnees': dict(row),
            })
            continue

        if cree:
            created += 1
        else:
            updated += 1
        lignes_job.append({
            'ligne': i, 'statut': 'ok', 'donnees': dict(row),
            'cible': 'notifications.holiday', 'cible_id': None,
            'modifications': [{
                'champ': 'nom', 'ancienne': '', 'nouvelle': libelle[:200],
                'ecrasement': not cree,
            }],
        })

    return enregistrer_job(
        company, TARGET, filename, user=user, mode='maj',
        total_lignes=len(rows), created=created, updated=updated,
        lignes=lignes_job)
