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
import hmac
import json
import logging
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

from django.conf import settings
from django.db.models import Count, Max, Min, Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import (
    api_view, authentication_classes, parser_classes, permission_classes,
    throttle_classes,
)
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from core.champs_stricts import (
    ChaineStricte, ChampsStrictsEntiersMixin, EntierStrict,
)
from core.parseurs import PARSEURS_JSON
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema

from .models import ProblemeClient
from .schema_fields import champ_choix

logger = logging.getLogger(__name__)


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


#: La clé qui fait d'une ligne « un même problème » (résumé ET tendance J-7).
CLE_PROBLEME = ('genre', 'methode', 'route', 'statut_reponse', 'code', 'ecran')

#: BPQ1 — pourquoi ce problème a eu lieu, pour le tri quotidien.
CLASSE_DEPLOIEMENT = 'deploiement'
CLASSE_CONNECTIVITE = 'connectivite'
CLASSE_MAINTENANCE = 'maintenance'
CLASSE_REEL = 'reel'

#: Une ligne 5xx/réseau jusqu'à 3 min après un démarrage de process : le
#: déploiement, pas un bug (le signalement n'atteint Django qu'une fois relancé).
DEPLOIEMENT_APRES_DEMARRAGE_S = 180
#: Au moins 4 routes sans réponse en moins de 2 s pour une même personne : c'est
#: sa connexion qui a lâché, pas ces 4 routes.
CONNECTIVITE_ROUTES_MIN = 4
CONNECTIVITE_FENETRE_S = 2

#: Liste Redis du marqueur de démarrage (BPQ2) : entrées JSON `{ts, sha}`.
CLE_DEMARRAGES = 'erp:demarrages'


def _client_redis():
    """Client Redis brut (mêmes clés nues que le marqueur de démarrage), ou
    `OSError` si le courtier n'est pas Redis (tests, environnement léger)."""
    import redis as redis_lib

    url = getattr(settings, 'CELERY_BROKER_URL', '') or ''
    if not url.startswith('redis'):
        raise OSError('courtier non Redis')
    return redis_lib.Redis.from_url(
        url, socket_timeout=0.5, decode_responses=True)


def _instants_demarrage():
    """Instants (aware) des derniers démarrages. Liste vide si Redis est absent
    ou si le marqueur n'est pas encore posé : la classe se rabat alors sur le
    reste, jamais une erreur dans le résumé."""
    try:
        bruts = _client_redis().lrange(CLE_DEMARRAGES, 0, -1)
        return [
            datetime.fromtimestamp(float(json.loads(brut)['ts']), dt_timezone.utc)
            for brut in bruts]
    except Exception:  # noqa: BLE001 — best-effort, le résumé doit sortir (D-ENF22-BLE001)
        logger.debug('démarrages illisibles : classe deploiement muette', exc_info=True)
        return []


def _fenetres_maintenance(depuis, maintenant):
    """Fenêtres NTOBS9 non annulées qui recoupent la période."""
    from core.maintenance_windows import MaintenanceWindow

    return list(
        MaintenanceWindow.objects
        .filter(debute_le__lt=maintenant, termine_le__gt=depuis)
        .exclude(statut=MaintenanceWindow.Statut.ANNULE)
        .values('company_id', 'debute_le', 'termine_le'))


def _ids_coupures(lignes):
    """Ids des lignes sans réponse d'une coupure de connexion : ≥ 4 routes en
    moins de 2 s pour une même personne. `lignes` triées par date."""
    par_personne = defaultdict(list)
    for ligne in lignes:
        if (ligne['genre'] == ProblemeClient.Genre.RESEAU
                and ligne['statut_reponse'] is None and ligne['utilisateur_id']):
            par_personne[ligne['utilisateur_id']].append(ligne)
    coupures = set()
    for suite in par_personne.values():
        debut = 0
        for fin, ligne in enumerate(suite):
            while ((ligne['created_at'] - suite[debut]['created_at']).total_seconds()
                   >= CONNECTIVITE_FENETRE_S):
                debut += 1
            tranche = suite[debut:fin + 1]
            if len({t['route'] for t in tranche}) >= CONNECTIVITE_ROUTES_MIN:
                coupures.update(t['id'] for t in tranche)
    return coupures


