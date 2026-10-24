"""ENF11 — Applique, après coup, les déclarations OpenAPI des vues publiques ventes.

Pose ``extend_schema`` sur les vues-fonctions de ``public/lecture_views.py``,
``public/signature_views.py`` et ``public/paiement_views.py`` au démarrage
(``apps.py`` ``ready``) : ces modules sont des régions DÉPLACÉES dont l'AST est
figé par ``tests/golden/split_pv_*.json`` (SPL246/252/253) — un décorateur
ajouté dans le fichier changerait l'empreinte. ``extend_schema`` sur une vue
``@api_view`` annote ``vue.cls`` EN PLACE et rend la même fonction : les
références déjà importées (URLconf, façade ``public_views``) voient la
déclaration. Aucune donnée renvoyée n'est modifiée (même motif que
``apps/adsengine/schema_apply.py``)."""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema


def _declarations(lecture, signature, paiement, SH):
    """(vue, arguments d'``extend_schema``) — une entrée par vue-fonction."""
    return [
        (lecture.proposal_engagement,
         dict(request=SH.EngagementRequest, responses={204: None})),
        # ADEV98 — beacon de lecture humaine (corps ignoré, toujours 204).
        (lecture.proposal_vu, dict(request=None, responses={204: None})),
        (signature.proposal_decliner,
         dict(request=SH.DeclinRequest, extensions=SH.DECLIN_AUTRE_TEXTE,
              responses={200: SH.DeclinResponse, 400: SH.DetailResponse,
                         403: SH.DetailResponse, 409: SH.AcceptRefus})),
        (signature.proposal_contact_request,
         dict(request=SH.ContactRequest, responses=SH.ContactResponses)),
        (signature.proposal_request_otp,
         dict(request=None,
              responses={200: SH.OtpEnvoye, 409: SH.OtpAucunCanal})),
        (signature.proposal_accept,
         dict(request=SH.AcceptRequest,
              responses={200: SH.AcceptResponse, 403: SH.OtpRequis,
                         409: SH.AcceptRefus})),
        (signature.proposal_activate_option,
         dict(request=SH.ActivateOptionRequest,
              responses={200: SH.ActivateOptionResponse,
                         403: SH.OtpRequis})),
        (paiement.proposal_virement_declare,
         dict(request=None,
              responses={200: SH.VirementDeclareResponse,
                         403: SH.DetailResponse})),
        (paiement.pay_page, dict(responses=SH.PayPageResponse)),
        (paiement.pay_webhook,
         dict(request=OpenApiTypes.OBJECT, responses=SH.PayWebhookResponse)),
    ]


def appliquer_schemas():
    """Pose les déclarations sur les vues (appelé par ``ready()``)."""
    from . import openapi_shapes as SH
    from .public import lecture_views, paiement_views, signature_views

    for vue, kw in _declarations(lecture_views, signature_views,
                                 paiement_views, SH):
        extend_schema(**kw)(vue)
