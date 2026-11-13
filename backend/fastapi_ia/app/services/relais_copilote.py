"""COP-B — relais du copilote commercial (code neuf du service de l'assistant).

`sql_agent_service` reste le moteur LangChain et sa sécurité SQL ; ce module
porte ce qui entoure un tour : l'historique remis au modèle, ce qui suit une
confirmation (carte, mémoire du tour). Contrat :
`backend/django_core/apps/agent/contract_samples/assistant_reponse.json`.

Les imports de `sql_agent_service` sont locaux (il importe ce module).
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from app.services import cartes as _cartes
from app.services import prompt_copilote

logger = logging.getLogger(__name__)

#: Valeurs de `moteur` dans la réponse (contrat `assistant_reponse.json`).
MOTEUR_LANGCHAIN = "langchain"
MOTEUR_NATIF = "natif"

#: Messages d'historique remis au modèle LangChain (2 derniers échanges).
HISTORIQUE_MODELE = 4
#: Ligne « Références : … » ajoutée au dernier message d'agent (COP-B2).
REFERENCES_MAX = 300

#: Bornes du tampon technique du navigateur (`contexte.diagnostic`).
DIAG_MAX_REQUETES = 15
DIAG_MAX_ERREURS = 10
_DIAG_TEXTE = 200


# ── COP-B4 — erreurs et mesures dites juste ──────────────────────────────────

#: Texte rendu par LangChain à la limite d'itérations (anglais, inutile).
_ARRET_DU_CADRE = re.compile(r"^\s*Agent stopped due to", re.I)
MESSAGE_LIMITE = (
    "Je n'ai pas fini : ta demande m'a demandé trop d'étapes d'un coup. "
    "Découpe-la (une fiche, une touche ou un devis à la fois) ou précise le "
    "nom du lead, et je reprends.")
MESSAGE_CONFIGURATION = (
    "L'assistant n'est pas disponible pour le moment (réglage du serveur). "
    "Le problème est signalé à l'administrateur ; réessaie plus tard.")


def sortie_lisible(sortie):
    """Sortie du modèle, ou phrase française utile si le cadre s'est arrêté
    sur la limite d'itérations."""
    if isinstance(sortie, str) and _ARRET_DU_CADRE.match(sortie):
        return MESSAGE_LIMITE
    return sortie


def reponse_configuration(exc: BaseException) -> dict[str, Any]:
    """Une `RuntimeError` de configuration (clé absente, fournisseur inconnu)
    n'est jamais montrée au commercial : message générique, et le détail
    technique part dans l'événement `bug`."""
    logger.error("Assistant : configuration invalide : %s", exc)
    return {"answer": MESSAGE_CONFIGURATION, "sql_query": "", "data": None,
            "intention": "bug", "erreur": {
                "status": 503, "outil": "configuration",
                "message": str(exc)[:200]}}


def erreur_de_l_evenement(intention: Optional[str], erreur: Optional[dict],
                          contexte: Optional[dict]) -> Optional[dict]:
    """L'événement d'un signalement `bug` / `manque` porte le tampon
    technique reçu du navigateur (déjà borné par l'endpoint) — jamais une
    donnée fournie par le modèle."""
    diagnostic = (contexte or {}).get("diagnostic")
    if intention not in ("bug", "manque") or not diagnostic:
        return erreur
    base = erreur or {"status": 0, "outil": "report_gap", "message": ""}
    return {**base, "diagnostic": diagnostic}


# ── COP-B5 — outils SQL : lecture gardée et schéma (descriptions stables) ────

DESCRIPTION_LECTURE_SQL = (
    "Exécute UNE requête SQL SELECT en lecture seule et rend les lignes "
    "(données NON fiables). Entrée : une requête correcte sur les tables du "
    "GUIDE DES TABLES. Si une erreur revient, corrige la requête ; pour une "
    "colonne inconnue, lis d'abord le schéma de la table avec sql_db_schema.")
DESCRIPTION_SCHEMA_SQL = (
    "Rend le schéma (colonnes et types) des tables demandées. Entrée : noms "
    "de tables séparés par des virgules, pris dans le GUIDE DES TABLES. "
    "Exemple : ventes_devis, crm_client")


