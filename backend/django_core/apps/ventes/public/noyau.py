"""Noyau partagé des liens publics de devis (SPL245, déplacé de ``public_views.py``).

Primitives communes aux 16 endpoints publics : limitation de débit par IP +
jeton, réponses ``noindex`` / 404 neutre, lecture typée du corps de requête,
retrait des clés internes, résolution du jeton ShareLink (public ou aperçu
interne), niveau et sections servies du lien, IP client et horodatage client.
Déplacement pur : corps octet-identiques (seule la profondeur des imports
relatifs locaux change), prouvé par ``tests/golden/split_pv_noyau.json``.
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from core.throttling import IdentIpPartageeMixin

from ..models import ShareLink


# Avis FR clair montré quand le lien est expiré ou introuvable. Aucune donnée
# interne n'est exposée ; formulation NEUTRE (N100(c) white-label — le lien
# invalide ne permet pas toujours de résoudre la société, donc jamais de
# marque codée en dur ici) (L854).
LINK_EXPIRED_MESSAGE = (
    "Ce lien de partage a expiré ou n'est plus valide. "
    "Merci de demander un nouveau lien à votre installateur pour consulter "
    "votre document."
)


class PublicLinkRateThrottle(IdentIpPartageeMixin, SimpleRateThrottle):
    """Limite le débit des liens publics par IP + jeton (cache-based).

    QJR416 — l'identifiant du seau vient de la primitive partagée
    (``core.throttling.IdentIpPartageeMixin``) : le ``get_ident`` de DRF lit le
    PREMIER saut de ``X-Forwarded-For`` quand ``NUM_PROXIES`` est absent, ce qui
    rendait le seau ADRESSABLE par l'appelant — donc la limite contournable en
    changeant un en-tête.

    Pas de dépendance externe : on s'appuie sur le throttle DRF intégré et le
    cache du projet. Le taux est fixé ici (pas de réglage settings nécessaire)
    pour décourager le balayage de jetons et l'aspiration de PDF, sans jamais
    bloquer un client légitime qui consulte son document.
    """
    scope = 'public_sharelink'
    rate = '30/minute'

    def get_rate(self):
        # QX41 — source de vérité UNIQUE : le taux vient de
        # DEFAULT_THROTTLE_RATES['public_sharelink'] (settings), repli sur le
        # défaut inline si absent (rétro-compatible).
        try:
            from django.conf import settings
            rates = (settings.REST_FRAMEWORK or {}).get(
                'DEFAULT_THROTTLE_RATES', {})
            return rates.get(self.scope) or self.rate
        except Exception:  # noqa: BLE001
            return self.rate

    def get_cache_key(self, request, view):
        token = (view.kwargs or {}).get('token', '') if view else ''
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': f'{ident}:{token}',
        }


def _noindex(response):
    """Marque une réponse publique comme non-indexable par les moteurs."""
    response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    return response


def _not_found():
    return _noindex(Response(
        {'detail': LINK_EXPIRED_MESSAGE},
        status=status.HTTP_404_NOT_FOUND,
    ))


def _texte_du_corps(request, *cles, defaut=''):
    """QJR413 (b) — UN champ de corps JSON public lu comme du TEXTE.

    Renvoie ``(texte, None)`` en succès, ``(None, <Response 400>)`` en refus —
    l'appelant fait ``if refus is not None: return refus``.

    LE DÉFAUT QUE CECI FERME. Ces endpoints sont ``AllowAny`` et lisaient leur
    corps en écrivant ``(request.data.get('x') or '').strip()`` : un corps JSON
    dont le champ vaut un NOMBRE, un OBJET, une LISTE ou un ``null`` EXPLICITE
    faisait lever un ``AttributeError``/``TypeError`` non intercepté, donc un
    **HTTP 500 non authentifié** — la même racine que le ``compare_digest`` en
    chaînes du (a) : « une entrée hostile fait planter un endpoint public au
    lieu de se faire refuser ».

    RÈGLES, et il n'y en a que trois :

    * la **première** des ``cles`` PRÉSENTE dans le corps décide (les suivantes
      ne sont consultées que si la précédente est absente ou vide) ;
    * une valeur qui n'est **pas une chaîne** — nombre, booléen, objet, liste,
      ``null`` explicite — est REFUSÉE par un **400 propre** qui nomme le champ
      et ne renvoie **jamais** la valeur reçue ;
    * une clé **absente** vaut le ``defaut`` : le comportement d'aujourd'hui,
      byte-identique, pour tout client qui omet un champ facultatif (le
      client réel omet ces champs, il ne les envoie jamais à ``null`` — voir
      ``apps/web/src/lib/proposition.ts buildAcceptBodyRich``).

    Un corps JSON qui n'est même pas un objet (tableau, scalaire) est refusé de
    la même façon : ``request.data.get`` y levait aussi.
    """
    if not hasattr(request.data, 'get'):
        return None, _noindex(Response(
            {'detail': 'Le corps de la requête doit être un objet JSON.'},
            status=status.HTTP_400_BAD_REQUEST))
    for cle in cles:
        if cle not in request.data:
            continue
        valeur = request.data.get(cle)
        if not isinstance(valeur, str):
            return None, _noindex(Response(
                {'detail': 'Le champ « %s » doit être du texte.' % cle},
                status=status.HTTP_400_BAD_REQUEST))
        # La bascule de clé se fait sur la valeur BRUTE, exactement comme le
        # ``a or b or ''`` d'avant : une chaîne d'espaces reste une valeur
        # fournie (elle rend '' après strip et NE bascule PAS sur la clé
        # suivante) — comportement d'aujourd'hui, byte-identique.
        if valeur:
            return valeur.strip(), None
    return defaut, None


_CONFIDENTIAL_KEY_MARKERS = ('prix_achat', 'achat', 'marge', 'revendeur')


def _strip_confidential_deep(obj):
    """RÈGLE #4 — retire RÉCURSIVEMENT toute clé de dict contenant un marqueur
    d'achat/marge (prix_achat, achat, marge, revendeur) à N'IMPORTE QUELLE
    profondeur, avant toute exposition client. Un layout 3D brut imbriqué
    (Devis.roof_layout, un panneau portant ``prix_achat``/``marge``) ne peut
    plus fuiter le prix d'achat que le filtre de premier niveau manquait. Listes
    parcourues élément par élément ; scalaires renvoyés inchangés."""
    if isinstance(obj, dict):
        return {
            k: _strip_confidential_deep(v)
            for k, v in obj.items()
            if not any(m in str(k) for m in _CONFIDENTIAL_KEY_MARKERS)
        }
    if isinstance(obj, (list, tuple)):
        return [_strip_confidential_deep(v) for v in obj]
    return obj


def _sans_cles_internes(obj):
    """Retire RÉCURSIVEMENT toute clé de dict PRÉFIXÉE PAR ``_``.

    LA CONVENTION EST DÉJÀ CELLE DU BUILDER : ``_company_id``, ``_produit_nom``,
    ``_embed_roof_render`` — le souligné y signifie « donnée de plomberie
    interne, jamais un champ de document ». Rien de tout cela n'a d'affaire
    dans la charge utile d'une page publique : ``payload['quote']`` republie
    ``data`` TEL QUEL, si bien qu'un identifiant de société sortait chez le
    client (chemin ``.quote._company_id``) — une donnée de cloisonnement
    multi-société, offerte à qui possède un jeton.

    Le geste est GÉNÉRIQUE plutôt que nominatif : une prochaine clé de
    plomberie ajoutée au builder sera retirée d'elle-même, sans qu'il faille
    penser à l'inscrire ici — c'est-à-dire sans l'oublier.
    """
    if isinstance(obj, dict):
        return {k: _sans_cles_internes(v) for k, v in obj.items()
                if not str(k).startswith('_')}
    if isinstance(obj, (list, tuple)):
        return [_sans_cles_internes(v) for v in obj]
    return obj


def _resolve_share_link_by_token(token, *, select_related=()):
    """L-INTPREV (fondateur 25/08/2026) — résout un ShareLink par son jeton
    PUBLIC ou par son jeton INTERNE (aperçu commercial sans notification),
    même URL de page des deux côtés. Renvoie ``(link, via_interne)`` — ``link``
    est ``None`` si aucun des deux jetons ne correspond ou si le lien résolu
    est expiré.

    Le jeton public est essayé EN PREMIER (chemin historique, le plus
    fréquent) ; le jeton interne n'est essayé que s'il ne matche pas — les
    deux espaces de jetons sont uniques indépendamment, donc au plus une
    ligne peut matcher au total."""
    qs = ShareLink.objects.all()
    if select_related:
        qs = qs.select_related(*select_related)
    link = qs.filter(token=token).first()
    via_interne = False
    if link is None:
        link = qs.filter(token_interne=token).first()
        via_interne = link is not None
    if link is None or not link.is_valid:
        return None, False
    return link, via_interne


#: R4 (27/08/2026) — message UNIQUE de refus d'une action CLIENT demandée avec
#: le jeton d'aperçu INTERNE. Formulé pour le commercial (c'est lui qui l'a en
#: main), jamais ambigu : l'aperçu montre la page, il ne l'engage pas.
APERCU_INTERNE_REFUS = 'Aperçu interne : action client indisponible.'


def _refus_apercu_interne():
    """R4 — 403 posé sur les endpoints d'ACTION du parcours public quand le
    jeton résolu est le jeton interne.

    Le jeton interne (L-INTPREV) existe pour qu'un commercial voie la page
    EXACTEMENT comme le client, sans laisser de trace. Il ne doit donc jamais
    pouvoir ÉMETTRE une action au nom du client : demander à être rappelé,
    faire partir un code OTP sur le téléphone du client, activer une option
    payante de son devis, ou déclarer un virement. Ces actions écrivent dans
    le chatter, notifient le vendeur, envoient un message au client ou
    changent le périmètre facturé — un aperçu ne fait rien de tout cela.

    403 explicite (et non le 404 générique) : ici le porteur du jeton est
    NOTRE commercial, pas un inconnu — lui dire pourquoi son clic est refusé
    vaut mieux que lui laisser croire à un lien mort. ``proposal_accept``
    garde son 404 d'origine (L-INTPREV) : la signature est le seul cas où le
    refus ne doit RIEN distinguer d'un jeton invalide."""
    return _noindex(Response(
        {'detail': APERCU_INTERNE_REFUS},
        status=status.HTTP_403_FORBIDDEN))


