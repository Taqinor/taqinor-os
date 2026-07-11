"""
Service Agent SQL — LangChain + selection de tables en memoire.
Architecture :
  Question NL
    -> Embedding (sentence-transformers, local, gratuit)
    -> top-5 tables pertinentes (similarite cosinus EN MEMOIRE, sans pgvector)
    -> SQLDatabase filtre
    -> LangChain SQL Agent (provider configurable via SQL_AGENT_PROVIDER)
    -> Securite : _SecureQueryTool intercepte chaque SQL avant execution
       et injecte company_id si absent
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

import sqlparse
from sqlparse.sql import Function, Identifier, IdentifierList, Parenthesis
from sqlparse.tokens import CTE, DDL, DML, Keyword, Punctuation

try:
    # langchain < 1.0
    from langchain.callbacks.base import BaseCallbackHandler
except ImportError:  # pragma: no cover - langchain >= 1.0 a deplace le module
    # langchain >= 1.0 : le module historique a ete retire au profit de
    # langchain_core. Le comportement est identique.
    from langchain_core.callbacks.base import BaseCallbackHandler

if TYPE_CHECKING:  # eviter un import circulaire au runtime
    from app.services.action_tools import ActionContext

from app.core.config import (
    CHAT_HISTORY_MAX,
    CHAT_HISTORY_TTL,
    CLAUDE_API_KEY,
    GROQ_API_KEY,
    OPENAI_API_KEY,
    REDIS_CHAT_URL,
    SQL_AGENT_DATABASE_URL,
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

# ── Securite : validation single-SELECT + isolation tenant (parser) ───────────
# ERR1/ERR2 — Le prompt LLM ne suffit pas. On valide CHAQUE requete au niveau du
# CODE avant execution, avec un parser (sqlparse), et on ECHOUE FERME (rejet) sur
# tout ce qu'on ne peut pas prouver sur. La requete doit etre EXACTEMENT une (1)
# instruction SELECT en lecture seule (aucun INSERT/UPDATE/DELETE/DROP/ALTER/
# CREATE/GRANT/TRUNCATE/COPY/CALL/... ni instructions multiples ni CTE-avec-DML),
# et chaque table de base referencee doit etre dans l'allowlist scoped-tenant.


class SQLSecurityError(Exception):
    """Levee quand une requete ne peut PAS etre prouvee sure (echec ferme)."""


# Mots-cles d'ecriture / DDL / administration interdits n'importe ou dans la
# requete (le parser categorise deja DML/DDL, mais on double avec une liste de
# tokens explicites pour les mots non categorises par sqlparse selon la version).
_FORBIDDEN_KEYWORDS = frozenset({
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE",
    "GRANT", "REVOKE", "MERGE", "REPLACE", "UPSERT", "CALL", "DO", "EXECUTE",
    "COPY", "VACUUM", "ANALYZE", "REINDEX", "CLUSTER", "REFRESH", "COMMENT",
    "SET", "RESET", "LOCK", "PREPARE", "DEALLOCATE", "DECLARE", "FETCH",
    "MOVE", "LISTEN", "NOTIFY", "BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT",
    "INTO",  # SELECT ... INTO cree une table → interdit
})


def _strip_sql_comments(sql: str) -> str:
    """Retire les commentaires SQL pour empecher de masquer un mot interdit
    derriere `--` ou `/* */`. sqlparse fournit un formatter dedie."""
    return sqlparse.format(sql or "", strip_comments=True).strip()


def _enforce_single_select(sql: str) -> None:
    """ERR1 — Rejette tout ce qui n'est pas EXACTEMENT une instruction SELECT en
    lecture seule. Leve SQLSecurityError sinon (echec ferme).

    Defenses :
      - une seule instruction (rejet des `;` separant plusieurs requetes) ;
      - le premier token significatif doit etre SELECT (ou WITH ... SELECT) ;
      - aucun mot-cle d'ecriture/DDL/admin nulle part (y compris dans les CTE,
        sous-requetes, UNION) ;
      - aucune DML/DDL categorisee par le parser.
    """
    cleaned = _strip_sql_comments(sql)
    if not cleaned:
        raise SQLSecurityError("Requete vide.")

    # Plusieurs instructions ? sqlparse les separe ; on n'en autorise qu'une.
    statements = [s for s in sqlparse.parse(cleaned) if str(s).strip()]
    if len(statements) != 1:
        raise SQLSecurityError(
            "Une seule instruction SELECT est autorisee (lecture seule)."
        )

    stmt = statements[0]

    # Type global de l'instruction : doit etre SELECT (sqlparse.get_type()).
    stmt_type = stmt.get_type()
    if stmt_type != "SELECT":
        raise SQLSecurityError(
            f"Seules les requetes SELECT sont autorisees (recu: {stmt_type})."
        )

    # Premier token DML doit etre SELECT ; un eventuel WITH (CTE) doit aboutir a
    # un SELECT et ne contenir aucune DML.
    saw_select = False
    for token in stmt.flatten():
        ttype = token.ttype
        value = token.value.upper()
        if ttype in (DML,):
            if value != "SELECT":
                raise SQLSecurityError(
                    f"Instruction de modification interdite: {value}."
                )
            saw_select = True
        elif ttype in (DDL,):
            raise SQLSecurityError(f"Instruction DDL interdite: {value}.")
        elif ttype in Keyword and value in _FORBIDDEN_KEYWORDS:
            raise SQLSecurityError(f"Mot-cle interdit: {value}.")
        # Un `;` interne (hors fin) signale une seconde instruction masquee.
        elif ttype in (Punctuation,) and token.value == ";":
            # Tolere uniquement un `;` final unique (deja retire via rstrip plus
            # haut dans le flux d'appel) — ici on refuse tout `;` restant.
            raise SQLSecurityError("Instructions multiples interdites.")

    if not saw_select:
        raise SQLSecurityError("Aucune instruction SELECT detectee.")


def _extract_base_tables(sql: str) -> set[str]:
    """Extrait l'ensemble des noms de tables de base referencees (FROM/JOIN, y
    compris dans les sous-requetes, CTE et UNION). Approche parser : on parcourt
    l'arbre sqlparse et on collecte tout identifiant qui suit FROM/JOIN.

    Fail-closed : on enleve les alias et schemas ; les noms inconnus declenchent
    un rejet en amont (voir `_assert_tenant_safe`)."""
    cleaned = _strip_sql_comments(sql)
    tables: set[str] = set()

    def _name_of(identifier) -> str | None:
        # Identifier.get_real_name() ignore l'alias ; on retire un eventuel
        # prefixe de schema (public.stock_produit → stock_produit).
        real = None
        try:
            real = identifier.get_real_name()
        except Exception:
            real = None
        if not real:
            real = str(identifier).strip().strip('"').split()[0]
        real = real.split(".")[-1]
        return real.strip().strip('"').lower() or None

    def _walk(token_list, expecting_table: bool = False):
        for tok in token_list.tokens:
            if tok.is_whitespace:
                continue
            # Mots-cles FROM / JOIN → le(s) prochain(s) identifiant(s) sont des tables.
            if tok.ttype in Keyword and tok.value.upper() in (
                "FROM", "JOIN", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN",
                "FULL JOIN", "CROSS JOIN", "LEFT OUTER JOIN",
                "RIGHT OUTER JOIN", "FULL OUTER JOIN",
            ) or (tok.ttype in Keyword and "JOIN" in tok.value.upper()):
                expecting_table = True
                continue
            # Apres FROM/JOIN : un identifiant simple, une liste, ou une
            # sous-requete entre parentheses.
            if expecting_table:
                if isinstance(tok, IdentifierList):
                    for ident in tok.get_identifiers():
                        if isinstance(ident, Parenthesis):
                            _walk(ident)
                        elif isinstance(ident, (Identifier, Function)):
                            # Une sous-requete aliasee est une Parenthesis dans l'Identifier.
                            paren = next(
                                (t for t in ident.tokens
                                 if isinstance(t, Parenthesis)), None)
                            if paren is not None:
                                _walk(paren)
                            else:
                                n = _name_of(ident)
                                if n:
                                    tables.add(n)
                        else:
                            n = _name_of(ident)
                            if n:
                                tables.add(n)
                    expecting_table = False
                    continue
                if isinstance(tok, Parenthesis):
                    _walk(tok)
                    expecting_table = False
                    continue
                if isinstance(tok, (Identifier, Function)):
                    paren = next(
                        (t for t in tok.tokens
                         if isinstance(t, Parenthesis)), None)
                    if paren is not None:
                        _walk(paren)
                    else:
                        n = _name_of(tok)
                        if n:
                            tables.add(n)
                    expecting_table = False
                    continue
                # Token suivant inattendu apres FROM → on arrete d'attendre.
                expecting_table = False
            # Recurse dans tout conteneur (parentheses, sous-requetes, CTE).
            if tok.is_group:
                _walk(tok)

    for stmt in sqlparse.parse(cleaned):
        _walk(stmt)

    # On retire les noms de CTE (alias internes definis par WITH) : ils ne sont
    # pas des tables de base et ne portent pas company_id.
    cte_names = _extract_cte_names(cleaned)
    return {t for t in tables if t and t not in cte_names}


def _extract_cte_names(sql: str) -> set[str]:
    """Noms des CTE definis par WITH name AS (...) — a ne pas confondre avec des
    tables de base."""
    names: set[str] = set()
    for stmt in sqlparse.parse(sql):
        in_cte = False
        for tok in stmt.tokens:
            if tok.ttype is CTE or (tok.ttype in Keyword
                                    and tok.value.upper() == "WITH"):
                in_cte = True
                continue
            if not in_cte:
                continue
            if isinstance(tok, IdentifierList):
                for ident in tok.get_identifiers():
                    if isinstance(ident, Identifier):
                        nm = ident.get_real_name()
                        if nm:
                            names.add(nm.lower())
            elif isinstance(tok, Identifier):
                nm = tok.get_real_name()
                if nm:
                    names.add(nm.lower())
            if tok.ttype in DML:  # le SELECT principal commence → fin des CTE
                break
    return names


# ── Securite : injection company_id ──────────────────────────────────────────


def _inject_company_filter(sql: str, company_id: int) -> str:
    """
    Garantit que toute requete sur une table sensible filtre par company_id.
    Injecte le filtre si le LLM l'a oublie.
    """
    if not company_id:
        return sql

    sql = sql.strip().rstrip(";")

    # Filtre deja present → rien a faire
    if re.search(
        rf"\bcompany_id\s*=\s*{company_id}\b", sql, re.IGNORECASE
    ):
        return sql

    # La requete utilise-t-elle une table sensible ?
    uses_sensitive = any(
        re.search(rf"\b{re.escape(t)}\b", sql, re.IGNORECASE)
        for t in _TABLES_WITH_COMPANY_ID
    )
    if not uses_sensitive:
        return sql

    logger.warning(
        "SECURITE: company_id absent du SQL genere — injection forcee "
        "(company_id=%s). SQL original: %s",
        company_id,
        sql[:200],
    )

    # Injection dans la requete principale (niveau 0, hors sous-requetes)
    # Cherche GROUP BY / ORDER BY / HAVING / LIMIT avant WHERE
    for kw in (r"GROUP\s+BY", r"ORDER\s+BY", r"HAVING", r"LIMIT",
               r"UNION", r"EXCEPT", r"INTERSECT"):
        m = re.search(rf"\b{kw}\b", sql, re.IGNORECASE)
        if m:
            before = sql[: m.start()]
            after = sql[m.start():]
            where_m = re.search(r"\bWHERE\b", before, re.IGNORECASE)
            if where_m:
                pos = where_m.end()
                return (
                    before[:pos]
                    + f" company_id = {company_id} AND "
                    + before[pos:]
                    + after
                )
            return before + f" WHERE company_id = {company_id} " + after

    # WHERE existant sans GROUP BY/ORDER BY
    where_m = re.search(r"\bWHERE\b", sql, re.IGNORECASE)
    if where_m:
        pos = where_m.end()
        return (
            sql[:pos]
            + f" company_id = {company_id} AND "
            + sql[pos:]
        )

    # Aucun WHERE — ajout en fin de requete
    return sql + f" WHERE company_id = {company_id}"


# ── ERR2 — Isolation tenant prouvee (fail-closed) ─────────────────────────────
# Strategie : on N'ESSAIE PAS de reecrire toutes les jointures (trop risque).
# On REJETTE toute requete qu'on ne peut pas PROUVER correctement scopee :
#   1. toute table de base hors de l'allowlist tenant -> rejet (pas de table non
#      scopee comme authentication_company en lecture libre, ni table inconnue) ;
#   2. la table tenant authentication_company doit etre contrainte par
#      `id = <company_id>` ;
#   3. CHAQUE table company_id referencee doit etre contrainte par un predicat
#      `company_id = <company_id>` litteral. Pour le cas mono-table courant,
#      `_inject_company_filter` l'ajoute ; des qu'il y a PLUSIEURS tables
#      company_id (JOIN/UNION/sous-requete multi-tenant), on exige que CHAQUE
#      occurrence soit explicitement filtree — sinon rejet. Robuste contre
#      `OR 1=1` (le predicat reste un AND obligatoire ; voir _has_company_predicate).


def _count_company_predicates(sql: str, company_id: int) -> int:
    """Nombre d'occurrences d'un predicat `company_id = <company_id>` (eventuel
    prefixe d'alias/table). On compte les occurrences pour exiger un predicat
    par table company_id presente."""
    pattern = rf"(?:\w+\.)?\bcompany_id\b\s*=\s*{company_id}\b"
    return len(re.findall(pattern, sql, re.IGNORECASE))


def _has_tenant_id_predicate(sql: str, company_id: int) -> bool:
    """La table tenant est-elle contrainte par `id = <company_id>` (ou
    `authentication_company.id = N`) ?"""
    pattern = (
        rf"(?:authentication_company\.|\b\w+\.)?\bid\b\s*=\s*{company_id}\b"
    )
    return bool(re.search(pattern, sql, re.IGNORECASE))


def _references_other_tenant(sql: str, company_id: int) -> bool:
    """True si un predicat `company_id = N` cible une AUTRE societe que celle de
    l'appelant (defense contre une jointure/UNION vers un autre tenant avec un
    `company_id = 8` code en dur)."""
    for m in re.finditer(
        r"(?:\w+\.)?\bcompany_id\b\s*=\s*(\d+)", sql, re.IGNORECASE
    ):
        if int(m.group(1)) != company_id:
            return True
    return False


def _has_or_operator(sql: str) -> bool:
    """True si un operateur logique OR apparait n'importe ou dans la requete.

    Le OR est le principal vecteur de contournement du scoping (`... company_id=7
    OR 1=1`, `OR true`, `OR company_id=8`). Comme on ne peut pas PROUVER qu'un OR
    ne neutralise pas le filtre tenant, on echoue ferme et on le refuse. Les
    questions metier utilisent `IN (...)` (vu dans les exemples du prompt) plutot
    que des OR, donc l'impact fonctionnel est minimal."""
    for stmt in sqlparse.parse(sql):
        for tok in stmt.flatten():
            if tok.ttype in Keyword and tok.value.upper() == "OR":
                return True
    return False


