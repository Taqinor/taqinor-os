"""
Outils d'ACTION de l'agent conversationnel — N86.

L'agent SQL est en LECTURE SEULE (requetes SELECT uniquement). Ce module ajoute
des outils d'ECRITURE surs et additifs : ouvrir un ticket SAV, brouillonner un
bon de commande fournisseur pour les manques d'un chantier, et planifier une
visite de maintenance (intervention).

REGLES DE SECURITE (CLAUDE.md) :
- AUCUNE ecriture SQL directe (regle #1). Chaque action appelle l'API REST
  Django interne (ORM cote serveur) en relayant le JWT de l'appelant. Django
  reste l'autorite finale : il applique le scope societe (multi-tenant) et les
  permissions de role sur chaque viewset.
- Defense en profondeur : on verifie cote FastAPI le role/les permissions du
  JWT AVANT d'appeler Django (un role lecture seule ne peut donc rien ecrire),
  mais c'est Django qui tranche.
- Aucune nouvelle dependance externe : on utilise httpx (deja requis).
- Degradation gracieuse : si aucune URL Django interne n'est configuree, les
  outils d'action ne sont pas exposes a l'agent.
- Tout le texte utilisateur est en francais.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import secrets
import time
from typing import Any, Optional

import httpx

from app.core.config import (
    ACTION_PROPOSAL_SECRET,
    ACTION_PROPOSAL_TTL,
    DJANGO_INTERNAL_URL,
    REDIS_PROPOSAL_URL,
)

logger = logging.getLogger(__name__)

# AG2 — Niveaux de risque du catalogue Django (apps/agent/registry.py). Les
# actions `internal` s'executent au vol ; `outward`/`irreversible` passent par
# une proposition signee a confirmer.
RISK_INTERNAL = "internal"
RISK_OUTWARD = "outward"
RISK_IRREVERSIBLE = "irreversible"
_RISK_NEEDS_CONFIRM = frozenset({RISK_OUTWARD, RISK_IRREVERSIBLE})

# Chemin du catalogue d'actions Django (AG1).
_CATALOGUE_PATH = "/api/django/agent/actions/"

# Roles « legacy » autorises a ecrire (cf. authentication.role_legacy + le
# precedent de ocr.py). Un role lecture seule (« normal ») n'ecrit jamais.
_WRITE_ROLES = ("admin", "responsable")

# Permissions fines qui autorisent une action precise. Si le role est
# admin/responsable, on autorise meme sans permission listee (compat « legacy »,
# comme HasPermissionOrLegacy cote Django). La permission fine permet a un role
# personnalise « normal » muni du droit explicite d'agir.
_TICKET_PERMS = ("sav_gerer",)
_BC_PERMS = ("installation_gerer", "chantier_gerer")
_VISITE_PERMS = ("installation_gerer", "chantier_gerer")

# Type d'intervention utilise pour une visite de maintenance planifiee.
_VISITE_TYPE = "controle"

_TIMEOUT = httpx.Timeout(20.0, connect=5.0)


class ActionContext:
    """Contexte d'appel d'un outil d'action : identite + jeton de l'appelant.

    Le token brut est relaye a Django (Authorization: Bearer) pour que Django
    applique lui-meme le scope societe et les permissions de role.
    """

    def __init__(
        self,
        company_id: int,
        role: str,
        permissions: list[str] | None,
        token: str,
        is_superuser: bool = False,
    ) -> None:
        self.company_id = int(company_id or 0)
        self.role = (role or "").lower()
        self.permissions = list(permissions or [])
        self.token = token or ""
        self.is_superuser = bool(is_superuser)

    # ── Gating cote FastAPI (defense en profondeur) ───────────────────────

    def can_write(self, fine_perms: tuple[str, ...]) -> bool:
        """True si l'appelant peut ecrire pour l'action donnee."""
        if self.is_superuser:
            return True
        if self.role in _WRITE_ROLES:
            return True
        return any(p in self.permissions for p in fine_perms)

    @property
    def can_act_at_all(self) -> bool:
        """True si l'appelant a au moins un droit d'ecriture exploitable.

        Sert a decider si l'on expose les outils d'action a l'agent.
        """
        if self.is_superuser or self.role in _WRITE_ROLES:
            return True
        all_perms = set(_TICKET_PERMS + _BC_PERMS + _VISITE_PERMS)
        return any(p in all_perms for p in self.permissions)


def actions_available(ctx: Optional["ActionContext"]) -> bool:
    """Les outils d'action sont-ils exploitables pour ce contexte ?

    AG2 — Conditions minimales : une URL Django interne configuree (sinon
    degradation gracieuse) et un jeton present. C'est le CATALOGUE Django
    (filtre par permission + societe cote serveur) qui decide ensuite QUELLES
    actions l'appelant peut voir/executer ; un appelant sans aucune action
    autorisee recevra simplement une liste d'outils vide. On ne pre-filtre donc
    plus sur les anciennes permissions d'ecriture codees en dur (qui excluaient
    a tort des actions de lecture comme « lister les leads »).
    """
    if not DJANGO_INTERNAL_URL:
        return False
    if ctx is None or not ctx.token:
        return False
    return True


# ── Client Django interne ─────────────────────────────────────────────────────


def _django_call(
    ctx: ActionContext,
    path: str,
    method: str = "POST",
    payload: dict | None = None,
) -> dict[str, Any]:
    """Appel authentifie vers l'API Django interne, methode au choix.

    AG2 — relais generique : relaie le JWT de l'appelant (Authorization: Bearer)
    a l'endpoint nomme par le catalogue, en GET/POST/PATCH/PUT/DELETE. Django
    reste l'autorite finale (scope societe + permissions). Retourne un dict
    normalise {ok, status, data|error}. Ne leve jamais : les erreurs sont
    renvoyees comme texte a l'agent.
    """
    url = DJANGO_INTERNAL_URL.rstrip("/") + path
    verb = (method or "POST").upper()
    headers = {
        "Authorization": f"Bearer {ctx.token}",
        "Accept": "application/json",
    }
    body = payload or {}
    request_kwargs: dict[str, Any] = {"headers": headers}
    # GET/DELETE : pas de corps JSON (les parametres voyagent dans l'URL ou en
    # query). POST/PATCH/PUT : corps JSON.
    if verb in ("POST", "PATCH", "PUT"):
        headers["Content-Type"] = "application/json"
        request_kwargs["json"] = body
    elif body:
        # GET avec parametres residuels -> query string.
        request_kwargs["params"] = body
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.request(verb, url, **request_kwargs)
    except Exception as exc:  # pragma: no cover - reseau
        logger.warning("Appel Django interne echoue (%s %s): %s", verb, path, exc)
        return {"ok": False, "status": 0,
                "error": "Service indisponible. Reessayez plus tard."}

    ok = 200 <= resp.status_code < 300
    try:
        data = resp.json()
    except Exception:
        data = {}
    if ok:
        return {"ok": True, "status": resp.status_code, "data": data}

    return _normalize_error(resp, data)


def _django_post(ctx: ActionContext, path: str, payload: dict) -> dict[str, Any]:
    """POST authentifie vers l'API Django interne (compat actions legacy).

    Conserve pour les trois actions historiques (ticket SAV, BC, visite) et
    leurs tests ; delegue au relais generique `_django_call`.
    """
    return _django_call(ctx, path, method="POST", payload=payload)


def _normalize_error(resp, data) -> dict[str, Any]:
    """Construit un message d'erreur lisible et masque les internes."""
    ok = 200 <= resp.status_code < 300
    if ok:
        return {"ok": True, "status": resp.status_code, "data": data}

    # Message d'erreur lisible (Django renvoie souvent {'detail': ...} ou un
    # dict de champs). On masque les internes.
    detail = ""
    if isinstance(data, dict):
        detail = str(data.get("detail") or "")
        if not detail:
            # Concatene les premiers messages de champ.
            parts = []
            for k, v in data.items():
                if isinstance(v, (list, tuple)):
                    v = ", ".join(str(x) for x in v)
                parts.append(f"{k}: {v}")
            detail = " ; ".join(parts[:4])
    if resp.status_code in (401, 403):
        detail = detail or "Vous n'avez pas les droits pour cette action."
    return {"ok": False, "status": resp.status_code,
            "error": detail or "La demande a ete refusee."}


