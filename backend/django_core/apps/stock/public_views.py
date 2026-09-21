"""Endpoint PUBLIC (sans login) — portail fournisseur en lecture seule
(XPUR22).

Accès uniquement via le jeton ``PortailFournisseurToken`` (long,
imprévisible, révocable/expirant — mêmes garanties que
``ventes.ShareLink``/``sav.Ticket.share_token``). Un jeton donne accès aux
documents d'UN SEUL fournisseur — jamais ceux d'un autre fournisseur, jamais
de marge. Le fournisseur peut :
  * consulter ses BCF en cours, réceptions, factures (statut de paiement) ;
  * confirmer un BCF + proposer une date d'arrivée (préserve la date
    demandée d'origine — OTD, XPUR7).

Protections : X-Robots-Tag noindex sur chaque réponse ; throttle cache-based
par IP + jeton (sans dépendance externe).
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle


class PortailFournisseurThrottle(SimpleRateThrottle):
    """Limite le débit du portail fournisseur par IP + jeton (cache-based,
    sans dépendance externe)."""
    scope = 'stock_portail_fournisseur'
    rate = '30/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        token = (view.kwargs or {}).get('token', '')
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope, 'ident': f'{ident}:{token}',
        }


def _noindex(response):
    response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    return response


def _not_found():
    return _noindex(Response(
        {'detail': "Ce lien du portail fournisseur est invalide, révoqué "
                   "ou expiré."},
        status=status.HTTP_404_NOT_FOUND,
    ))


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([PortailFournisseurThrottle])
def portail_fournisseur_documents_view(request, token):
    """XPUR22 — documents (BCF/réceptions/factures) DU SEUL fournisseur
    porteur de ce jeton. 404 sans fuite de données si le jeton est invalide,
    révoqué ou expiré."""
    from .services import (
        resoudre_token_portail_fournisseur, portail_fournisseur_documents,
    )
    token_obj = resoudre_token_portail_fournisseur(token)
    if token_obj is None:
        return _not_found()
    return _noindex(Response(portail_fournisseur_documents(token_obj)))


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PortailFournisseurThrottle])
def portail_fournisseur_confirmer_bcf_view(request, token, bcf_id):
    """XPUR22 — le fournisseur confirme un BCF et propose une date
    d'arrivée. Corps : ``{"date_confirmee_fournisseur": "YYYY-MM-DD",
    "numero_confirmation_fournisseur": "..."}``. Isolation stricte : le BCF
    doit appartenir au fournisseur porteur du jeton (sinon 404, jamais
    d'accès croisé)."""
    from .services import (
        resoudre_token_portail_fournisseur, confirmer_bcf_portail_fournisseur,
    )
    token_obj = resoudre_token_portail_fournisseur(token)
    if token_obj is None:
        return _not_found()

    date_confirmee = request.data.get('date_confirmee_fournisseur')
    if not date_confirmee:
        return _noindex(Response(
            {'detail': 'date_confirmee_fournisseur est requise.'},
            status=status.HTTP_400_BAD_REQUEST))

    try:
        bc = confirmer_bcf_portail_fournisseur(
            token_obj, bcf_id, date_confirmee=date_confirmee,
            numero_confirmation=request.data.get(
                'numero_confirmation_fournisseur', ''))
    except ValueError:
        return _not_found()

    return _noindex(Response({
        'id': bc.id, 'reference': bc.reference,
        'date_confirmee_fournisseur': bc.date_confirmee_fournisseur,
        'numero_confirmation_fournisseur':
            bc.numero_confirmation_fournisseur,
    }))


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS8 — Kiosque d'enregistrement de quai (check-in chauffeur, SANS compte)
# ═══════════════════════════════════════════════════════════════════════════

class QuaiCheckinThrottle(SimpleRateThrottle):
    """Anti-force-brute du code de rendez-vous, par IP (cache-based, sans
    dépendance externe). Un code fait 8 caractères sur un alphabet de 32 : ce
    débit rend l'énumération inexploitable."""
    scope = 'stock_quai_checkin'
    rate = '10/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope, 'ident': self.get_ident(request),
        }


@extend_schema(request=None, responses={
    200: inline_serializer('StockQuaiCheckinResultat', {
        'quai': serializers.CharField(),
        'type_quai': serializers.CharField(),
        'heure_rendez_vous': serializers.DateTimeField(),
        'horodatage_arrivee': serializers.DateTimeField(),
        'message': serializers.CharField(),
    }),
    404: inline_serializer('StockQuaiCheckinErreur', {
        'detail': serializers.CharField(),
    }),
})
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([QuaiCheckinThrottle])
def quai_checkin_view(request):
    """NTWMS8 — un chauffeur EXTERNE s'enregistre à son arrivée.

    Corps : ``{"societe": "<slug>", "code": "<code de rendez-vous>"}``. Aucune
    authentification ERP. La réponse ne contient QUE la confirmation et le
    numéro de quai assigné — jamais le client, le transporteur, le contenu de
    la livraison ni un identifiant interne exploitable. Un code inconnu renvoie
    404 sans révéler si c'est la société ou le code qui est faux.
    """
    from .services import enregistrer_arrivee_chauffeur

    donnees = request.data if isinstance(request.data, dict) else {}
    resultat = enregistrer_arrivee_chauffeur(
        societe_slug=donnees.get('societe'), code=donnees.get('code'))
    if resultat is None:
        return _noindex(Response(
            {'detail': 'Code de rendez-vous inconnu ou expiré.'},
            status=status.HTTP_404_NOT_FOUND,
        ))
    return _noindex(Response(resultat))


