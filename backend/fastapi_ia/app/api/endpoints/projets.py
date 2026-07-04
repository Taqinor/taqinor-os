"""XPRJ29 — Génération IA d'un brouillon de plan de tâches depuis un devis.

``POST /projets/generer-plan`` : reçoit les données DÉJÀ résolues côté ERP
(``apps.ventes.selectors.devis_pour_projet`` + ``type_installation``) et
renvoie une PROPOSITION de WBS JSON. Ne matérialise RIEN — l'ERP (Django)
crée les tâches/dépendances seulement APRÈS confirmation utilisateur
(``apps.gestion_projet.services.materialiser_plan_taches``).

Key-gated : sans ``GROQ_API_KEY`` (ou provider équivalent), renvoie 503
proprement (aucune requête réseau, aucun coût).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.security import verify_token
from app.services.plan_taches_service import (
    PlanTachesIndisponible,
    generer_plan_taches,
)

router = APIRouter()


class DevisData(BaseModel):
    id: int | None = None
    montant_materiel: float = 0
    montant_main_oeuvre: float = 0
    nb_lignes_materiel: int = 0
    nb_lignes_main_oeuvre: int = 0


class GenererPlanRequest(BaseModel):
    devis: DevisData
    type_installation: str = 'residentiel'


class TachePlan(BaseModel):
    code: str
    libelle: str
    phase: str
    duree_jours: int
    dependances_fs: list[str] = []


class GenererPlanResponse(BaseModel):
    taches: list[TachePlan]


@router.post("/generer-plan", response_model=GenererPlanResponse)
async def generer_plan(
    request: GenererPlanRequest,
    token_payload: dict = Depends(verify_token),
):
    """Propose un brouillon de WBS (JSON) depuis un devis (XPRJ29).

    Sans clé LLM configurée → 503 (dégradation propre, jamais une 500 brute).
    Une réponse LLM inexploitable → 502 (l'ERP peut re-essayer/annuler).
    """
    try:
        plan = generer_plan_taches(
            request.devis.model_dump(), request.type_installation)
    except PlanTachesIndisponible as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return GenererPlanResponse(**plan)
