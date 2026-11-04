"""YJPB1 — Journal des problèmes vécus par les utilisateurs (côté navigateur).

Point d'entrée UNIQUE que `frontend/src/lib/journalProblemes.js` appelle quand
une requête n'obtient AUCUNE réponse (délai de 20 s dépassé, réseau coupé),
quand le serveur répond 5xx, ou quand une erreur JavaScript non interceptée
survient. Avant cette tâche, ces trois cas ne laissaient aucune trace : le
toast « La connexion a expiré… » et l'état « Indisponible pour le moment. »
restaient dans le navigateur de l'utilisateur, et Sentry (VX72/QAH8) est un
no-op tant qu'aucun DSN n'est configuré.

Volontairement MINIMAL et indépendant de Sentry : un POST best-effort, 201
sans corps, débit borné par utilisateur. `company`/`utilisateur` sont TOUJOURS
posés côté serveur depuis `request.user` — jamais lus du corps. L'agent
utilisateur BRUT n'est jamais stocké : seule sa FAMILLE est déduite ici.

Lecture : `python manage.py problemes_utilisateurs --jours 7`.
"""
import re

from rest_framework import serializers
from rest_framework.decorators import (
    api_view, parser_classes, permission_classes, throttle_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from core.champs_stricts import (
    ChaineStricte, ChampsStrictsEntiersMixin, EntierStrict,
)
from core.parseurs import PARSEURS_JSON
from drf_spectacular.utils import extend_schema

from .models import ProblemeClient
from .schema_fields import champ_choix


class JournalProblemesThrottle(UserRateThrottle):
    """Un écran qui boucle (re-render en erreur) peut émettre des dizaines de
    signalements par seconde : le débit est borné PAR UTILISATEUR, largement
    au-dessus d'un usage réel (le navigateur dédoublonne déjà de son côté).
    Scope déclaré dans `DEFAULT_THROTTLE_RATES` (settings) — source unique."""

    scope = 'problemes_client'


#: Familles d'agent utilisateur, dans l'ORDRE de test (un navigateur Chromium
#: annonce aussi « Safari », et Edge annonce aussi « Chrome » : le plus
#: spécifique d'abord). Jetons volontairement grossiers — on veut « quel
#: navigateur rencontre ce problème », jamais identifier un appareil.
_FAMILLES = (
    ('Edg', 'Edge'),
    ('SamsungBrowser', 'Samsung Internet'),
    ('OPR', 'Opera'),
    ('Opera', 'Opera'),
    ('FxiOS', 'Firefox'),
    ('Firefox', 'Firefox'),
    ('CriOS', 'Chrome'),
    ('Chrome', 'Chrome'),
    ('Chromium', 'Chrome'),
    ('Safari', 'Safari'),
)

#: Plateformes, même principe (iPad/iPhone avant Mac : un iPad annonce « Mac
#: OS X » dans certains modes).
_PLATEFORMES = (
    ('Android', 'Android'),
    ('iPhone', 'iOS'),
    ('iPad', 'iOS'),
    ('iPod', 'iOS'),
    ('Windows', 'Windows'),
    ('Macintosh', 'macOS'),
    ('Mac OS X', 'macOS'),
    ('Linux', 'Linux'),
)


def famille_navigateur(agent):
    """Famille d'agent utilisateur (« Chrome Android », « Safari iOS »…) à
    partir de l'agent BRUT, qui n'est jamais stocké. Chaîne vide si l'agent
    est absent ou inconnu ; borné à 40 caractères (taille du champ)."""
    agent = agent or ''
    if not agent:
        return ''
    navigateur = next(
        (nom for jeton, nom in _FAMILLES if jeton in agent), '')
    plateforme = next(
        (nom for jeton, nom in _PLATEFORMES if jeton in agent), '')
    return ' '.join(p for p in (navigateur, plateforme) if p)[:40]


#: Forme de l'identifiant de `core.middleware.RequestIdMiddleware` (uuid4 hex).
_REQUEST_ID = re.compile(r'[0-9a-fA-F]{32}')


class ProblemeClientSerializer(ChampsStrictsEntiersMixin,
                               serializers.ModelSerializer):
    # Les textes sont TRONQUÉS, jamais rejetés : un signalement
    # « fire-and-forget » ne doit jamais être perdu pour une longueur (c'est
    # précisément quand tout va mal qu'on veut la trace). Les champs ne
    # publient donc pas de `maxLength` — même contrat que le beacon Web Vitals.
    route = ChaineStricte(required=False, allow_blank=True)
    ecran = ChaineStricte(required=False, allow_blank=True)
    code = ChaineStricte(required=False, allow_blank=True)
    message = ChaineStricte(required=False, allow_blank=True)
    methode = ChaineStricte(required=False, allow_blank=True)
    # Entier STRICT et SANS borne publiée : le champ de modèle est un
    # `PositiveSmallIntegerField`, dont ModelSerializer tirerait
    # `max_value=32767` — un statut aberrant répondrait alors 400 et le
    # signalement serait PERDU. Ici il est simplement oublié par
    # `validate_statut_reponse` (le genre porte déjà le sens).
    statut_reponse = EntierStrict(required=False, allow_null=True)
    request_id = ChaineStricte(required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = ProblemeClient
        # company/utilisateur/navigateur : posés côté serveur dans la vue,
        # jamais lus du corps — absents des champs acceptés en écriture.
        fields = ['genre', 'methode', 'route', 'ecran', 'statut_reponse', 'code',
                  'message', 'request_id']

    def validate_methode(self, value):
        return (value or '')[:8].upper()

    def validate_route(self, value):
        return (value or '')[:255]

    def validate_ecran(self, value):
        return (value or '')[:255]

    def validate_code(self, value):
        return (value or '')[:64]

    def validate_message(self, value):
        return (value or '')[:255]

    def validate_statut_reponse(self, value):
        # Un statut hors plage HTTP n'est pas une raison de perdre la trace :
        # il est simplement oublié (le genre reste porteur du sens).
        return value if value is not None and 100 <= value <= 599 else None

    def validate_request_id(self, value):
        # Même logique : un identifiant illisible est oublié, la trace reste.
        return value if value and _REQUEST_ID.fullmatch(value) else None


class ProblemeClientRequeteSerializer(ProblemeClientSerializer):
    genre = champ_choix(ProblemeClient.Genre.values)


@extend_schema(
    request=ProblemeClientRequeteSerializer,
    responses={201: None})
@api_view(['POST'])
# Signalement JSON (statut = nombre) — un formulaire n'en porte que des chaînes.
@parser_classes(PARSEURS_JSON)
@permission_classes([IsAuthenticated])
@throttle_classes([JournalProblemesThrottle])
def signaler_probleme(request):
    """POST best-effort — une ligne par problème vécu. L'appelant n'attend
    jamais le corps de la réponse : un 201 minimal suffit."""
    co = request.user.company
    if co is None:
        # Jamais un 500 sur l'endpoint du journal : un utilisateur sans
        # société n'a pas de place où ranger la ligne (la FK est obligatoire,
        # multi-tenant). On le DIT, au lieu de planter — l'appelant ignore de
        # toute façon le corps de la réponse (miroir de `vitals_p75`).
        return Response({'detail': 'Accès refusé.'}, status=403)
    serializer = ProblemeClientSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save(
        company=co,
        utilisateur=request.user,
        navigateur=famille_navigateur(request.META.get('HTTP_USER_AGENT')))
    return Response(status=201)


def resume_problemes(jours=7, company=None, maintenant=None):
    """LECTURE SEULE — regroupement « quels problèmes les utilisateurs ont-ils
    rencontrés ces N derniers jours ? », trié du plus fréquent au moins
    fréquent.

    Une entrée par (genre, méthode, route, statut, code, écran) avec le nombre
    d'occurrences, le nombre d'utilisateurs DISTINCTS touchés (un problème vu
    par 4 personnes n'est pas le même incident qu'un problème vu 40 fois par
    une seule) et la date du dernier cas, en heure locale. Le `code` fait partie
    de la clé : deux erreurs JavaScript différentes sur le même écran ne sont
    pas le même problème. L'`écran` aussi (ERR-JPB-RESUME-SANS-ECRAN-ET-UTC) :
    pour un genre `script` (qui n'a pas de route), c'est le seul « où ? ».
    `company=None` balaie TOUTES les
    sociétés (usage administrateur serveur) ; sinon le résumé est borné à
    cette société — jamais un mélange implicite.
    """
    from django.db.models import Count, Max
    from django.utils import timezone

    maintenant = maintenant or timezone.now()
    depuis = maintenant - timezone.timedelta(days=max(int(jours), 0))
    qs = ProblemeClient.objects.filter(created_at__gte=depuis)
    if company is not None:
        qs = qs.filter(company=company)
    lignes = list(
        qs.values('genre', 'methode', 'route', 'statut_reponse',
                  'code', 'ecran')
          .annotate(occurrences=Count('id'),
                    utilisateurs=Count('utilisateur', distinct=True),
                    dernier=Max('created_at'),
                    exemple_request_id=Max('request_id'))
          .order_by('-occurrences', 'route', 'ecran'))
    for ligne in lignes:
        ligne['dernier'] = timezone.localtime(ligne['dernier'])
    return lignes
