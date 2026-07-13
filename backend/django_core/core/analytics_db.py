"""YHARD9 — fondation analytique : routage des lectures BI vers un réplica.

Couche de FONDATION (n'importe AUCUNE app métier). Deux pièces :

* ``AnalyticsRouter`` (posé dans ``DATABASE_ROUTERS``) — garde-fou d'écriture :
  garantit que RIEN n'est jamais écrit ni migré vers la base ``replica`` (un
  réplica de lecture est en lecture seule). Il NE détourne PAS les lectures
  globalement — le routage analytique reste EXPLICITE via ``analytics_queryset``
  ci-dessous, pour ne toucher QUE les requêtes BI lourdes et laisser tout le
  reste de l'ORM sur ``default``.

* ``analytics_queryset(qs)`` — helper que reporting / monitoring / data_explorer
  appellent sur leurs querysets d'AGRÉGATION lourds : renvoie ``qs.using(alias)``
  où ``alias`` est ``replica``. Key-gated par les settings : sans ``DB_REPLICA_HOST``,
  ``replica`` est un alias octet-identique de ``default`` (cf. settings/base.py),
  donc l'appel est un no-op fonctionnel — le BI tourne sur la base transactionnelle
  exactement comme avant. Avec un réplica configuré, ces lectures partent dessus
  et cessent de contendre avec la charge OLTP.

Sécurité multi-tenant : INCHANGÉE. Le scoping société vit dans le queryset
fourni par l'appelant (déjà filtré par ``company``) ; changer la base de
LECTURE ne change rien au filtre. Aucune écriture n'est jamais routée vers le
réplica (garanti par le routeur ET par le fait que le helper ne sert que des
agrégats en lecture).
"""
from __future__ import annotations

# Alias logique de la base analytique. Résolu dans settings/base.py : réplica
# physique si DB_REPLICA_HOST est posé, sinon alias de `default`.
ANALYTICS_DB_ALIAS = 'replica'

# Bases considérées comme portant les MÊMES données (default + son réplica) —
# une relation entre objets lus de l'une et de l'autre est légitime.
_SAME_DATA = {'default', ANALYTICS_DB_ALIAS}


def analytics_queryset(qs):
    """Route un queryset de LECTURE analytique vers le réplica.

    No-op fonctionnel quand aucun réplica n'est configuré (``replica`` = alias de
    ``default``). Ne JAMAIS utiliser pour un queryset qu'on va ``save()``/
    ``update()``/``delete()`` : réservé aux agrégations/lectures BI.
    """
    return qs.using(ANALYTICS_DB_ALIAS)


class AnalyticsRouter:
    """Routeur DB : le réplica est en LECTURE SEULE.

    * lectures : non détournées (``None``) — le routage analytique est explicite ;
    * écritures : toujours ``default`` (jamais le réplica) ;
    * migrations : jamais sur le réplica ;
    * relations : autorisées entre ``default`` et son réplica (mêmes données).
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
        # Aucun DDL/migration sur le réplica (lecture seule / mirroir).
        if db == ANALYTICS_DB_ALIAS:
            return False
        return None