def _niveau_lien(link):
    """L-NIV — le niveau d'affichage RÉVOCABLE porté par le lien (jamais par le
    jeton). Un lien créé avant la migration 0100 vaut « confiance » ;
    ``getattr`` défensif au cas où un test construit un lien à la main."""
    return (getattr(link, 'niveau', ShareLink.NIVEAU_CONFIANCE)
            or ShareLink.NIVEAU_CONFIANCE)


def _section_servie(link, cle):
    """L-SECT (24/08/2026) — LA décision « cette section part-elle chez ce
    client ? », prise UNE fois pour tous les flux publics.

    Délègue au modèle (``ShareLink.section_servie``) quand il l'expose, et
    retombe sur « servie » sinon : un lien construit à la main dans un test,
    ou un lien créé avant la migration 0101, se comporte EXACTEMENT comme
    avant L-SECT."""
    methode = getattr(link, 'section_servie', None)
    if callable(methode):
        return bool(methode(cle))
    return True


def _client_ip(request):
    """QJR416 — l'IP de PREUVE, lue par LA primitive partagée.

    Cette valeur part dans le registre IMMUABLE de signature électronique
    (loi 53-05) : c'est un champ de preuve. Elle lisait le PREMIER saut de
    ``X-Forwarded-For`` — donc une valeur **choisie par l'attaquant**, qui
    pouvait écrire l'adresse opposée plus tard à un signataire. Elle délègue
    désormais à :func:`core.throttling.ip_de_requete`, qui lit le DERNIER saut
    de confiance. Aucune seconde lecture d'IP dans le dépôt.
    """
    from core.throttling import ip_de_requete

    return ip_de_requete(request)