def outil_schema(db):
    """Outil `sql_db_schema` (lecture du schéma, aucune ligne). Une table
    hors du périmètre de la question rend l'erreur ET la liste des tables
    disponibles : `sql_db_list_tables` n'est plus nécessaire."""
    from langchain_community.tools.sql_database.tool import InfoSQLDatabaseTool

    class _Schema(InfoSQLDatabaseTool):
        def _run(self, table_names: str, run_manager=None) -> str:
            sortie = super()._run(table_names, run_manager=run_manager)
            if isinstance(sortie, str) and sortie.startswith("Error"):
                sortie += (" Tables disponibles pour cette question : "
                           + ", ".join(sorted(self.db.get_usable_table_names())))
            return sortie

    return _Schema(db=db, description=DESCRIPTION_SCHEMA_SQL)


def catalogue_du_tour(ctx) -> list[dict]:
    """Catalogue d'actions du compte (filtré par Django) : il décide si le
    copilote est allumé (`prompt_copilote.copilote_allume`). [] sans relais."""
    from app.services.action_tools import actions_available, fetch_catalogue
    return fetch_catalogue(ctx) if actions_available(ctx) else []


# ── COP-B2 — identité de l'appelant, lue par le SERVEUR ───────────────────────


def lire_appelant(ctx) -> dict[str, str]:
    """UNE lecture de `/auth/me/` par requête : remplit `ctx.permissions`
    (échec fermé, même règle que `fetch_caller_permissions`) ET garde le
    prénom et le rôle pour l'en-tête de tour (`ctx.identite`). Jamais lus du
    corps de la requête."""
    from app.services import action_tools as at

    data = None
    if at.DJANGO_INTERNAL_URL and ctx.token:
        res = at._django_call(ctx, at._ME_PATH, method="GET")
        data = res.get("data") if res.get("ok") else None
        if data is None:
            logger.warning("Appelant illisible (/auth/me/): %s", res.get("error"))
    data = data if isinstance(data, dict) else {}
    perms = data.get("permissions")
    ctx.permissions = ([p for p in perms if isinstance(p, str)]
                       if isinstance(perms, list) else [])
    ctx.identite = {"prenom": str(data.get("first_name") or "")[:60],
                    "role": str(data.get("role_nom") or "")[:60]}
    return ctx.identite


# ── COP-B2 — tampon technique du navigateur (donnée NON fiable) ───────────────


def _texte(valeur, borne: int = _DIAG_TEXTE) -> str:
    if isinstance(valeur, bool) or not isinstance(valeur, (str, int, float)):
        return ""
    return str(valeur)[:borne]


def _entier(valeur) -> Optional[int]:
    return valeur if isinstance(valeur, int) and not isinstance(valeur, bool) else None


def _liste(brut, cle: str, borne: int) -> list[dict]:
    valeurs = brut.get(cle)
    lignes = [v for v in valeurs if isinstance(v, dict)] if isinstance(valeurs, list) else []
    return lignes[-borne:]


def borner_diagnostic(brut) -> Optional[dict]:
    """Forme et bornes du contrat (`assistant_reponse.json` → `diagnostic`) :
    15 requêtes et 10 erreurs au plus (les plus récentes), chaînes tronquées,
    routes sans chaîne de requête ; toute autre clé est écartée."""
    if not isinstance(brut, dict):
        return None
    requetes = [{
        "methode": _texte(r.get("methode"), 10),
        "route": _texte(r.get("route")).split("?", 1)[0],
        "statut": _entier(r.get("statut")),
        "duree_ms": _entier(r.get("duree_ms")),
        "request_id": _texte(r.get("request_id"), 64),
        "code": _texte(r.get("code"), 64),
        "il_y_a_s": _entier(r.get("il_y_a_s")),
    } for r in _liste(brut, "requetes", DIAG_MAX_REQUETES)]
    erreurs = [{
        "genre": _texte(e.get("genre"), 40),
        "message": _texte(e.get("message"), 300),
        "il_y_a_s": _entier(e.get("il_y_a_s")),
    } for e in _liste(brut, "erreurs", DIAG_MAX_ERREURS)]
    return {
        "version": _texte(brut.get("version"), 40),
        "ecran": _texte(brut.get("ecran")).split("?", 1)[0],
        "navigateur": _texte(brut.get("navigateur"), 60),
        "en_ligne": brut.get("en_ligne") if isinstance(brut.get("en_ligne"), bool) else None,
        "requetes": requetes,
        "erreurs": erreurs,
    }


