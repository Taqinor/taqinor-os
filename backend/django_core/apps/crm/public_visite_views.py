"""T-TRACE — beacon PUBLIC des visites du site (finalité anti-fraude).

Contrat figé et committé AVANT cette implémentation (PACT10) :
``apps/crm/contract_samples/visite_externe.json`` — la lane web code contre
CE fichier, jamais contre une forme devinée.

AUTHENTIFICATION : strictement CELLE DU WEBHOOK LEAD DU SITE. Ce module ne
réinvente aucun secret — il importe ``_secret_ok`` / ``_freshness_ok`` /
``_resolve_company`` de ``apps.crm.webhooks`` et les applique dans le même
ordre. Le site passe par le même chemin Worker/proxy que le tunnel, donc les
mêmes en-têtes (``X-Webhook-Secret``, ``X-Webhook-Timestamp``) sont déjà
posés. Secret non configuré = endpoint FERMÉ (jamais ouvert par défaut).

LE BEACON EST MUET. Il répond ``{"ok": true}`` et RIEN d'autre — jamais le
nombre de visites déjà connues, jamais un identifiant de lead, jamais un
état interne : une page publique ne doit rien pouvoir apprendre du CRM. Un
corps inexploitable vaut aussi ``{"ok": true}`` : un beacon ne doit jamais
faire apparaître une erreur dans la console d'un visiteur.
"""
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from .models import VisiteExterne
from .visites import (
    MAX_APPAREIL,
    MAX_CONTEXTE,
    MAX_LANGUE,
    ip_de_requete,
    nettoyer_texte,
    tracer_et_correler,
)
from .webhooks import _freshness_ok, _resolve_company, _secret_ok


class PublicVisiteRateThrottle(SimpleRateThrottle):
    """Débit borné par (IP, appareil) — généreux, jamais illimité.

    Le beacon bat toutes les ~20 s, soit 3 requêtes/minute par onglet : 120
    laisse une marge très large (plusieurs onglets, une reprise après coupure
    réseau) tout en gardant une borne. La clé inclut l'``appareil_id`` parce
    qu'au Maroc une IP est massivement partagée : un seul compteur par IP
    ferait taire les visiteurs légitimes d'un même réseau d'entreprise.
    L'IP est extraite comme dans le webhook (``X-Forwarded-For`` d'abord),
    jamais via un ``get_ident`` qui verrait l'IP du Worker pour tout le monde.
    """

    scope = 'public_visite'
    rate = '120/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        appareil = ''
        donnees = getattr(request, 'data', None)
        if isinstance(donnees, dict):
            appareil = nettoyer_texte(donnees.get('appareil_id'), MAX_APPAREIL)
        return self.cache_format % {
            'scope': self.scope,
            'ident': f'{ip_de_requete(request)}:{appareil}',
        }


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PublicVisiteRateThrottle])
def public_visite(request):
    """T-TRACE — enregistre (ou prolonge) la visite anonyme d'une page du site.

    Corps : ``{appareil_id, page, duree_s, fin, langue}`` — voir le contrat.
    ``ip`` et ``user_agent`` ne sont JAMAIS lus du corps : le service les
    prend côté serveur dans les en-têtes HTTP.

    Les battements successifs du même appareil sur la même page mettent à
    jour la MÊME visite (fenêtre de 30 min) — jamais une ligne par battement.
    """
    if not _secret_ok(request):
        return Response({'detail': 'Secret invalide ou absent.'}, status=401)
    if not _freshness_ok(request):
        return Response({'detail': 'Horodatage hors tolérance.'}, status=401)

    donnees = request.data if isinstance(request.data, dict) else {}
    company = _resolve_company()
    if company is not None:
        # Best-effort par construction (``tracer_et_correler`` avale et
        # journalise toute erreur) : la réponse est décidée d'avance.
        tracer_et_correler(
            company,
            point=VisiteExterne.Point.VISITE_SITE,
            appareil_id=nettoyer_texte(donnees.get('appareil_id'), MAX_APPAREIL),
            contexte=nettoyer_texte(donnees.get('page'), MAX_CONTEXTE),
            langue=nettoyer_texte(donnees.get('langue'), MAX_LANGUE),
            duree_s=donnees.get('duree_s'),
            fin=bool(donnees.get('fin')),
            request=request,
        )
    return Response({'ok': True})
