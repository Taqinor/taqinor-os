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