# ── COP-B2 — en-tête de tour et mémoire des identifiants ──────────────────────


def question_du_tour(question: str, contexte: Optional[dict] = None,
                     identite: Optional[dict] = None, maintenant=None) -> str:
    """La question remise au modèle (LES DEUX moteurs) : en-tête posé par le
    serveur (date et heure de Casablanca, prénom, rôle, écran, foyer) puis le
    texte de l'utilisateur. Le contexte entre dans le message UTILISATEUR,
    jamais dans le bloc système (son cache reste intact)."""
    contexte, identite = contexte or {}, identite or {}
    entete = prompt_copilote.entete_tour(
        maintenant=maintenant, prenom=identite.get("prenom") or "",
        role=identite.get("role") or "",
        contexte={k: contexte.get(k)
                  for k in ("ecran", "lead_id", "devis_id", "touche_id")})
    return f"{entete}\n\n{question}"


def _refs_noeud(noeud: dict) -> list[str]:
    """Identifiants portés par UN objet de `donnees` (formes des contrats CRM)."""
    refs, touche = [], noeud.get("touche")
    if isinstance(touche, dict) and _entier(touche.get("id")):
        lead = _entier(touche.get("lead"))
        refs.append(f"touche {touche['id']}" + (f" (lead {lead})" if lead else ""))
    lead = _entier(noeud.get("lead_id"))
    if _entier(noeud.get("touche_id")):
        refs.append(f"touche {noeud['touche_id']}" + (f" (lead {lead})" if lead else ""))
    elif lead:
        refs.append(f"lead {lead}")
    identite = noeud.get("identite")
    if isinstance(identite, dict) and _entier(identite.get("id")):
        refs.append(f"lead {identite['id']}")
    ids, objets = noeud.get("devis_ids"), noeud.get("devis")
    objets = [objets] if isinstance(objets, dict) else objets
    devis = [noeud.get("devis_id"), *(ids if isinstance(ids, list) else [])]
    devis += [d.get("id") for d in (objets if isinstance(objets, list) else [])
              if isinstance(d, dict)]
    refs += [f"devis {d}" for d in devis if _entier(d)]
    return refs


def _parcourir(noeud, refs: list[str], profondeur: int = 0) -> None:
    if profondeur > 4:
        return
    if isinstance(noeud, list):
        for element in noeud[:25]:
            _parcourir(element, refs, profondeur + 1)
    elif isinstance(noeud, dict):
        refs.extend(_refs_noeud(noeud))
        for cle, valeur in noeud.items():
            if cle not in ("touche", "identite", "devis") and isinstance(valeur, (dict, list)):
                _parcourir(valeur, refs, profondeur + 1)


def references_des_cartes(cartes: Optional[list]) -> str:
    """« Références : touche 412 (lead 1489) ; devis 45 » tirée des CARTES du
    tour (≤ 300 caractères) — le moteur LangChain n'a que du texte : sans
    elle, « il ne répond pas » ne retrouve pas la touche du tour d'avant.
    Jamais affichée à l'écran."""
    refs: list[str] = []
    for carte in cartes or []:
        if isinstance(carte, dict):
            _parcourir(carte.get("donnees"), refs)
    vus, ligne = set(), "Références :"
    for ref in refs:
        if ref in vus or len(ligne) + len(ref) + 3 > REFERENCES_MAX:
            continue
        vus.add(ref)
        ligne += (" " if ligne.endswith(":") else " ; ") + ref
    return ligne if vus else ""


def historique_langchain(brut: Optional[list]) -> list:
    """Historique Redis -> messages LangChain (2 derniers échanges seulement :
    d'anciens résultats ne doivent pas contaminer une nouvelle question ; tout
    l'historique reste dans Redis pour l'écran). Un message ancien sans
    `cartes` se relit tel quel ; le DERNIER message d'agent reçoit la ligne
    « Références : … » de ses cartes."""
    from langchain_core.messages import AIMessage, HumanMessage

    recents = [m for m in (brut or []) if isinstance(m, dict)][-HISTORIQUE_MODELE:]
    dernier = max((i for i, m in enumerate(recents) if m.get("role") == "agent"),
                  default=None)
    messages = []
    for i, msg in enumerate(recents):
        texte = msg.get("content") or ""
        if msg.get("role") == "user":
            messages.append(HumanMessage(content=texte))
        elif msg.get("role") == "agent":
            refs = references_des_cartes(msg.get("cartes")) if i == dernier else ""
            messages.append(AIMessage(content=f"{texte}\n\n{refs}" if refs else texte))
    return messages


