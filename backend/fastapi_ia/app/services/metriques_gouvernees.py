"""NTDATA12 — les METRIQUES GOUVERNEES offertes a l'agent NL->SQL.

LE PROBLEME. « Quel est notre DSO ? » : l'agent ecrivait un SQL ad-hoc, avec
SA definition du DSO — un second chiffre, qui ne correspond ni au tableau de
bord ni a l'alerte KPI. La couche semantique Django (``apps/semantic``) tient
UNE definition par cle ; l'agent doit la preferer quand l'intention correspond.

CE QUE FAIT CE MODULE. A la construction de l'agent, il lit le catalogue
``GET /api/django/semantic/metriques/pour-agent/`` (cle + libelle + definition
+ unite, metriques actives de la societe de l'appelant) avec le JWT de
l'appelant relaye — Django reste l'autorite (scope societe, permissions). Il en
fait UN outil LangChain ``metrique_gouvernee`` dont la DESCRIPTION liste le
catalogue (c'est ainsi que le modele « voit » les metriques) ; l'appeler lit la
valeur par ``GET /api/django/semantic/metriques/<cle>/valeur/`` — le resolveur
serveur, jamais un recalcul ici.

LECTURE SEULE, aucun secret : le catalogue ne porte ni dataset, ni mesure, ni
filtres. Une metrique de MARGE n'est offerte qu'a un appelant autorise a voir
la marge (meme decision que le garde L17 de l'outil SQL). Sans URL Django
interne, sans jeton, catalogue vide ou injoignable : pas d'outil (degradation
gracieuse, l'agent garde son chemin SQL).
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from app.services.action_tools import ActionContext, _django_call, actions_available

logger = logging.getLogger(__name__)

CATALOGUE_PATH = "/api/django/semantic/metriques/pour-agent/"
VALEUR_PATH = "/api/django/semantic/metriques/{cle}/valeur/"

#: Une cle de metrique (meme forme que le serializer Django).
_CLE_VALIDE = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
#: Une metrique de marge n'est offerte qu'avec le droit de voir la marge (L17).
_MOTS_MARGE = ("marge",)
#: Borne de la description de l'outil (le catalogue entre dans le prompt).
MAX_METRIQUES = 40


def catalogue_metriques(ctx: Optional[ActionContext],
                        allow_price: bool = False) -> list[dict[str, str]]:
    """Le catalogue des metriques gouvernees visibles par l'appelant.

    ``[]`` si Django est injoignable, sans jeton, ou sans metrique : jamais une
    exception (l'agent doit repondre quand meme).
    """
    if not actions_available(ctx):
        return []
    res = _django_call(ctx, CATALOGUE_PATH, method="GET")
    data = res.get("data") if res.get("ok") else None
    metriques = data.get("metriques") if isinstance(data, dict) else None
    if not isinstance(metriques, list):
        return []
    out = []
    for m in metriques:
        if not isinstance(m, dict):
            continue
        cle = str(m.get("cle") or "")
        if not _CLE_VALIDE.match(cle):
            continue
        if not allow_price and any(mot in cle for mot in _MOTS_MARGE):
            continue
        out.append({
            "cle": cle,
            "libelle": str(m.get("libelle") or "")[:150],
            "description": str(m.get("description") or "")[:300],
            "unite": str(m.get("unite") or "")[:10],
        })
    return out[:MAX_METRIQUES]


def description_outil(metriques: list[dict[str, str]]) -> str:
    """Le texte que le modele lit : la consigne + le catalogue."""
    lignes = [
        "Renvoie la valeur OFFICIELLE d'une metrique gouvernee de l'ERP, "
        "calculee par le serveur avec la definition partagee par tous les "
        "tableaux de bord. PREFERE cet outil a une requete SQL ad-hoc des que "
        "la question porte sur l'une de ces metriques (ex. « quel est notre "
        "DSO » -> cle dso). Parametre : cle. Metriques disponibles :",
    ]
    for m in metriques:
        unite = f" ({m['unite']})" if m.get("unite") else ""
        definition = f" — {m['description']}" if m.get("description") else ""
        lignes.append(f"- {m['cle']} : {m['libelle']}{unite}{definition}")
    return "\n".join(lignes)


def lire_valeur(ctx: ActionContext, cles_autorisees: set[str],
                cle: str) -> dict[str, Any]:
    """La valeur globale de ``cle`` lue chez Django (jamais recalculee ici)."""
    cle = (cle or "").strip()
    if cle not in cles_autorisees:
        return {"ok": False,
                "erreur": "Metrique inconnue : utilise une cle de la liste."}
    res = _django_call(ctx, VALEUR_PATH.format(cle=cle), method="GET",
                       payload={"group_by": ""})
    if not res.get("ok"):
        return {"ok": False, "statut": res.get("status"),
                "erreur": res.get("error") or "Valeur indisponible."}
    data = res.get("data") if isinstance(res.get("data"), dict) else {}
    return {"ok": True, "cle": cle, "libelle": data.get("libelle"),
            "unite": data.get("unite"), "valeur": data.get("valeur")}


def outil_metrique_gouvernee(ctx: Optional[ActionContext],
                             allow_price: bool = False):
    """L'outil LangChain ``metrique_gouvernee``, ou ``None`` sans catalogue."""
    metriques = catalogue_metriques(ctx, allow_price)
    if not metriques:
        return None

    from langchain_core.tools import StructuredTool
    from pydantic import create_model

    cles = {m["cle"] for m in metriques}
    args = create_model("Args_metrique_gouvernee", cle=(str, ...))

    def _lire(cle: str) -> str:
        return json.dumps(lire_valeur(ctx, cles, cle), ensure_ascii=False,
                          default=str)

    return StructuredTool.from_function(
        name="metrique_gouvernee", func=_lire, args_schema=args,
        description=description_outil(metriques))
