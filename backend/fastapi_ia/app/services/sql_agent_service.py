"""
Service Agent SQL — LangChain + selection de tables en memoire.
Architecture :
  Question NL
    -> Embedding (sentence-transformers, local, gratuit)
    -> top-5 tables pertinentes (similarite cosinus EN MEMOIRE, sans pgvector)
    -> SQLDatabase filtre
    -> LangChain SQL Agent (provider configurable via SQL_AGENT_PROVIDER)
    -> Securite : _SecureQueryTool intercepte chaque SQL avant execution
       et REECRIT chaque table en sous-requete filtree company_id (AANA2)
    -> Reponse NL en francais

Changer de LLM : modifier SQL_AGENT_PROVIDER dans .env
  groq   -> llama-3.3-70b-versatile (defaut, gratuit)
  openai -> gpt-4o
  claude -> claude-sonnet-4-6
  ollama -> modele local
"""
from __future__ import annotations

import asyncio
import logging
import re
import threading
from typing import Any, TYPE_CHECKING

import sqlglot
import sqlglot.errors
from sqlglot import exp

try:
    # langchain < 1.0
    from langchain.callbacks.base import BaseCallbackHandler
except ImportError:  # pragma: no cover - langchain >= 1.0 a deplace le module
    # langchain >= 1.0 : le module historique a ete retire au profit de
    # langchain_core. Le comportement est identique.
    from langchain_core.callbacks.base import BaseCallbackHandler

if TYPE_CHECKING:  # eviter un import circulaire au runtime
    from app.services.action_tools import ActionContext

from app.core.config import N_EXISTE_PAS  # noqa: F401  (JOUET ADEP99 P3.6 — ne pas merger)
from app.core.config import (
    CHAT_HISTORY_MAX,
    CHAT_HISTORY_TTL,
    CLAUDE_API_KEY,
    GROQ_API_KEY,
    OPENAI_API_KEY,
    REDIS_CHAT_URL,
    SQL_AGENT_MODEL,
    SQL_AGENT_PROVIDER,
)

logger = logging.getLogger(__name__)

# ── Tables autorisees (tables Django internes exclues) ────────────────────────

_ALLOWED_TABLES = [
    "stock_produit",
    "stock_categorie",
    "stock_fournisseur",
    "stock_mouvementstock",
    "crm_client",
    "ventes_devis",
    "ventes_lignedevis",
    "ventes_boncommande",
    "ventes_facture",
    "ventes_lignefacture",
    "authentication_company",
    "authentication_customuser",
    "parametres_companyprofile",
    "roles_role",
    "ia_ocr_document",
    # ── N86 — objets apres-vente / chantiers / parc / maintenance (LECTURE) ──
    "installations_installation",
    "installations_intervention",
    "sav_equipement",
    "sav_ticket",
    "sav_contratmaintenance",
    # ── PUB106 — compte publicitaire Meta (LECTURE seule, scope societe). Vues
    # de LECTURE sur les miroirs adsengine : campagnes, perf datee, leads par ad.
    # Jamais adsengine_metaconnection (credentials write-only) ni prix d'achat.
    "adsengine_adcampaignmirror",
    "adsengine_insightsnapshot",
    "adsengine_metaleadmirror",
]

# Tables qui possedent une colonne company_id → filtrage obligatoire
_TABLES_WITH_COMPANY_ID = frozenset([
    "stock_produit",
    "stock_categorie",
    "stock_fournisseur",
    "stock_mouvementstock",
    "crm_client",
    "ventes_devis",
    "ventes_lignedevis",
    "ventes_boncommande",
    "ventes_facture",
    "ventes_lignefacture",
    "authentication_customuser",
    "parametres_companyprofile",
    "ia_ocr_document",
    "roles_role",  # ERR2 — porte bien company_id (modele Django roles.Role)
    # ── N86 — toutes ces tables portent une colonne company_id ──
    "installations_installation",
    "installations_intervention",
    "sav_equipement",
    "sav_ticket",
    "sav_contratmaintenance",
    # ── PUB106 — miroirs adsengine (tous porteurs de company_id, TenantModel) ──
    "adsengine_adcampaignmirror",
    "adsengine_insightsnapshot",
    "adsengine_metaleadmirror",
])

# ERR2 — La table tenant elle-meme : son PK `id` EST le company_id. Une requete
# qui la lit doit etre contrainte par `id = <company_id>` (pas `company_id`).
_TENANT_TABLE = "authentication_company"

# ERR2 — Ensemble FERME des tables qu'un appelant peut lire. Toute table de base
# hors de cet ensemble est rejetee (fail-closed) : pas de fuite via une table
# non scopee. = tables company_id + la table tenant.
_TENANT_SCOPED_TABLES = frozenset(_TABLES_WITH_COMPANY_ID | {_TENANT_TABLE})

# Descriptions en francais pour pgvector
_TABLE_DESCRIPTIONS: dict[str, str] = {
    "stock_produit": (
        "Produits du stock : nom, reference, prix achat, prix vente, "
        "quantite en stock, seuil alerte, categorie, fournisseur, TVA"
    ),
    "stock_categorie": "Categories de produits du stock",
    "stock_fournisseur": "Fournisseurs de produits : nom, email, telephone, adresse",
    "stock_mouvementstock": (
        "Mouvements de stock : entrees et sorties de produits "
        "avec quantite, date, motif, produit concerne"
    ),
    "crm_client": "Clients de l'entreprise : nom, prenom, email, telephone, adresse",
    "ventes_devis": (
        "Devis commerciaux : numero, date, client, montant total, "
        "statut (brouillon / accepte / refuse / expire)"
    ),
    "ventes_lignedevis": (
        "Lignes de produits dans les devis : produit, quantite, "
        "prix unitaire, remise, montant"
    ),
    "ventes_boncommande": "Bons de commande clients confirmes depuis un devis accepte",
    "ventes_facture": (
        "Factures clients : numero, date, client, montant HT, TVA, "
        "montant TTC, statut paiement"
    ),
    "ventes_lignefacture": (
        "Lignes de produits dans les factures : produit, quantite, "
        "prix unitaire, montant"
    ),
    "authentication_company": "Entreprises (multi-tenant) : nom, adresse, email, telephone",
    "authentication_customuser": "Utilisateurs du systeme : nom, email, role, entreprise",
    "parametres_companyprofile": "Parametres de l'entreprise : logo, couleur, informations legales",
    "roles_role": "Roles et permissions des utilisateurs",
    "ia_ocr_document": "Documents OCR analyses : factures et bons de livraison scannes",
    # ── N86 — apres-vente / chantiers / parc / maintenance (LECTURE seule) ──
    "installations_installation": (
        "Chantiers (installations solaires) : reference, client, devis, statut "
        "(signe, materiel_commande, planifie, en_cours, installe, receptionne, "
        "cloture, et statuts herites a_planifier/pose/mise_en_service), "
        "puissance_installee_kwc, type_installation, dates cles "
        "(date_pose_prevue, date_reception, date_cloture), parc_actif. "
        "Utiliser statut='a_planifier' ou 'planifie' pour les chantiers a "
        "planifier."
    ),
    "installations_intervention": (
        "Interventions terrain rattachees a un chantier (installation_id) : "
        "type_intervention (pose, raccordement, mise_en_service, controle, "
        "depannage), statut, date_prevue, date_realisee, technicien. "
        "Les visites de maintenance sont des interventions de type 'controle'."
    ),
    "sav_equipement": (
        "Parc d'equipements installes : un appareil physique pose chez un "
        "client (produit_id, numero_serie, installation_id, date_pose). "
        "date_fin_garantie et date_fin_garantie_production donnent l'expiration "
        "des garanties — utiliser date_fin_garantie pour savoir quels "
        "equipements/garanties expirent sur une periode."
    ),
    "sav_ticket": (
        "Tickets SAV (service apres-vente) : reference, client, installation, "
        "equipement, type (correctif/preventif), statut (nouveau, planifie, "
        "en_cours, resolu, cloture), priorite, date_ouverture, date_resolution."
    ),
    "sav_contratmaintenance": (
        "Contrats de maintenance preventive : client, installation, "
        "periodicite (mensuel/trimestriel/semestriel/annuel), date_debut, "
        "derniere_visite, actif, date_renouvellement."
    ),
    # ── PUB106 — compte publicitaire Meta (LECTURE seule) ──
    "adsengine_adcampaignmirror": (
        "Campagnes publicitaires Meta (miroir LECTURE) : meta_id, name (nom de "
        "la campagne), status, objective. Une campagne regroupe des annonces."
    ),
    "adsengine_insightsnapshot": (
        "Performance publicitaire datee (miroir LECTURE) : spend (depense, "
        "devise du compte), results, leads_count (leads), conversations "
        "(WhatsApp), impressions, clicks, date. Une ligne par jour et par objet "
        "cible (campagne/adset/ad, via content_type_id + object_id). Pour la "
        "depense d'une campagne, joindre object_id au adsengine_adcampaignmirror.id "
        "quand content_type designe une campagne. Filtrer par date pour un mois."
    ),
    "adsengine_metaleadmirror": (
        "Leads publicitaires Meta par annonce (miroir LECTURE) : leadgen_id, "
        "ad_id, adset_id, campaign_id (identifiants Meta), created_time, "
        "is_organic. Compter les lignes pour le nombre de leads d'une campagne."
    ),
}

