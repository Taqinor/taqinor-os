"""NTI18N29 — Export/import CSV du catalogue de traductions (Paramètres →
Traductions), pour relecture humaine hors-ligne par un traducteur externe.

``apps.parametres`` est une app de FONDATION (exemptée de la frontière
selectors/services, comme ``core``/``roles``/``authentication`` — voir
CLAUDE.md) : ce module importe directement
``parametres.models_translations.TranslationOverride``, jamais un import
d'app métier au sens du contrat import-linter (parametres n'y est pas soumis).

PÉRIMÈTRE HONNÊTE — seules les clés qui portent DÉJÀ au moins une surcharge
(``TranslationOverride``) sont exportables ici : le catalogue STATIQUE des
clés i18n (N93) vit côté frontend (JS), pas en base — l'exporter exigerait un
inventaire côté build frontend, hors périmètre de ce module. Un traducteur
qui corrige des surcharges déjà saisies (le cas d'usage visé : relire/ajuster
des libellés déjà personnalisés) est donc pleinement couvert ; découvrir des
clés JAMAIS encore surchargées ne l'est pas — jamais un inventaire inventé.

Réutilise ``dataimport.ImportJob``/``ImportJobRow`` (``enregistrer_job``)
pour le journal, mapping simple clé→valeur (une ligne CSV = une clé, une
colonne par locale) — pas le pipeline générique ``dry_run``/``commit`` (qui
mappe UNE ligne à UN seul champ d'UN seul modèle ; une ligne de ce CSV écrit
jusqu'à 3 ``TranslationOverride`` différentes, une par locale renseignée).
"""
from __future__ import annotations

import csv
import io

from .parsing import iter_rows, normalize_header

LOCALES = ('fr', 'en', 'ar')

FIELDNAMES = ['cle', 'fr', 'en', 'ar', 'statut_traduction']

STATUT_COMPLET = 'complet'
STATUT_INCOMPLET = 'incomplet'

TARGET = 'traductions'


def lignes_export(company):
    """Une ligne par clé i18n SURCHARGÉE (au moins une locale), triées par
    clé. ``statut_traduction`` vaut ``'complet'`` quand les 3 locales sont
    renseignées, ``'incomplet'`` sinon (jamais un booléen par locale — la
    colonne fr/en/ar montre déjà la valeur exacte manquante ou présente)."""
    from apps.parametres.models_translations import TranslationOverride

    par_locale = TranslationOverride.overrides_for_company(company)
    cles = sorted({cle for valeurs in par_locale.values() for cle in valeurs})
    lignes = []
    for cle in cles:
        valeurs = {locale: par_locale.get(locale, {}).get(cle, '')
                   for locale in LOCALES}
        complet = all(valeurs[locale] for locale in LOCALES)
        lignes.append({
            'cle': cle, **valeurs,
            'statut_traduction': STATUT_COMPLET if complet else STATUT_INCOMPLET,
        })
    return lignes


def exporter_traductions_csv(company):
    """Le CSV (bytes UTF-8) des surcharges de traduction de la société."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=FIELDNAMES)
    writer.writeheader()
    for ligne in lignes_export(company):
        writer.writerow(ligne)
    return buf.getvalue().encode('utf-8')


def importer_traductions_csv(file_bytes, filename, company, user=None):
    """Réimporte un CSV corrigé : pour chaque ligne, upsert la valeur de
    chaque locale FOURNIE (colonne présente et non vide) — une colonne
    ABSENTE ou vide laisse la surcharge existante INTACTE (jamais un
    effacement silencieux ; pour supprimer une surcharge, l'écran Traductions
    existant reste le chemin, pas cet import de relecture).

    Journalise un ``dataimport.ImportJob`` (``target='traductions'``) — même
    primitive que tout autre import, réversible/auditable via le même écran.
    Renvoie le job créé.
    """
    from apps.parametres.models_translations import TranslationOverride

    from .services import enregistrer_job

    headers, rows = iter_rows(file_bytes, filename)
    normalises = {normalize_header(h): h for h in headers}
    col_cle = normalises.get('cle')

    lignes_job = []
    created = 0
    updated = 0
    for i, row in enumerate(rows, 1):
        cle = (row.get(col_cle) if col_cle else None) or ''
        cle = str(cle).strip()
        if not cle:
            lignes_job.append({
                'ligne': i, 'statut': 'erreur', 'motif': 'clé manquante',
                'donnees': dict(row),
            })
            continue
        modifications = []
        for locale in LOCALES:
            col = normalises.get(locale)
            if not col:
                continue
            valeur = row.get(col)
            if valeur is None or str(valeur).strip() == '':
                continue
            valeur = str(valeur)
            obj, cree = TranslationOverride.objects.update_or_create(
                company=company, locale=locale, key=cle,
                defaults={'value': valeur})
            if cree:
                created += 1
            else:
                updated += 1
            modifications.append({
                'champ': locale, 'ancienne': '', 'nouvelle': valeur[:200],
                'ecrasement': not cree,
            })
        lignes_job.append({
            'ligne': i, 'statut': 'ok', 'donnees': dict(row),
            'cible': 'parametres.translationoverride', 'cible_id': None,
            'modifications': modifications,
        })

    return enregistrer_job(
        company, TARGET, filename, user=user, mode='maj',
        total_lignes=len(rows), created=created, updated=updated,
        lignes=lignes_job)