def carte_de_confirmation(resultat: dict) -> Optional[dict]:
    """Carte `resultat` d'une confirmation réussie (`/confirm`), par la
    fabrique unique des cartes. Les clés `libelle` / `carte` du résultat de
    `confirm_proposal` sont lues par `.get()` (absentes : carte générique)."""
    return _cartes.carte_depuis_sortie({
        "type": "result",
        "action_key": resultat.get("action_key") or "",
        "libelle": resultat.get("libelle") or "",
        "carte": resultat.get("carte"),
        "data": resultat.get("data"),
    })


def apres_confirmation(service, ctx, company_id: int, user_id: int,
                       resultat: dict) -> dict[str, Any]:
    """Après une confirmation RÉUSSIE : la carte du résultat, et l'action
    écrite dans l'historique (au tour suivant, le modèle sait qu'elle a eu
    lieu). Rend `{carte, suite}` ; `suite` vaut None sous le moteur LangChain
    et `{answer, cartes, evenement_id}` quand le moteur natif reprend."""
    carte = carte_de_confirmation(resultat)
    libelle = (carte or {}).get("libelle") or resultat.get("action_key") or ""
    service._ajouter_historique(user_id, [{
        "role": "agent",
        "content": f"Action confirmée par l'utilisateur et exécutée : {libelle}.",
        "cartes": [carte] if carte else [],
    }])
    return {"carte": carte,
            "suite": reprise_native(service, ctx, company_id, user_id,
                                    libelle, resultat)}


# ── COP-B6 — aiguillage vers le moteur natif ─────────────────────────────────

MESSAGE_ACTION_INTERROMPUE = (
    "Je n'ai pas pu terminer : une partie de la demande a déjà été faite (voir "
    "les cartes). Vérifie la fiche avant de redemander la suite.")
MESSAGE_REFUS = (
    "Je ne peux pas traiter cette demande telle quelle. Reformule-la, ou fais "
    "le geste depuis l'écran.")
_SUFFIXE_SENSIBLE = (
    " ATTENTION : action sensible — elle n'est PAS exécutée directement ; "
    "l'outil rend une PROPOSITION que l'utilisateur confirme sur sa carte.")


def moteur_natif_actif(catalogue: Optional[list], fournisseur: str) -> bool:
    """Moteur natif SEULEMENT si : réglage `natif` ET fournisseur claude ET
    copilote allumé pour ce compte (catalogue reçu de Django)."""
    from app.core import config
    return (config.ASSISTANT_MOTEUR == MOTEUR_NATIF
            and (fournisseur or "").lower() == "claude"
            and prompt_copilote.copilote_allume(catalogue))


def conversation_de(company_id: int, user_id: int) -> str:
    """Clé de la conversation native : « société:utilisateur »."""
    return f"{int(company_id or 0)}:{int(user_id or 0)}"


def _outil_action(ctx, action: dict, collecteur: list):
    """Une action du catalogue -> OutilNatif : nom de `_tool_name_for`,
    schéma = `inputs` du catalogue, exécution = `run_catalogue_action` (mêmes
    validations, propositions signées, collecteur de cartes)."""
    from app.services.action_tools import _tool_name_for, run_catalogue_action
    from app.services.sql_agent_service import _etiqueter_non_fiable
    from app.services import moteur_natif

    entrees = action.get("inputs") if isinstance(action.get("inputs"), dict) else {}
    description = action.get("description") or action.get("label") or action["key"]
    if action.get("risk") in ("outward", "irreversible"):
        description += _SUFFIXE_SENSIBLE
    return moteur_natif.OutilNatif(
        nom=_tool_name_for(action), description=description,
        schema={"type": "object", "properties": {}, **entrees},
        executer=lambda args: _etiqueter_non_fiable(run_catalogue_action(
            ctx, action, dict(args or {}), collecteur)))