def _classe_ligne(ligne, coupures, demarrages, fenetres):
    statut = ligne['statut_reponse']
    quand = ligne['created_at']
    if statut == 503 and any(
            f['debute_le'] <= quand <= f['termine_le']
            and f['company_id'] in (None, ligne['company_id'])
            for f in fenetres):
        return CLASSE_MAINTENANCE
    serveur_ou_reseau = (
        ligne['genre'] == ProblemeClient.Genre.RESEAU
        or (statut is not None and statut >= 500))
    if serveur_ou_reseau and any(
            0 <= (quand - d).total_seconds() <= DEPLOIEMENT_APRES_DEMARRAGE_S
            for d in demarrages):
        return CLASSE_DEPLOIEMENT
    if ligne['id'] in coupures:
        return CLASSE_CONNECTIVITE
    return CLASSE_REEL


def _classes_par_probleme(qs, depuis, maintenant):
    """{clé du problème: Counter(classe → occurrences)}. Seules les lignes
    5xx/réseau ont une autre classe que `reel`, les autres ne sont pas relues."""
    lignes = list(
        qs.filter(Q(genre=ProblemeClient.Genre.RESEAU) | Q(statut_reponse__gte=500))
          .order_by('created_at', 'id')
          .values('id', 'company_id', 'utilisateur_id', 'created_at', *CLE_PROBLEME))
    if not lignes:
        return {}
    coupures = _ids_coupures(lignes)
    demarrages = _instants_demarrage()
    fenetres = _fenetres_maintenance(depuis, maintenant)
    classes = defaultdict(Counter)
    for ligne in lignes:
        cle = tuple(ligne[champ] for champ in CLE_PROBLEME)
        classes[cle][_classe_ligne(ligne, coupures, demarrages, fenetres)] += 1
    return classes


def _classe_du_probleme(occurrences, compte):
    """Une seule occurrence inexpliquée suffit : ce problème reste à regarder."""
    if sum(compte.values()) < occurrences or compte[CLASSE_REEL]:
        return CLASSE_REEL
    return compte.most_common(1)[0][0]


def resume_problemes(jours=7, company=None, maintenant=None):
    """LECTURE SEULE — regroupement « quels problèmes les utilisateurs ont-ils
    rencontrés ces N derniers jours ? », trié du plus fréquent au moins
    fréquent.

    Une entrée par (genre, méthode, route, statut, code, écran) avec le nombre
    d'occurrences, le nombre d'utilisateurs DISTINCTS touchés (un problème vu
    par 4 personnes n'est pas le même incident qu'un problème vu 40 fois par
    une seule), le premier et le dernier cas en heure locale, sa `classe`
    (BPQ1 : `deploiement`/`connectivite`/`maintenance`/`reel`) et sa `tendance`
    (la même signature la semaine précédente). Le `code` fait partie de la clé :
    deux erreurs JavaScript différentes sur le même écran ne sont pas le même
    problème. L'`écran` aussi (ERR-JPB-RESUME-SANS-ECRAN-ET-UTC) : pour un genre
    `script` (qui n'a pas de route), c'est le seul « où ? ». `company=None`
    balaie TOUTES les sociétés (usage administrateur serveur) ; sinon le résumé
    est borné à cette société — jamais un mélange implicite.
    """
    maintenant = maintenant or timezone.now()
    depuis = maintenant - timedelta(days=max(int(jours), 0))
    base = ProblemeClient.objects.all()
    if company is not None:
        base = base.filter(company=company)
    qs = base.filter(created_at__gte=depuis, created_at__lte=maintenant)
    lignes = list(
        qs.values(*CLE_PROBLEME)
          .annotate(occurrences=Count('id'),
                    utilisateurs=Count('utilisateur', distinct=True),
                    premier=Min('created_at'),
                    dernier=Max('created_at'),
                    exemple_request_id=Max('request_id'))
          .order_by('-occurrences', 'route', 'ecran'))
    classes = _classes_par_probleme(qs, depuis, maintenant)
    une_semaine = timedelta(days=7)
    semaine_precedente = {
        tuple(ligne[champ] for champ in CLE_PROBLEME): ligne['occurrences']
        for ligne in base
        .filter(created_at__gte=depuis - une_semaine,
                created_at__lt=maintenant - une_semaine)
        .values(*CLE_PROBLEME)
        .annotate(occurrences=Count('id'))
        .order_by()
    }
    for ligne in lignes:
        cle = tuple(ligne[champ] for champ in CLE_PROBLEME)
        compte = classes.get(cle, Counter())
        ligne['premier'] = timezone.localtime(ligne['premier'])
        ligne['dernier'] = timezone.localtime(ligne['dernier'])
        ligne['classe'] = _classe_du_probleme(ligne['occurrences'], compte)
        anciennes = semaine_precedente.get(cle, 0)
        ligne['tendance'] = {
            'semaine_precedente': anciennes > 0, 'occurrences': anciennes}
    return lignes


