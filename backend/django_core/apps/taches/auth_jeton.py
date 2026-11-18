"""Jetons d'accès de l'app `taches` (reference/api.md §0 « J:x » ; donnees.md §2.14, §5, inv. 20).

Un jeton par USAGE (`capture`, `flux`, `tuile`), stocké en EMPREINTE seulement (SHA-256 hex) ; le clair
n'existe qu'une fois, dans la réponse de `POST jetons/` (`emettre_jeton`). Un jeton se révoque
(`revoquer_jeton`) ; en émettre un nouveau révoque l'ancien du même usage.

`JetonAccesAuthentication` (une sous-classe par usage : `JetonCapture`, `JetonFlux`, `JetonTuile`) :
- ne reconnaît QUE son usage : un jeton `flux` sur `capture/`, un jeton faux, révoqué, d'un compte
  désactivé, portail, sans `taches_voir`, d'une société suspendue ou dont le module est éteint
  répondent EXACTEMENT pareil (401 neutre ; 404 neutre pour le flux), sans jamais dire pourquoi ;
- `user_can_operate(user, jeton.company_id)` puis le rôle de CETTE société, puis
  `user.company = jeton.company` EN MÉMOIRE (jamais un `save()`, MAJ-4) : c'est la société du jeton
  qui borne toute la requête ;
- `dernier_usage_le` écrit au plus une fois par minute.
Aucun clair ni empreinte n'est journalisé ni rendu dans une erreur. Le flux porte son jeton DANS
l'adresse : l'app DÉCLARE ses `CHEMINS_SENSIBLES` à `core.chemins_sensibles` (`declarer_chemins_sensibles`,
appelée par `TachesConfig.ready()`), et c'est cette fonction de `core` qui masque CHAQUE sortie (contexte de
requête lu par les journaux et Sentry, tout enregistrement de journal, évènements et transactions Sentry) ;
`FluxVue` masque aussi `request.path` et marque ses réponses d'erreur comme déjà journalisées. Les jetons
`capture` et `tuile` voyagent dans `Authorization` : aucun journal ne lit cet en-tête, Sentry l'écarte
(`send_default_pii=False`) et leur forme est masquée partout où elle paraîtrait. L'empreinte relue est
comparée à temps constant (`hmac.compare_digest`).
"""
import datetime
import hashlib
import hmac
import logging
import re
import secrets

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework import authentication, exceptions

from apps.taches.choix import UsageJeton
from apps.taches.models.presence import JetonAcces

logger = logging.getLogger(__name__)

DROIT = 'taches_voir'
MODULE = 'taches'
MOT_CLE = 'Bearer'
DETAIL_REFUS = 'Authentification requise.'
DETAIL_FLUX = 'Introuvable.'
PREFIXES = {UsageJeton.CAPTURE: 'tqc_', UsageJeton.FLUX: 'tqf_', UsageJeton.TUILE: 'tqt_'}
#: Forme d'un clair : préfixe d'usage + au moins 20 caractères url-safe (un clair émis en a 43).
FORME_CLAIR = re.compile(r'^tq[cft]_[A-Za-z0-9_-]{20,100}$')
LONGUEUR_PREFIXE = 8
#: Ce que voit une sortie d'observabilité à la place d'un jeton.
MASQUE = '<masqué>'
#: Les secrets d'adresse déclarés à `core.chemins_sensibles`, dans l'ordre : le segment du flux qui porte
#: le jeton (quel qu'il soit, `.ics` gardé, `/` encodé compris), puis tout clair de jeton isolé (variable
#: locale d'une pile, `Referer`…), préfixe d'usage gardé pour diagnostiquer.
CHEMINS_SENSIBLES = (
    ('taches.flux', r'((?:/|%2[Ff])taches(?:/|%2[Ff])flux(?:/|%2[Ff]))[^/?#&%\s"\'<>.]+', r'\1' + MASQUE),
    ('taches.jeton', r'(?<![A-Za-z0-9_-])(tq[cft]_)[A-Za-z0-9_-]{20,}', r'\1' + MASQUE),
)
OCTETS_ALEATOIRES = 32
INTERVALLE_DERNIER_USAGE = datetime.timedelta(minutes=1)


