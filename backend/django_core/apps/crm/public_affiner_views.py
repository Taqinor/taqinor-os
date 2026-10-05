"""CIQ413 (contrat CIQ400 ``lead_affiner_pro.json``, D-CIQ-8) — relève
« Affiner » : le site obtient le lien du questionnaire PRO de SA soumission,
et rien d'autre.

CONTEXTE. L'envoi du lead depuis le site est FIRE-AND-FORGET (voir
``public_lead_ref_views``) : l'écran du site n'a que l'``idempotencyKey`` de
sa soumission. L'étape « Affiner », FACULTATIVE et placée APRÈS la porte de
contact, a besoin d'un jeton de questionnaire pro pour ce lead-là — sans
créer un second lead (une seconde soumission du site en crée un).

RÈGLES (toutes reprises de la relève ``lead-ref``, rien de réinventé) :
  · même validation de clé, même résolution de société
    (``webhooks._resolve_company``), même throttle IP + clé, même 404 OPAQUE
    (corps identique quel que soit le motif — anti-énumération) ;
  · le jeton n'est servi QUE si la soumission de CETTE clé a créé un lead
    ``commercial``/``industriel``, encore à l'étape ``NEW`` (importée de
    STAGES.py, jamais un littéral) et non anonymisé ;
  · le jeton vient de ``questionnaire.mint_lien`` (idempotent : jamais deux
    liens vivants) et n'ouvre que les sections PRO (CIQ412) ;
  · une note de chatter « lien Affiner ouvert depuis le site » n'est écrite
    qu'à la CRÉATION du lien ; aucune autre écriture sur le lead.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from .models import Lead, LeadActivity, WebsiteLeadPayload
from .public_lead_ref_views import _IDEMPOTENCY_KEY_RE, _OPAQUE_404
from .stages import NEW
from .webhooks import _resolve_company

#: Texte de la note posée à la création du lien.
NOTE_LIEN_AFFINER = 'Lien Affiner ouvert depuis le site (questionnaire pro).'

_TYPES_PRO = (Lead.TypeInstallation.COMMERCIAL,
              Lead.TypeInstallation.INDUSTRIEL)


class PublicLeadAffinerThrottle(SimpleRateThrottle):
    """Débit limité par IP + clé — même patron que la relève ``lead-ref``."""

    scope = 'public_lead_affiner'
    rate = '20/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        key = (view.kwargs or {}).get('idempotency_key', '') if view else ''
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': f'{ident}:{key}',
        }


def _lead_de_la_soumission(company, idempotency_key):
    """Le lead créé par la soumission de cette clé (le plus récent), ou None.
    Lecture scopée société ; un lead supprimé (corbeille) n'est jamais lu."""
    for champ in ('idempotencyKey', 'idempotency_key'):
        lead_id = (
            WebsiteLeadPayload.objects
            .filter(company=company, **{f'payload__{champ}': idempotency_key})
            .exclude(lead__isnull=True)
            .order_by('-received_at')
            .values_list('lead_id', flat=True)
            .first())
        if lead_id:
            return Lead.objects.filter(pk=lead_id, company=company).first()
    return None


def _eligible(lead):
    from .dsr_provider import LEAD_NOM_ANONYMISE
    return (lead is not None
            and lead.type_installation in _TYPES_PRO
            and lead.stage == NEW
            and lead.nom != LEAD_NOM_ANONYMISE)


@extend_schema(
    request=None,
    responses=inline_serializer('LeadAffinerProResponse', {
        'questionnaire_token': serializers.CharField(
            help_text='Jeton client du questionnaire pro du lead'),
    }),
    description=('Relève « Affiner » : jeton du questionnaire PRO du lead créé '
                 'par cette soumission (contract_samples/lead_affiner_pro.json)'
                 '. 404 opaque constant pour tout échec — anti-énumération.'),
)
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PublicLeadAffinerThrottle])
def lead_affiner_pro(request, idempotency_key):
    """POST public/lead-affiner/<idempotency_key>/ →
    ``{'questionnaire_token': '…'}`` ou 404 opaque. Aucun corps attendu."""
    from .questionnaire import mint_lien

    if not _IDEMPOTENCY_KEY_RE.match(idempotency_key or ''):
        return Response(_OPAQUE_404, status=status.HTTP_404_NOT_FOUND)
    company = _resolve_company()
    if company is None:
        return Response(_OPAQUE_404, status=status.HTTP_404_NOT_FOUND)
    lead = _lead_de_la_soumission(company, idempotency_key)
    if not _eligible(lead):
        return Response(_OPAQUE_404, status=status.HTTP_404_NOT_FOUND)
    lien, _change, cree = mint_lien(lead)
    if cree:
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE, body=NOTE_LIEN_AFFINER)
    return Response({'questionnaire_token': lien.token})