# ── Prompt systeme ────────────────────────────────────────────────────────────

_AGENT_PREFIX = """\
Tu es un expert en analyse de donnees pour TAQINOR ERP, \
un systeme de gestion d'entreprise marocain.
Tu reponds TOUJOURS en francais, de maniere claire et professionnelle.
Les montants sont en DH (dirhams marocains).

REGLES OBLIGATOIRES :
- Utilise UNIQUEMENT des requetes SELECT. \
Jamais INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE.
- Limite les resultats a 100 lignes maximum avec LIMIT 100.
- Si aucune donnee n'est trouvee, explique-le clairement en francais.
- Ne retourne jamais de donnees brutes JSON — formule une reponse naturelle.
- Le filtrage par company_id est gere automatiquement par le systeme.
- INTERDIT ABSOLU : ne jamais mentionner de noms de tables SQL dans ta reponse \
(stock_produit, authentication_customuser, crm_client, etc.). \
Utilise uniquement des termes metier : "produits", "employes", "clients", \
"factures", "devis", "mouvements de stock". \
Cela inclut les explications, les notes et les commentaires.
- Si une table n'existe pas mais qu'une autre peut repondre a la question, \
utilise-la directement sans demander confirmation.

GUIDE DES TABLES — utilise TOUJOURS la bonne table :

Stock actuel des produits → stock_produit
  - quantite       = quantite actuellement en stock
  - prix_vente_ht  = prix de vente HT
  - prix_achat_ht  = prix d'achat HT
  - seuil_alerte   = seuil minimum avant rupture
  - categorie_id   = FK vers stock_categorie
  - fournisseur_id = FK vers stock_fournisseur

Historique des entrees/sorties → stock_mouvementstock
  (NE PAS utiliser pour connaitre le stock actuel,
   utiliser stock_produit.quantite a la place)
  - type_mouvement = 'entree' ou 'sortie'
  - quantite       = quantite du mouvement (pas le stock actuel)

Clients → crm_client (nom, prenom, email, telephone)

Devis → ventes_devis + ventes_lignedevis
  - statut : 'brouillon', 'accepte', 'refuse', 'expire'
  - montant_total = montant total du devis

Factures → ventes_facture + ventes_lignefacture
  - statut_paiement : 'non_paye', 'partiel', 'paye'
  - montant_ttc = montant total TTC

Chantiers (installations) → installations_installation
  - statut : 'signe', 'materiel_commande', 'planifie', 'en_cours',
    'installe', 'receptionne', 'cloture' (+ herites : 'a_planifier', 'pose',
    'mise_en_service'). Chantiers a planifier = statut 'a_planifier' OU 'planifie'.
  - client_id, devis_id, puissance_installee_kwc, type_installation
  - dates : date_pose_prevue, date_reception, date_cloture

Interventions terrain → installations_intervention
  - installation_id = FK vers le chantier
  - type_intervention : 'pose','raccordement','mise_en_service','controle','depannage'
  - statut, date_prevue, date_realisee

Parc d'equipements / garanties → sav_equipement
  - produit_id, numero_serie, installation_id, date_pose
  - date_fin_garantie / date_fin_garantie_production = expiration des garanties
    (garanties qui expirent ce trimestre = date_fin_garantie dans la periode)

Tickets SAV → sav_ticket
  - statut : 'nouveau','planifie','en_cours','resolu','cloture'
  - type : 'correctif' / 'preventif' ; priorite ; client_id ; installation_id

Contrats de maintenance → sav_contratmaintenance
  - periodicite, date_debut, derniere_visite, actif

EXEMPLES DE REQUETES CORRECTES :
- Stock actuel : SELECT nom, quantite FROM stock_produit ORDER BY quantite DESC
- Ruptures : SELECT nom, quantite FROM stock_produit WHERE quantite <= seuil_alerte
- CA factures : SELECT SUM(montant_ttc) FROM ventes_facture WHERE statut_paiement='paye'
- Chantiers a planifier : SELECT reference FROM installations_installation \
WHERE statut IN ('a_planifier','planifie')
- Factures en retard : SELECT numero FROM ventes_facture \
WHERE statut_paiement <> 'paye' AND date_echeance < CURRENT_DATE
- Garanties qui expirent : SELECT numero_serie, date_fin_garantie \
FROM sav_equipement WHERE date_fin_garantie BETWEEN CURRENT_DATE AND \
(CURRENT_DATE + INTERVAL '3 months')
"""

# Instruction ajoutee dynamiquement quand l'appelant n'a PAS la permission
# 'prix_achat_voir' : interdit de divulguer prix d'achat / marge (CLAUDE.md —
# le prix_achat est un indicateur generateur, jamais client-facing).
_MARGIN_RESTRICTION = """\

CONFIDENTIALITE — RESTRICTION PRIX D'ACHAT / MARGE :
- INTERDIT ABSOLU de retourner, calculer ou mentionner le prix d'achat \
(prix_achat) ou la marge. Si on te le demande, reponds que tu n'es pas \
autorise a divulguer ces informations. N'inclus JAMAIS la colonne prix_achat \
dans une requete ou une reponse.
"""

