import asyncio
import base64
import binascii
import re
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import (BaseModel, Field, TypeAdapter, ValidationError, field_validator,
                      model_validator)

from app.core import database as _database
from app.core.security import exiger_compte_interne, get_raw_token, verify_token
# AANA7 — UN seul helper (societe ACTIVE d'abord, 403 sans societe),
# partage avec l'OCR ; le nom local est garde pour les appelants.
from app.core.security import require_company_id as _require_company_id
from app.services import action_tools as _at
from app.services.action_tools import ActionContext
from app.services import relais_copilote
from app.services.sql_agent_service import (
    sql_agent_service, suggestions_pour_ecran,
)

router = APIRouter(dependencies=[Depends(exiger_compte_interne)])  # APFS2

# AANA5 (C-AANA-034) — bornes de l'agent : une question de 1 Mo ou une rafale
# de requetes ne doit ni saturer le LLM (payant) ni la base.
# Copilote v2 (F4) : 6 000 quand le copilote est allume pour l'appelant
# (`relais_copilote.capacites`) ; sinon 2 000, avec le MEME 422 qu'avant.
SQL_AGENT_QUESTION_MAX_LENGTH = relais_copilote.LIMITE_QUESTION   # 2000 caracteres
SQL_AGENT_QUESTION_MAX_LENGTH_COPILOTE = relais_copilote.LIMITE_QUESTION_COPILOTE
SQL_AGENT_RATE_LIMIT_MAX = 20             # requetes max par utilisateur...
SQL_AGENT_RATE_LIMIT_WINDOW = 60          # ...sur une fenetre de 60 s


def _check_sql_agent_rate_limit(user_id) -> None:
    """Limiteur Redis partage (fenetre glissante, fail-closed comme l'OCR)."""
    _database.check_rate_limit(
        "sql_agent_rate", user_id,
        SQL_AGENT_RATE_LIMIT_MAX, SQL_AGENT_RATE_LIMIT_WINDOW,
        detail=(
            f"Limite atteinte : {SQL_AGENT_RATE_LIMIT_MAX} questions par "
            "minute. Reessayez dans un instant."
        ),
    )


_PROGRESSION_ID = r"^[A-Za-z0-9_-]{8,64}$"  # AIC91 — identifiant donne par l'ecran


class ContexteEcran(BaseModel):
    """AIC9 — contexte de l'ecran d'ou part la question (evenement DOM
    `taqinor:assistant:ouvrir`, ou `window.location.pathname`). COP-B2 :
    fiche de devis ouverte, touche FOYER de la conversation et tampon
    technique du navigateur (donnee NON fiable : bornee, cles inconnues
    ecartees). Toute autre cle du corps est ignoree."""
    ecran: str = Field("", max_length=255)
    lead_id: int | None = Field(None, ge=1)
    devis_id: int | None = Field(None, ge=1)
    touche_id: int | None = Field(None, ge=1)
    diagnostic: dict | None = None

    @field_validator("diagnostic", mode="before")
    @classmethod
    def _borner_diagnostic(cls, valeur):
        return relais_copilote.borner_diagnostic(valeur)


#: Copilote v2 (F5) — images jointes a une question (capture d'un message de
#: client) : 3 au plus, chacune <= 2 000 000 caracteres base64, types du
#: contrat ; contenu verifie par la signature du fichier (meme table que l'OCR).
IMAGES_MAX = 3
IMAGE_BASE64_MAX = 2_000_000


class ImageJointe(BaseModel):
    media_type: Literal["image/jpeg", "image/png", "image/webp"]
    data: str = Field(..., min_length=16, max_length=IMAGE_BASE64_MAX)

    @model_validator(mode="after")
    def _verifier_contenu(self):
        from app.api.endpoints.ocr import _check_magic_bytes  # meme table que l'OCR (ocr.py MAGIC_BYTES)
        try:
            octets = base64.b64decode(self.data, validate=True)
        except (binascii.Error, ValueError):
            raise ValueError("Image illisible : base64 invalide.") from None
        if not _check_magic_bytes(self.media_type, octets[:16]):
            raise ValueError("Le contenu de l'image ne correspond pas à son type.")
        return self


