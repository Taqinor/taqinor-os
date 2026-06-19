"""
Service Agent SQL — LangChain + pgvector.
Architecture :
  Question NL
    -> Embedding (sentence-transformers, local, gratuit)
    -> pgvector : top-5 tables pertinentes
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

from langchain.callbacks.base import BaseCallbackHandler

if TYPE_CHECKING:  # eviter un import circulaire au runtime
    from app.services.action_tools import ActionContext

from app.core.config import (
    CHAT_HISTORY_MAX,
    CHAT_HISTORY_TTL,
    CLAUDE_API_KEY,
    DATABASE_URL,
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
    # ── N86 — toutes ces tables portent une colonne company_id ──
    "installations_installation",
    "installations_intervention",
    "sav_equipement",
    "sav_ticket",
    "sav_contratmaintenance",
])

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


def _references_forbidden_column(sql: str) -> bool:
    """True si la requete reference une colonne confidentielle (prix d'achat /
    marge). Test purement lexical sur le SQL genere — defense en profondeur."""
    return bool(_FORBIDDEN_RE.search(sql or ""))


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
            secured = _inject_company_filter(query, _cid)
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
        self._vectorstore = None
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

    # ── pgvector : init + recherche de tables pertinentes ─────────────────

    def _init_vectorstore(self):
        from langchain_community.vectorstores import PGVector
        from langchain.schema import Document
        from sqlalchemy import create_engine, text

        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()

        docs = [
            Document(
                page_content=f"Table: {table}\nDescription: {desc}",
                metadata={"table_name": table},
            )
            for table, desc in _TABLE_DESCRIPTIONS.items()
        ]

        self._vectorstore = PGVector.from_documents(
            documents=docs,
            embedding=self._get_embeddings(),
            collection_name="sql_agent_table_descriptions",
            connection=DATABASE_URL,
            connection_string=DATABASE_URL,
            pre_delete_collection=False,
        )

    def _get_relevant_tables(self, question: str, k: int = 5) -> list[str]:
        try:
            # Lock : un seul thread initialise pgvector, les autres attendent
            if self._vectorstore is None:
                with self._init_lock:
                    if self._vectorstore is None:  # double-checked locking
                        self._init_vectorstore()
            results = self._vectorstore.similarity_search(question, k=k)
            tables = [r.metadata["table_name"] for r in results]
            logger.info("Tables selectionnees: %s", tables)
            return tables
        except Exception as exc:
            logger.warning("pgvector indisponible, toutes les tables: %s", exc)
            return _ALLOWED_TABLES

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

        # 2. Tables pertinentes via pgvector
        relevant_tables = self._get_relevant_tables(question)

        # 2. SQLDatabase filtre
        db = SQLDatabase.from_uri(
            DATABASE_URL,
            include_tables=relevant_tables,
            sample_rows_in_table_info=2,
        )

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
        action_tool_names: set[str] = set()
        if actions_available(action_ctx):
            action_tools = build_action_tools(action_ctx)
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

        return {
            "answer": answer,
            "sql_query": capture.queries[-1] if capture.queries else "",
            "data": None,
            # N86 — True si l'agent a effectue une action d'ecriture (le
            # frontend affiche alors un badge « Action »).
            "action_performed": capture.action_used,
        }

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
