"""YOPSB6 — Helper d'index concurrent + ``lock_timeout`` pour les migrations
d'index sur des tables à forte croissance.

Couche de FONDATION pure (aucune importation d'app domaine) : construit une
CLASSE ``Migration`` prête à l'emploi qui pose un index sans verrou d'écriture
bloquant sur une table déjà peuplée en production (``crm_lead``,
``ventes_devis``, ``installations_intervention``…).

Conception
----------

Créer un index « normalement » (``AddIndex`` dans une migration
``atomic=True`` par défaut) verrouille la table en ÉCRITURE pendant toute la
construction — inacceptable sur une table à fort trafic en production.
``AddIndexConcurrently`` (Postgres ``CREATE INDEX CONCURRENTLY``) construit
l'index SANS bloquer les écritures, mais :

  * exige ``atomic = False`` (impossible dans une transaction) ;
  * peut échouer/rester bloqué indéfiniment si une AUTRE transaction tient un
    verrou long — d'où le ``RunSQL(\"SET lock_timeout = '3s'\")`` initial qui
    fait échouer VITE plutôt que de geler la base entière.

Utilisation (dans un fichier de migration d'app) ::

    from core.migrations_utils import concurrent_index_migration

    Migration = concurrent_index_migration(
        app_label='crm', dependencies=[('crm', '0030_pointcontact')],
        model_name='lead', fields=['statut'], index_name='crm_lead_statut_idx')

Convention documentée dans ``docs/CODEMAP.md`` §7 : tout NOUVEL index sur une
table à forte croissance passe par ce helper plutôt qu'un ``AddIndex`` nu.
"""
from __future__ import annotations

import time

from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


def concurrent_index_migration(app_label, dependencies, model_name, fields,
                               index_name):
    """Construit une classe ``Migration`` prête (``atomic=False`` +
    ``lock_timeout`` + ``AddIndexConcurrently``) pour poser ``index_name`` sur
    ``model_name.fields`` sans verrou d'écriture bloquant.

    ``dependencies`` : liste de tuples ``(app_label, migration_name)``, comme
    tout fichier de migration Django standard.
    Renvoie la CLASSE (pas une instance) — à assigner à ``Migration`` dans le
    fichier de migration appelant."""

    class ConcurrentIndexMigration(migrations.Migration):
        # CREATE INDEX CONCURRENTLY est interdit dans une transaction —
        # Django l'exige explicitement pour AddIndexConcurrently.
        atomic = False

        operations = [
            # Échoue vite (3s) plutôt que de geler la base si un autre verrou
            # long est déjà tenu sur la table cible.
            migrations.RunSQL(
                sql="SET lock_timeout = '3s';",
                reverse_sql=migrations.RunSQL.noop,
            ),
            AddIndexConcurrently(
                model_name=model_name,
                index=models.Index(fields=fields, name=index_name),
            ),
        ]

    ConcurrentIndexMigration.dependencies = list(dependencies)
    return ConcurrentIndexMigration


# ---------------------------------------------------------------------------
# NTPLT56 — Backfill par lots + ajout d'une colonne NOT NULL SANS verrou long.
#
# Leçon directe de l'incident « AddField(unique) sur base peuplée » : ajouter
# une colonne NOT NULL (ou remplir une colonne) en UNE passe verrouille la
# table le temps de réécrire toutes les lignes — inacceptable en prod à fort
# trafic. Ces helpers découpent le travail en LOTS avec une pause entre
# chaque, de sorte que les futures migrations sur tables peuplées ne bloquent
# plus la prod.
# ---------------------------------------------------------------------------


def batched_backfill(model, fn, batch=1000, pause_ms=50):
    """Applique ``fn(instance)`` à toutes les lignes de ``model`` par lots.

    * ``model`` : classe de modèle (ou un queryset — on itère alors dessus).
    * ``fn(instance)`` : mute l'instance en place (ou renvoie les champs à
      sauver). Chaque lot est parcouru puis ``bulk_update`` n'est PAS présumé —
      ``fn`` est responsable d'appeler ``instance.save(update_fields=...)`` si
      besoin ; on fournit aussi ``bulk=`` plus bas pour le cas courant.
    * ``batch`` : taille de lot (défaut 1000) — borne la durée d'un verrou.
    * ``pause_ms`` : pause entre lots (défaut 50 ms) — laisse respirer les
      écritures concurrentes.

    Parcourt par ``pk`` croissant via un curseur keyset (jamais d'OFFSET
    profond). Renvoie le nombre total de lignes traitées. Conçu pour
    ``RunPython`` : ``fn`` doit être idempotent (une migration peut être
    rejouée).
    """
    qs = model if hasattr(model, 'order_by') else model._default_manager.all()
    qs = qs.order_by('pk')
    last_pk = None
    total = 0
    while True:
        chunk_qs = qs.filter(pk__gt=last_pk) if last_pk is not None else qs
        chunk = list(chunk_qs[:batch])
        if not chunk:
            break
        for instance in chunk:
            fn(instance)
        last_pk = chunk[-1].pk
        total += len(chunk)
        if len(chunk) < batch:
            break
        if pause_ms:
            time.sleep(pause_ms / 1000.0)
    return total


def add_not_null_safe(model_name, field_name, field, backfill_fn,
                      batch=1000, pause_ms=50):
    """Construit les 3 opérations d'un ajout de colonne NOT NULL SANS verrou.

    Pattern en 3 temps, sûr sur une table peuplée :
      1. ``AddField`` de la colonne en ``null=True`` (instantané) ;
      2. ``RunPython`` de backfill PAR LOTS (``backfill_fn(apps, schema_editor)``
         appelle typiquement ``batched_backfill``) ;
      3. ``AlterField`` vers la contrainte définitive (``null=False``).

    ``field`` est l'instance de champ FINALE (``null=False``) ; on en dérive
    automatiquement la variante nullable pour l'étape 1. Renvoie la LISTE
    d'opérations à insérer dans ``Migration.operations``.
    """
    from django.db import migrations

    nullable = field.clone()
    nullable.null = True

    return [
        migrations.AddField(
            model_name=model_name, name=field_name, field=nullable),
        migrations.RunPython(
            backfill_fn, migrations.RunPython.noop),
        migrations.AlterField(
            model_name=model_name, name=field_name, field=field),
    ]