class SQLQuery(BaseModel):
    # AANA5 — plafond DUR du schema (6 000 : 422 pydantic standard au-dela) ;
    # puis, apres le limiteur, la borne de l'APPELANT (`_borner_question` :
    # 2 000, ou 6 000 copilote allume sous claude — F4), avant tout appel LLM.
    question: str = Field(..., max_length=SQL_AGENT_QUESTION_MAX_LENGTH_COPILOTE)
    # AIC9 — optionnel : injecte dans le message UTILISATEUR, journalise.
    contexte: ContexteEcran | None = None
    # AIC91 — optionnel : identifiant aleatoire pour sonder les etapes du tour.
    progression_id: str | None = Field(None, pattern=_PROGRESSION_ID)
    # F5 — optionnel : servies au moteur natif seulement (relais_copilote.tour_avec_images).
    images: list[ImageJointe] | None = Field(None, max_length=IMAGES_MAX)


class SQLResponse(BaseModel):
    answer: str
    # ERR84 — Le SQL genere (avec les vrais noms de tables) n'est jamais
    # divulgue au client (divulgation de schema). Le champ reste present pour
    # ne pas casser le contrat frontend, mais il est TOUJOURS vide cote reponse.
    sql_query: str = ""
    data: list | None = None
    # N86 — True si l'agent a effectue une action d'ecriture (ticket SAV,
    # brouillon de bon de commande, visite). Le frontend affiche un badge.
    action_performed: bool = False
    # AG2 — proposition d'action SENSIBLE (outward/irreversible) a confirmer :
    # {action_key, human_preview, confirm_token, inputs?}. Le `confirm_token`
    # est le MEME jeton signe attendu par /sql-agent/confirm — c'est le seul
    # chemin pour confirmer. None quand aucune action sensible n'a ete proposee.
    proposal: dict | None = None
    # AG2 — resultat d'une action INTERNE deja executee ce tour :
    # {action_key, reference?, wa_url?, devis_id?, detail?, ...}. None sinon.
    result: dict | None = None
    # AIC6 — id de l'evenement journalise (note du commercial, AIC8) ; None
    # si le journal n'a pas pu etre ecrit (best-effort).
    evenement_id: int | None = None
    # COP-B1 — TOUTES les cartes du tour, dans l'ordre (contrat
    # assistant_reponse.json) ; l'ecran ne lit plus que celles-ci.
    cartes: list[dict] = Field(default_factory=list)
    # COP-B1 — moteur qui a servi la reponse : "langchain" ou "natif".
    moteur: str = "langchain"


def _contexte_de_lecture(token_payload: dict, raw_token: str) -> ActionContext:
    """Contexte minimal pour LIRE le catalogue de l'appelant (Django tranche
    par le jeton : la societe passee ici ne sert a rien)."""
    return ActionContext(company_id=0, role=str(token_payload.get("role") or ""),
                         permissions=[], token=raw_token,
                         is_superuser=bool(token_payload.get("is_superuser", False)))


def _refus_longueur(question: str, limite: int) -> None:
    """Le 422 de pydantic, octet pour octet (`string_too_long`, loc
    body.question) — copilote eteint, la meme reponse qu'avant F4."""
    try:
        TypeAdapter(Annotated[str, Field(max_length=limite)]).validate_python(question)
    except ValidationError as exc:
        raise RequestValidationError([
            {**err, "loc": ("body", "question", *err["loc"])}
            for err in exc.errors(include_url=False)]) from None


async def _borner_question(question: str, token_payload: dict, raw_token: str) -> None:
    """AANA5 + F4 — au-dela de 2 000 caracteres, la borne de l'appelant est
    lue chez Django (une lecture du catalogue, seulement dans ce cas)."""
    if len(question) <= SQL_AGENT_QUESTION_MAX_LENGTH:
        return
    caps = await asyncio.to_thread(
        relais_copilote.capacites, _contexte_de_lecture(token_payload, raw_token))
    _refus_longueur(question, caps["limite_question"])


class Capacites(BaseModel):
    """Contrat `assistant_reponse.json` → `capacites` (copilote v2, F4)."""
    limite_question: int
    images_acceptees: bool


class HistoryMessage(BaseModel):
    role: str
    content: str
    # COP-B1 — cartes du message d'agent (absentes d'un historique ancien).
    cartes: list[dict] | None = None