def _outils_fixes(lecture, schema, collecteur: list) -> list:
    """Lecture SQL gardée et schéma (les outils du moteur LangChain,
    enveloppés : leur sécurité n'est pas réécrite) + le signalement."""
    from app.services.action_tools import outil_report_gap
    from app.services.moteur_natif import OutilNatif

    signalement = outil_report_gap(collecteur)
    texte = {"type": "string"}
    return [
        OutilNatif("sql_db_query", lecture.description, {
            "type": "object", "properties": {"query": texte}, "required": ["query"]},
            lambda a: lecture.invoke({"query": str((a or {}).get("query") or "")})),
        OutilNatif("sql_db_schema", schema.description, {
            "type": "object", "properties": {"table_names": texte},
            "required": ["table_names"]},
            lambda a: schema.invoke({"table_names": str((a or {}).get("table_names") or "")})),
        OutilNatif("report_gap", signalement.description, {
            "type": "object", "properties": {
                "intention": {"type": "string", "enum": ["hors_champ", "manque", "bug"]},
                "resume": texte, "ecran": texte},
            "required": ["intention", "resume"]},
            lambda a: signalement.invoke(dict(a or {}))),
    ]


def _preparer(service, question: str, company_id: int, ctx,
              catalogue: list, collecteur: list) -> dict[str, Any]:
    """Outils, blocs système (ordre stable, sans point de cache : le moteur
    les pose) et réglages du modèle pour un tour natif."""
    from app.services import sql_agent_service as svc

    droits = service._droits_sql(ctx)
    lecture, schema = service._outils_sql(
        service._base_sql(question, company_id), company_id, droits)
    outils = [_outil_action(ctx, a, collecteur) for a in catalogue]
    outils += _outils_fixes(lecture, schema, collecteur)
    contenu, present = svc._contenu_systeme("claude", droits[0], copilote=True)
    blocs = contenu if isinstance(contenu, list) else [{"text": contenu}]
    return {"outils": outils, "manuel_present": present,
            "cles": {o.nom: a["key"] for o, a in zip(outils, catalogue)},
            "reglages": {"systeme": [{"type": "text", "text": b["text"]} for b in blocs],
                         "modele": svc._modele_effectif("claude"),
                         "effort": (svc.SQL_AGENT_EFFORT or "low").lower()}}


def _sortie_native(service, question: Optional[str], user_id: int,
                   rendu: dict, collecteur: list, prep: dict) -> dict[str, Any]:
    """Retour du moteur natif mis à la forme de `_run_agent` ; l'historique
    texte de l'écran est écrit comme sous LangChain (repli instantané)."""
    from app.services import moteur_natif
    from app.services import sql_agent_service as svc

    arret, texte = rendu.get("arret"), rendu.get("answer") or ""
    if arret == moteur_natif.ARRET_ERREUR:
        raise moteur_natif.MoteurIndisponible("erreur du fournisseur")
    if arret == moteur_natif.ARRET_REFUS:
        texte = MESSAGE_REFUS
    elif arret == moteur_natif.ARRET_LIMITE:
        texte = f"{texte}\n\n{MESSAGE_LIMITE}" if texte.strip() else MESSAGE_LIMITE
    answer, intention = svc._extraire_intention(texte)
    intention, erreur = svc._intention_et_erreur(collecteur, intention)
    cartes = _cartes.construire_cartes(collecteur)
    agent = {"role": "agent", "content": answer, "cartes": cartes}
    service._ajouter_historique(user_id, ([{"role": "user", "content": question}]
                                          if question is not None else []) + [agent])
    jetons = rendu.get("tokens") or {}
    return {
        "answer": answer, "sql_query": "", "data": None,
        "action_performed": any(s.get("type") in ("proposal", "result")
                                for s in collecteur),
        "proposal": svc.SQLAgentService._build_proposal_payload(collecteur),
        "result": svc.SQLAgentService._build_result_payload(collecteur),
        "cartes": cartes, "moteur": MOTEUR_NATIF,
        "manuel_present": prep["manuel_present"],
        "intention": intention, "erreur": erreur,
        "outils_appeles": [prep["cles"].get(n, n) for n in rendu.get("outils_appeles") or []],
        "tokens": {k: int(jetons.get(k) or 0)
                   for k in ("cache_read", "cache_write", "input", "output")},
    }


