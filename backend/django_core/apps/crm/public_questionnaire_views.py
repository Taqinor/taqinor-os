"""L-QUEST — Questionnaire client PUBLIC, tokenisé par lead, expirant (30 j).

Endpoints PUBLICS (sans login) pour le prospect qui a reçu son lien : voir les
questions que le commercial lui pose (avec ses propres réponses déjà connues
en pré-remplissage) et y répondre SECTION PAR SECTION, chez lui, à son rythme
— il peut fermer la page et revenir, le lien se rouvre.

Même modèle de confiance que ``public_booking_views.py`` : jeton long et
imprévisible, aucun login, débit limité par IP+jeton, et un 404 à corps
CONSTANT sur tout échec (jamais bavard, jamais énumérable).

DEUX JETONS (ordre fondateur 25/08/2026) :
  · ``token``          — celui du CLIENT : lecture + écriture ;
  · ``token_interne``  — celui du COMMERCIAL, jamais montré au client : même
    page en APERÇU, qui ne journalise RIEN (aucune LeadActivity, aucun
    ``derniere_reponse_at``, aucun ``sections_repondues``) et où toute
    écriture est REFUSÉE (403). Un aperçu ne doit rien déclencher, et le
    commercial ne répond jamais à la place du client.

Ces vues n'exposent AUCUNE donnée interne du lead : uniquement le prénom
d'accueil, le nom de la société émettrice, les sections demandées et les
valeurs que le client a lui-même fournies. Jamais de prix, jamais de marge,
jamais un autre lead.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from .questionnaire import (
    LienIndisponible,
    SectionInconnue,
    appliquer_section,
    champs_a_poser,
    prefill,
    resoudre,
    sections_a_servir,
)

#: Corps CONSTANT de tout échec de résolution (jeton inconnu OU expiré) —
#: aucune distinction qui aiderait à énumérer les jetons.
_INTROUVABLE = {'detail': 'Introuvable.'}


class PublicQuestionnaireRateThrottle(SimpleRateThrottle):
    """Débit limité par IP + jeton — décourage l'abus sans jamais bloquer un
    client légitime (même patron que ``PublicBookingRateThrottle``)."""

    scope = 'public_questionnaire'
    rate = '20/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        token = (view.kwargs or {}).get('token', '') if view else ''
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': f'{ident}:{token}',
        }


# Forme DÉCLARÉE (cliquet R2 check_openapi_shapes — jamais deviner) : miroir
# du contrat contract_samples/questionnaire_lead.json (GET = affichage,
# POST = une section de réponses ; prefill/reponses restent des DictField
# ouverts — leurs clés varient par section, la whitelist vit dans
# questionnaire.CHAMPS_PAR_SECTION, jamais dupliquée ici).
@extend_schema(
    request=inline_serializer('PublicQuestionnaireReponseRequest', {
        'section': serializers.CharField(required=False),
        'reponses': serializers.DictField(required=False),
        'photo': serializers.CharField(required=False, allow_blank=True),
        'appareil_id': serializers.CharField(
            required=False, allow_blank=True),
    }),
    responses={200: inline_serializer('PublicQuestionnaireReponse', {
        'entreprise': serializers.CharField(required=False),
        'prenom': serializers.CharField(required=False),
        'sections': serializers.ListField(
            child=serializers.CharField(), required=False),
        'prefill': serializers.DictField(required=False),
        'repondu': serializers.DictField(required=False),
        'interne': serializers.BooleanField(required=False),
        'ok': serializers.BooleanField(required=False),
        'enregistrees': serializers.ListField(
            child=serializers.CharField(), required=False),
    })},
)
@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
@throttle_classes([PublicQuestionnaireRateThrottle])
def public_questionnaire(request, token):
    """L-QUEST — LA page questionnaire : GET affiche, POST enregistre.

    Une SEULE URL pour les deux (contrat ``questionnaire_lead.json``) — la
    page publique n'a qu'une adresse à connaître, celle du lien envoyé."""
    try:
        lien, interne = resoudre(token)
    except LienIndisponible:
        return Response(_INTROUVABLE, status=status.HTTP_404_NOT_FOUND)
    if request.method == 'POST':
        return _repondre(request, lien, interne)
    return _detail(lien, interne)


def _detail(lien, interne):
    """Contenu de la page : sections DEMANDÉES, pré-remplissage de leurs
    champs (valeurs actuelles du lead — une valeur absente vaut ``null``,
    jamais un défaut inventé) et sections déjà répondues (reprise).

    ``champs`` (ordre fondateur 25/08/2026) porte le grain FIN : pour chaque
    section servie, les SEULES colonnes que la page a le droit de dessiner.
    Une donnée que le lead porte déjà y revient (pré-remplie, confirmable) ;
    une donnée vide mais couverte par une autre déjà connue — l'adresse d'un
    client qui a donné son GPS — n'y est PAS, et la question disparaît. Cette
    clé n'expose rien de neuf : ce sont les noms des colonnes que ``prefill``
    accompagne déjà, jamais une donnée interne de plus.

    Aucune écriture, aucune trace : un simple affichage ne modifie jamais la
    fiche — ce qui rend l'aperçu interne du commercial parfaitement muet."""
    sections = sections_a_servir(lien.lead, lien.sections_actives())
    repondues = lien.sections_repondues
    if not isinstance(repondues, dict):
        repondues = {}
    return Response({
        'entreprise': (getattr(lien.company, 'nom', '') or '').strip(),
        'prenom': (lien.lead.prenom or '').strip(),
        'sections': sections,
        'champs': champs_a_poser(lien.lead, sections),
        'prefill': prefill(lien.lead, sections),
        'repondu': {cle: True for cle in sections if repondues.get(cle)},
        'interne': interne,
    })