def _assert_tenant_safe(sql: str, company_id: int) -> None:
    """Leve SQLSecurityError si la requete n'est pas PROUVABLEMENT scopee au
    tenant `company_id`. Fail-closed."""
    if not company_id:
        # Sans company_id on ne peut RIEN prouver -> refus total (ERR44 garantit
        # deja un company_id non nul cote endpoint, ceci est une 2e barriere).
        raise SQLSecurityError("Contexte societe absent : requete refusee.")

    tables = _extract_base_tables(sql)
    if not tables:
        # Aucune table identifiee = on ne peut pas prouver le scoping -> refus.
        raise SQLSecurityError(
            "Impossible d'identifier les tables : requete refusee."
        )

    # 1. Toute table hors allowlist tenant -> rejet.
    unknown = tables - _TENANT_SCOPED_TABLES
    if unknown:
        raise SQLSecurityError(
            "Table non autorisee ou non scopee par societe : "
            + ", ".join(sorted(unknown))
        )

    # 2. Aucun predicat ne doit viser une autre societe (JOIN/UNION cross-tenant).
    if _references_other_tenant(sql, company_id):
        raise SQLSecurityError(
            "Reference a une autre societe detectee : requete refusee."
        )

    # 3. Aucun OR (vecteur de contournement du scoping) — echec ferme.
    if _has_or_operator(sql):
        raise SQLSecurityError(
            "Operateur OR interdit (risque de contournement du filtrage)."
        )

    # 4. Table tenant -> doit etre contrainte par id = company_id.
    if _TENANT_TABLE in tables and not _has_tenant_id_predicate(sql, company_id):
        raise SQLSecurityError(
            "La table societe doit etre filtree par son identifiant."
        )

    # 5. Chaque table company_id doit etre filtree. Cas mono-table : un predicat
    # suffit (injecte si besoin). Multi-table : exiger un predicat par table.
    company_tables = tables & _TABLES_WITH_COMPANY_ID
    if company_tables:
        n_predicates = _count_company_predicates(sql, company_id)
        if n_predicates < len(company_tables):
            raise SQLSecurityError(
                "Chaque table doit etre filtree par company_id "
                f"(attendu {len(company_tables)}, trouve {n_predicates})."
            )


