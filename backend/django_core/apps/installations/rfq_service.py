"""XPUR20/21 — envoi de la RFQ aux fournisseurs consultés (email + WhatsApp)
et réponse fournisseur en ligne sans login.

XPUR20 : chaque fournisseur consulté (``RFQConsultation``) reçoit le PDF RFQ
(produits/quantités/date limite — AUCUN prix interne) par email (pièce
jointe) et un brouillon wa.me avec le lien public tokenisé vers sa page de
réponse. L'envoi WhatsApp reste MANUEL-FIRST (on ouvre le brouillon, le
commercial appuie lui-même sur Envoyer) — jamais d'envoi automatique.

XPUR21 : la page publique (``public_views.rfq_consultation_public``) résout
le jeton, affiche/collecte l'offre du fournisseur (idempotent : re-soumettre
tant que la RFQ n'est pas clôturée met à jour SA PROPRE offre), sans jamais
exposer les offres des autres fournisseurs ni un prix interne.

ARC39 — ces envois ciblent des FOURNISSEURS (tiers externes), PAS des
utilisateurs internes : exception documentée à la règle « plus d'email brut
interne » (cf. `apps/notifications/`), au même titre que
`ventes/email_service.py` et le rapport O&M client de `monitoring/report.py`.
"""
import logging

from django.conf import settings
from django.core.mail import EmailMessage, get_connection

from apps.ventes.utils.whatsapp import build_wa_url

logger = logging.getLogger(__name__)


def _public_rfq_url(request, token):
    """URL absolue publique de la page de réponse fournisseur (XPUR21)."""
    base = getattr(settings, 'PUBLIC_BASE_URL', '') or ''
    path = f'/api/django/public/installations/rfq/{token}/'
    if base:
        return base.rstrip('/') + path
    if request is not None:
        return request.build_absolute_uri(path)
    return path


def _send_email(to_email, sujet, corps, pdf_bytes, filename):
    """Envoi best-effort : sans backend configuré, Django reste sur le
    backend console (NO-OP fonctionnel) — jamais d'exception remontée."""
    try:
        connection = get_connection(fail_silently=False)
        msg = EmailMessage(
            subject=sujet, body=corps,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', '')
            or 'noreply@erp.local',
            to=[to_email], connection=connection)
        if pdf_bytes:
            msg.attach(filename, pdf_bytes, 'application/pdf')
        msg.send(fail_silently=False)
        return True, ''
    except Exception as exc:  # pragma: no cover - dépend du backend réel
        logger.warning('RFQ email échoué vers %s : %s', to_email, exc)
        return False, str(exc)


def envoyer_consultation(consultation, request=None):
    """XPUR20 — envoie la RFQ à UN fournisseur consulté : email (PDF joint)
    si un email est catalogué, brouillon wa.me si un téléphone/whatsapp est
    catalogué. Renvoie un dict de statut par canal — n'envoie RIEN (bouton
    grisé côté frontend) si les deux coordonnées manquent."""
    from django.utils import timezone
    from . import rfq_pdf

    rfq = consultation.rfq
    fournisseur = consultation.fournisseur
    result = {
        'consultation': consultation.id,
        'fournisseur': fournisseur_id_or_none(fournisseur),
        'email': {'envoye': False, 'raison': None},
        'whatsapp': {'envoye': False, 'url': None, 'raison': None},
    }

    email = getattr(fournisseur, 'email', None)
    telephone = getattr(fournisseur, 'telephone', None)

    if not email:
        result['email']['raison'] = 'Aucun email catalogué.'
    else:
        pdf_bytes = rfq_pdf.rfq_pdf_bytes(rfq)
        sujet = f'Demande de prix {rfq.reference}'
        corps = (
            f'Bonjour,\n\nVeuillez trouver ci-joint notre demande de prix '
            f'{rfq.reference} ({rfq.objet}).\n'
            'Merci de nous transmettre votre meilleure offre avant la date '
            'limite indiquée dans le document joint.\n\nCordialement.')
        ok, err = _send_email(
            email, sujet, corps, pdf_bytes, f'{rfq.reference}.pdf')
        result['email']['envoye'] = ok
        if ok:
            consultation.email_envoye_le = timezone.now()
        else:
            result['email']['raison'] = err

    if not telephone:
        result['whatsapp']['raison'] = 'Aucun téléphone catalogué.'
    else:
        url = _public_rfq_url(request, consultation.token)
        message = (
            f'Bonjour, voici notre demande de prix {rfq.reference} '
            f'({rfq.objet}). Merci de répondre ici : {url}')
        wa_url = build_wa_url(telephone, message)
        if wa_url:
            result['whatsapp']['envoye'] = True
            result['whatsapp']['url'] = wa_url
            consultation.whatsapp_envoye_le = timezone.now()
        else:
            result['whatsapp']['raison'] = 'Numéro inexploitable.'

    consultation.save(
        update_fields=['email_envoye_le', 'whatsapp_envoye_le'])
    return result


def fournisseur_id_or_none(fournisseur):
    return getattr(fournisseur, 'id', None)