@router.post("/query", response_model=SQLResponse)
async def query_database(
    request: SQLQuery,
    token_payload: dict = Depends(verify_token),
    raw_token: str = Depends(get_raw_token),
):
    """Agent SQL conversationnel — repond aux questions en francais.

    N86 — l'agent peut aussi effectuer des ACTIONS d'ecriture (ticket SAV,
    brouillon de bon de commande, planification de visite) quand l'appelant a
    le droit d'ecriture. Le contexte d'action porte le role/les permissions du
    JWT, les permissions du role (lues par /auth/me/, AANA8) + le jeton brut
    (relaye a l'API Django interne, qui tranche).
    """
    user_id = int(token_payload.get("user_id", 0))
    # ERR44 — exige un company_id present et non nul (403 sinon).
    company_id = _require_company_id(token_payload)
    # AANA6 — production sans role Postgres dedie : agent desactive (503).
    _database.require_sql_agent_enabled()
    # AANA5 — plafond de debit (429) ; Redis injoignable => 503 (fail-closed).
    _check_sql_agent_rate_limit(user_id)
    # AANA5 / F4 — borne de l'APPELANT (2 000, ou 6 000) APRES le limiteur :
    # la lecture du catalogue qu'elle demande au-dela de 2 000 est bornee aussi.
    await _borner_question(request.question, token_payload, raw_token)

    action_ctx = ActionContext(
        company_id=company_id,
        role=token_payload.get("role", ""),
        # AANA8 — plus jamais le claim JWT `permissions` (il n'est plus emis :
        # toujours []) : la source est /auth/me/ de Django, resolue ci-dessous.
        permissions=[],
        token=raw_token,
        is_superuser=bool(token_payload.get("is_superuser", False)),
    )
    # COP-B2 — UNE lecture de /auth/me/ : permissions + prenom et role.
    await asyncio.to_thread(relais_copilote.lire_appelant, action_ctx)
    if request.progression_id:
        action_ctx.progression_cle = _at.cle_progression(user_id, request.progression_id)

    options = {}
    if request.contexte is not None:
        options["contexte"] = request.contexte.model_dump()
    if request.images:  # F5 — jamais journalisees ni gardees (marqueur seulement)
        options["images"] = [image.model_dump() for image in request.images]
    try:
        result = await sql_agent_service.query(
            question=request.question,
            user_id=user_id,
            company_id=company_id,
            action_ctx=action_ctx,
            **options,
        )
    finally:  # AIC91 — l'ecran arrete de sonder
        await asyncio.to_thread(_at.noter_etape, action_ctx, None, True)
    return SQLResponse(
        answer=result["answer"],
        # ERR84 — jamais le SQL brut : redige cote serveur.
        sql_query="",
        data=result["data"],
        action_performed=bool(result.get("action_performed", False)),
        # AG2 — surface la proposition signee (avec confirm_token) et/ou le
        # resultat d'action interne produit ce tour ; None quand absent.
        proposal=result.get("proposal"),
        result=result.get("result"),
        evenement_id=result.get("evenement_id"),
        cartes=result.get("cartes") or [],
        moteur=result.get("moteur") or "langchain",
    )


@router.get("/history", response_model=list[HistoryMessage],
            response_model_exclude_none=True)
def get_history(token_payload: dict = Depends(verify_token)):
    """Retourne l'historique de conversation (24h, 20 messages max)."""
    user_id = int(token_payload.get("user_id", 0))
    return sql_agent_service.get_history(user_id)


@router.delete("/history", status_code=204)
def clear_history(token_payload: dict = Depends(verify_token)):
    """Efface la conversation de l'utilisateur (et sa conversation native,
    rangee sous la societe active, COP-B6)."""
    user_id = int(token_payload.get("user_id", 0))
    try:
        company_id = _require_company_id(token_payload)
    except HTTPException:
        company_id = None
    sql_agent_service.clear_history(user_id, company_id)


@router.get("/suggestions", response_model=list[str])
def get_suggestions(ecran: str = "/", token_payload: dict = Depends(verify_token)):
    """AIC9 — trois questions suggerees pour l'ecran, lues du manifeste
    `capacites.yml` deja charge (cle `suggestions`) ; [] sans manifeste."""
    return suggestions_pour_ecran(ecran[:255])


@router.get("/capacites", response_model=Capacites)
async def get_capacites(token_payload: dict = Depends(verify_token),
                        raw_token: str = Depends(get_raw_token)):
    """Copilote v2 (F4) — ce que l'ecran peut envoyer pour CE compte :
    `{limite_question, images_acceptees}` (6 000 / vrai seulement copilote
    allume ; images : moteur natif + fournisseur claude en plus ; sinon
    2 000 / faux). Lu par le panneau a son ouverture."""
    return await asyncio.to_thread(
        relais_copilote.capacites, _contexte_de_lecture(token_payload, raw_token))