def empreinte(clair):
    """SHA-256 hexadécimal d'un clair (256 bits d'aléa : un hachage simple suffit)."""
    return hashlib.sha256(clair.encode('utf-8')).hexdigest()


def declarer_chemins_sensibles():
    """Déclare les secrets d'adresse de l'app à `core.chemins_sensibles` (idempotent, `ready()`)."""
    from core import chemins_sensibles
    for nom, motif, remplacement in CHEMINS_SENSIBLES:
        chemins_sensibles.enregistrer(nom, motif, remplacement)


# --- Émission et révocation ----------------------------------------------------------------------

def _emettre(user, usage, libelle, maintenant):
    """Révoque l'actif du même usage puis crée le nouveau ; rend `(jeton, clair)`."""
    JetonAcces.objects.filter(company_id=user.company_id, proprietaire=user, usage=usage,
                              revoque_le__isnull=True).update(revoque_le=maintenant)
    clair = PREFIXES[UsageJeton(usage)] + secrets.token_urlsafe(OCTETS_ALEATOIRES)
    jeton = JetonAcces.objects.create(
        company_id=user.company_id, proprietaire=user, usage=usage, prefixe=clair[:LONGUEUR_PREFIXE],
        jeton_hash=empreinte(clair), libelle=libelle)
    return jeton, clair


def emettre_jeton(user, usage, libelle=''):
    """Nouveau jeton de `usage` pour `user` dans SA société (l'ancien du même usage est révoqué) ;
    rend `(JetonAcces, clair)`. Deux émissions simultanées : la seconde voit la contrainte
    `taches_jeton_actif_uniq` et recommence une fois (elle révoque alors celui de la première)."""
    try:
        with transaction.atomic():
            return _emettre(user, usage, libelle, timezone.now())
    except IntegrityError:
        logger.info('taches : émission concurrente d\'un jeton %s, nouvel essai', usage)
    with transaction.atomic():
        return _emettre(user, usage, libelle, timezone.now())


def revoquer_jeton(jeton):
    """Révoque `jeton` (déjà révoqué : rien ne change)."""
    if jeton.revoque_le is None:
        jeton.revoque_le = timezone.now()
        JetonAcces.objects.filter(pk=jeton.pk, revoque_le__isnull=True).update(revoque_le=jeton.revoque_le)
    return jeton


# --- Authentification ----------------------------------------------------------------------------

def _compte_interne_actif(user):
    interne = getattr(type(user), 'PORTEE_INTERNE', 'interne')
    return bool(user.is_active) and getattr(user, 'portee', interne) == interne


def _poser_societe(user, jeton):
    """Pose la société du jeton (et son rôle) sur l'instance ; faux si le compte n'y opère pas."""
    from authentication.active_company import role_dans_societe, user_can_operate
    if jeton.company_id != user.company_id:
        if not user_can_operate(user, jeton.company_id):
            return False
        autorise, role = role_dans_societe(user, jeton.company_id)
        if not autorise:
            return False
        user._company_id_attache = user.company_id
        user.role = role
    user.company = jeton.company
    return True


def _admis(user, jeton):
    from core.feature_flags import module_actif
    if not _compte_interne_actif(user) or not getattr(jeton.company, 'est_operationnel', True):
        return False
    if not _poser_societe(user, jeton):
        return False
    return bool(user.has_erp_permission(DROIT)) and module_actif(jeton.company, MODULE)