def _repondre(request, lien, interne):
    """Enregistre UNE section répondue (enregistrement progressif).

    Corps : ``section`` (clé de la whitelist, requise), ``reponses`` (objet
    {champ: valeur}) ou ``photo`` (base64/data-URL, sections ``photo_*``).
    Une section inconnue ou non demandée sur ce lien → 400. Le jeton INTERNE
    (aperçu commercial) → 403 : un aperçu n'écrit jamais."""
    if interne:
        return Response(
            {'detail': 'Aperçu interne : lecture seule.'},
            status=status.HTTP_403_FORBIDDEN)

    section = request.data.get('section')
    if not isinstance(section, str) or not section.strip():
        return Response({'detail': 'Section manquante.'},
                        status=status.HTTP_400_BAD_REQUEST)

    try:
        enregistrees = appliquer_section(
            lien, section.strip(),
            reponses=request.data.get('reponses'),
            photo=request.data.get('photo'),
        )
    except SectionInconnue as exc:
        return Response({'detail': str(exc)},
                        status=status.HTTP_400_BAD_REQUEST)

    _tracer_reponse(request, lien, section.strip())
    return Response({'ok': True, 'enregistrees': enregistrees})


def _tracer_reponse(request, lien, section):
    """T-TRACE (25/08/2026) — trace anti-fraude d'une réponse CLIENT.

    Posé sur le POST uniquement — jamais sur le GET : la docstring de
    ``_detail`` promet « aucune écriture, aucune trace » à l'affichage, et
    c'est cette promesse qui rend l'aperçu interne du commercial parfaitement
    muet. Le jeton INTERNE n'atteint jamais cette fonction (``_repondre``
    répond 403 avant), donc la garde existante suffit — aucune seconde garde
    qui pourrait diverger de la première.

    Le jeton n'est pas transmis en entier : le service n'en garde que les 6
    derniers caractères. Strictement best-effort — une réponse client
    enregistrée ne doit jamais échouer à cause d'une trace."""
    try:
        from .services import appareil_de_requete, tracer_et_correler
        tracer_et_correler(
            lien.company, point='questionnaire', lead=lien.lead,
            appareil_id=appareil_de_requete(request),
            contexte=f'Questionnaire — section {section}'[:200],
            token=getattr(lien, 'token', ''),
            request=request,
        )
    except Exception:  # noqa: BLE001 — best-effort, jamais de fuite
        pass