# ── Securite : lecture seule + liste blanche de fonctions (arbre sqlglot) ─────
# ERR1 — Le prompt LLM ne suffit pas. Chaque requete est PARSEE (sqlglot) et on
# ECHOUE FERME (rejet) sur tout ce qu'on ne peut pas prouver sur : EXACTEMENT une
# (1) requete de lecture (SELECT / UNION...), aucun noeud d'ecriture, de DDL,
# d'administration, de verrou ou de `SELECT ... INTO` nulle part (CTE et
# sous-requetes comprises).
# AANA3 (C-AANA-002) — et AUCUNE fonction hors d'une LISTE BLANCHE (agregats,
# dates, chaines, arrondis, fenetres). L'ancienne liste NOIRE de mots-cles
# textuels laissait passer `query_to_xml('select ... from crm_client')` (lecture
# de toutes les societes depuis une chaine), `pg_read_file`, `lo_export`,
# `set_config('app.current_company', ...)`, `pg_sleep`, `dblink`... Une liste
# blanche refuse par defaut tout ce qui n'a pas ete juge sur.


class SQLSecurityError(Exception):
    """Levee quand une requete ne peut PAS etre prouvee sure (echec ferme)."""


# Noeuds qui ne doivent apparaitre NULLE PART dans une requete de lecture.
_NOEUDS_INTERDITS = tuple(
    cls for cls in (
        getattr(exp, name, None) for name in (
            "DML", "DDL", "Into", "Lock", "Command", "Set", "SetItem",
            "Transaction", "Commit", "Rollback", "Copy", "Grant", "Revoke",
            "Use", "Pragma", "Describe", "Show", "Analyze", "Kill",
            "Summarize", "LoadData", "Refresh", "Cache", "Uncache",
        )
    ) if isinstance(cls, type)
)

# Fonctions reconnues (typees) par sqlglot et jugees sures : agregats,
# fenetres, dates, chaines, arrondis, conditionnelles. Toute AUTRE classe de
# fonction est refusee (fail-closed), y compris celles qu'une future version de
# sqlglot ajouterait.
_FONCTIONS_TYPEES_AUTORISEES = tuple(
    cls for cls in (
        getattr(exp, name, None) for name in (
            # agregats
            "Count", "Sum", "Avg", "Min", "Max", "ArrayAgg", "GroupConcat",
            "LogicalAnd", "LogicalOr", "Stddev", "StddevPop", "StddevSamp",
            "Variance", "VariancePop", "PercentileCont", "PercentileDisc",
            "Mode",
            # fenetres
            "RowNumber", "Rank", "DenseRank", "Ntile", "Lag", "Lead",
            "FirstValue", "LastValue",
            # conditionnelles / types
            "Case", "If", "Coalesce", "Nullif", "Greatest", "Least", "Cast",
            "Exists",
            # nombres
            "Abs", "Round", "Floor", "Ceil", "Trunc", "Pow", "Sqrt", "Sign",
            "ToNumber",
            # dates
            "CurrentDate", "CurrentTime", "CurrentTimestamp", "Localtimestamp",
            "Date", "DateTrunc", "TimestampTrunc", "Extract", "TimeToStr",
            "StrToDate", "StrToTime",
            # chaines
            "Upper", "Lower", "Initcap", "Length", "Concat", "ConcatWs",
            "Substring", "Trim", "Replace", "Left", "Right", "Pad",
            "StrPosition", "SplitPart", "Reverse",
        )
    ) if isinstance(cls, type)
)

# Fonctions Postgres que sqlglot laisse « anonymes » (non typees) et jugees
# sures. Nom NON qualifie uniquement (un appel `schema.f()` est refuse).
_FONCTIONS_ANONYMES_AUTORISEES = frozenset({
    "age", "date_part", "make_date", "make_timestamp", "justify_days",
    "justify_hours", "justify_interval", "char_length", "character_length",
    "btrim", "ltrim", "rtrim", "substr", "strpos", "mod", "ceiling", "trunc",
    "to_char", "to_date", "to_timestamp",
})


_OPERATEURS = (exp.Binary, exp.Connector, exp.Unary)


def _assert_lecture_seule(tree: exp.Expression) -> None:
    """ERR1 — aucun noeud d'ecriture / DDL / admin / verrou / INTO, ou qu'il
    soit dans l'arbre."""
    for node in tree.walk():
        if isinstance(node, _NOEUDS_INTERDITS):
            raise SQLSecurityError(
                f"Instruction interdite ({type(node).__name__}) : seules les "
                "lectures (SELECT) sont autorisees."
            )


def _assert_fonctions_autorisees(tree: exp.Expression) -> None:
    """AANA3 — toute fonction appelee doit etre dans la liste blanche."""
    for func in tree.find_all(exp.Func):
        if isinstance(func, _OPERATEURS):
            # sqlglot range certains OPERATEURS (AND, OR, ~, ->, ^...) parmi
            # les « fonctions » : operateurs integres, pas des appels.
            continue
        if isinstance(func.parent, exp.Dot) and func.arg_key == "expression":
            raise SQLSecurityError(
                "Appel de fonction qualifie par un schema interdit."
            )
        if isinstance(func, exp.Anonymous):
            nom = func.name.lower()
            if nom in _FONCTIONS_ANONYMES_AUTORISEES:
                continue
            raise SQLSecurityError(f"Fonction non autorisee : {nom}.")
        if not isinstance(func, _FONCTIONS_TYPEES_AUTORISEES):
            raise SQLSecurityError(
                f"Fonction non autorisee : {type(func).__name__}."
            )


def _enforce_single_select(sql: str) -> exp.Query:
    """ERR1 — Rejette tout ce qui n'est pas EXACTEMENT une requete de lecture
    (SELECT / WITH ... SELECT / UNION ...) sans aucun noeud d'ecriture.
    Leve SQLSecurityError sinon (echec ferme) ; renvoie l'arbre valide."""
    tree = _parse_single_query(sql)
    _assert_lecture_seule(tree)
    return tree


# ── AANA2 — Isolation societe par REECRITURE D'ARBRE (sqlglot) ──────────────
# D-AANA-4 : l'etancheite n'est JAMAIS « prouvee » par une regex sur le texte
# SQL. L'ancien garde cherchait un motif `company_id = <id>` dans la requete :
# `WHERE NOT (company_id = 7)`, `(company_id = 7) IS NOT NULL`,
# `company_id = 7 - 1`, une projection `company_id = 7 AS mine` ou meme un
# litteral `'company_id = 7'` le satisfaisaient — et la requete lisait toutes
# les societes (sonde du 05/10, C-AANA-001).
#
# Desormais la requete est PARSEE (sqlglot, dialecte postgres) et CHAQUE table
# autorisee lue, ou qu'elle soit (FROM, JOIN, sous-requete, CTE, UNION,
# EXISTS...), est REMPLACEE dans l'arbre par la sous-requete filtree
#     (SELECT * FROM <t> WHERE company_id = <id du jeton>) AS <alias>
# (`id = <id>` pour la table societe elle-meme). Le predicat ecrit par le LLM
# n'a donc plus aucune importance : la requete ne VOIT que les lignes de la
# societe de l'appelant. C'est le SQL REGENERE depuis l'arbre — jamais le texte
# d'origine — qui est execute ; ce qui a ete verifie est donc ce qui tourne.
#
# Fail-closed : SQL illisible, plusieurs instructions, table hors allowlist,
# table qualifiee par un schema etranger, fonction en position de table,
# WITH RECURSIVE, CTE homonyme d'une table autorisee -> SQLSecurityError.

_SQL_DIALECT = "postgres"

# Arguments d'un noeud Table que la reecriture sait conserver. Tout autre
# argument (TABLESAMPLE, pivots, hints, time-travel...) -> rejet.
_TABLE_ARGS_REECRITS = frozenset({"this", "db", "catalog", "alias", "only"})


