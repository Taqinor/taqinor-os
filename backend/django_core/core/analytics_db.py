"""YHARD9 — fondation analytique : routage des lectures BI vers un réplica.

Couche de FONDATION (n'importe AUCUNE app métier — uniquement Django/stdlib).
Deux pièces :

* ``AnalyticsRouter`` (posé dans ``DATABASE_ROUTERS``) — garde-fou d'écriture :
  garantit que RIEN n'est jamais écrit ni migré vers la base ``replica`` (un
  réplica de lecture est en lecture seule). Il NE détourne PAS les lectures
  globalement (``db_for_read`` → ``None``) — le routage analytique reste
  EXPLICITE via ``analytics_queryset`` ci-dessous, pour ne toucher QUE les
  requêtes BI lourdes et laisser tout le reste de l'ORM sur ``default``.

* ``analytics_queryset(qs)`` — helper que reporting / monitoring / data_explorer
  appellent sur leurs querysets d'AGRÉGATION lourds. Il route vers le réplica
  **UNIQUEMENT si un alias ``replica`` est réellement configuré** dans
  ``settings.DATABASES`` (c.-à-d. un réplica physique via ``DB_REPLICA_HOST``).
  Sans réplica configuré, il renvoie ``qs`` INCHANGÉ : aucune connexion
  ``replica`` n'est jamais ouverte, donc les tests (qui ne configurent jamais de
  réplica) sont OCTET-IDENTIQUES et ne peuvent pas heurter une base absente.

Sécurité multi-tenant : INCHANGÉE. Le scoping société vit dans le queryset
fourni par l'appelant (déjà filtré par ``company``) ; changer la base de
LECTURE ne change rien au filtre. Aucune écriture n'est jamais routée vers le
réplica (garanti par le routeur ET par le fait que le helper ne sert que des
agrégats en lecture).
"""
from __future__ import annotations

from django.conf import settings

# Alias logique de la base analytique. Présent dans ``settings.DATABASES``
# UNIQUEMENT quand un réplica physique est configuré (DB_REPLICA_HOST).
ANALYTICS_DB_ALIAS = 'replica'

# Bases considérées comme portant les MÊMES données (default + son réplica) —
# une relation entre objets lus de l'une et de l'autre est légitime.
_SAME_DATA = {'default', ANALYTICS_DB_ALIAS}


def analytics_queryset(qs):
    """Route un queryset de LECTURE analytique vers le réplica, si configuré.

    * Réplica configuré (``'replica' in settings.DATABASES``) → ``qs.using('replica')``.
    * Aucun réplica → ``qs`` renvoyé TEL QUEL (no-op strict : aucune connexion
      ``replica`` ouverte, comportement octet-identique — c'est le cas des tests).

    Ne JAMAIS utiliser pour un queryset qu'on va ``save()``/``update()``/
    ``delete()`` : réservé aux agrégations/lectures BI.
    """
    if ANALYTICS_DB_ALIAS in settings.DATABASES:
        return qs.using(ANALYTICS_DB_ALIAS)
    return qs


class AnalyticsRouter:
    """Routeur DB : le réplica est en LECTURE SEULE.

    * lectures : non détournées (``None``) — le routage analytique est explicite ;
    * écritures : toujours ``default`` (jamais le réplica) ;
    * migrations : jamais sur le réplica (``False``), neutre ailleurs (``None``) ;
    * relations : autorisées entre ``default`` et son réplica (mêmes données).

    Inoffensif quand une seule base est configurée : ``db_for_read`` ne détourne
    rien et ``allow_migrate`` ne renvoie ``False`` que pour l'alias ``replica``
    (absent), donc byte-identique à l'absence de routeur.
    """

    def db_for_read(self, model, **hints):
        # Routage explicite via analytics_queryset — on ne hijacke pas tous les
        # reads (sinon on déporterait aussi les lectures transactionnelles).
        return None

    def db_for_write(self, model, **hints):
        # Une écriture ne part JAMAIS vers le réplica.
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        db1 = obj1._state.db
        db2 = obj2._state.db
        if db1 in _SAME_DATA and db2 in _SAME_DATA:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # Aucun DDL/migration sur le réplica (lecture seule / miroir).
        if db == ANALYTICS_DB_ALIAS:
            return False
        return None
