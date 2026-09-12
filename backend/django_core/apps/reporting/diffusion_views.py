"""NTDATA39 — diffusion WhatsApp d'un LIEN tokenisé vers un rapport (GATED).

Pourquoi un lien et pas la pièce jointe : WhatsApp n'est pas un canal de
transport de fichiers d'entreprise, et un .xlsx qui circule dans des
téléphones ne se révoque pas. On envoie donc un LIEN SIGNÉ et EXPIRANT vers un
rendu du rapport — même modèle de confiance que le flux ICS tokenisé (FG6) et
que les liens de partage GED/proposal : jeton signé côté serveur, aucune
session, jeton invalide → 404 générique (jamais d'indice sur l'existence du
rapport).

GATED fondateur : sans le canal WhatsApp BSP réellement armé
(``WHATSAPP_BSP_ENABLED=1`` + les trois credentials Meta —
``notifications.services.whatsapp_bsp_actif``), ``diffuser_whatsapp`` est un
NO-OP TOTAL : aucun message, aucun appel réseau, aucune ligne de log de
message. Armé, un message contenant le lien part vers chaque numéro configuré.
"""
from django.core import signing
from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

_SALT = 'reporting.rapport_partage'

#: Durée de vie d'un lien de rapport (7 jours) — un lien qui traîne s'éteint.
DUREE_LIEN_SECONDES = 7 * 24 * 3600

#: Chemin public du rendu tokenisé (monté par ``reporting/urls.py``).
CHEMIN_PARTAGE = '/api/django/reporting/rapports-partages/{token}/'


def make_report_token(report):
    """Jeton signé, expirant, désignant UN rapport sauvegardé."""
    return signing.dumps(report.pk, salt=_SALT)


def resolve_report_token(token, max_age=DUREE_LIEN_SECONDES, ip=None):
    """Rapport désigné par le jeton, ou ``None``.

    ``None`` couvre : jeton absent, signature invalide, jeton expiré, rapport
    supprimé — et, depuis AUD803, rapport dont le PARTAGE A ÉTÉ RÉVOQUÉ.

    AUD803 — la révocabilité est la justification ÉCRITE du dispositif
    (« un .xlsx qui circule ne se révoque pas », en-tête de ce module), or le
    LIEN ne se révoquait pas davantage : cette fonction ne faisait qu'un
    ``filter(pk=…).first()``, sans aucun état révocable ; seule l'expiration à
    7 jours bornait l'exposition (catalogue + stocks + funnel leads, servis en
    ``AllowAny``). Chaque résolution RÉUSSIE écrit désormais une ligne
    ``AccesRapportPartage`` (IP + horodatage) — sans elle, personne ne peut
    savoir qu'un lien fuité est consulté, ni décider de le révoquer.
    """
    if not token:
        return None
    try:
        report_id = signing.loads(token, salt=_SALT, max_age=max_age)
    except signing.BadSignature:
        return None
    from .models import SavedReport
    report = SavedReport.objects.filter(pk=report_id).first()
    if report is None or not report.partage_actif:
        return None
    _tracer_acces(report, ip)
    return report


def _tracer_acces(report, ip):
    """Écrit la trace d'accès (best-effort : jamais bloquer un lien légitime)."""
    from .models import AccesRapportPartage
    try:
        AccesRapportPartage.objects.create(
            company=report.company, saved_report=report, ip=ip or None)
    except Exception:  # noqa: BLE001 — une trace en échec ne casse pas l'accès
        import logging
        logging.getLogger(__name__).warning(
            'AUD803 : trace d\'accès non écrite (rapport %s)', report.pk,
            exc_info=True)


def _ip_appelant(request):
    """IP du demandeur — ``X-Forwarded-For`` d'abord (le service est derrière
    Caddy/nginx), sinon ``REMOTE_ADDR``. Jamais d'exception."""
    if request is None:
        return None
    transmise = (request.META.get('HTTP_X_FORWARDED_FOR') or '').split(',')[0]
    return (transmise.strip() or request.META.get('REMOTE_ADDR') or '') or None