def _parse_single_query(sql: str) -> exp.Query:
    """Parse `sql` en UN arbre de requete (SELECT / UNION / ...). Echec ferme."""
    try:
        statements = [
            s for s in sqlglot.parse(sql or "", read=_SQL_DIALECT)
            if s is not None
        ]
    except sqlglot.errors.SqlglotError as exc:
        raise SQLSecurityError("Requete SQL illisible : refusee.") from exc
    if len(statements) != 1:
        raise SQLSecurityError(
            "Une seule instruction SELECT est autorisee (lecture seule)."
        )
    root = statements[0]
    if not isinstance(root, exp.Query):
        raise SQLSecurityError("Seules les requetes SELECT sont autorisees.")
    return root


def _scoped_source(name: str, company_id: int, alias) -> exp.Subquery:
    """`(SELECT * FROM <name> WHERE company_id = <id>) AS <alias>`.

    La table societe (`authentication_company`) est filtree par son `id`. Sans
    alias explicite, la sous-requete reprend le NOM de la table pour que les
    references qualifiees (`crm_client.nom`) restent valides."""
    colonne = "id" if name == _TENANT_TABLE else "company_id"
    inner = (
        exp.select(exp.Star())
        .from_(exp.Table(this=exp.to_identifier(name)))
        .where(exp.EQ(
            this=exp.column(colonne),
            expression=exp.Literal.number(int(company_id)),
        ))
    )
    if alias is None:
        alias = exp.TableAlias(this=exp.to_identifier(name))
    return exp.Subquery(this=inner, alias=alias)


def _rewrite_table(table: exp.Table, visibles: frozenset, company_id: int):
    """Remplace une table autorisee par sa sous-requete filtree ; laisse une
    reference de CTE visible intacte ; rejette tout le reste."""
    extra = {
        k for k, v in table.args.items()
        if v not in (None, False, []) and k not in _TABLE_ARGS_REECRITS
    }
    if extra:
        raise SQLSecurityError(
            "Clause de table non supportee : " + ", ".join(sorted(extra))
        )
    if not isinstance(table.this, exp.Identifier):
        # Fonction en position de table (generate_series, unnest, ...).
        raise SQLSecurityError("Source de donnees non autorisee.")
    if table.args.get("catalog") is not None:
        raise SQLSecurityError("Reference de base externe interdite.")
    name = table.name.lower()
    schema = table.text("db").lower()
    if not schema and name in visibles:
        return table  # reference a une CTE de la requete (deja reecrite)
    if schema not in ("", "public") or name not in _TENANT_SCOPED_TABLES:
        raise SQLSecurityError(
            "Table non autorisee ou non scopee par societe : "
            + (f"{schema}." if schema else "") + name
        )
    return _scoped_source(name, company_id, table.args.get("alias"))


def _rewrite_node(node, visibles: frozenset, company_id: int, found: list):
    """Parcours recursif respectant la PORTEE des CTE (Postgres) : une CTE n'est
    visible que dans la requete qui la porte, et dans le corps des CTE
    SUIVANTES de la meme liste — jamais avant (sinon `WITH a AS (SELECT * FROM
    pg_user), pg_user AS (...)` ferait passer la vraie table pour une CTE)."""
    if isinstance(node, exp.Table):
        found.append(node.name.lower())
        return _rewrite_table(node, visibles, company_id)
    inner_visibles = visibles
    for value in node.args.values():
        if isinstance(value, exp.With):
            if value.args.get("recursive"):
                raise SQLSecurityError("WITH RECURSIVE interdit.")
            noms = set(visibles)
            for cte in value.expressions:
                nom = (cte.alias or "").lower()
                if not nom or nom in _TENANT_SCOPED_TABLES:
                    raise SQLSecurityError(
                        "Nom de CTE invalide ou homonyme d'une table."
                    )
                cte.set("this", _rewrite_node(
                    cte.this, frozenset(noms), company_id, found))
                noms.add(nom)
            inner_visibles = frozenset(noms)
    for key, value in list(node.args.items()):
        if isinstance(value, exp.With):
            continue
        if isinstance(value, exp.Expression):
            node.set(key, _rewrite_node(
                value, inner_visibles, company_id, found))
        elif isinstance(value, list):
            node.set(key, [
                _rewrite_node(v, inner_visibles, company_id, found)
                if isinstance(v, exp.Expression) else v
                for v in value
            ])
    return node


def _assert_no_foreign_company_literal(tree: exp.Expression,
                                       company_id: int) -> None:
    """Un predicat `company_id = <autre id>` (ou `IN (..autre..)`) trahit une
    tentative de lecture d'une autre societe : on le refuse explicitement
    plutot que de renvoyer silencieusement zero ligne. Verification sur
    l'ARBRE (colonne + litteral), pas sur le texte."""
    def _foreign(lit) -> bool:
        return (
            isinstance(lit, exp.Literal) and not lit.is_string
            and lit.this.isdigit() and int(lit.this) != int(company_id)
        )

    for cmp in tree.find_all(exp.EQ, exp.In):
        if isinstance(cmp, exp.EQ):
            pairs = [(cmp.this, cmp.expression), (cmp.expression, cmp.this)]
            for col, lit in pairs:
                if (isinstance(col, exp.Column)
                        and col.name.lower() == "company_id" and _foreign(lit)):
                    raise SQLSecurityError(
                        "Reference a une autre societe detectee : requete "
                        "refusee."
                    )
        elif (isinstance(cmp.this, exp.Column)
              and cmp.this.name.lower() == "company_id"
              and any(_foreign(v) for v in cmp.expressions)):
            raise SQLSecurityError(
                "Reference a une autre societe detectee : requete refusee."
            )


def _inject_company_filter(sql: str, company_id: int) -> str:
    """AANA2 — Reecrit `sql` pour que TOUTE table lue soit la sous-requete
    `(SELECT * FROM <t> WHERE company_id = <company_id>)`. Renvoie le SQL
    REGENERE depuis l'arbre (sans commentaires). Leve SQLSecurityError sur
    tout ce qui ne peut pas etre reecrit sur. Aucun raccourci « le filtre est
    deja la » : le texte ecrit par le LLM ne prouve rien (C-AANA-001)."""
    if not company_id:
        # Sans company_id on ne peut RIEN garantir -> refus total (ERR44
        # garantit deja un company_id non nul cote endpoint ; 2e barriere).
        raise SQLSecurityError("Contexte societe absent : requete refusee.")
    tree = _enforce_single_select(sql)
    _assert_fonctions_autorisees(tree)
    _assert_no_foreign_company_literal(tree, company_id)
    found: list[str] = []
    tree = _rewrite_node(tree, frozenset(), int(company_id), found)
    if not found:
        # Aucune table : rien a scoper, rien a lire -> refus (fail-closed).
        raise SQLSecurityError(
            "Impossible d'identifier les tables : requete refusee."
        )
    return tree.sql(dialect=_SQL_DIALECT, comments=False)


def _extract_base_tables(sql: str) -> set[str]:
    """Noms des tables de BASE lues par `sql` (hors CTE), via l'arbre sqlglot.
    Utilise par le banc d'evaluation (tests/eval/runner.py). Ensemble vide si
    la requete est illisible."""
    try:
        tree = _parse_single_query(sql)
    except SQLSecurityError:
        return set()
    ctes = {(c.alias or "").lower() for c in tree.find_all(exp.CTE)}
    return {
        t.name.lower() for t in tree.find_all(exp.Table)
        if t.name and t.name.lower() not in ctes
    }