#: BPQ3 — bornes d'affichage : le résumé reste lisible même un mauvais jour.
LIMITE_ECHECS = 100
LONGUEUR_ERREUR = 200
#: Clés du payload d'un événement qui peuvent nommer un destinataire.
_CLES_DESTINATAIRE = ('destinataire', 'recipient', 'to', 'email', 'telephone')
#: Services de `core.health` que le tri quotidien regarde (beat, base, Redis).
_SERVICES_SANTE = ('database', 'cache', 'beat')


def _masquer_destinataire(valeur):
    """`n***@exemple.ma`, `06***78` : assez pour reconnaître, jamais une adresse."""
    texte = str(valeur or '').strip()
    if '@' in texte:
        local, domaine = texte.split('@', 1)
        return f'{local[:1]}***@{domaine}'
    return f'{texte[:2]}***{texte[-2:]}' if len(texte) >= 6 else ('***' if texte else '')


def _outbox_en_echec(depuis, company):
    """Événements `failed`/`dead` modifiés dans la fenêtre. `OutboxEvent` ne garde
    pas de colonne d'erreur : canal, destinataire et erreur viennent du payload,
    vides quand l'événement n'en porte pas."""
    from core.models import OutboxEvent

    qs = OutboxEvent.objects.filter(
        statut__in=[OutboxEvent.STATUT_FAILED, OutboxEvent.STATUT_DEAD],
        updated_at__gte=depuis)
    if company is not None:
        qs = qs.filter(company=company)
    resultat = []
    for evenement in qs.order_by('-updated_at')[:LIMITE_ECHECS]:
        charge = evenement.payload if isinstance(evenement.payload, dict) else {}
        destinataire = next(
            (charge[cle] for cle in _CLES_DESTINATAIRE if charge.get(cle)), '')
        resultat.append({
            'evenement': evenement.event_name,
            'statut': evenement.statut,
            'tentatives': evenement.tentatives,
            'canal': str(charge.get('canal') or ''),
            'destinataire': _masquer_destinataire(destinataire),
            'derniere_erreur': str(
                charge.get('erreur') or charge.get('error') or '')[:LONGUEUR_ERREUR],
            'modifie_le': timezone.localtime(evenement.updated_at).isoformat(),
        })
    return resultat


def _sauvegardes_en_echec(depuis, company):
    from core.models import BackupRun

    qs = BackupRun.objects.filter(
        statut=BackupRun.STATUT_ECHEC, updated_at__gte=depuis)
    if company is not None:
        qs = qs.filter(company=company)
    return [
        {
            'type': run.kind,
            'mode': run.mode,
            'message': str((run.detail or {}).get('message') or '')[:LONGUEUR_ERREUR],
            'modifie_le': timezone.localtime(run.updated_at).isoformat(),
        }
        for run in qs.order_by('-updated_at')[:LIMITE_ECHECS]
    ]