def _validate_and_secure(sql: str, company_id: int) -> str:
    """Point d'entree unique de securisation d'une requete generee :
      ERR1 : prouve que c'est une seule instruction SELECT en lecture seule ;
      ERR2 : injecte le filtre company_id (cas mono-table) puis PROUVE que la
             requete finale est correctement scopee, sinon rejet (fail-closed).
    Leve SQLSecurityError en cas d'echec — l'appelant renvoie un refus francais
    a l'agent sans jamais executer la requete."""
    _enforce_single_select(sql)
    secured = _inject_company_filter(sql, company_id)
    _assert_tenant_safe(secured, company_id)
    return secured


# ── Securite : colonnes confidentielles (prix d'achat / marge) ────────────────
# CLAUDE.md : `Produit.prix_achat` est un indicateur GENERATEUR, jamais
# client-facing. Le chatbot stock ne doit JAMAIS restituer le prix d'achat ni la
# marge. Le prompt _MARGIN_RESTRICTION le DECONSEILLE au LLM, mais ce n'est pas
# une garantie ; ce garde DUR bloque toute requete qui touche ces colonnes quand
# l'appelant n'a pas la permission `prix_achat_voir`. La valeur n'atteint donc
# jamais l'agent ni la reponse, quoi que fasse le LLM.
_FORBIDDEN_COLUMNS = (
    "prix_achat",
    "prix_achat_unitaire",
    "prix_achat_ht",
    "prix_revendeur",
    "marge",
)

# Mot-cle isole (frontiere de mot) pour eviter les faux positifs.
_FORBIDDEN_RE = re.compile(
    r"\b(" + "|".join(re.escape(c) for c in _FORBIDDEN_COLUMNS) + r")\b",
    re.IGNORECASE,
)

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


def _references_forbidden_column(sql: str) -> bool:
    """True si la requete reference une colonne confidentielle (prix d'achat /
    marge). Test purement lexical sur le SQL genere — defense en profondeur."""
    return bool(_FORBIDDEN_RE.search(sql or ""))


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
            # Garde confidentialite : refus AVANT toute execution SQL.
            if not _allow_price and _references_forbidden_column(query):
                logger.warning(
                    "SECURITE: requete bloquee (prix_achat/marge non autorise). "
                    "SQL: %s", (query or "")[:200],
                )
                return _FORBIDDEN_TOOL_REPLY
            # ERR1/ERR2 — Validation au niveau code (single-SELECT en lecture
            # seule + isolation tenant prouvee). Fail-closed : tout ce qui n'est
            # pas prouve sur est refuse sans jamais etre execute.
            try:
                secured = _validate_and_secure(query, _cid)
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
        db = SQLDatabase.from_uri(
            SQL_AGENT_DATABASE_URL,
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
