"""WREF2-L3 (fondateur, GO 21/08/2026 — option B) — relève PUBLIQUE de la
référence serveur « NOM-N » pour l'écran de succès du site.

CONTEXTE. L'envoi du lead depuis le site (``POST /api/capture-lead`` côté
apps/web, relayé vers ``webhooks.website_lead_webhook``) est délibérément
FIRE-AND-FORGET — zéro-perte, le formulaire n'attend jamais la réponse du
webhook (voir ``apps/web/src/pages/api/capture-lead.ts``). L'écran de succès
ne peut donc PAS connaître la référence « NOM-N » attribuée par
``webhooks.assign_client_ref`` au moment où il s'affiche : il n'a que le code
provisoire tiré par le navigateur (``TQ-XXXX``). Ce petit endpoint public est
la RELÈVE : le site l'interroge après coup (quelques tentatives espacées),
clé = ``idempotencyKey`` déjà envoyée dans le payload du lead
(``lib/lead.ts`` — un jeton par session de saisie, régénéré à chaque nouvelle
soumission).

COMMENT LA CLÉ EST RETROUVÉE. ``webhooks.website_lead_webhook`` stocke le
payload BRUT reçu (``WebsiteLeadPayload.payload``, un ``JSONField`` — donc
``idempotencyKey`` y est conservé tel quel) et rattache ``WebsiteLeadPayload.
lead`` dès que le mapping réussit. On relit ce même triplet : la ligne dont
``payload__idempotencyKey`` correspond ET dont le lead rattaché porte déjà une
``client_ref``. Une soumission dédupliquée (même clé rejouée, YDATA12) ne
rattache JAMAIS de lead (voir webhooks.py, bloc ``dedupe_event``) : le filtre
``lead__client_ref`` l'exclut donc naturellement, aucun risque de retour d'un
brouillon.

SCOPING SOCIÉTÉ. ``idempotencyKey`` est générée côté NAVIGATEUR, qui ignore
tout de la société — exactement la même situation que le webhook de capture
lui-même. On réutilise donc ``webhooks._resolve_company()`` telle quelle
(même résolution serveur, ``WEBSITE_LEADS_COMPANY_ID`` sinon repli 1re
``Company``) plutôt que d'inventer un second mécanisme : la ligne
``WebsiteLeadPayload`` a été écrite sous CETTE société par le webhook, la
relève doit lire sous la MÊME pour la retrouver.

THROTTLE + ANTI-ÉNUMÉRATION. Même patron que ``public_booking_views``/
``public_chat_views`` (``SimpleRateThrottle`` scopé IP + clé). Le corps 404
est CONSTANT et opaque (``_OPAQUE_404``) quel que soit le motif (clé mal
formée, société non résolue, aucune ligne, lead sans référence) — aucune
donnée du lead (nom, téléphone, ville…) n'est jamais exposée ici, seule la
référence courte quand elle existe.
"""
import re

from rest_framework import status
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from .models import WebsiteLeadPayload
from .webhooks import _resolve_company

#: Même discipline anti-garbage que le site (lib/lead.ts, validation
#: `idempotencyKey` avant envoi) — une clé hors de cette forme ne peut être
#: celle d'AUCUNE soumission réelle, jamais la peine d'interroger la base.
_IDEMPOTENCY_KEY_RE = re.compile(r'^[A-Za-z0-9_-]{8,64}$')

#: Corps 404 CONSTANT, quel que soit le motif — anti-énumération (jamais un
#: message qui distinguerait « clé invalide » de « pas encore de référence »).
_OPAQUE_404 = {'detail': 'Introuvable.'}


class PublicLeadRefLookupThrottle(SimpleRateThrottle):
    """Débit limité par IP + clé — même patron que ``PublicBookingRateThrottle``
    (décourage l'abus sans jamais bloquer un visiteur légitime : l'écran de
    succès ne fait que 2-3 tentatives espacées par soumission)."""

    scope = 'public_lead_ref'
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


def _find_client_ref(company, idempotency_key: str, field: str):
    """Ligne ``WebsiteLeadPayload`` la plus récente, scopée société, dont le
    payload brut porte cette clé sous ``field`` (``'idempotencyKey'`` ou son
    repli snake_case) ET dont le lead rattaché porte déjà une référence."""
    lookup = f'payload__{field}'
    return (
        WebsiteLeadPayload.objects
        .filter(company=company, **{lookup: idempotency_key})
        .exclude(lead__isnull=True)
        .exclude(lead__client_ref__isnull=True)
        .exclude(lead__client_ref='')
        .order_by('-received_at')
        .values_list('lead__client_ref', flat=True)
        .first()
    )


@extend_schema(
    responses=inline_serializer('LeadRefLookupResponse', {
        'client_ref': serializers.CharField(
            help_text='Référence serveur NOM-N attribuée au lead'),
    }),
    description=('Relève publique de la référence client par idempotencyKey '
                 '(contract_samples/lead_ref_lookup.json). 404 opaque constant '
                 'pour tout échec — anti-énumération.'),
)
@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([PublicLeadRefLookupThrottle])
def lead_ref_lookup(request, idempotency_key):
    """GET public/lead-ref/<idempotency_key>/ → ``{'client_ref': 'BENALI-1'}``
    ou 404 opaque. AUCUNE autre donnée n'est jamais renvoyée."""
    if not _IDEMPOTENCY_KEY_RE.match(idempotency_key or ''):
        return Response(_OPAQUE_404, status=status.HTTP_404_NOT_FOUND)

    company = _resolve_company()
    if company is None:
        return Response(_OPAQUE_404, status=status.HTTP_404_NOT_FOUND)

    # `idempotencyKey` est la clé émise par les workers actuels (lib/lead.ts) ;
    # `idempotency_key` (snake_case) reste tolérée en repli — même lecture
    # tolérante que `webhooks._map_and_link_lead`/`website_lead_webhook`, pour
    # ne jamais manquer une ligne écrite par un ancien format de payload.
    client_ref = (
        _find_client_ref(company, idempotency_key, 'idempotencyKey')
        or _find_client_ref(company, idempotency_key, 'idempotency_key'))
    if not client_ref:
        return Response(_OPAQUE_404, status=status.HTTP_404_NOT_FOUND)
    return Response({'client_ref': client_ref})