# ── AUD401 + L17 + AANA4 — confidentialite INTRA-societe des PROJECTIONS ─────
# La reecriture AANA2 garantit l'isolation ENTRE societes, mais ne borne AUCUNE
# colonne DANS une societe. Deux familles de colonnes ne doivent jamais sortir
# par le canal du chatbot :
#   - les SECRETS de compte (hash PBKDF2, graine TOTP, drapeaux d'elevation) :
#     garde INCONDITIONNEL — aucune permission metier ne le leve (AUD401) ;
#   - le PRIX D'ACHAT / la MARGE (CLAUDE.md : `Produit.prix_achat` est un
#     indicateur GENERATEUR, jamais client-facing) : leve uniquement pour un
#     porteur de `prix_achat_voir` (L17).
# AANA4 (C-AANA-003) — une colonne sort aussi SANS ETRE NOMMEE, par une
# projection LIGNE ENTIERE : `*`, `alias.*`, `(alias).*`, `row_to_json(alias)`,
# `alias::text`, `array_agg(alias)`... (sonde du 05/10 : `row_to_json(u)`
# contenait la cle `password`). UNE seule verification, sur l'ARBRE sqlglot
# (plus de regex sur le texte) : `_references_forbidden_column`.
#
# Verifie a l'ecriture d'AUD401 : `parametres_companyprofile` ne porte AUCUN
# secret SMTP/API dans ce depot — elle reste donc lisible.
_SECRET_COLUMNS = (
    "password",            # hash PBKDF2 (AbstractBaseUser)
    "last_login",
    "is_superuser",
    "is_staff",
    "totp_secret",         # graine 2FA (chiffree au repos, dechiffree par l'ORM)
    "totp_recovery_codes",
)

# Tables dont une projection LIGNE ENTIERE exposerait un secret de compte.
_SECRET_TABLES = ("authentication_customuser",)

_FORBIDDEN_COLUMNS = (
    "prix_achat",
    "prix_achat_unitaire",
    "prix_achat_ht",
    "prix_revendeur",
    "marge",
    "marge_snapshot",      # ventes.Devis — marge HT figee (manager-only)
)

# Tables autorisees portant un prix d'achat ou une marge (verifie sur les
# modeles Django : stock.Produit.prix_achat, ventes.Devis.marge_snapshot).
_PRICE_TABLES = ("stock_produit", "ventes_devis")

# Reponse renvoyee a l'agent quand il tente d'acceder a une colonne interdite —
# le LLM la verbalise alors proprement, sans jamais voir la donnee.
_FORBIDDEN_TOOL_REPLY = (
    "Erreur : acces refuse. La consultation du prix d'achat ou de la marge "
    "n'est pas autorisee. Reformule la question sans ces informations."
)

# ERR1/ERR2 — Reponse renvoyee a l'agent quand la requete generee n'est pas une
# lecture seule prouvee ou n'est pas correctement scopee par societe. La requete
# n'est JAMAIS executee.
_UNSAFE_QUERY_REPLY = (
    "Erreur : requete refusee pour raison de securite. Seules des consultations "
    "(SELECT) limitees aux donnees de votre entreprise sont autorisees. "
    "Reformule ta question."
)


def _select_sources(select: exp.Select) -> list:
    """Sources DIRECTES (FROM + JOIN) d'un SELECT."""
    sources = []
    from_ = select.args.get("from_") or select.args.get("from")
    if from_ is not None:
        sources.append(from_.this)
    for join in select.args.get("joins") or []:
        sources.append(join.this)
    return sources


def _references_forbidden_column(sql: str, allow_price: bool = False) -> bool:
    """True si la requete peut RESTITUER une colonne confidentielle — secret de
    compte (toujours) ou prix d'achat / marge (sauf `allow_price`) — qu'elle
    soit NOMMEE ou emportee par une projection LIGNE ENTIERE d'une table qui la
    porte. Verification sur l'arbre sqlglot ; SQL illisible -> True (fail-closed).

    Frontiere STRICTE par identifiant : `password_min_length` ou
    `must_change_password` ne sont PAS des secrets (politique interrogeable)."""
    try:
        tree = _parse_single_query(sql)
    except SQLSecurityError:
        return True
    colonnes = set(_SECRET_COLUMNS)
    tables = set(_SECRET_TABLES)
    if not allow_price:
        colonnes |= set(_FORBIDDEN_COLUMNS)
        tables |= set(_PRICE_TABLES)

    # 1. Colonne NOMMEE (identifiant, quel que soit le contexte ou la casse).
    for ident in tree.find_all(exp.Identifier):
        if ident.name.lower() in colonnes:
            return True

    # 2. Projection LIGNE ENTIERE d'une table sensible : noms de « ligne » =
    # nom de la table et son alias.
    lignes: set[str] = set()
    for table in tree.find_all(exp.Table):
        if table.name.lower() in tables:
            lignes.add(table.name.lower())
            if table.alias:
                lignes.add(table.alias.lower())
    if not lignes:
        return False

    # 2a. Reference a la ligne comme VALEUR : row_to_json(u), u::text,
    # array_agg(u), (u).*, `SELECT stock_produit FROM stock_produit`...
    for col in tree.find_all(exp.Column):
        if col.name.lower() in lignes:
            return True

    # 2b. Etoiles : `alias.*` d'une table sensible, ou `*` nu dans un SELECT
    # dont une source DIRECTE est une table sensible. `COUNT(*)` ne restitue
    # aucune colonne : tolere (« combien d'utilisateurs ? »).
    for star in tree.find_all(exp.Star):
        parent = star.parent
        if isinstance(parent, exp.Count):
            continue
        if isinstance(parent, exp.Column):
            if (parent.table or "").lower() in lignes:
                return True
            continue
        select = star.find_ancestor(exp.Select)
        if select is None:
            return True
        for source in _select_sources(select):
            if (isinstance(source, exp.Table)
                    and source.name.lower() in tables):
                return True
    return False


def _references_secret_column(sql: str) -> bool:
    """Secrets de compte SEULS (garde inconditionnel AUD401) : meme
    verification que `_references_forbidden_column`, prix d'achat autorise."""
    return _references_forbidden_column(sql, allow_price=True)


def _validate_and_secure(sql: str, company_id: int,
                         allow_price: bool = False) -> str:
    """Point d'entree unique de securisation d'une requete generee :
      ERR1 : prouve que c'est une seule instruction SELECT en lecture seule ;
      AANA3 : refuse toute fonction hors liste blanche ;
      AUD401/L17/AANA4 : refuse toute projection d'un secret de compte
             (toujours) ou d'un prix d'achat / marge (sans `allow_price`),
             nommee OU emportee par une projection ligne entiere ;
      AANA2 : REECRIT l'arbre pour que chaque table lue soit la sous-requete
             filtree sur la societe du jeton (sqlglot) ; renvoie le SQL
             regenere — c'est LUI, et lui seul, qui est execute.
    Leve SQLSecurityError en cas d'echec — l'appelant renvoie un refus francais
    a l'agent sans jamais executer la requete."""
    _enforce_single_select(sql)
    if _references_secret_column(sql):
        raise SQLSecurityError(
            "Colonne confidentielle de compte (mot de passe / 2FA / privileges) "
            "— lecture refusee."
        )
    if not allow_price and _references_forbidden_column(sql):
        raise SQLSecurityError(
            "Colonne confidentielle (prix d'achat / marge) — lecture refusee."
        )
    return _inject_company_filter(sql, company_id)


