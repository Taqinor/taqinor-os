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

# ─────────────────────────────────────────────────────────────────────────────
# AUD422 — LE PREMIER LOT DÉPLOYÉ : LES TABLES ARGENT.
# ─────────────────────────────────────────────────────────────────────────────
# Toute la mécanique ci-dessus existait depuis NTPLT2 mais n'avait JAMAIS été
# appliquée à une seule table : `manage.py rls` était tout-ou-rien (aucune
# option de ciblage), donc le seul chemin disponible était un big-bang sur les
# ~900 tables company-scopées — que personne n'ose lancer. Décision fondateur :
# démarrer par les tables ARGENT seules, par migration, table par table.
#
# Ces libellés sont des CHAÎNES (jamais un import d'app métier : `core` reste
# fondation). Deux d'entre eux surprennent et c'est VOULU : `Facture` et
# `Paiement` vivent dans l'app `facturation` (ODX17 — `apps.ventes.models` n'en
# garde qu'un ré-export), même si leurs tables s'appellent toujours
# `ventes_facture` / `ventes_paiement`. Viser `ventes.Facture` échouerait
# bruyamment (`tables_for_labels` lève sur un libellé inconnu — fail-closed).
TABLES_ARGENT = (
    'compta.EcritureComptable',
    'compta.LigneEcriture',
    'ventes.Devis',
    'facturation.Facture',
    'facturation.Paiement',
)


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


def discover_company_scoped_tables(apps_registry=None) -> list[RlsTable]:
    """Renvoie chaque table portant une FK ``company``, triée par nom de table.

    Dédupliquée par table réelle : plusieurs modèles ne partagent jamais une
    table ici, mais on déduplique par sûreté (proxy/hérédité). Utilise le
    registre Django (``get_models``) — aucun import d'app métier.

    ``apps_registry`` (AUD422) permet de passer le registre HISTORIQUE d'une
    migration (le ``apps`` reçu par ``RunPython``) : une migration doit décrire
    le schéma tel qu'il était, jamais tel qu'il est aujourd'hui — sinon son
    rejeu casse le jour où un modèle disparaît. Défaut : le registre vivant.
    """
    registre = django_apps if apps_registry is None else apps_registry
    seen: dict[str, RlsTable] = {}
    for model in registre.get_models():
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


def tables_for_labels(labels, apps_registry=None) -> list[RlsTable]:
    """AUD422 — les tables des seuls ``labels`` (``app_label.Model``).

    FAIL-CLOSED : un libellé inconnu — mal orthographié, modèle sans FK
    ``company``, ou app parquée par l'édition courante — lève ``ValueError``
    en le NOMMANT, au lieu d'être silencieusement ignoré. Une migration RLS
    qui « n'a rien trouvé » et n'a donc rien protégé serait le pire des
    résultats : elle se déclarerait appliquée.

    Comparaison insensible à la casse (``compta.ecriturecomptable`` marche),
    ordre de sortie stable (par nom de table, comme la découverte complète).
    """
    voulus = {str(label).strip().lower() for label in labels if str(label).strip()}
    if not voulus:
        return []
    trouvees = {}
    for entry in discover_company_scoped_tables(apps_registry=apps_registry):
        clef = entry.label.lower()
        if clef in voulus:
            trouvees[clef] = entry
    manquants = sorted(voulus - set(trouvees))
    if manquants:
        raise ValueError(
            'RLS : libellé(s) introuvable(s) parmi les modèles portant une FK '
            'company — ' + ', '.join(manquants)
            + '. Vérifiez l\'app_label (Facture/Paiement vivent dans '
              '`facturation`, pas `ventes` — ODX17).')
    return [trouvees[c] for c in sorted(trouvees, key=lambda c: trouvees[c].table)]


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


def migration_functions(labels):
    """AUD422 — ``(appliquer, revenir)`` pour un ``migrations.RunPython``.

    Trois garanties, dans cet ordre :

    * NO-OP HORS POSTGRESQL — RLS n'existe que là ; sur tout autre backend la
      migration s'applique sans rien faire, jamais une erreur ;
    * REGISTRE HISTORIQUE — la résolution des libellés passe par le ``apps``
      reçu de ``RunPython``, donc une migration ne dépend jamais de l'état
      d'aujourd'hui des modèles. Corollaire : ne passer ICI que des libellés de
      l'app à laquelle appartient la migration (un modèle d'une autre app peut
      ne pas encore exister dans l'état à ce point du plan) ;
    * RÉVERSIBLE — ``revenir`` rejoue ``revert_sql`` (DROP POLICY + NO FORCE +
      DISABLE), qui ramène la table à son état pré-RLS EXACT. ``migrate <app>
      <migration précédente>`` défait donc la bascule sans perte.
    """
    def _executer(schema_editor, generateur, apps_registry):
        if schema_editor.connection.vendor != 'postgresql':
            return
        entries = tables_for_labels(labels, apps_registry=apps_registry)
        with schema_editor.connection.cursor() as cursor:
            for entry in entries:
                for stmt in generateur(entry):
                    cursor.execute(stmt)

    def appliquer(apps, schema_editor):
        _executer(schema_editor, enable_sql, apps)

    def revenir(apps, schema_editor):
        _executer(schema_editor, revert_sql, apps)

    return appliquer, revenir


def build_statements(action: str, only=None) -> tuple[list[RlsTable], list[str]]:
    """Renvoie ``(tables, statements)`` pour l'action ``apply`` ou ``revert``.

    Ne touche PAS la base — pure génération, consommée par la commande (dry-run
    imprime, apply/revert exécute).

    ``only`` (AUD422) restreint aux libellés ``app_label.Model`` donnés, pour
    un déploiement ÉTAGÉ (les tables argent d'abord) au lieu du tout-ou-rien
    d'origine. ``None`` = tout le périmètre découvert, comportement historique
    strictement inchangé.
    """
    tables = (discover_company_scoped_tables() if only is None
              else tables_for_labels(only))
    gen = enable_sql if action == "apply" else revert_sql
    statements: list[str] = []
    for entry in tables:
        statements.extend(gen(entry))
    return tables, statements
