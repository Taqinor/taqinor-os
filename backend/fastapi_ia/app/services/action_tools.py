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

import logging
from typing import Any, Optional

import httpx

from app.core.config import DJANGO_INTERNAL_URL

logger = logging.getLogger(__name__)

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

    Conditions : une URL Django interne configuree (sinon degradation
    gracieuse), un jeton present, et un droit d'ecriture.
    """
    if not DJANGO_INTERNAL_URL:
        return False
    if ctx is None or not ctx.token:
        return False
    return ctx.can_act_at_all


# ── Client Django interne ─────────────────────────────────────────────────────


def _django_post(ctx: ActionContext, path: str, payload: dict) -> dict[str, Any]:
    """POST authentifie vers l'API Django interne. Retourne un dict normalise
    {ok, status, data|error}. Ne leve jamais : les erreurs sont renvoyees comme
    texte a l'agent."""
    url = DJANGO_INTERNAL_URL.rstrip("/") + path
    headers = {
        "Authorization": f"Bearer {ctx.token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(url, json=payload, headers=headers)
    except Exception as exc:  # pragma: no cover - reseau
        logger.warning("Appel Django interne echoue (%s): %s", path, exc)
        return {"ok": False, "status": 0,
                "error": "Service indisponible. Reessayez plus tard."}

    ok = 200 <= resp.status_code < 300
    try:
        data = resp.json()
    except Exception:
        data = {}
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


# ── Fabrique d'outils LangChain ───────────────────────────────────────────────


def build_action_tools(ctx: ActionContext) -> list:
    """Construit la liste d'outils LangChain d'action lies au contexte appelant.

    Chaque outil capture `ctx` par closure : l'agent ne fournit jamais la
    societe ni le jeton — ils viennent toujours du serveur.
    """
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    class OuvrirTicketArgs(BaseModel):
        client_id: int = Field(..., description="Identifiant du client concerne.")
        description: str = Field(..., description="Description du probleme SAV.")
        installation_id: Optional[int] = Field(
            None, description="Chantier concerne (optionnel).")
        priorite: str = Field(
            "normale",
            description="basse, normale, haute ou urgente.")
        type_ticket: str = Field(
            "correctif", description="correctif ou preventif.")

    class BrouillonBCArgs(BaseModel):
        installation_id: int = Field(
            ..., description="Chantier dont on commande les manques.")
        fournisseur_id: Optional[int] = Field(
            None, description="Fournisseur (optionnel).")

    class PlanifierVisiteArgs(BaseModel):
        installation_id: int = Field(..., description="Chantier a visiter.")
        date_prevue: str = Field(
            ..., description="Date prevue au format AAAA-MM-JJ.")
        technicien_id: Optional[int] = Field(
            None, description="Technicien assigne (optionnel).")

    tools = []

    if ctx.can_write(_TICKET_PERMS):
        tools.append(StructuredTool.from_function(
            name="ouvrir_ticket_sav",
            description=(
                "Ouvre un nouveau ticket SAV (service apres-vente) pour un "
                "client. A utiliser quand l'utilisateur demande de creer/ouvrir "
                "un ticket ou de signaler une panne."
            ),
            args_schema=OuvrirTicketArgs,
            func=lambda **kw: open_sav_ticket(ctx, **kw),
        ))

    if ctx.can_write(_BC_PERMS):
        tools.append(StructuredTool.from_function(
            name="brouillon_bon_commande_chantier",
            description=(
                "Cree un bon de commande fournisseur BROUILLON pour les "
                "manques de materiel d'un chantier. A utiliser quand "
                "l'utilisateur demande de commander le materiel manquant d'un "
                "chantier."
            ),
            args_schema=BrouillonBCArgs,
            func=lambda **kw: draft_bon_commande_for_chantier(ctx, **kw),
        ))

    if ctx.can_write(_VISITE_PERMS):
        tools.append(StructuredTool.from_function(
            name="planifier_visite_maintenance",
            description=(
                "Planifie une visite de maintenance (intervention de controle) "
                "sur un chantier a une date donnee. A utiliser quand "
                "l'utilisateur demande de planifier/programmer une visite ou "
                "une maintenance."
            ),
            args_schema=PlanifierVisiteArgs,
            func=lambda **kw: schedule_maintenance_visit(ctx, **kw),
        ))

    return tools