# ── Implementations des actions ───────────────────────────────────────────────


def open_sav_ticket(
    ctx: ActionContext,
    client_id: int,
    description: str,
    installation_id: int | None = None,
    priorite: str = "normale",
    type_ticket: str = "correctif",
) -> str:
    """Ouvre un ticket SAV. Renvoie un message francais (confirmation ou refus)."""
    if not ctx.can_write(_TICKET_PERMS):
        return ("Action refusee : vous n'avez pas la permission d'ouvrir un "
                "ticket SAV.")
    if not client_id:
        return "Impossible : un client (client_id) est requis pour le ticket."
    description = (description or "").strip()
    if not description:
        return "Impossible : une description du probleme est requise."
    if priorite not in ("basse", "normale", "haute", "urgente"):
        priorite = "normale"
    if type_ticket not in ("correctif", "preventif"):
        type_ticket = "correctif"

    payload: dict[str, Any] = {
        "client": int(client_id),
        "description": description,
        "priorite": priorite,
        "type": type_ticket,
    }
    if installation_id:
        payload["installation"] = int(installation_id)

    res = _django_post(ctx, "/api/django/sav/tickets/", payload)
    if not res["ok"]:
        return f"Le ticket SAV n'a pas pu etre cree. {res['error']}"
    ref = (res.get("data") or {}).get("reference") or "(reference en attente)"
    return (f"Ticket SAV cree avec succes : {ref} "
            f"(priorite {priorite}, type {type_ticket}).")