def _noter_usage(jeton):
    """`dernier_usage_le`, au plus une écriture par minute (relue en mémoire d'abord)."""
    maintenant = timezone.now()
    seuil = maintenant - INTERVALLE_DERNIER_USAGE
    if jeton.dernier_usage_le is not None and jeton.dernier_usage_le > seuil:
        return
    (JetonAcces.objects.filter(pk=jeton.pk)
     .filter(Q(dernier_usage_le__isnull=True) | Q(dernier_usage_le__lte=seuil))
     .update(dernier_usage_le=maintenant))
    jeton.dernier_usage_le = maintenant


class JetonAccesAuthentication(authentication.BaseAuthentication):
    """`Authorization: Bearer <clair>` d'un jeton ACTIF de `usage` (posé par la sous-classe).

    Ne rend jamais `None` : sans jeton, un jeton illisible ou refusé, la même exception neutre
    (`_refuser`). Rend `(compte, JetonAcces)` ; `request.auth` est le jeton."""

    usage = None

    def clair(self, request):
        entete = authentication.get_authorization_header(request).decode('latin-1')
        morceaux = entete.split()
        if len(morceaux) != 2 or morceaux[0].lower() != MOT_CLE.lower():
            return ''
        return morceaux[1]

    def _refuser(self):
        raise exceptions.AuthenticationFailed(DETAIL_REFUS)

    def _jeton(self, clair):
        if not FORME_CLAIR.match(clair or '') or not clair.startswith(PREFIXES[UsageJeton(self.usage)]):
            return None
        attendue = empreinte(clair)
        jeton = (JetonAcces.objects
                 .select_related('company', 'proprietaire', 'proprietaire__role')
                 .filter(jeton_hash=attendue, usage=self.usage, revoque_le__isnull=True)
                 .first())
        # Comparaison à temps constant de l'empreinte relue (la recherche indexée ne porte que sur
        # l'empreinte, jamais sur le clair).
        if jeton is None or not hmac.compare_digest(jeton.jeton_hash, attendue):
            return None
        if not _admis(jeton.proprietaire, jeton):
            return None
        return jeton

    def authenticate(self, request):
        jeton = self._jeton(self.clair(request))
        if jeton is None:
            logger.info('taches : jeton %s refusé', self.usage)
            self._refuser()
        _noter_usage(jeton)
        return jeton.proprietaire, jeton

    def authenticate_header(self, request):
        return f'{MOT_CLE} realm="taches"'


class JetonCapture(JetonAccesAuthentication):
    usage = UsageJeton.CAPTURE


class JetonTuile(JetonAccesAuthentication):
    usage = UsageJeton.TUILE


class JetonFlux(JetonAccesAuthentication):
    """Le jeton du flux est DANS l'adresse (`flux/<jeton>.ics`) : l'abonnement du Calendrier
    n'envoie aucun en-tête. Refus : 404 neutre."""

    usage = UsageJeton.FLUX

    def clair(self, request):
        return ((getattr(request, 'parser_context', None) or {}).get('kwargs') or {}).get('jeton') or ''

    def _refuser(self):
        raise exceptions.NotFound(DETAIL_FLUX)


class _JetonSchema(OpenApiAuthenticationExtension):
    """Base : un schéma de sécurité NOMMÉ par usage (un nom par classe d'authentification, sinon
    drf-spectacular signale des composants homonymes d'identités différentes)."""

    match_subclasses = False
    usage_libelle = ''

    def get_security_definition(self, auto_schema):
        return {'type': 'http', 'scheme': 'bearer',
                'description': "Jeton d'accès personnel de l'app Tâches (%s)." % self.usage_libelle}


class JetonCaptureSchema(_JetonSchema):
    target_class = 'apps.taches.auth_jeton.JetonCapture'
    name = 'jetonCapture'
    usage_libelle = 'capture'


class JetonTuileSchema(_JetonSchema):
    target_class = 'apps.taches.auth_jeton.JetonTuile'
    name = 'jetonTuile'
    usage_libelle = 'tuile'


class JetonFluxSchema(_JetonSchema):
    target_class = 'apps.taches.auth_jeton.JetonFlux'
    name = 'jetonFlux'
    usage_libelle = 'flux calendrier'