@router.get("/progression/{progression_id}")
def get_progression(progression_id: str, token_payload: dict = Depends(verify_token)):
    """AIC91 — etapes du tour en cours `{etapes: [{libelle, t}], fini}`,
    sondees par l'ecran ; identifiant inconnu ou d'un autre utilisateur ->
    vide (la cle porte l'utilisateur du jeton)."""
    if not re.match(_PROGRESSION_ID, progression_id or ""):
        return {"etapes": [], "fini": False}
    return _at.lire_progression(_at.cle_progression(
        int(token_payload.get("user_id", 0)), progression_id))


@router.get("/schema")
async def get_schema(token_payload: dict = Depends(verify_token)):
    """Retourne les tables disponibles et le provider LLM actif."""
    return await sql_agent_service.get_schema_summary()


# ── AG2 — Confirmation d'une action proposee ──────────────────────────────────


class ConfirmRequest(BaseModel):
    # Jeton opaque renvoye par une proposition d'action (outward/irreversible).
    token: str


class ConfirmResponse(BaseModel):
    ok: bool
    action_key: str = ""
    detail: str = ""
    data: dict | list | None = None
    # COP-B1 — carte `resultat` de l'action confirmee (fabrique des cartes).
    carte: dict | None = None
    # COP-B6 — reprise du moteur natif {answer, cartes, evenement_id} ;
    # toujours None sous le moteur langchain.
    suite: dict | None = None


@router.post("/confirm", response_model=ConfirmResponse)
async def confirm_action(
    request: ConfirmRequest,
    token_payload: dict = Depends(verify_token),
    raw_token: str = Depends(get_raw_token),
):
    """AG2 — Execute une action SENSIBLE precedemment PROPOSEE, par jeton.

    Une action `outward`/`irreversible` n'est jamais executee a la volee :
    l'agent renvoie une proposition signee, stashee en Redis (TTL court). Cet
    endpoint la rejoue APRES :
      - verification de la signature (rejet si alteree / expiree) ;
      - controle que la societe du jeton == societe de l'appelant ;
      - re-recuperation du catalogue de l'appelant (l'action doit toujours y
        figurer) et RE-VALIDATION des entrees contre le JSON-Schema courant
        (les entrees hors catalogue sont rejetees) ;
      - relais JWT a Django, qui re-tranche permission + societe.
    """
    if not request.token or not request.token.strip():
        raise HTTPException(status_code=400, detail="Jeton de confirmation requis.")

    company_id = _require_company_id(token_payload)
    action_ctx = ActionContext(
        company_id=company_id,
        role=token_payload.get("role", ""),
        # AANA8 — plus jamais le claim JWT `permissions` (il n'est plus emis :
        # toujours []) : la source est /auth/me/ de Django, resolue ci-dessous.
        permissions=[],
        token=raw_token,
        is_superuser=bool(token_payload.get("is_superuser", False)),
    )
    # COP-B2 — UNE lecture de /auth/me/ : permissions + prenom et role.
    await asyncio.to_thread(relais_copilote.lire_appelant, action_ctx)

    result = await sql_agent_service.confirm_action(action_ctx, request.token.strip())
    if not result.get("ok"):
        detail = result.get("error", "L'action n'a pas pu etre executee.")
        # D-COP-5 — l'échec entre dans la conversation : le modèle le sait et
        # dit le geste qui marche (le 20/11 il reproposait la même carte, 4 fois).
        # L4 (revue adverse du 21/11, B2) — reprise SEULEMENT sur un refus
        # métier net (4xx : rien d'écrit). Jeton introuvable / déjà confirmé
        # (double appui) ou issue incertaine (0, 5xx) : jamais « refusée,
        # corrige » — le modèle referait une action peut-être déjà faite.
        statut = int(result.get("status") or 0)
        suite = (await asyncio.to_thread(
            relais_copilote.apres_echec_confirmation, sql_agent_service, action_ctx,
            company_id, int(token_payload.get("user_id", 0)), result)
            if 400 <= statut < 500 else None)
        return ConfirmResponse(ok=False, detail=detail, suite=suite)
    data = result.get("data")
    apres = await asyncio.to_thread(
        relais_copilote.apres_confirmation, sql_agent_service, action_ctx,
        company_id, int(token_payload.get("user_id", 0)), result)
    return ConfirmResponse(
        ok=True,
        action_key=result.get("action_key", ""),
        data=data if isinstance(data, (dict, list)) else None,
        detail="Action executee.",
        carte=apres.get("carte"),
        suite=apres.get("suite"),
    )
