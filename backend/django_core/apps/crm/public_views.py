"""NTCRM17/18 — Salle de vente PUBLIQUE, tokenisée, sans login.

Même modèle de confiance que ``public_booking_views.py``/``ged.PartageGed`` :
un jeton long/imprévisible (``SalleVente.token``) est le SEUL secret d'accès.
404 générique pour un jeton inconnu/révoqué/expiré (jamais de fuite), 403
distinct pour un mot de passe manquant/faux (le lien existe mais est
protégé). Le contenu retourné n'expose JAMAIS de prix d'achat/marge — les
devis sont résolus via ``apps.ventes.selectors`` (jamais ``ventes.models``
directement).

QJR23 (29/08/2026, décisions fondateur D2/D9) — le total exposé est le total
AFFICHÉ du devis (``display_totals``, la MÊME chaîne canonique par option que
la liste/le Kanban) : remise globale honorée, et sur un devis à deux options,
JAMAIS la somme des deux — l'ancien ``devis.total_ttc`` servait le brut.
"""
import hashlib

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from core.throttling import IdentIpPartageeMixin

from .models import SalleVente, SalleVenteItem, SalleVenteVue

_SALLE_VENTE_RESPONSE = inline_serializer('PublicSalleVente', {
    'titre': drf_serializers.CharField(),
    'expires_at': drf_serializers.DateTimeField(allow_null=True),
    'items': drf_serializers.ListField(child=inline_serializer(
        'PublicSalleVenteItem', {
            'id': drf_serializers.IntegerField(),
            'type': drf_serializers.CharField(),
            'titre': drf_serializers.CharField(),
            'ordre': drf_serializers.IntegerField(),
            'reference': drf_serializers.CharField(allow_null=True),
        })),
})

_APPORTEUR_DEALS_RESPONSE = inline_serializer('PublicApporteurMesDeals', {
    'apporteur': drf_serializers.CharField(),
    'deals': drf_serializers.ListField(child=inline_serializer(
        'PublicApporteurDeal', {
            'id': drf_serializers.IntegerField(),
            'client_nom': drf_serializers.CharField(allow_null=True),
            'client_ville': drf_serializers.CharField(allow_null=True),
            'statut': drf_serializers.CharField(),
            'date_enregistrement': drf_serializers.DateTimeField(),
            'montant_commission_estime': drf_serializers.CharField(allow_null=True),
            'montant_commission_du': drf_serializers.CharField(allow_null=True),
        })),
})


class PublicSalleVenteRateThrottle(IdentIpPartageeMixin, SimpleRateThrottle):
    """Débit limité par IP + jeton — même patron que
    ``PublicBookingRateThrottle``.

    QJR416 — l'identifiant du seau vient de la primitive partagée : le
    ``get_ident`` de DRF lisait le PREMIER saut de ``X-Forwarded-For``, donc un
    seau ADRESSABLE par l'appelant."""
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


def _hash_ip(request, salle=None):
    """QJR416 (QJR4-11, requalifié « qualité de données ») — identifiant de
    VISITEUR, salé PAR LIEN.

    DEUX DÉFAUTS, UN SEUL CORRECTIF.

    * L'adresse lue était ``REMOTE_ADDR`` : derrière le proxy, elle vaut la
      MÊME valeur pour TOUS les visiteurs, donc le journal de consultation
      NTCRM18 ne distinguait plus personne (tout le monde partageait une
      empreinte unique). On lit désormais LA primitive partagée
      (``core.throttling.ip_de_requete``, dernier saut de confiance).
    * Le hachage était un SHA-256 NU : la même IP produit la même empreinte sur
      TOUS les liens du dépôt, ce qui permet de recouper les consultations d'un
      même visiteur d'une salle à l'autre — et un dictionnaire d'IPv4 le
      renverse en quelques minutes. Le hachage est désormais SALÉ PAR LIEN
      (jeton de la salle) : deux visiteurs distincts d'un même lien produisent
      deux identifiants, et un même visiteur sur deux liens en produit deux
      DIFFÉRENTS.

    Aucune IP en clair n'est persistée — seulement cette empreinte.
    """
    from core.throttling import ip_de_requete

    ip = ip_de_requete(request)
    if not ip:
        return ''
    sel = str(getattr(salle, 'token', '') or '')
    return hashlib.sha256(
        ('%s|%s' % (sel, ip)).encode('utf-8')).hexdigest()