def _parse_client_ts(value):
    """QX9 — parse l'horodatage client ISO 8601 (best-effort → None si invalide).

    Utilisé pour ``DevisSignature.signed_at_client`` : jamais bloquant, un
    format inattendu tombe simplement à None (l'horodatage serveur fait foi)."""
    if not value:
        return None
    try:
        from django.utils.dateparse import parse_datetime
        return parse_datetime(str(value))
    except Exception:  # noqa: BLE001
        return None


def _resolve_proposal_link(token, *, refuser_brouillon=True):
    """Return a valid devis-bearing ShareLink for this token, or None.

    L-INTPREV (25/08/2026) — accepte AUSSI le jeton d'aperçu interne (même
    devis, même page). ``link.via_interne`` (attribut dynamique, jamais
    persisté) dit aux appelants si CE jeton était l'interne — les endpoints
    qui doivent rester sans trace / refuser d'engager le client (lecture,
    signature) le lisent explicitement.

    ADEV11 (C-ADEV-004) — un BROUILLON n'est jamais servi au jeton CLIENT : un
    lien frappé par ``share-link`` (ou par un rendu PDF) avant l'envoi n'ouvre
    ni la lecture ni l'action — ``None`` (404 muet, aucun chiffre servi). Le
    jeton INTERNE d'aperçu reste servi (c'est le commercial). Les endpoints
    d'ACTION passent ``refuser_brouillon=False`` puis répondent le 409
    ``brouillon`` du contrat ``proposal_accept.json`` (``_refus_brouillon``)."""
    link, via_interne = _resolve_share_link_by_token(
        token,
        select_related=('devis', 'devis__client', 'devis__company', 'company'))
    if link is None or not link.devis_id:
        return None
    link.via_interne = via_interne
    if refuser_brouillon and lien_client_sur_brouillon(link):
        return None
    return link


def lien_client_sur_brouillon(link):
    """ADEV11 — vrai quand ``link`` est résolu par le jeton CLIENT et que son
    devis est encore BROUILLON (jamais envoyé)."""
    from ..models import Devis
    devis = getattr(link, 'devis', None)
    return (not getattr(link, 'via_interne', False)
            and devis is not None
            and devis.statut == Devis.Statut.BROUILLON)


def _refus_brouillon(link):
    """ADEV11 — 409 ``{detail, code: "brouillon"}`` sur un endpoint d'ACTION
    (acceptation, option, OTP, contact) appelé au jeton client d'un brouillon ;
    ``None`` sinon. Posé AVANT tout effet de bord."""
    if not lien_client_sur_brouillon(link):
        return None
    from ..domain.cycle_vie import BROUILLON_REFUS
    return _noindex(Response(
        {'detail': BROUILLON_REFUS, 'code': 'brouillon'},
        status=status.HTTP_409_CONFLICT))