def tour_natif(service, question: str, company_id: int, user_id: int, ctx,
               contexte: Optional[dict], catalogue: list) -> Optional[dict]:
    """Un tour servi par le moteur natif quand il est actif pour ce compte ;
    None = le tour est servi par LangChain (moteur éteint, indisponible, ou
    panne AVANT toute action exécutée — journalisée). Une panne APRÈS une
    action exécutée n'est jamais rejouée (doublon) : réponse d'erreur."""
    from app.services import moteur_natif
    from app.services import sql_agent_service as svc

    if not moteur_natif_actif(catalogue, svc.SQL_AGENT_PROVIDER):
        return None
    collecteur: list = []
    try:
        prep = _preparer(service, question, company_id, ctx, catalogue, collecteur)
        rendu = moteur_natif.executer(
            question=question_du_tour(question, contexte, getattr(ctx, "identite", None)),
            outils=prep["outils"], conversation=conversation_de(company_id, user_id),
            **prep["reglages"])
        sortie = _sortie_native(service, question, user_id, rendu, collecteur, prep)
    except Exception as exc:
        if not any(s.get("type") == "result" for s in collecteur):
            logger.warning("Moteur natif indisponible (%s) : tour servi par LangChain.", exc)
            return None
        logger.error("Moteur natif en panne après une action exécutée : %s", exc)
        return {"answer": MESSAGE_ACTION_INTERROMPUE, "sql_query": "", "data": None,
                "cartes": _cartes.construire_cartes(collecteur), "moteur": MOTEUR_NATIF,
                "intention": "bug", "repli": False, "modele": svc._modele_effectif("claude"),
                "erreur": {"status": 500, "outil": "moteur_natif", "message": str(exc)[:200]}}
    return {**sortie, "repli": False, "modele": svc._modele_effectif("claude")}


def reprise_native(service, ctx, company_id: int, user_id: int, libelle: str,
                   resultat: dict) -> Optional[dict]:
    """Après une confirmation, si le moteur natif sert ce compte : il reprend
    la tâche avec le résultat de l'ERP (sous enveloppe non fiable). Rend
    `{answer, cartes, evenement_id}`, ou None (autre moteur, rien à reprendre,
    panne — journalisée)."""
    from app.services import moteur_natif
    from app.services import sql_agent_service as svc

    if not (MOTEUR_NATIF == _moteur_regle()
            and (svc.SQL_AGENT_PROVIDER or "").lower() == "claude"):
        return None
    catalogue = catalogue_du_tour(ctx)
    if not moteur_natif_actif(catalogue, svc.SQL_AGENT_PROVIDER):
        return None
    message = (f"L'utilisateur a confirmé : {libelle}.\n"
               + svc._etiqueter_non_fiable(resultat.get("data")))
    collecteur: list = []
    try:
        prep = _preparer(service, libelle, company_id, ctx, catalogue, collecteur)
        rendu = moteur_natif.reprendre(conversation=conversation_de(company_id, user_id),
                                       message=message, outils=prep["outils"],
                                       **prep["reglages"])
        if rendu is None:
            return None
        sortie = _sortie_native(service, None, user_id, rendu, collecteur, prep)
    except Exception as exc:
        logger.warning("Reprise du moteur natif impossible : %s", exc)
        return None
    sortie["modele"] = svc._modele_effectif("claude")
    return {"answer": sortie["answer"], "cartes": sortie["cartes"],
            "evenement_id": svc.SQLAgentService._journaliser(message, sortie, ctx)}


def _moteur_regle() -> str:
    from app.core import config
    return config.ASSISTANT_MOTEUR


def effacer_conversation(company_id: Optional[int], user_id: int) -> None:
    """« Effacer » efface aussi la conversation native (quel que soit le
    réglage : une conversation a pu naître quand il était allumé)."""
    if not company_id:
        return
    from app.services import moteur_natif
    try:
        moteur_natif.effacer(conversation_de(company_id, user_id))
    except Exception as exc:  # best-effort : l'historique Redis est effacé
        logger.warning("Conversation native non effacée : %s", exc)