def draft_bon_commande_for_chantier(
    ctx: ActionContext,
    installation_id: int,
    fournisseur_id: int | None = None,
) -> str:
    """Brouillonne un bon de commande fournisseur pour les manques d'un
    chantier (endpoint commander-besoin)."""
    if not ctx.can_write(_BC_PERMS):
        return ("Action refusee : vous n'avez pas la permission de creer un "
                "bon de commande.")
    if not installation_id:
        return "Impossible : un chantier (installation_id) est requis."

    payload: dict[str, Any] = {}
    if fournisseur_id:
        payload["fournisseur"] = int(fournisseur_id)

    res = _django_post(
        ctx,
        f"/api/django/installations/chantiers/{int(installation_id)}/commander-besoin/",
        payload,
    )
    if not res["ok"]:
        return f"Le bon de commande n'a pas pu etre cree. {res['error']}"
    data = res.get("data") or {}
    numero = data.get("numero") or data.get("reference") or "(brouillon)"
    nb = data.get("nb_lignes")
    extra = f" ({nb} ligne(s) de manque)" if nb is not None else ""
    return (f"Bon de commande fournisseur brouillon cree : {numero}{extra}. "
            "Il reste a confirmer manuellement.")


def schedule_maintenance_visit(
    ctx: ActionContext,
    installation_id: int,
    date_prevue: str,
    technicien_id: int | None = None,
) -> str:
    """Planifie une visite de maintenance (intervention de type controle) sur
    un chantier a une date donnee (AAAA-MM-JJ)."""
    if not ctx.can_write(_VISITE_PERMS):
        return ("Action refusee : vous n'avez pas la permission de planifier "
                "une visite.")
    if not installation_id:
        return "Impossible : un chantier (installation_id) est requis."
    date_prevue = (date_prevue or "").strip()
    if not date_prevue:
        return ("Impossible : une date prevue (format AAAA-MM-JJ) est "
                "requise.")

    payload: dict[str, Any] = {
        "installation": int(installation_id),
        "type_intervention": _VISITE_TYPE,
        "date_prevue": date_prevue,
    }
    if technicien_id:
        payload["technicien"] = int(technicien_id)

    res = _django_post(ctx, "/api/django/installations/interventions/", payload)
    if not res["ok"]:
        return f"La visite n'a pas pu etre planifiee. {res['error']}"
    return (f"Visite de maintenance planifiee le {date_prevue} sur le "
            f"chantier {installation_id}.")


# ══════════════════════════════════════════════════════════════════════════════
# AG2 — Outils PILOTES PAR LE CATALOGUE (registry-driven) + propose→confirm
# ══════════════════════════════════════════════════════════════════════════════
# Plutot que trois outils codes en dur, on construit les outils dynamiquement a
# partir du catalogue Django (GET /api/django/agent/actions/). Chaque entree
# devient un StructuredTool dont la description et les entrees proviennent de
# l'entree. Les actions `internal` s'executent au vol (relais JWT) ; les actions
# `outward`/`irreversible` ne s'executent PAS : elles renvoient une proposition
# signee, stockee en Redis avec un TTL court, a confirmer via l'endpoint /confirm.


