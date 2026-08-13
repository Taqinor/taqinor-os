"""NTCRM17/18 — Salle de vente PUBLIQUE, tokenisée, sans login.

Même modèle de confiance que ``public_booking_views.py``/``ged.PartageGed`` :
un jeton long/imprévisible (``SalleVente.token``) est le SEUL secret d'accès.
404 générique pour un jeton inconnu/révoqué/expiré (jamais de fuite), 403
distinct pour un mot de passe manquant/faux (le lien existe mais est
protégé). Le contenu retourné n'expose JAMAIS de prix d'achat/marge — les
devis sont résolus via ``apps.ventes.selectors`` (jamais ``ventes.models``
directement), et le total exposé est TOUJOURS le TTC client existant.
"""
import hashlib

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from .models import SalleVente, SalleVenteItem, SalleVenteVue


class PublicSalleVenteRateThrottle(SimpleRateThrottle):
    """Débit limité par IP + jeton — même patron que
    ``PublicBookingRateThrottle``."""
    scope = 'public_salle_vente'
    rate = '30/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        token = (view.kwargs or {}).get('token', '') if view else ''
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': f'{ident}:{token}',
        }


def _resolve_salle(token):
    return SalleVente.objects.select_related('company').filter(token=token).first()


def _hash_ip(request):
    ip = request.META.get('REMOTE_ADDR', '') or ''
    if not ip:
        return ''
    return hashlib.sha256(ip.encode('utf-8')).hexdigest()


def _item_payload(item):
    payload = {
        'id': item.id, 'type': item.type, 'titre': item.titre,
        'ordre': item.ordre,
    }
    if item.type == SalleVenteItem.TypeItem.DEVIS:
        # NTCRM17 — jamais apps.ventes.models directement : `get_devis_by_pk`
        # est le point d'entrée cross-app sanctionné (lecture seule) ; le
        # rendu client complet reste le canal `/proposal` existant (règle #4).
        from apps.ventes.selectors import get_devis_by_pk
        devis = get_devis_by_pk(item.reference)
        if devis is not None and str(devis.company_id) == str(item.salle.company_id):
            payload.update({
                'reference': devis.reference,
                'statut': devis.statut,
                'total_ttc': str(devis.total_ttc),
                'proposal_path': f'/api/django/ventes/devis/{devis.pk}/proposal/',
            })
        else:
            payload['reference'] = None
    else:
        payload['reference'] = item.reference
    return payload


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([PublicSalleVenteRateThrottle])
def public_salle_vente(request, token):
    """NTCRM17/18 — Détail public d'une salle de vente. Journalise une
    ``SalleVenteVue`` à CHAQUE consultation réussie (NTCRM18/19), IP hachée
    uniquement."""
    salle = _resolve_salle(token)
    if salle is None:
        return Response(status=status.HTTP_404_NOT_FOUND)
    if not salle.is_accessible:
        return Response(status=status.HTTP_410_GONE)
    if salle.has_password:
        mot_de_passe = request.query_params.get('mot_de_passe') or ''
        if not mot_de_passe and request.data:
            mot_de_passe = request.data.get('mot_de_passe', '')
        if not salle.check_password(mot_de_passe):
            return Response(
                {'detail': 'Mot de passe requis ou invalide.'},
                status=status.HTTP_403_FORBIDDEN)

    SalleVenteVue.objects.create(salle=salle, ip_hash=_hash_ip(request))
    try:
        # NTCRM27 — best-effort : ne doit jamais faire échouer la vue publique.
        from .services import detecter_signal_interet_salle_vente
        detecter_signal_interet_salle_vente(salle)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        pass

    items = salle.items.all().order_by('ordre', 'id')
    return Response({
        'titre': salle.titre,
        'expires_at': salle.expires_at.isoformat() if salle.expires_at else None,
        'items': [_item_payload(i) for i in items],
    })


# ── NTCRM21 — Portail apporteur en lecture seule (tokenisé) ────────────────
# Même modèle de confiance que ci-dessus : le token `Apporteur.token_acces`
# est le SEUL secret — jamais un id d'URL devinable, jamais une session
# CustomUser. Ne montre QUE les deals de CET apporteur (jamais ceux d'un
# autre) et n'expose du client que nom/ville (jamais téléphone/email/adresse
# complète — cf. `AUTH`).

class PublicApporteurRateThrottle(SimpleRateThrottle):
    scope = 'public_apporteur_portail'
    rate = '30/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        token = (view.kwargs or {}).get('token', '') if view else ''
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': f'{ident}:{token}',
        }


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([PublicApporteurRateThrottle])
def public_apporteur_mes_deals(request, token):
    """NTCRM21 — Deals + commissions estimées de CET apporteur uniquement.

    404 générique pour un jeton inconnu ou un apporteur inactif (jamais de
    fuite « ce token existe mais est désactivé »)."""
    from .models import Apporteur

    apporteur = Apporteur.objects.filter(
        token_acces=token, actif=True).first()
    if apporteur is None:
        return Response(status=status.HTTP_404_NOT_FOUND)

    deals = (apporteur.deals
             .select_related('lead')
             .order_by('-date_enregistrement'))
    return Response({
        'apporteur': apporteur.nom,
        'deals': [{
            'id': d.id,
            'client_nom': d.lead.nom if d.lead_id else None,
            'client_ville': d.lead.ville if d.lead_id else None,
            'statut': d.statut,
            'date_enregistrement': d.date_enregistrement.isoformat(),
            'montant_commission_estime': (
                str(d.montant_commission_estime)
                if d.montant_commission_estime is not None else None),
            'montant_commission_du': (
                str(d.montant_commission_du)
                if d.montant_commission_du is not None else None),
        } for d in deals],
    })