# ── NTPLT4 — GUC tenant sur la connexion du SQL-agent (defense en profondeur) ─


def _rls_enabled() -> bool:
    """True si POSTGRES_RLS_ENABLED=1 (defaut OFF)."""
    import os
    return os.environ.get("POSTGRES_RLS_ENABLED", "0") == "1"


def _apply_tenant_guc(db, company_id: int) -> None:
    """NTPLT4 — pose app.current_company sur les connexions du moteur du SQL-agent.

    Meme une requete SQL ECRITE PAR LE LLM ne peut alors PHYSIQUEMENT pas lire
    un autre tenant : les policies RLS Postgres (NTPLT2) filtrent sur ce GUC.
    C'est une defense en profondeur qui s'AJOUTE a l'injection company_id
    applicative existante (_inject_company_filter), jamais un remplacement.

    Sur : le moteur ``SQLDatabase.from_uri`` est CREE A CHAQUE requete de
    l'agent et n'est scope qu'a UNE seule societe (company_id). On enregistre
    donc un listener ``connect`` qui pose le GUC des l'ouverture de chaque
    connexion physique de CE moteur — jamais partage entre societes. Le SQL-agent
    est en LECTURE SEULE (role dedie ERR3), donc un SET de session est acceptable
    ici (moteur mono-societe, ephemere) ; on reste conservateur en repoussant
    le GUC a chaque connexion neuve.

    No-op total quand RLS est desactive (defaut) OU sans company_id : aucun SET
    n'est emis, comportement byte-identique a aujourd'hui.
    """
    if not _rls_enabled() or not company_id:
        return
    engine = getattr(db, "_engine", None)
    if engine is None:
        return
    from sqlalchemy import event

    cid = int(company_id)

    @event.listens_for(engine, "connect")
    def _set_current_company(dbapi_connection, connection_record):  # noqa: ANN001
        # set_config(..., false) == SET de session sur CETTE connexion physique ;
        # le moteur etant mono-societe et ephemere, aucune fuite inter-tenant.
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute(
                "SELECT set_config('app.current_company', %s, false)",
                (str(cid),),
            )
        finally:
            cursor.close()


# ── Outil SQL securise ────────────────────────────────────────────────────────


def _make_secure_query_tool(db, company_id: int, allow_purchase_price: bool = False):
    """
    Retourne un QuerySQLDataBaseTool qui :
      1. BLOQUE toute requete touchant le prix d'achat / la marge quand
         l'appelant n'a pas la permission `prix_achat_voir` (garde DUR, L17) ;
      2. injecte company_id avant execution.
    Utilise une closure pour eviter les problemes Pydantic avec les attributs prives.
    """
    from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool

    _cid = company_id  # capture par closure — immune aux reinitialisations Pydantic
    _allow_price = allow_purchase_price

    class _SecureQueryTool(QuerySQLDataBaseTool):
        def _run(self, query: str, run_manager=None) -> str:
            # Garde confidentialite : refus AVANT toute execution SQL. Reponse
            # « prix d'achat » seulement quand c'est bien LUI qui bloque (un
            # secret de compte ou un SQL illisible -> refus generique plus bas).
            if (not _allow_price and _references_forbidden_column(query)
                    and not _references_secret_column(query)):
                logger.warning(
                    "SECURITE: requete bloquee (prix_achat/marge non autorise). "
                    "SQL: %s", (query or "")[:200],
                )
                return _FORBIDDEN_TOOL_REPLY
            # ERR1/ERR2 — Validation au niveau code (single-SELECT en lecture
            # seule + isolation tenant prouvee). Fail-closed : tout ce qui n'est
            # pas prouve sur est refuse sans jamais etre execute.
            try:
                secured = _validate_and_secure(
                    query, _cid, allow_price=_allow_price)
            except SQLSecurityError as exc:
                logger.warning(
                    "SECURITE: requete refusee (%s). SQL: %s",
                    exc, (query or "")[:200],
                )
                return _UNSAFE_QUERY_REPLY
            return super()._run(secured, run_manager=run_manager)

    return _SecureQueryTool(db=db)


# ── Callback pour capturer la requete SQL generee ─────────────────────────────


class _SQLCapture(BaseCallbackHandler):
    """Intercepte les appels d'outils : capture le SQL final et signale si un
    outil d'ACTION (ecriture) a ete utilise."""

    def __init__(self, action_tool_names: set[str] | None = None) -> None:
        self.queries: list[str] = []
        self._action_names = action_tool_names or set()
        self.action_used = False

    def on_tool_start(
        self, serialized: dict, input_str: str, **kwargs: Any
    ) -> None:
        name = serialized.get("name")
        if name == "sql_db_query":
            self.queries.append(str(input_str))
        elif name in self._action_names:
            self.action_used = True


# ── Service ───────────────────────────────────────────────────────────────────


