"""NTPLT2 — Politiques RLS Postgres générées par introspection.

Défense en profondeur multi-tenant (couche BASE, sous le scoping applicatif).
Pour chaque modèle portant une FK ``company`` (découverte partagée avec le scan
d'isolation YRBAC12), on émet :

    ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;
    ALTER TABLE <table> FORCE ROW LEVEL SECURITY;
    CREATE POLICY <name> ON <table>
        USING (company_id = NULLIF(current_setting('app.current_company', true), '')::int);

Le GUC ``app.current_company`` est posé par requête (NTPLT1,
``core.tenant_context``). Une fois RLS actif ET le rôle applicatif non-BYPASSRLS
en place (NTPLT3), même une requête SQL brute ne peut PHYSIQUEMENT pas lire les
lignes d'un autre tenant.

Ce module fournit la MÉCANIQUE (introspection + génération SQL, idempotente et
réversible) consommée par la commande ``manage.py rls``. Il n'APPLIQUE jamais
rien tout seul : la commande exige ``--apply``/``--revert`` explicites, jamais
lancée automatiquement (bascule d'infrastructure délibérée).

Contrainte de conception (docs/scale-runway.md § SCA14) : la policy s'appuie sur
``current_setting('app.current_company', true)`` posé en ``SET LOCAL``
transaction-scopé (NTPLT1) — jamais un ``SET`` de session, sous peine de fuite
inter-tenants sous pooling transaction.

``core`` reste FONDATION : aucun import statique d'app métier — la découverte
passe par ``django.apps.apps.get_models()`` (registre Django), pas par un import
d'``apps.*``.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.apps import apps as django_apps
from django.db import models as m

# Préfixe des policies posées par ce module (identifie/permet le revert ciblé).
POLICY_PREFIX = "rls_company_"


@dataclass(frozen=True)
class RlsTable:
    """Une table company-scopée éligible RLS."""
    label: str          # ex. "crm.Lead"
    table: str          # nom de table réel (db_table)
    company_column: str  # colonne de la FK company (quasi toujours company_id)

    @property
    def policy_name(self) -> str:
        # Nom de policy stable et unique par table (Postgres limite à 63 car.).
        return (POLICY_PREFIX + self.table)[:63]


def _has_local_company_fk(model):
    """True si ``model`` porte une FK ``company`` CONCRÈTE et LOCALE.

    Miroir de la découverte YRBAC12 (``core.tenant_isolation_scan`` teste
    ``"company" in field_names``) mais restreinte aux ForeignKey concrètes
    locales — c'est la colonne réelle sur laquelle la policy RLS s'applique.
    On exclut les modèles abstraits/proxy et les relations héritées non
    matérialisées sur la table du modèle.
    """
    meta = getattr(model, "_meta", None)
    if meta is None or meta.abstract or meta.proxy:
        return False
    try:
        field = meta.get_field("company")
    except Exception:  # noqa: BLE001 - pas de champ company => hors périmètre
        return False
    return isinstance(field, m.ForeignKey)


def discover_company_scoped_tables() -> list[RlsTable]:
    """Renvoie chaque table portant une FK ``company``, triée par nom de table.

    Dédupliquée par table réelle : plusieurs modèles ne partagent jamais une
    table ici, mais on déduplique par sûreté (proxy/hérédité). Utilise le
    registre Django (``get_models``) — aucun import d'app métier.
    """
    seen: dict[str, RlsTable] = {}
    for model in django_apps.get_models():
        if not _has_local_company_fk(model):
            continue
        meta = model._meta
        field = meta.get_field("company")
        table = meta.db_table
        if table in seen:
            continue
        label = f"{meta.app_label}.{model.__name__}"
        seen[table] = RlsTable(
            label=label, table=table, company_column=field.attname)
    return [seen[t] for t in sorted(seen)]


def _quote_ident(identifier: str) -> str:
    """Quote défensif d'un identifiant SQL (nom de table/colonne/policy).

    Les noms viennent de l'introspection Django (jamais d'une entrée
    utilisateur), mais on quote quand même pour être robuste aux noms mixtes
    ou réservés. Double les guillemets internes par prudence.
    """
    return '"' + identifier.replace('"', '""') + '"'


def enable_sql(entry: RlsTable) -> list[str]:
    """SQL idempotent activant RLS + la policy company pour une table.

    - ``ENABLE`` / ``FORCE ROW LEVEL SECURITY`` sont idempotents nativement.
    - La policy est posée en ``DROP POLICY IF EXISTS`` + ``CREATE POLICY`` pour
      rester idempotente (Postgres < 15 n'a pas ``CREATE POLICY IF NOT
      EXISTS``). ``FORCE`` garantit que même le PROPRIÉTAIRE de la table est
      soumis à la policy (sinon le rôle owner la contournerait).
    """
    t = _quote_ident(entry.table)
    p = _quote_ident(entry.policy_name)
    col = _quote_ident(entry.company_column)
    return [
        f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;",
        f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY;",
        f"DROP POLICY IF EXISTS {p} ON {t};",
        # NULLIF(..., '') : le GUC « pas de tenant » est posé en CHAÎNE VIDE
        # (core.tenant_context pose set_config(..., '', ...) au nettoyage), et
        # ''::int lève « invalid input syntax for type integer ». NULLIF ramène
        # la chaîne vide à NULL → « company_id = NULL » ne matche RIEN → 0 ligne
        # (le sceau RLS attendu), au lieu d'une DataError.
        (f"CREATE POLICY {p} ON {t} USING ("
         f"{col} = NULLIF(current_setting('app.current_company', true), '')::int);"),
    ]


def revert_sql(entry: RlsTable) -> list[str]:
    """SQL réversible : retire la policy et désactive RLS pour une table.

    ``DROP POLICY IF EXISTS`` + ``NO FORCE`` + ``DISABLE`` — idempotent, ramène
    la table à son état pré-RLS exact.
    """
    t = _quote_ident(entry.table)
    p = _quote_ident(entry.policy_name)
    return [
        f"DROP POLICY IF EXISTS {p} ON {t};",
        f"ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY;",
        f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY;",
    ]


def build_statements(action: str) -> tuple[list[RlsTable], list[str]]:
    """Renvoie ``(tables, statements)`` pour l'action ``apply`` ou ``revert``.

    Ne touche PAS la base — pure génération, consommée par la commande (dry-run
    imprime, apply/revert exécute).
    """
    tables = discover_company_scoped_tables()
    gen = enable_sql if action == "apply" else revert_sql
    statements: list[str] = []
    for entry in tables:
        statements.extend(gen(entry))
    return tables, statements