# ── Recuperation du catalogue ─────────────────────────────────────────────────


def fetch_catalogue(ctx: ActionContext) -> list[dict[str, Any]]:
    """Recupere le sous-ensemble du catalogue que l'appelant peut executer.

    Relaie le JWT a Django (GET /agent/actions/) qui filtre par permission +
    societe. Retourne la liste des dicts d'action ; [] si indisponible ou si
    aucune URL Django n'est configuree (degradation gracieuse, jamais d'erreur).
    """
    if not DJANGO_INTERNAL_URL or ctx is None or not ctx.token:
        return []
    res = _django_call(ctx, _CATALOGUE_PATH, method="GET")
    if not res.get("ok"):
        logger.warning("Catalogue d'actions indisponible: %s",
                       res.get("error"))
        return []
    data = res.get("data") or {}
    actions = data.get("actions") if isinstance(data, dict) else None
    return [a for a in (actions or []) if isinstance(a, dict) and a.get("key")]


def _catalogue_by_key(ctx: ActionContext) -> dict[str, dict[str, Any]]:
    """Catalogue indexe par `key` pour la (re)validation."""
    return {a["key"]: a for a in fetch_catalogue(ctx)}


# ── Validation des entrees contre le JSON-Schema d'une entree ─────────────────
# Validation volontairement legere et FAIL-CLOSED : on n'accepte que les cles
# declarees dans `properties`, on exige les `required`, et on verifie un type de
# base. Toute cle hors catalogue est rejetee — c'est la garantie « off-catalogue
# inputs are rejected ».

_JSON_TYPE_CHECK = {
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
}


class ActionValidationError(Exception):
    """Levee quand des entrees ne respectent pas le JSON-Schema de l'action."""


