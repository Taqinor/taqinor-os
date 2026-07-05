"""XRH20 — endpoints publics tokenisés de la promesse d'embauche.

Le candidat consulte et signe SA promesse via un lien tokenisé (pattern
liens publics WhatsApp FG79 / ``ventes.public_views``) : jeton long,
imprévisible, expirant (30 j). AUCUNE session, AUCUN login requis. Le PDF
n'est JAMAIS indexé (X-Robots-Tag: noindex) et throttlé contre le brute-force.
"""
from django.conf import settings
from django.http import Http404, HttpResponse
from rest_framework import status
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle

from . import services
from .models import PromesseEmbauche
from .pdf import render_promesse_embauche_pdf


class PromesseLinkRateThrottle(SimpleRateThrottle):
    """Throttle des liens publics de promesse — protège contre le brute-force
    du jeton (même limite que les liens publics ventes)."""
    scope = 'rh_promesse_publique'

    def get_cache_key(self, request, view):
        token = view.kwargs.get('token', '') if hasattr(view, 'kwargs') \
            else request.resolver_match.kwargs.get('token', '')
        ident = f'{self.get_ident(request)}:{token}'
        return self.cache_format % {'scope': self.scope, 'ident': ident}

    def get_rate(self):
        return '30/min'


def _not_found():
    resp = Response(status=status.HTTP_404_NOT_FOUND)
    resp['X-Robots-Tag'] = 'noindex'
    return resp