def _etat_sante():
    """État des services que le tri surveille, ou `{}` si la sonde elle-même
    tombe (le résumé des problèmes doit sortir quand même)."""
    from core import health

    try:
        return {
            service['name']: {
                'statut': service['status'],
                'detail': str(service.get('detail') or '')[:LONGUEUR_ERREUR],
            }
            for service in health.check_services()
            if service['name'] in _SERVICES_SANTE
        }
    except Exception:  # noqa: BLE001 — best-effort, le résumé doit sortir (D-ENF22-BLE001)
        logger.warning('sonde santé illisible pour le résumé', exc_info=True)
        return {}


def resume_json(jours=7, company=None, maintenant=None):
    """BPQ1 — le résumé en objets sérialisables, pour la boucle quotidienne.
    BPQ3 — avec les problèmes « que personne ne vit encore » : événements en
    échec, sauvegardes en échec, état des services."""
    maintenant = maintenant or timezone.now()
    depuis = maintenant - timedelta(days=max(int(jours), 0))
    return {
        'jours': int(jours),
        'genere_le': timezone.localtime(maintenant).isoformat(),
        'problemes': [
            {
                **{champ: ligne[champ] for champ in CLE_PROBLEME},
                'occurrences': ligne['occurrences'],
                'personnes': ligne['utilisateurs'],
                'premier': ligne['premier'].isoformat(),
                'dernier': ligne['dernier'].isoformat(),
                'classe': ligne['classe'],
                'tendance': ligne['tendance'],
                'exemple_request_id': ligne['exemple_request_id'],
            }
            for ligne in resume_problemes(jours, company, maintenant)
        ],
        'outbox_en_echec': _outbox_en_echec(depuis, company),
        'sauvegardes_en_echec': _sauvegardes_en_echec(depuis, company),
        'sante': _etat_sante(),
    }


#: BPQ6 lit ce battement de cœur : « le tri quotidien a-t-il tourné ? ».
CLE_DERNIER_TRI = 'erp:dernier_tri_problemes'
#: Une fenêtre de résumé, pas un export : au-delà, c'est la commande serveur.
JOURS_RESUME_MAX = 90


class JetonServiceResumeProblemes(BasePermission):
    """BPQ4 — UNE seule authentification : le jeton de service
    `PROBLEMES_RESUME_TOKEN` en `Authorization: Bearer`, comparé à temps constant.
    Ce résumé couvre TOUTES les sociétés : ni session, ni clé API société. Jeton
    non configuré = fermé."""

    def has_permission(self, request, view):
        attendu = settings.PROBLEMES_RESUME_TOKEN
        entete = request.META.get('HTTP_AUTHORIZATION', '')
        if not attendu or not entete.startswith('Bearer '):
            return False
        return hmac.compare_digest(
            entete[len('Bearer '):].strip().encode(), attendu.encode())


class ResumeProblemesParams(serializers.Serializer):
    jours = serializers.IntegerField(
        required=False, default=1, min_value=1, max_value=JOURS_RESUME_MAX)
    tri = serializers.BooleanField(required=False, default=False)


def _horodater_tri(maintenant):
    """Pose le battement de cœur ; `False` si Redis ne répond pas : la routine le
    voit dans sa réponse, et le résumé reste servi."""
    try:
        _client_redis().set(
            CLE_DERNIER_TRI, timezone.localtime(maintenant).isoformat())
        return True
    except Exception:  # noqa: BLE001 — best-effort, le résumé doit sortir (D-ENF22-BLE001)
        logger.warning('battement de cœur du tri non posé', exc_info=True)
        return False


@extend_schema(
    parameters=[ResumeProblemesParams],
    responses={200: OpenApiTypes.OBJECT})
@api_view(['GET'])
@authentication_classes([])
@permission_classes([JetonServiceResumeProblemes])
def resume_problemes_service(request):
    """GET — le résumé de BPQ1/BPQ3 pour la routine de tri (`tri=1` la marque
    comme passée). Contrat : `contract_samples/problemes_resume.json`."""
    params = ResumeProblemesParams(data=request.query_params)
    params.is_valid(raise_exception=True)
    maintenant = timezone.now()
    corps = resume_json(jours=params.validated_data['jours'], maintenant=maintenant)
    corps['tri_horodate'] = (
        _horodater_tri(maintenant) if params.validated_data['tri'] else False)
    return Response(corps)