def lien_rapport(report, base_url=''):
    """Lien profond tokenisé vers le rendu du rapport."""
    chemin = CHEMIN_PARTAGE.format(token=make_report_token(report))
    return f"{base_url.rstrip('/')}{chemin}" if base_url else chemin


def corps_message(report, lien):
    """Message WhatsApp : un lien, jamais de chiffre d'affaires en clair."""
    return (f'Bonjour, votre rapport « {report.name} » est disponible ici '
            f'(lien valable 7 jours) : {lien}')


def diffuser_whatsapp(report, base_url=''):
    """Envoie le LIEN du rapport à ses numéros WhatsApp. GATED.

    Renvoie ``(envoyes, detail)`` : ``envoyes`` = nombre de messages réellement
    partis (0 si le canal n'est pas armé ou sans numéro), ``detail`` = motif
    lisible pour le journal de diffusion (NTDATA40). Ne lève jamais.
    """
    numeros = report.whatsapp_list()
    if not numeros:
        return 0, 'Aucun numéro WhatsApp configuré.'
    from apps.notifications.services import (
        send_whatsapp_campaign_message,
        whatsapp_bsp_actif,
    )
    if not whatsapp_bsp_actif():
        return 0, ('Canal WhatsApp non configuré (WHATSAPP_BSP_ENABLED + '
                   'credentials) — aucun envoi.')
    lien = lien_rapport(report, base_url=base_url)
    corps = corps_message(report, lien)
    envoyes = 0
    for numero in numeros:
        try:
            resultat = send_whatsapp_campaign_message(
                report.company, recipient=numero, body=corps)
        except Exception:  # noqa: BLE001 - un numéro KO n'arrête pas les autres
            continue
        if (resultat or {}).get('provider') == 'bsp':
            envoyes += 1
    if not envoyes:
        return 0, 'Aucun message accepté par le fournisseur WhatsApp.'
    return envoyes, f'{envoyes} message(s) WhatsApp envoyé(s) avec le lien.'


class RapportPartageThrottle(SimpleRateThrottle):
    """Débit par IP + jeton — décourage le balayage de jetons sans jamais
    gêner un destinataire légitime (même patron que les autres liens publics)."""

    scope = 'rapport_partage'
    rate = '20/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        token = (view.kwargs or {}).get('token', '') if view else ''
        return self.cache_format % {
            'scope': self.scope,
            'ident': f'{self.get_ident(request)}:{token}',
        }


@extend_schema(responses={200: OpenApiTypes.BINARY})
@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([RapportPartageThrottle])
def rapport_partage_public(request, token):
    """Rendu PUBLIC d'un rapport, résolu depuis le SEUL jeton signé.

    Aucune identité de confiance : le jeton porte le rapport et son expiration.
    Un jeton invalide/expiré — ou dont le partage a été RÉVOQUÉ (AUD803) —
    renvoie le MÊME 404 générique : jamais d'indice sur l'existence du rapport
    ni sur le motif du refus. Chaque résolution réussie laisse une trace
    (IP + horodatage)."""
    report = resolve_report_token(token, ip=_ip_appelant(request))
    if report is None:
        return Response({'detail': 'Lien invalide ou expiré.'},
                        status=status.HTTP_404_NOT_FOUND)
    # NTDATA37 — la cible peut être un tableau de bord (PDF) ou une requête
    # sauvegardée (XLSX) : c'est le RENDU qui dit son nom de fichier et son
    # type MIME. Servir un PDF sous un nom .xlsx ne s'ouvrirait nulle part.
    from .scheduled_reports import MIME_XLSX, rendre_rapport
    contenu, titre, nom_fichier, type_mime = rendre_rapport(report)
    if contenu is None:
        return Response({'detail': 'Rapport indisponible.'},
                        status=status.HTTP_404_NOT_FOUND)
    reponse = HttpResponse(contenu, content_type=type_mime or MIME_XLSX)
    reponse['Content-Disposition'] = (
        'attachment; filename="%s"'
        % (nom_fichier or f'{report.target_kind}.xlsx'))
    reponse['X-Rapport'] = titre or report.target_kind
    return reponse
