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
    verrou long — d'où le ``SET lock_timeout = '3s'`` posé autour de la
    construction, qui fait échouer VITE plutôt que de geler la base entière.

Le ``lock_timeout`` est REMIS dans un ``finally`` (revue critique du
25/08/2026, finding #11). Une migration ``atomic=False`` s'exécute en
autocommit : un ``SET`` y vaut pour toute la SESSION, donc pour TOUTE LA SUITE
du plan de migration. Laissé à 3 s, il faisait avorter sous trafic la première
opération lourde qui suit (``ventes/0103``, un UNIQUE = ACCESS EXCLUSIVE) —
c'est-à-dire l'état dangereux « code déployé, migrations non appliquées ».

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

import logging

logger = logging.getLogger(__name__)


#: Délai d'attente d'un verrou pendant la construction d'un index concurrent.
#: Échouer vite vaut mieux que geler la base — mais uniquement PENDANT cette
#: opération (voir :class:`_AddIndexConcurrentlyBorne`).
LOCK_TIMEOUT_INDEX = '3s'
# ENF12 (semgrep no-formatted-raw-sql) : instruction CONSTANTE figée à l'import
# (aucune donnée d'exécution n'y entre).
_SQL_LOCK_TIMEOUT = f"SET lock_timeout = '{LOCK_TIMEOUT_INDEX}';"


class _AddIndexConcurrentlyBorne(AddIndexConcurrently):
    """``AddIndexConcurrently`` dont le ``lock_timeout`` est RENDU après coup.

    Finding #11 (revue critique 25/08/2026). Le réglage était posé par un
    ``RunSQL`` séparé et n'était JAMAIS remis : en ``atomic=False`` (donc en
    autocommit), un ``SET`` vaut pour toute la session, et les migrations
    SUIVANTES du même ``manage.py migrate`` héritaient d'un ``lock_timeout``
    de 3 s. Sous trafic, la première opération lourde d'après (un ``UNIQUE``,
    qui prend un ACCESS EXCLUSIVE) avortait — laissant la prod dans l'état le
    plus dangereux qui soit : code déployé, migrations non appliquées.

    Le ``RESET`` est dans un ``finally`` : il a lieu que l'index se construise
    ou qu'il échoue, et son propre échec n'écrase jamais l'erreur d'origine.
    """

    def database_forwards(self, app_label, schema_editor, from_state,
                          to_state):
        # ``AddIndexConcurrently`` est déjà PostgreSQL-seul ; la garde évite
        # simplement d'émettre du SQL non portable si un backend tiers passait
        # par là.
        postgres = getattr(
            schema_editor.connection, 'vendor', '') == 'postgresql'
        if postgres:
            schema_editor.execute(_SQL_LOCK_TIMEOUT)
        try:
            super().database_forwards(
                app_label, schema_editor, from_state, to_state)
        finally:
            if postgres:
                try:
                    schema_editor.execute('RESET lock_timeout;')
                except Exception:  # noqa: BLE001 — ne masque jamais l'erreur (D-ENF22-BLE001)
                    logger.warning("database forwards : échec ignoré, comportement dégradé", exc_info=True)


def concurrent_index_migration(app_label, dependencies, model_name, fields,
                               index_name, index_class=models.Index,
                               condition=None):
    """Construit une classe ``Migration`` prête (``atomic=False`` +
    ``lock_timeout`` borné + ``AddIndexConcurrently``) pour poser ``index_name``
    sur ``model_name.fields`` sans verrou d'écriture bloquant.

    ``dependencies`` : liste de tuples ``(app_label, migration_name)``, comme
    tout fichier de migration Django standard.
    ``index_class`` (NTPLT32) : ``models.Index`` par défaut (B-tree, inchangé) ;
    ``GinIndex`` pour un ``SearchVectorField`` — même pose concurrente.
    ``condition`` (NTPLT33) : un ``Q`` pour un index PARTIEL (``WHERE …``).
    Renvoie la CLASSE (pas une instance) — à assigner à ``Migration`` dans le
    fichier de migration appelant."""

    class ConcurrentIndexMigration(migrations.Migration):
        # CREATE INDEX CONCURRENTLY est interdit dans une transaction —
        # Django l'exige explicitement pour AddIndexConcurrently.
        atomic = False

        operations = [
            # Le ``lock_timeout`` (échouer vite plutôt que geler la base) est
            # posé ET REMIS par l'opération elle-même : un ``RunSQL`` séparé
            # laissait le réglage fuir sur toute la suite du plan (finding #11).
            _AddIndexConcurrentlyBorne(
                model_name=model_name,
                index=index_class(
                    fields=fields, name=index_name,
                    **({'condition': condition} if condition is not None else {})),
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


# ---------------------------------------------------------------------------
# NTPLT34 — index GIN TRIGRAMME (pg_trgm) posés CONCURREMMENT, sans jamais
# faire échouer ``migrate``.
#
# Même raison que STKCAT27 (stock/0148) : le rôle applicatif de la production
# n'a pas forcément le droit de ``CREATE EXTENSION``. Une migration qui
# planterait laisserait l'état le plus dangereux (« code déployé, migrations
# non appliquées »). Ici : extension tentée, index posé SEULEMENT si pg_trgm
# est présent (``schema_editor.add_index(..., concurrently=True)`` : SQL
# construit par Django, ``lock_timeout`` borné puis REMIS), tout échec devient
# un AVERTISSEMENT journalisé. Les index ne sont PAS dans ``Meta.indexes``
# (Django ne doit pas vouloir les recréer sur une base sans l'extension) :
# aucun état de modèle ne bouge. Idempotent (index existant : ignoré).
# ---------------------------------------------------------------------------

_SQL_EXTENSION_TRGM = 'CREATE EXTENSION IF NOT EXISTS pg_trgm;'
_SQL_SONDE_TRGM = "SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm';"


def _extension_trgm_presente(connexion):
    with connexion.cursor() as curseur:
        curseur.execute(_SQL_SONDE_TRGM)
        return curseur.fetchone() is not None


def _index_existe(connexion, table, nom):
    with connexion.cursor() as curseur:
        return nom in connexion.introspection.get_constraints(curseur, table)


def _index_trigramme(champ, nom):
    from django.contrib.postgres.indexes import GinIndex
    return GinIndex(fields=[champ], name=nom, opclasses=['gin_trgm_ops'])


def _poser_trigrammes(apps, schema_editor, app_label, cibles):
    connexion = schema_editor.connection
    if getattr(connexion, 'vendor', '') != 'postgresql':
        return
    try:
        schema_editor.execute(_SQL_EXTENSION_TRGM)
    except Exception:  # noqa: BLE001 — droits insuffisants : jamais bloquant (D-ENF22-BLE001)
        logger.warning('NTPLT34 : CREATE EXTENSION pg_trgm refusé', exc_info=True)
    if not _extension_trgm_presente(connexion):
        logger.warning('NTPLT34 : pg_trgm absente — index trigramme non posés '
                       "(l'autocomplétion retombe sur icontains).")
        return
    for model_name, champ, nom in cibles:
        modele = apps.get_model(app_label, model_name)
        if _index_existe(connexion, modele._meta.db_table, nom):
            continue
        schema_editor.execute(_SQL_LOCK_TIMEOUT)
        try:
            schema_editor.add_index(modele, _index_trigramme(champ, nom),
                                    concurrently=True)
        except Exception:  # noqa: BLE001 — jamais bloquant (D-ENF22-BLE001)
            logger.warning('NTPLT34 : index %s non posé', nom, exc_info=True)
        finally:
            try:
                schema_editor.execute('RESET lock_timeout;')
            except Exception:  # noqa: BLE001 — ne masque rien (D-ENF22-BLE001)
                logger.warning('NTPLT34 : RESET lock_timeout échoué', exc_info=True)


def _retirer_trigrammes(apps, schema_editor, app_label, cibles):
    connexion = schema_editor.connection
    if getattr(connexion, 'vendor', '') != 'postgresql':
        return
    for model_name, champ, nom in cibles:
        modele = apps.get_model(app_label, model_name)
        if _index_existe(connexion, modele._meta.db_table, nom):
            schema_editor.remove_index(modele, _index_trigramme(champ, nom),
                                       concurrently=True)


def trigram_index_migration(app_label, dependencies, cibles):
    """Classe ``Migration`` (``atomic=False``) posant des index GIN trigramme.

    ``cibles`` : liste de ``(model_name, champ, nom_index)``. Le retour arrière
    retire les index, jamais l'extension (objet de base partagé)."""

    def avant(apps, schema_editor):
        _poser_trigrammes(apps, schema_editor, app_label, cibles)

    def arriere(apps, schema_editor):
        _retirer_trigrammes(apps, schema_editor, app_label, cibles)

    class TrigramIndexMigration(migrations.Migration):
        atomic = False
        operations = [migrations.RunPython(avant, arriere)]

    TrigramIndexMigration.dependencies = list(dependencies)
    return TrigramIndexMigration