class SQLAgentService:

    def __init__(self) -> None:
        self._embeddings = None
        # Selection de tables EN MEMOIRE (plus de pgvector) : les vecteurs des
        # descriptions sont calcules une seule fois puis mis en cache.
        self._table_names: list[str] | None = None
        self._table_vectors: list[list[float]] | None = None
        self._init_lock = threading.Lock()  # evite la race condition au demarrage

    # ── Embeddings (sentence-transformers, local, gratuit) ────────────────

    def _get_embeddings(self):
        if self._embeddings is None:
            from langchain_community.embeddings import HuggingFaceEmbeddings
            self._embeddings = HuggingFaceEmbeddings(
                model_name="all-MiniLM-L6-v2",
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
        return self._embeddings

    # ── Selection de tables pertinentes (EN MEMOIRE, sans pgvector) ───────
    # pgvector etait fragile : selon la version, l'API `connection=` attend un
    # Engine SQLAlchemy ; lui passer une URL en chaine levait « 'str' object has
    # no attribute 'connect' ». L'ancien repli renvoyait alors TOUTES les tables,
    # gonflant le prompt a ~20k tokens et depassant la limite TPM du palier
    # gratuit Groq (12k) -> 413/504. Pour ~20 courtes descriptions, un vector
    # store persistant est inutile : on embarque les descriptions en memoire
    # (modele local deja charge) et on classe par similarite cosinus. Le repli
    # (modele indisponible) score par mots-cles et reste BORNE a k tables —
    # JAMAIS toutes — pour que le prompt tienne sous la limite en toute
    # circonstance.

    def _ensure_table_vectors(self) -> None:
        if self._table_vectors is None:
            with self._init_lock:
                if self._table_vectors is None:  # double-checked locking
                    emb = self._get_embeddings()
                    names = list(_TABLE_DESCRIPTIONS.keys())
                    docs = [f"Table: {t}. {_TABLE_DESCRIPTIONS[t]}" for t in names]
                    self._table_vectors = emb.embed_documents(docs)
                    self._table_names = names

    def _get_relevant_tables(self, question: str, k: int = 5) -> list[str]:
        try:
            self._ensure_table_vectors()
            qv = self._get_embeddings().embed_query(question)
            # Embeddings normalises (normalize_embeddings=True) -> produit
            # scalaire = cosinus. Pas de numpy : ~20x384 multiplications.
            scored = [
                (sum(a * b for a, b in zip(vec, qv)), name)
                for name, vec in zip(self._table_names, self._table_vectors)
            ]
            scored.sort(key=lambda s: s[0], reverse=True)
            tables = [name for _, name in scored[: max(1, k)]]
            logger.info("Tables pertinentes (embeddings en memoire): %s", tables)
            return tables
        except Exception as exc:
            logger.warning(
                "Embeddings indisponibles, repli mots-cles borne: %s", exc)
            return self._keyword_relevant_tables(question, k)

    @staticmethod
    def _keyword_relevant_tables(question: str, k: int = 5) -> list[str]:
        """Repli SANS modele : score par recouvrement de mots, BORNE a k tables.
        Ne renvoie JAMAIS toutes les tables (sinon prompt > limite TPM Groq)."""
        words = {w for w in re.findall(r"\w+", question.lower()) if len(w) > 3}
        scored = []
        for table, desc in _TABLE_DESCRIPTIONS.items():
            hay = (table + " " + desc).lower()
            scored.append((sum(1 for w in words if w in hay), table))
        scored.sort(key=lambda s: s[0], reverse=True)
        top = [t for score, t in scored if score > 0][: max(1, k)]
        # Aucun mot connu -> petit noyau commercial par defaut (jamais tout).
        return top or ["crm_client", "ventes_devis",
                       "ventes_facture", "stock_produit"][: max(1, k)]

    # ── Factory LLM ───────────────────────────────────────────────────────

    @staticmethod
    def _build_llm():
        provider = SQL_AGENT_PROVIDER.lower()
        model = SQL_AGENT_MODEL

        if provider == "groq":
            if not GROQ_API_KEY:
                raise RuntimeError("GROQ_API_KEY manquante dans .env")
            from langchain_groq import ChatGroq
            return ChatGroq(model=model, api_key=GROQ_API_KEY, temperature=0)

        if provider == "openai":
            if not OPENAI_API_KEY:
                raise RuntimeError("OPENAI_API_KEY manquante dans .env")
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model=model, api_key=OPENAI_API_KEY, temperature=0)

        if provider == "claude":
            if not CLAUDE_API_KEY:
                raise RuntimeError("CLAUDE_API_KEY manquante dans .env")
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(model=model, api_key=CLAUDE_API_KEY, temperature=0)

        if provider == "ollama":
            from langchain_ollama import ChatOllama
            return ChatOllama(model=model, temperature=0)

        raise RuntimeError(
            f"SQL_AGENT_PROVIDER='{provider}' non supporte. "
            "Valeurs: groq, openai, claude, ollama"
        )

    # ── Historique Redis ──────────────────────────────────────────────────

    @staticmethod
    def _history_key(user_id: int) -> str:
        return f"chat_history:user_{user_id}"

    def _load_history(self, user_id: int) -> list[dict]:
        """Charge les messages depuis Redis. Retourne [] si Redis indisponible."""
        try:
            import redis as redis_lib
            r = redis_lib.from_url(REDIS_CHAT_URL, decode_responses=True)
            raw = r.lrange(self._history_key(user_id), 0, -1)
            import json
            return [json.loads(m) for m in raw]
        except Exception as exc:
            logger.warning("Redis historique indisponible (lecture): %s", exc)
            return []

    def _save_history(
        self, user_id: int, question: str, answer: str
    ) -> None:
        """Sauvegarde un echange dans Redis avec TTL 24h."""
        try:
            import json
            import redis as redis_lib
            r = redis_lib.from_url(REDIS_CHAT_URL, decode_responses=True)
            key = self._history_key(user_id)
            pipe = r.pipeline()
            pipe.rpush(key, json.dumps({"role": "user", "content": question}))
            pipe.rpush(key, json.dumps({"role": "agent", "content": answer}))
            # Garde seulement les CHAT_HISTORY_MAX derniers messages
            pipe.ltrim(key, -CHAT_HISTORY_MAX, -1)
            # Renouvelle le TTL a chaque echange
            pipe.expire(key, CHAT_HISTORY_TTL)
            pipe.execute()
        except Exception as exc:
            logger.warning("Redis historique indisponible (ecriture): %s", exc)

    def get_history(self, user_id: int) -> list[dict]:
        """Endpoint GET /history — retourne l'historique pour le frontend."""
        return self._load_history(user_id)

    def clear_history(self, user_id: int) -> None:
        """Endpoint DELETE /history — efface la conversation."""
        try:
            import redis as redis_lib
            r = redis_lib.from_url(REDIS_CHAT_URL, decode_responses=True)
            r.delete(self._history_key(user_id))
        except Exception as exc:
            logger.warning("Redis historique indisponible (suppression): %s", exc)

    # ── Methode principale ────────────────────────────────────────────────

    def _run_agent(
        self, question: str, company_id: int, user_id: int = 0,
        action_ctx: "ActionContext | None" = None,
    ) -> dict[str, Any]:
        """Execution synchrone de l'agent (appelee via asyncio.to_thread)."""
        from langchain_community.utilities import SQLDatabase
        from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
        from langchain.agents import AgentExecutor, create_tool_calling_agent
        from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
        from langchain_core.messages import HumanMessage, AIMessage
        from app.services.action_tools import (
            actions_available, build_action_tools,
        )

        # 1. Historique Redis → messages LangChain (2 derniers echanges seulement)
        # On limite volontairement pour eviter que d'anciens resultats incorrects
        # contaminent les nouvelles questions. L'historique complet reste dans Redis
        # pour l'affichage frontend, mais le LLM ne recoit que le contexte recent.
        raw_history = self._load_history(user_id)
        recent = raw_history[-4:] if len(raw_history) >= 4 else raw_history
        lc_history = []
        for msg in recent:
            if msg.get("role") == "user":
                lc_history.append(HumanMessage(content=msg["content"]))
            elif msg.get("role") == "agent":
                lc_history.append(AIMessage(content=msg["content"]))

        # 2. Tables pertinentes via pgvector. ERR43 — on RESTREINT a l'allowlist
        # company-scoped : aucune table hors allowlist n'est jamais exposee aux
        # outils sql_db_list_tables / sql_db_schema.
        relevant_tables = [
            t for t in self._get_relevant_tables(question)
            if t in _ALLOWED_TABLES
        ] or list(_ALLOWED_TABLES)

        # 2. SQLDatabase filtre.
        # ERR3 — connexion DEDIEE LECTURE SEULE (SQL_AGENT_DATABASE_URL) : l'agent
        # ne se connecte jamais avec le role owner. Retombe sur DATABASE_URL si
        # SQL_AGENT_DB_USER n'est pas defini (non-cassant).
        # ERR43 — sample_rows_in_table_info=0 : aucune ligne reelle n'est injectee
        # dans le contexte du LLM (sinon fuite incidente inter-tenant).
        # AANA5 — moteur cree par app.core.database (statement_timeout 15 s).
        from app.core import database as _database
        db = SQLDatabase(
            _database.create_sql_agent_engine(),
            include_tables=relevant_tables,
            sample_rows_in_table_info=0,
        )
        # NTPLT4 — defense en profondeur : pose app.current_company sur les
        # connexions de CE moteur (mono-societe, ephemere) quand RLS est actif,
        # de sorte que meme une requete ecrite par le LLM ne puisse pas lire un
        # autre tenant. No-op sans POSTGRES_RLS_ENABLED (defaut).
        _apply_tenant_guc(db, company_id)

        # 3. LLM
        llm = self._build_llm()

        # L17 — autorisation de voir le prix d'achat / la marge : UNIQUEMENT les
        # appelants disposant de la permission `prix_achat_voir` (ou superuser).
        # Sinon le garde DUR de l'outil SQL bloque toute requete confidentielle.
        allow_price = bool(
            action_ctx is not None
            and (
                action_ctx.is_superuser
                or "prix_achat_voir" in action_ctx.permissions
            )
        )

        # 4. Toolkit → remplacement de l'outil sql_db_query par la version securisee
        # On compare par nom d'outil (fiable) et non par classe (nom instable selon version)
        toolkit = SQLDatabaseToolkit(db=db, llm=llm)
        tools = [
            _make_secure_query_tool(db, company_id, allow_price)
            if t.name == "sql_db_query"
            else t
            for t in toolkit.get_tools()
        ]

        # 4b. N86 — outils d'ACTION (ecriture). Exposes UNIQUEMENT si l'appelant
        # a un droit d'ecriture et qu'une URL Django interne est configuree. Un
        # role lecture seule n'en recoit aucun. Django reste l'autorite finale.
        # ERR19 — Separation stricte des chemins : le chemin SQL (sql_db_query)
        # est PUREMENT lecture seule (garde single-SELECT ERR1 — toute DML
        # injectee via le prompt est refusee AVANT execution) ; les outils
        # d'action n'executent JAMAIS de SQL, ils relaient un appel REST a Django
        # qui re-applique scope societe + permissions. Une injection de prompt ne
        # peut donc ni ecrire en base via SQL, ni atteindre un outil d'action si
        # l'appelant n'a pas deja le droit d'ecriture cote serveur.
        # AG2 (surfacage) — collecteur partage par requete : chaque outil
        # d'action y depose sa sortie structuree (proposition signee avec
        # confirm_token, ou resultat d'une action interne). On le remonte ensuite
        # au frontend, qui ne peut PAS recuperer le jeton autrement (le LLM ne
        # re-emet jamais le JSON brut).
        action_outputs: list[dict[str, Any]] = []
        action_tool_names: set[str] = set()
        if actions_available(action_ctx):
            action_tools = build_action_tools(action_ctx, action_outputs)
            tools.extend(action_tools)
            action_tool_names = {t.name for t in action_tools}

        # 5. Prompt avec historique (+ restriction marge si non autorise).
        # Defense en profondeur : meme decision que le garde DUR de l'outil SQL.
        system_prompt = _AGENT_PREFIX
        if not allow_price:
            system_prompt = system_prompt + _MARGIN_RESTRICTION
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        # 6. Agent + capture SQL/actions
        capture = _SQLCapture(action_tool_names)
        agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)
        executor = AgentExecutor(
            agent=agent,
            tools=tools,
            max_iterations=10,
            verbose=False,
            handle_parsing_errors=True,
        )

        result = executor.invoke(
            {"input": question, "chat_history": lc_history},
            config={"callbacks": [capture]},
        )

        answer = result.get("output", "Aucune reponse obtenue.")

        # Sauvegarde l'echange dans Redis
        self._save_history(user_id, question, answer)

        # ERR84 — le SQL genere (avec les vrais noms de tables) reste cote
        # serveur (log de debug uniquement) et n'est JAMAIS renvoye au client :
        # divulgation de schema. La reponse client porte `sql_query=""`.
        final_sql = capture.queries[-1] if capture.queries else ""
        if final_sql:
            logger.debug("SQL agent — requete finale (serveur): %s", final_sql)

        # AG2 (surfacage) — on remonte la DERNIERE proposition en attente et/ou
        # le DERNIER resultat d'action interne produit ce tour, pour que le
        # frontend puisse afficher une carte de proposition et, surtout, appeler
        # /confirm avec le `confirm_token` signe (le seul chemin pour confirmer).
        proposal = self._build_proposal_payload(action_outputs)
        action_result = self._build_result_payload(action_outputs)

        return {
            "answer": answer,
            "sql_query": "",
            "data": None,
            # N86 — True si l'agent a effectue une action d'ecriture (le
            # frontend affiche alors un badge « Action »).
            "action_performed": capture.action_used,
            # AG2 — proposition a confirmer (outward/irreversible) ou resultat
            # d'une action interne deja executee. None quand aucune action.
            "proposal": proposal,
            "result": action_result,
        }

    @staticmethod
    def _build_proposal_payload(
        action_outputs: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """AG2 — extrait la derniere PROPOSITION (outward/irreversible) du
        collecteur d'actions. Renvoie le sous-ensemble destine au frontend
        (avec le `confirm_token` signe), ou None si aucune proposition."""
        for out in reversed(action_outputs or []):
            if out.get("type") == "proposal":
                payload = {
                    "action_key": out.get("action_key"),
                    "human_preview": out.get("human_preview"),
                    "confirm_token": out.get("confirm_token"),
                    "inputs": out.get("inputs"),
                }
                if out.get("note"):
                    payload["note"] = out["note"]
                return payload
        return None

    @staticmethod
    def _build_result_payload(
        action_outputs: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """AG2 — extrait le dernier RESULTAT d'action interne deja executee.
        Aplatit le payload Django (`data`) au niveau racine pour que le frontend
        y lise directement reference / wa_url / devis_id / detail. None si aucun
        resultat."""
        for out in reversed(action_outputs or []):
            if out.get("type") == "result":
                payload: dict[str, Any] = {"action_key": out.get("action_key")}
                data = out.get("data")
                if isinstance(data, dict):
                    payload.update(data)
                elif data is not None:
                    payload["data"] = data
                return payload
        return None

    async def query(
        self,
        question: str,
        user_id: int | None = None,
        company_id: int | None = None,
        action_ctx: "ActionContext | None" = None,
    ) -> dict[str, Any]:
        try:
            return await asyncio.to_thread(
                self._run_agent, question, company_id or 0, user_id or 0,
                action_ctx,
            )
        except RuntimeError as exc:
            return {"answer": str(exc), "sql_query": "", "data": None}
        except Exception as exc:
            err_str = str(exc)
            logger.error("SQL agent error: %s", exc)
            if "rate_limit" in err_str.lower() or "429" in err_str:
                return {
                    "answer": (
                        "Le service IA a atteint sa limite d'utilisation journaliere. "
                        "Veuillez reessayer dans quelques minutes."
                    ),
                    "sql_query": "",
                    "data": None,
                }
            return {
                "answer": (
                    "Je n'ai pas pu traiter votre demande. "
                    "Essayez de reformuler votre question autrement, "
                    "ou posez une question plus simple."
                ),
                "sql_query": "",
                "data": None,
            }

    async def confirm_action(
        self, action_ctx: "ActionContext", token: str,
    ) -> dict[str, Any]:
        """AG2 — Rejoue une proposition d'action stashee, par jeton.

        Delegue a `action_tools.confirm_proposal` (re-validation contre le
        catalogue + relais JWT). Execute dans un thread car l'appel Django et
        Redis sont synchrones."""
        from app.services.action_tools import confirm_proposal
        try:
            return await asyncio.to_thread(confirm_proposal, action_ctx, token)
        except Exception as exc:  # pragma: no cover - defensif
            logger.error("Confirmation d'action échouée: %s", exc)
            return {"ok": False, "error": "La confirmation a échoué."}

    async def get_schema_summary(self) -> dict[str, Any]:
        return {
            "tables": [
                {"table": t, "description": _TABLE_DESCRIPTIONS.get(t, "")}
                for t in _ALLOWED_TABLES
            ],
            "provider": SQL_AGENT_PROVIDER,
            "model": SQL_AGENT_MODEL,
            "status": "ok",
        }


# Singleton exporte
sql_agent_service = SQLAgentService()