# ── NTWMS20 — Portail 3PL : le dépositaire consulte SON solde de stock ──────

class PortailTiersThrottle(SimpleRateThrottle):
    """Limite le débit du portail 3PL par IP + jeton (cache-based, sans
    dépendance externe) — même patron que le portail fournisseur."""
    scope = 'stock_portail_tiers'
    rate = '30/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        token = (view.kwargs or {}).get('token', '')
        return self.cache_format % {
            'scope': self.scope,
            'ident': f'{self.get_ident(request)}:{token}',
        }


@extend_schema(responses={
    200: inline_serializer('StockPortailTiersSolde', {
        'tiers_nom': serializers.CharField(),
        'lignes': serializers.ListField(child=serializers.DictField()),
        'total_unites': serializers.IntegerField(),
    }),
    404: inline_serializer('StockPortailTiersErreur', {
        'detail': serializers.CharField(),
    }),
})
@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([PortailTiersThrottle])
def portail_tiers_solde_view(request, token):
    """NTWMS20 — solde de stock DU SEUL dépositaire porteur de ce jeton.

    Lecture seule, sans compte ERP. La réponse ne contient QUE les quantités
    du tiers (produit, SKU, emplacement) — jamais le stock interne de la
    société, jamais un autre dépositaire, jamais un prix ou une marge. Jeton
    invalide, révoqué ou expiré → 404 sans fuite.
    """
    from .services import resoudre_token_portail_tiers, solde_portail_tiers

    token_obj = resoudre_token_portail_tiers(token)
    if token_obj is None:
        return _noindex(Response(
            {'detail': "Ce lien de portail est invalide, révoqué ou expiré."},
            status=status.HTTP_404_NOT_FOUND,
        ))
    return _noindex(Response(solde_portail_tiers(token_obj)))


# ─────────────────────────────────────────────────────────────────────────────
# NTWMS35 — Créneaux de rendez-vous ENTRANT proposés au fournisseur.
# Le portail fournisseur (XPUR22) gagne la prise de rendez-vous : le
# fournisseur voit les créneaux LIBRES des quais de réception (NTWMS7) et
# réserve lui-même — plus d'arrivée non planifiée à absorber au quai. Mêmes
# garanties que le reste du portail : jeton opaque, throttle, noindex,
# isolation stricte au SEUL fournisseur porteur du jeton.
# ─────────────────────────────────────────────────────────────────────────────


@extend_schema(responses={
    200: inline_serializer('StockPortailCreneauxDisponibles', {
        'date_debut': serializers.CharField(allow_blank=True),
        'periode_jours': serializers.IntegerField(),
        'creneaux': serializers.ListField(child=serializers.DictField()),
    }),
})
@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([PortailFournisseurThrottle])
def portail_fournisseur_creneaux_view(request, token):
    """NTWMS35 — créneaux LIBRES des quais de réception
    (``?quai=&periode=`` en jours, plafonné). Lecture seule."""
    from .services import resoudre_token_portail_fournisseur
    from .services_creneaux import creneaux_disponibles

    token_obj = resoudre_token_portail_fournisseur(token)
    if token_obj is None:
        return _not_found()

    periode = request.query_params.get('periode') or 7
    try:
        creneaux = creneaux_disponibles(
            token_obj.company,
            quai_id=request.query_params.get('quai'),
            date_debut=request.query_params.get('date_debut'),
            periode_jours=periode)
    except ValueError as exc:
        return _noindex(Response({'detail': str(exc)},
                                 status=status.HTTP_400_BAD_REQUEST))
    try:
        periode_int = int(periode)
    except (TypeError, ValueError):
        periode_int = 7
    return _noindex(Response({
        'date_debut': (creneaux[0]['date'] if creneaux else ''),
        'periode_jours': periode_int,
        'creneaux': creneaux,
    }))


@extend_schema(request=None, responses={
    201: inline_serializer('StockPortailCreneauReserve', {
        'id': serializers.IntegerField(),
        'quai': serializers.IntegerField(),
        'debut': serializers.CharField(),
        'fin': serializers.CharField(),
        'code_checkin': serializers.CharField(),
    }),
})
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PortailFournisseurThrottle])
def portail_fournisseur_reserver_creneau_view(request, token):
    """NTWMS35 — le fournisseur réserve LUI-MÊME un créneau entrant.

    Corps : ``{quai, debut (ISO), bon_commande?, chauffeur_nom?,
    immatriculation?}``. Renvoie le code de check-in NTWMS8 à remettre au
    chauffeur — il ne donne accès à rien d'autre que la confirmation
    d'arrivée."""
    from .services import resoudre_token_portail_fournisseur
    from .services_creneaux import reserver_creneau_fournisseur

    token_obj = resoudre_token_portail_fournisseur(token)
    if token_obj is None:
        return _not_found()

    try:
        rdv = reserver_creneau_fournisseur(
            token_obj,
            quai_id=request.data.get('quai'),
            debut=request.data.get('debut'),
            bon_commande_id=request.data.get('bon_commande'),
            chauffeur_nom=request.data.get('chauffeur_nom') or '',
            immatriculation=request.data.get('immatriculation') or '')
    except ValueError as exc:
        return _noindex(Response({'detail': str(exc)},
                                 status=status.HTTP_400_BAD_REQUEST))
    return _noindex(Response({
        'id': rdv.id, 'quai': rdv.quai_id,
        'debut': rdv.date_heure_debut.isoformat(),
        'fin': rdv.date_heure_fin.isoformat(),
        'code_checkin': rdv.code_checkin,
    }, status=status.HTTP_201_CREATED))