def validate_inputs(schema: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    """Valide `inputs` contre `schema` (JSON-Schema simplifie). Renvoie un dict
    NORMALISE ne contenant QUE les cles declarees. Leve ActionValidationError si
    une cle est inconnue, un `required` manque, ou un type est incorrect."""
    if not isinstance(inputs, dict):
        raise ActionValidationError("Les entrees doivent etre un objet.")
    schema = schema or {}
    properties = schema.get("properties") or {}
    required = schema.get("required") or []

    # Cles hors catalogue -> rejet (fail-closed).
    unknown = set(inputs) - set(properties)
    if unknown:
        raise ActionValidationError(
            "Entrees non autorisees : " + ", ".join(sorted(unknown))
        )

    cleaned: dict[str, Any] = {}
    for name, spec in properties.items():
        if name not in inputs:
            continue
        value = inputs[name]
        if value is None:
            continue
        expected = (spec or {}).get("type")
        checker = _JSON_TYPE_CHECK.get(expected)
        # int passe pour un champ number ; on tolere une string numerique pour
        # un champ integer/number (le LLM renvoie parfois "12").
        if checker and not checker(value):
            coerced = _coerce(value, expected)
            if coerced is None:
                raise ActionValidationError(
                    f"Champ '{name}' : type {expected} attendu."
                )
            value = coerced
        cleaned[name] = value

    missing = [r for r in required if cleaned.get(r) in (None, "")]
    if missing:
        raise ActionValidationError(
            "Champs requis manquants : " + ", ".join(missing)
        )
    return cleaned


def _coerce(value: Any, expected: str) -> Any:
    """Tente une coercition douce (string numerique -> int/number)."""
    try:
        if expected == "integer" and isinstance(value, str) and value.strip().lstrip("-").isdigit():
            return int(value)
        if expected == "number" and isinstance(value, str):
            return float(value)
    except (ValueError, TypeError):
        return None
    return None


# ── Construction de l'URL cible (templates de chemin) ─────────────────────────

_PATH_PARAM_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def _build_path(endpoint: str, inputs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Substitue les parametres de chemin templates (ex. `/devis/{id}/proposal/`)
    par leur valeur dans `inputs`. Renvoie (chemin_resolu, entrees_restantes).

    Les cles consommees par le chemin sont retirees du corps : elles ne doivent
    pas etre renvoyees aussi dans le payload JSON. Leve ActionValidationError si
    un parametre de chemin n'a pas de valeur fournie."""
    consumed: set[str] = set()

    def _sub(match):
        name = match.group(1)
        if name not in inputs or inputs[name] in (None, ""):
            raise ActionValidationError(
                f"Parametre de chemin manquant : {name}"
            )
        consumed.add(name)
        # quote minimal : les ids sont numeriques ; on encode tout de meme.
        from urllib.parse import quote
        return quote(str(inputs[name]), safe="")

    resolved = _PATH_PARAM_RE.sub(_sub, endpoint or "")
    remaining = {k: v for k, v in inputs.items() if k not in consumed}
    return resolved, remaining


# ── Stash signe des propositions (Redis, TTL court) ───────────────────────────


def _proposal_redis():
    """Client Redis pour les propositions (db 2). None si Redis absent."""
    try:
        import redis as redis_lib
    except Exception:  # pragma: no cover - redis non installe
        return None
    try:
        return redis_lib.from_url(REDIS_PROPOSAL_URL, decode_responses=True)
    except Exception as exc:  # pragma: no cover - reseau
        logger.warning("Redis propositions indisponible: %s", exc)
        return None


def _proposal_key(token: str) -> str:
    return f"agent_proposal:{token}"


def _sign(blob: str) -> str:
    """Signature HMAC-SHA256 hexadecimale d'une charge serialisee."""
    secret = (ACTION_PROPOSAL_SECRET or "").encode("utf-8")
    return hmac.new(secret, blob.encode("utf-8"), hashlib.sha256).hexdigest()


def _stash_proposal(
    ctx: ActionContext, action: dict[str, Any], inputs: dict[str, Any],
    human_preview: str,
) -> Optional[str]:
    """Stocke une proposition SIGNEE en Redis sous un jeton aleatoire avec un
    TTL court. La signature couvre {action_key, inputs, company_id} : une
    proposition alteree (cle/entrees/societe) echoue a la verification au
    moment de /confirm. Renvoie le jeton, ou None si Redis indisponible."""
    r = _proposal_redis()
    if r is None:
        return None
    token = secrets.token_urlsafe(24)
    record = {
        "action_key": action["key"],
        "inputs": inputs,
        "company_id": ctx.company_id,
        "human_preview": human_preview,
        "ts": int(time.time()),
    }
    # On signe la charge canonique (cles triees) sans la signature elle-meme.
    payload = json.dumps(record, sort_keys=True, ensure_ascii=False)
    record["sig"] = _sign(payload)
    try:
        r.set(_proposal_key(token), json.dumps(record, ensure_ascii=False),
              ex=ACTION_PROPOSAL_TTL)
    except Exception as exc:  # pragma: no cover - reseau
        logger.warning("Stash proposition echoue: %s", exc)
        return None
    return token


def _load_proposal(token: str) -> Optional[dict[str, Any]]:
    """Charge et VERIFIE la signature d'une proposition stashee. Renvoie le
    record (sans `sig`) si la signature est valide, sinon None (tampered /
    expire / absent)."""
    r = _proposal_redis()
    if r is None:
        return None
    try:
        raw = r.get(_proposal_key(token))
    except Exception as exc:  # pragma: no cover - reseau
        logger.warning("Lecture proposition echouee: %s", exc)
        return None
    if not raw:
        return None
    try:
        record = json.loads(raw)
    except Exception:
        return None
    sig = record.pop("sig", None)
    if not sig:
        return None
    payload = json.dumps(record, sort_keys=True, ensure_ascii=False)
    # Comparaison a temps constant contre la falsification.
    if not hmac.compare_digest(sig, _sign(payload)):
        logger.warning("Signature de proposition invalide (token rejete).")
        return None
    return record


def _discard_proposal(token: str) -> None:
    """Supprime une proposition (usage unique apres confirmation)."""
    r = _proposal_redis()
    if r is None:
        return
    try:
        r.delete(_proposal_key(token))
    except Exception:  # pragma: no cover - reseau
        pass


# ── Execution d'une action du catalogue ───────────────────────────────────────


def _human_preview(action: dict[str, Any], inputs: dict[str, Any]) -> str:
    """Texte court montre a l'utilisateur avant confirmation."""
    summary = action.get("confirm_summary") or action.get("label") or action["key"]
    if inputs:
        parts = ", ".join(f"{k}={v}" for k, v in sorted(inputs.items()))
        return f"{summary} ({parts})"
    return summary


def _execute_catalogue_action(
    ctx: ActionContext, action: dict[str, Any], inputs: dict[str, Any],
) -> dict[str, Any]:
    """Relaie l'appel a l'endpoint du catalogue avec le JWT. `inputs` sont deja
    valides. Renvoie le dict normalise de `_django_call`."""
    path, body = _build_path(action.get("endpoint", ""), inputs)
    return _django_call(ctx, path, method=action.get("method", "POST"),
                        payload=body)


def run_catalogue_action(
    ctx: ActionContext, action: dict[str, Any], raw_inputs: dict[str, Any],
    collector: Optional[list[dict[str, Any]]] = None,
) -> str:
    """Point d'entree appele par chaque outil dynamique.

    - Valide les entrees contre le JSON-Schema de l'entree (fail-closed).
    - `internal` -> execute au vol via relais JWT.
    - `outward`/`irreversible` -> stash signe + renvoie une proposition JSON
      `{action_key, inputs, human_preview, confirm_token}` ; n'execute PAS.

    AG2 (surfacage) — l'outil renvoie au LLM une chaine JSON, mais la sortie
    STRUCTUREE (proposition ou resultat) est aussi APPENDUE a `collector` quand
    il est fourni, pour que l'endpoint /query puisse la remonter telle quelle au
    frontend (avec le `confirm_token` signe) sans dependre de ce que le LLM
    re-emet en texte.
    """
    try:
        inputs = validate_inputs(action.get("inputs") or {}, raw_inputs)
    except ActionValidationError as exc:
        return f"Action refusee : {exc}"

    risk = action.get("risk", RISK_INTERNAL)
    if risk in _RISK_NEEDS_CONFIRM:
        preview = _human_preview(action, inputs)
        token = _stash_proposal(ctx, action, inputs, preview)
        proposal = {
            "type": "proposal",
            "action_key": action["key"],
            "inputs": inputs,
            "human_preview": preview,
            "confirm_token": token,
        }
        if token is None:
            # Sans Redis on ne peut pas stasher : on renvoie tout de meme la
            # proposition (non confirmable) pour ne pas executer a l'aveugle.
            proposal["confirm_token"] = None
            proposal["note"] = (
                "Confirmation requise mais le stockage est indisponible."
            )
        if collector is not None:
            collector.append(proposal)
        return json.dumps(proposal, ensure_ascii=False)

    # Action interne -> execution immediate.
    res = _execute_catalogue_action(ctx, action, inputs)
    if not res.get("ok"):
        return f"L'action « {action.get('label', action['key'])} » a echoue. {res.get('error', '')}"
    result = {
        "type": "result", "action_key": action["key"],
        "ok": True, "data": res.get("data"),
    }
    if collector is not None:
        collector.append(result)
    return json.dumps(result, ensure_ascii=False)


def confirm_proposal(ctx: ActionContext, token: str) -> dict[str, Any]:
    """Rejoue une proposition stashee par jeton, APRES re-validation.

    Etapes de securite :
      1. charge la proposition et VERIFIE sa signature (rejet si alteree) ;
      2. exige que la societe du jeton == societe de l'appelant ;
      3. RE-RECUPERE le catalogue de l'appelant et exige que l'action y figure
         (l'appelant a toujours le droit de l'executer) ;
      4. RE-VALIDE les entrees contre le JSON-Schema courant du catalogue
         (rejet des cles hors catalogue) ;
      5. relaie l'appel a Django (qui re-tranche permission + societe) ;
      6. consomme le jeton (usage unique).
    Renvoie {ok, ...}. Ne leve pas pour les refus metier (renvoie ok=False)."""
    record = _load_proposal(token)
    if record is None:
        return {"ok": False, "error": "Proposition introuvable, expiree ou alteree."}

    if int(record.get("company_id") or 0) != ctx.company_id:
        # Defense en profondeur : un jeton ne vaut que pour SA societe.
        return {"ok": False, "error": "Proposition non valable pour cette societe."}

    action_key = record.get("action_key")
    catalogue = _catalogue_by_key(ctx)
    action = catalogue.get(action_key)
    if action is None:
        return {"ok": False,
                "error": "Action non autorisee ou indisponible pour ce compte."}

    # Re-validation des entrees contre le catalogue COURANT (fail-closed).
    try:
        inputs = validate_inputs(action.get("inputs") or {}, record.get("inputs") or {})
    except ActionValidationError as exc:
        return {"ok": False, "error": f"Entrees invalides : {exc}"}

    res = _execute_catalogue_action(ctx, action, inputs)
    _discard_proposal(token)  # usage unique, quel que soit le resultat
    if not res.get("ok"):
        return {"ok": False, "status": res.get("status"),
                "error": res.get("error", "L'action a echoue.")}
    return {"ok": True, "action_key": action_key, "data": res.get("data")}


# ── Fabrique d'outils LangChain ───────────────────────────────────────────────


# Type JSON-Schema -> annotation Python pour le modele pydantic genere.
_PY_TYPE = {
    "integer": int,
    "number": float,
    "string": str,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def _tool_name_for(action: dict[str, Any]) -> str:
    """Nom d'outil LangChain valide derive de la cle catalogue
    (ex. `ventes.devis.create` -> `ventes_devis_create`)."""
    return re.sub(r"[^0-9a-zA-Z_]", "_", action["key"])


def _args_model_for(action: dict[str, Any]):
    """Construit un modele pydantic `args_schema` a partir du JSON-Schema
    `inputs` de l'entree catalogue."""
    from pydantic import create_model

    schema = action.get("inputs") or {}
    properties = schema.get("properties") or {}
    required = set(schema.get("required") or [])

    fields: dict[str, Any] = {}
    for name, spec in properties.items():
        spec = spec or {}
        py_type = _PY_TYPE.get(spec.get("type"), str)
        desc = spec.get("description", "")
        if name in required:
            fields[name] = (py_type, _pyd_field(..., desc))
        else:
            fields[name] = (Optional[py_type], _pyd_field(None, desc))

    model_name = f"Args_{_tool_name_for(action)}"
    if not fields:
        return create_model(model_name)
    return create_model(model_name, **fields)


def _pyd_field(default, description):
    from pydantic import Field
    return Field(default, description=description or "")


def build_action_tools(
    ctx: ActionContext, collector: Optional[list[dict[str, Any]]] = None,
) -> list:
    """Construit dynamiquement la liste d'outils LangChain a partir du CATALOGUE
    Django (AG2). Chaque entree que l'appelant a le droit d'executer devient un
    StructuredTool dont le nom/description/entrees viennent de l'entree.

    L'outil capture `ctx` par closure : l'agent ne fournit jamais la societe ni
    le jeton — ils viennent toujours du serveur. L'execution / la proposition
    est deleguee a `run_catalogue_action` (internal => execute ; outward /
    irreversible => proposition signee a confirmer).

    AG2 (surfacage) — quand `collector` est fourni (une liste partagee par
    requete), chaque outil y APPEND sa sortie structuree (proposition/resultat)
    pour que /query la remonte au frontend avec le `confirm_token`.
    """
    from langchain_core.tools import StructuredTool

    tools = []
    for action in fetch_catalogue(ctx):
        try:
            args_model = _args_model_for(action)
        except Exception as exc:  # pragma: no cover - schema malforme
            logger.warning("Schema d'action invalide (%s): %s",
                           action.get("key"), exc)
            continue

        description = action.get("description") or action.get("label") or action["key"]
        if action.get("risk") in _RISK_NEEDS_CONFIRM:
            description = (
                description
                + " ATTENTION : action sensible — elle n'est PAS executee "
                "directement ; l'outil renvoie une PROPOSITION a confirmer."
            )

        def _make_func(act):
            return lambda **kw: run_catalogue_action(ctx, act, kw, collector)

        tools.append(StructuredTool.from_function(
            name=_tool_name_for(action),
            description=description,
            args_schema=args_model,
            func=_make_func(action),
        ))

    return tools