def _item_payload(item):
    """QJR419 (QJR4-10) — la charge utile publique ne remet plus au visiteur un
    chemin INTERNE qu'il ne peut pas ouvrir.

    ``proposal_path`` valait ``/api/django/ventes/devis/<pk>/proposal/`` : un
    lien vers un endpoint AUTHENTIFIÉ, servi par un endpoint ``AllowAny``. Deux
    défauts d'un coup — il était inutilisable pour son destinataire (le
    visiteur anonyme n'a pas de session), et il DIVULGUAIT la clé primaire
    interne du devis. On sert désormais LE LIEN PUBLIC (la page tokenisée du
    site, construite par le builder unique ``ventes.utils.client_links`` —
    jamais une URL forgée à la main), c'est-à-dire celui qui fonctionne
    réellement pour un visiteur. Aucune clé primaire, aucun ``/api/django/``.

    Le nom de clé ``proposal_path`` est CONSERVÉ : c'est le contrat de l'écran
    qui le consomme, et cette tâche ne touche pas d'écran.
    """
    payload = {
        'id': item.id, 'type': item.type, 'titre': item.titre,
        'ordre': item.ordre,
    }
    if item.type == SalleVenteItem.TypeItem.DEVIS:
        # NTCRM17 — jamais apps.ventes.models directement : `get_devis_by_pk`
        # est le point d'entrée cross-app sanctionné (lecture seule) ; le
        # rendu client complet reste le canal `/proposal` existant (règle #4).
        from apps.ventes.selectors import get_devis_by_pk
        # QJR23 — `display_totals` est LA fonction canonique du total affiché
        # (même chemin que `DevisSerializer.total_affiche`, la liste et le
        # Kanban) : chaîne canonique par option, remise honorée, jamais la
        # somme des deux options d'un devis à deux options (D2/D9).
        from apps.ventes.quote_engine.builder import display_totals
        # QJR419 — builder UNIQUE des URLs client-facing (QX13) : jamais un
        # chemin reconstruit à la main. Utilitaire pur, aucun import de
        # ``ventes.models``.
        from apps.ventes.utils.client_links import url_proposition
        devis = get_devis_by_pk(item.reference)
        if devis is not None and str(devis.company_id) == str(item.salle.company_id):
            payload.update({
                'reference': devis.reference,
                'statut': devis.statut,
                'total_ttc': str(display_totals(devis)['total']),
            })
            # Le lien public est OMIS plutôt que fabriqué si sa résolution
            # échoue : mieux vaut aucune clé qu'un lien mort (Done « ou rien
            # du tout »).
            try:
                payload['proposal_path'] = url_proposition(devis)
            except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
                pass
        else:
            payload['reference'] = None
    else:
        payload['reference'] = item.reference
    return payload


@extend_schema(responses={200: _SALLE_VENTE_RESPONSE})
@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
@throttle_classes([PublicSalleVenteRateThrottle])
def public_salle_vente(request, token):
    """NTCRM17/18 — Détail public d'une salle de vente. Journalise une
    ``SalleVenteVue`` à CHAQUE consultation réussie (NTCRM18/19), IP hachée
    uniquement.

    QJR420 (QJR4-06) — LE MOT DE PASSE A QUITTÉ LA CHAÎNE DE REQUÊTE. Il était
    lu dans ``request.query_params`` (le corps n'étant consulté qu'à défaut) :
    un secret atterrissait donc dans les **journaux d'accès du serveur**,
    l'**historique du navigateur** et l'en-tête **Referer** envoyé à tout
    tiers. Il se transmet désormais **UNIQUEMENT dans le corps d'un POST** ; la
    lecture depuis la chaîne de requête est **SUPPRIMÉE**, pas laissée en repli
    (règle permanente 2 : un repli qui accepte encore le secret en clair dans
    l'URL ne corrige rien).

    Le GET reste servi à l'identique pour une salle SANS mot de passe — c'est
    le cas courant, il ne change pas ; une salle protégée exige un POST.
    """
    salle = _resolve_salle(token)
    if salle is None:
        return Response(status=status.HTTP_404_NOT_FOUND)
    if not salle.is_accessible:
        return Response(status=status.HTTP_410_GONE)
    if salle.has_password:
        corps = request.data if hasattr(request.data, 'get') else {}
        mot_de_passe = corps.get('mot_de_passe') or ''
        if not isinstance(mot_de_passe, str):
            mot_de_passe = ''
        if not salle.check_password(mot_de_passe):
            return Response(
                {'detail': 'Mot de passe requis ou invalide.'},
                status=status.HTTP_403_FORBIDDEN)

    SalleVenteVue.objects.create(
        salle=salle, ip_hash=_hash_ip(request, salle))
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

class PublicApporteurRateThrottle(IdentIpPartageeMixin, SimpleRateThrottle):
    # QJR416 — même primitive d'identifiant que les autres throttles publics.
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


@extend_schema(responses={200: _APPORTEUR_DEALS_RESPONSE})
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