def _noindex(resp):
    resp['X-Robots-Tag'] = 'noindex'
    return resp


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([PromesseLinkRateThrottle])
def public_promesse_detail(request, token):
    """Détail (JSON) de la promesse — pour l'écran de consultation candidat."""
    promesse = (
        PromesseEmbauche.objects.select_related('candidature', 'company')
        .filter(token=token).first())
    if promesse is None or not promesse.is_valid:
        return _not_found()
    return _noindex(Response({
        'candidat_nom': promesse.candidature.nom,
        'poste_propose': promesse.poste_propose,
        'type_contrat': promesse.type_contrat,
        'date_debut_proposee': promesse.date_debut_proposee,
        'salaire_propose': promesse.salaire_propose,
        'statut': promesse.statut,
        'signataire_nom': promesse.signataire_nom,
        'date_signature': promesse.date_signature,
        'expires_at': promesse.expires_at,
    }))


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([PromesseLinkRateThrottle])
def public_promesse_pdf(request, token):
    """PDF de la promesse via son jeton (jamais indexé)."""
    promesse = (
        PromesseEmbauche.objects.select_related('candidature', 'company')
        .filter(token=token).first())
    if promesse is None or not promesse.is_valid:
        return _not_found()
    try:
        pdf_bytes = render_promesse_embauche_pdf(promesse)
    except Exception:  # noqa: BLE001 — jamais de fuite de stack au public.
        return _noindex(Response(
            {'detail': 'Document indisponible pour le moment.'},
            status=status.HTTP_404_NOT_FOUND))
    resp = HttpResponse(pdf_bytes, content_type='application/pdf')
    resp['Content-Disposition'] = 'inline; filename="promesse_embauche.pdf"'
    return _noindex(resp)


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        ip = forwarded.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '') or ''
    return ip[:45]


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PromesseLinkRateThrottle])
def public_promesse_signer(request, token):
    """Signature e-sign (loi 53-05, nom tapé) de la promesse via son jeton."""
    promesse = (
        PromesseEmbauche.objects.select_related('candidature', 'company')
        .filter(token=token).first())
    if promesse is None:
        return _not_found()
    nom = (request.data.get('signataire_nom') or '').strip()
    try:
        services.signer_promesse_embauche(
            promesse, signataire_nom=nom, ip_adresse=_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''))
    except services.PromesseSignatureError as exc:
        return _noindex(Response(
            {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST))
    return _noindex(Response({
        'statut': promesse.statut,
        'signataire_nom': promesse.signataire_nom,
        'date_signature': promesse.date_signature,
    }))


# ── XRH33 — page carrières publique (flag-gated OFF, décision fondateur) ───
#
# Même pattern que le formulaire de contact PARKÉ (apps.contact.views) :
# tant que ``settings.CAREERS_ENABLED`` est faux, les DEUX endpoints publics
# répondent 404 (traités comme s'ils n'existaient pas) — aucune fuite
# d'information, aucune écriture possible. La page apps/web qui consomme ces
# endpoints est une tâche WEB_PLAN séparée (hors périmètre ici).


class CareersApplyThrottle(AnonRateThrottle):
    """Throttle de la candidature publique — protège contre le spam/abus
    (même ordre de grandeur que le formulaire de contact PARKÉ).

    DRF applique le throttle AVANT le corps de la vue (``initial()`` avant
    le handler) : si on ne court-circuitait pas ici, un flag OFF pourrait
    quand même renvoyer 429 (fuite d'info sur l'existence de l'endpoint, et
    incohérent avec le contrat « 404 peu importe l'état ») dès que le
    quota est déjà consommé. Laisse passer sans compter de requête tant que
    la page carrières est désactivée — la vue renverra 404 elle-même.
    """
    scope = 'rh_careers_apply'

    def get_rate(self):
        return '5/hour'

    def allow_request(self, request, view):
        if not getattr(settings, 'CAREERS_ENABLED', False):
            return True
        return super().allow_request(request, view)


def _careers_or_404():
    """Lève 404 si la page carrières est désactivée (flag OFF, défaut)."""
    if not getattr(settings, 'CAREERS_ENABLED', False):
        raise Http404('Careers page is disabled.')


@api_view(['GET'])
@permission_classes([AllowAny])
def careers_list(request, company_slug):
    """XRH33 — liste PUBLIQUE des ouvertures de poste PUBLIÉES d'une société
    (résolue par ``slug``), intitulé/description/ville UNIQUEMENT (aucune
    donnée interne — pas de département, pas de statut RH, pas de compteur).

    404 si ``CAREERS_ENABLED`` est faux (comportement PARKÉ) OU si la société
    n'existe pas (jamais de fuite d'existence entre les deux cas).
    """
    _careers_or_404()
    from authentication.models import Company

    from .models import OuverturePoste

    company = Company.objects.filter(slug=company_slug).first()
    if company is None:
        return _not_found()

    ouvertures = OuverturePoste.objects.filter(
        company=company, publiee=True,
        statut=OuverturePoste.Statut.OUVERT,
    ).order_by('-date_creation')
    return _noindex(Response([
        {
            'id': o.pk,
            'intitule': o.intitule,
            'description': o.description,
            'ville': o.ville,
        }
        for o in ouvertures
    ]))


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([CareersApplyThrottle])
def careers_apply(request, company_slug, ouverture_id):
    """XRH33 — candidature PUBLIQUE (nom/email/téléphone/CV) sur une
    ouverture PUBLIÉE. Honeypot anti-spam : le champ caché ``site_web``
    (nom trompeur, un bot le remplit, un humain le laisse vide) — rempli =
    404 silencieux (aucun indice donné à un bot que la détection a eu lieu).

    ``company`` résolue par ``slug`` (jamais acceptée du corps) ; la
    candidature créée porte ``source='site_web'``, étape ``recu`` (comme
    toute candidature entrante).
    """
    _careers_or_404()
    from authentication.models import Company

    from .models import Candidature, OuverturePoste

    company = Company.objects.filter(slug=company_slug).first()
    if company is None:
        return _not_found()

    ouverture = OuverturePoste.objects.filter(
        company=company, pk=ouverture_id, publiee=True,
        statut=OuverturePoste.Statut.OUVERT,
    ).first()
    if ouverture is None:
        return _not_found()

    # Honeypot : un champ caché que seul un bot remplit.
    if (request.data.get('site_web') or '').strip():
        return _not_found()

    nom = (request.data.get('nom') or '').strip()[:160]
    email = (request.data.get('email') or '').strip()[:254]
    telephone = (request.data.get('telephone') or '').strip()[:30]
    if not nom or not email:
        return _noindex(Response(
            {'detail': 'Nom et email sont obligatoires.'},
            status=status.HTTP_400_BAD_REQUEST))

    candidature = Candidature.objects.create(
        company=company,
        ouverture=ouverture,
        nom=nom,
        email=email,
        telephone=telephone,
        source='site_web',
        cv_fichier=request.FILES.get('cv_fichier'),
        etape=Candidature.Etape.RECU,
    )
    return _noindex(Response(
        {'id': candidature.pk, 'detail': 'Candidature reçue.'},
        status=status.HTTP_201_CREATED))
