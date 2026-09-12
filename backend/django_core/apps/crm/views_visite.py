"""VT12 — la porte CRM vers la texture de toit d'un lead.

VTA3 — le ViewSet de la visite technique terrain et ses actions ont déménagé
dans ``apps.visites.views`` (app autonome : le commercial terrain n'a pas
l'accès CRM). Ce module ne garde QUE l'endpoint qui vit légitimement côté CRM :
``GET /api/django/crm/leads/<pk>/photo-toit/``, monté sur le LEAD et lu par des
écrans qui ne connaissent rien au module visite.

Il appelle ``apps.visites.selectors.texture_toit_pour_lead`` en import
PARESSEUX — frontière M3 : une lecture cross-app passe par le ``selectors.py``
de l'app cible, jamais par ses modèles.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import HasPermissionOrLegacy


@extend_schema(responses=inline_serializer(
    name='LeadPhotoToit',
    fields={
        'visite_id': serializers.IntegerField(allow_null=True),
        'url': serializers.CharField(allow_null=True),
        'texture_calage': serializers.JSONField(allow_null=True),
    }))
@api_view(['GET'])
@permission_classes([HasPermissionOrLegacy('crm_voir')])
def lead_photo_toit(request, lead_id):
    """VT12 — ``GET /api/django/crm/leads/<pk>/photo-toit/``.

    La porte par laquelle l'atelier 3D/calepinage et la carte de la fiche lead
    lisent le toit réaliste SANS connaître le module visite : ils demandent la
    texture d'un LEAD, le serveur choisit la dernière visite VALIDÉE.

    JAMAIS 404 : sans visite validée, sans image, ou pour un lead qui n'est pas
    de la société de l'appelant, la réponse porte les MÊMES clés à ``null``
    (``{"visite_id": null, "url": null, "texture_calage": null}``). Une seule
    forme à consommer côté écran, et aucune différence de réponse qui
    laisserait deviner l'existence du lead d'une autre société.

    Permission : ``crm_voir`` — la lecture CRM ordinaire, celle que portent
    déjà le commercial ET l'atelier ; exiger ``visites_voir`` fermerait la
    porte aux écrans qui ne font que peindre le toit.
    """
    from apps.visites import selectors  # noqa: PLC0415 - frontière M3

    from .models import Lead  # noqa: PLC0415

    lead = Lead.objects.filter(pk=lead_id,
                               company=request.user.company).first()
    return Response(selectors.texture_toit_pour_lead(lead))
