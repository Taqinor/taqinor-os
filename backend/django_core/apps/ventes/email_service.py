"""N87 — Intégration email (Brevo) pour l'envoi de documents clients et de
relances depuis un compte d'envoi configurable.

Principe directeur (règle fondatrice) : **sans clé d'envoi configurée, l'envoi
est un NO-OP qui préserve le comportement actuel** (backend console de Django).
On ne lève jamais d'exception pour une absence de clé, et les tests n'exigent
jamais de clé vivante : ils s'appuient sur le backend `locmem`/console de Django.

Stack d'envoi :
  - Backend de messagerie Django configuré (settings.EMAIL_BACKEND). En prod,
    on pointe sur `anymail.backends.sendinblue.EmailBackend` (Brevo, ex-
    Sendinblue) en passant la clé `BREVO_API_KEY`. `django-anymail` est déjà
    installé ; aucune nouvelle dépendance pip.
  - À défaut de clé Brevo/SMTP, Django reste sur le backend console : l'email
    est « envoyé » sans appel réseau (NO-OP fonctionnel), exactement comme
    aujourd'hui.

Chaque envoi est consigné dans `EmailLog` (fil du client + document) ET, pour un
devis, une note est ajoutée au chatter `DevisActivity` — on réutilise le patron
d'activité existant, on n'invente pas de nouveau mécanisme de log.

ARC39 — ce module envoie des emails CLIENTS (documents/relances), PAS des
notifications internes : exception documentée à la règle « plus d'email brut
interne » (cf. `apps/notifications/`), au même titre que
`installations/rfq_service.py` et le rapport O&M client de
`monitoring/report.py`.
"""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection

from .models import EmailLog

logger = logging.getLogger(__name__)


def _branded_html(company, sujet, corps):
    """VX76 — wrapper HTML de marque (logo + en-tête navy + pied) autour du
    corps texte existant. Best-effort : jamais d'exception, jamais de
    changement du corps texte brut conservé en repli MIME."""
    try:
        from apps.parametres.selectors import company_identity
        from core.selectors import wrap_email_html
        identite = company_identity(company) if company is not None else {}
        return wrap_email_html(
            sujet, corps,
            company_nom=identite.get('nom', ''),
            company_adresse=identite.get('adresse', ''),
            company_telephone=identite.get('telephone', ''),
            company_email=identite.get('email', ''),
            couleur_principale=identite.get('couleur_principale', ''),
        )
    except Exception:  # noqa: BLE001 — un email ne casse jamais sur ce point
        return ''


def is_email_configured():
    """True si un compte d'envoi (Brevo ou SMTP) est réellement configuré.

    Sert UNIQUEMENT à informer l'UI / décider d'un envoi réel ; l'absence de
    configuration n'est jamais une erreur — on retombe sur le backend console
    (NO-OP). On considère « configuré » : une clé Brevo, OU un backend non
    console explicitement choisi (ex. SMTP avec hôte).

    QW8 — CORRECTIF : ``ANYMAIL`` (settings/base.py) ne pose JAMAIS de clé
    littéralement nommée ``BREVO_API_KEY`` — la valeur de l'env var
    ``BREVO_API_KEY`` est rangée sous ``SENDINBLUE_API_KEY`` (nom du backend
    anymail pour Brevo, ex-Sendinblue) ; ce contrôle vérifiait donc une clé
    qui n'existe JAMAIS dans ``ANYMAIL``, rendant l'email config-mort même
    avec une vraie clé Brevo configurée en prod. On honore les DEUX clés
    réellement posées par les settings (Sendinblue/Brevo ET SendGrid,
    héritage)."""
    anymail = settings.ANYMAIL or {}
    if anymail.get('SENDINBLUE_API_KEY') or anymail.get('SENDGRID_API_KEY'):
        return True
    backend = getattr(settings, 'EMAIL_BACKEND', '') or ''
    if 'console' in backend or 'dummy' in backend:
        return False
    if 'locmem' in backend:
        # Backend de test : non « configuré » au sens d'un compte réel, mais on
        # laisse l'envoi se faire (les tests vérifient le contenu via locmem).
        return False
    if 'smtp' in backend:
        return bool(getattr(settings, 'EMAIL_HOST', ''))
    # Tout autre backend explicitement choisi (anymail prod) → configuré.
    return True


def _from_email():
    return getattr(settings, 'DEFAULT_FROM_EMAIL', '') or 'noreply@erp.local'


def _reply_to_address():
    """QX36 — adresse Reply-To des emails sortants (devis/facture).

    Pointe vers la boîte entrante relevée par ``core.email_intake`` /
    ``ventes.inbound_email`` pour qu'une réponse client revienne s'attacher au
    devis. Précédence : ``INBOUND_REPLY_EMAIL`` (settings/env) → adresse
    d'expédition par défaut. Vide → pas de Reply-To (comportement inchangé)."""
    return (getattr(settings, 'INBOUND_REPLY_EMAIL', '') or '').strip()


def _signature(company, **context):
    """SCA25 — signature d'email de la société (BrandedTemplate ou repli neutre).

    Résout le nom de la société via ``parametres.company_identity``
    (``CompanyProfile``) puis délègue à ``core.selectors.resolve_email_signature``
    qui applique le ``BrandedTemplate`` de la société s'il existe, sinon
    « L'équipe {nom} ». Plus jamais « TAQINOR » codé en dur : le fondateur ne
    voit son nom que parce que SON profil le porte. Ne casse jamais l'envoi."""
    nom = ''
    try:
        from apps.parametres.selectors import company_identity
        nom = (company_identity(company).get('nom') or '').strip()
    except Exception:  # noqa: BLE001 — un email ne casse jamais sur ce point
        nom = ''
    try:
        from core.selectors import resolve_email_signature
        return resolve_email_signature(company, nom, **context)
    except Exception:  # noqa: BLE001 — repli ultime, jamais d'échec d'envoi
        return f"L'équipe {nom}" if nom else "L'équipe"


def _send(to_email, sujet, corps, attachment=None, attachment_name=None,
          company=None):
    """Envoie via le backend Django configuré. Retourne (ok, erreur).

    Sans clé configurée → backend console → l'email est « envoyé » sans appel
    réseau ni exception (NO-OP). Toute exception réelle est capturée et
    renvoyée comme erreur, jamais propagée à l'appelant.

    QX36 — pose un ``Reply-To`` vers la boîte entrante (si configurée) pour
    qu'une réponse client atterrisse sur le fil du devis (voir
    ``ventes.inbound_email``).

    VX76 — le corps texte existant reste le corps MIME principal (repli
    ``text/plain`` inchangé) ; une alternative ``text/html`` brandée
    (wrapper logo/en-tête navy/pied) est ajoutée quand le rendu réussit —
    additif, jamais cassant."""
    try:
        connection = get_connection(fail_silently=False)
        reply_to = _reply_to_address()
        msg = EmailMultiAlternatives(
            subject=sujet, body=corps, from_email=_from_email(),
            to=[to_email], connection=connection,
            reply_to=[reply_to] if reply_to else None)
        html = _branded_html(company, sujet, corps)
        if html:
            msg.attach_alternative(html, 'text/html')
        if attachment and attachment_name:
            msg.attach(attachment_name, attachment, 'application/pdf')
        msg.send(fail_silently=False)
        return True, ''
    except Exception as exc:  # pragma: no cover - dépend du backend réel
        logger.warning('Envoi email échoué vers %s : %s', to_email, exc)
        return False, str(exc)


def _document_pdf(document):
    """Récupère les octets du PDF stocké d'un document (best-effort).

    Renvoie (bytes, nom_fichier) ou (None, None). Jamais d'exception remontée :
    un PDF indisponible n'empêche pas l'envoi du corps de l'email.

    QX9 — pour un devis signé, PRÉFÈRE la clé du PDF SIGNÉ persistée sur le
    ``DevisSignature`` (``signed_pdf_key``) : c'est l'exemplaire promis
    « ci-joint votre exemplaire signé ». À défaut, on retombe sur
    ``document.fichier_pdf``. La branche « aucune pièce jointe » est désormais
    journalisée (elle était silencieuse — un email promettant un PDF partait
    sans PDF sans trace)."""
    key = getattr(document, 'fichier_pdf', None)
    # QX9 — préfère l'exemplaire signé s'il existe (devis accepté).
    signed_key = None
    try:
        sig = getattr(document, 'signature', None)
        if sig is not None:
            signed_key = getattr(sig, 'signed_pdf_key', None) or None
    except Exception:  # noqa: BLE001 — pas de signature liée → ignore
        signed_key = None
    chosen = signed_key or key
    ref = getattr(document, 'reference', 'document')
    if not chosen:
        logger.warning(
            'QX9: aucun PDF disponible en pièce jointe pour %s '
            '(ni signed_pdf_key ni fichier_pdf) — email envoyé sans exemplaire',
            ref)
        return None, None
    try:
        from .utils.pdf import download_pdf
        data = download_pdf(chosen)
        return data, f'{ref}.pdf'
    except Exception as exc:
        logger.warning('PDF indisponible pour pièce jointe (%s) : %s', ref, exc)
        return None, None


def _chatter_note(devis, body, user):
    """Ajoute une note au chatter du devis (réutilise DevisActivity)."""
    try:
        from .models import DevisActivity
        DevisActivity.objects.create(
            company=devis.company, devis=devis, user=user,
            kind=DevisActivity.Kind.NOTE, body=body)
    except Exception:  # pragma: no cover - le log email reste la source de vérité
        pass


def send_document_email(document, *, to_email=None, sujet=None, corps=None,
                        user=None, attach_pdf=True, log_activity=True):
    """Envoie un document (Devis ou Facture) au client par email et consigne
    l'envoi sur le fil (EmailLog + chatter du devis le cas échéant).

    NO-OP réseau quand aucune clé n'est configurée (backend console) : l'email
    est tout de même journalisé comme « envoyé » pour garder une trace lisible.
    Templates FR par défaut. Renvoie l'EmailLog créé.
    """
    from .models import Devis, Facture
    client = getattr(document, 'client', None)
    dest = (to_email or (getattr(client, 'email', '') or '')).strip()
    reference = getattr(document, 'reference', '') or ''
    est_facture = isinstance(document, Facture)
    type_doc = 'facture' if est_facture else 'devis'

    if not sujet:
        sujet = (f'Votre facture {reference}' if est_facture
                 else f'Votre devis {reference}')
    if not corps:
        nom_client = ''
        if client is not None:
            nom_client = f"{client.nom} {getattr(client, 'prenom', '') or ''}".strip()
        salut = f'Bonjour {nom_client},' if nom_client else 'Bonjour,'
        signature = _signature(
            getattr(document, 'company', None), reference=reference)
        corps = (
            f"{salut}\n\n"
            f"Veuillez trouver ci-joint votre {type_doc} "
            f"{reference}.\n\n"
            f"Nous restons à votre disposition pour toute question.\n\n"
            f"Cordialement,\n{signature}"
        )

    attachment = attachment_name = None
    if attach_pdf:
        attachment, attachment_name = _document_pdf(document)

    log = EmailLog(
        company=getattr(document, 'company', None),
        direction=EmailLog.Direction.SORTANT,
        client=client,
        devis=document if isinstance(document, Devis) else None,
        facture=document if est_facture else None,
        to_email=dest, from_email=_from_email(),
        sujet=sujet[:300], corps=corps,
        reference=reference[:80],
        piece_jointe=(attachment_name or '')[:255],
        created_by=user if getattr(user, 'is_authenticated', False) else None,
    )

    if not dest:
        # Pas de destinataire : on ne tente rien, on consigne l'échec.
        log.statut = EmailLog.Statut.ECHEC
        log.erreur = 'Aucune adresse email destinataire.'
        log.save()
        return log

    ok, err = _send(
        dest, sujet, corps, attachment, attachment_name,
        company=getattr(document, 'company', None))
    log.statut = EmailLog.Statut.ENVOYE if ok else EmailLog.Statut.ECHEC
    log.erreur = err
    log.save()

    if log_activity and isinstance(document, Devis):
        etat = 'envoyé' if ok else 'échec d\'envoi'
        _chatter_note(
            document, f"Email du devis {reference} — {etat} (à {dest}).", user)
    return log


def send_relance_email(facture, *, niveau_nom='', message='', user=None,
                       attach_pdf=False):
    """Envoie un email de relance pour une facture impayée et le consigne.

    Le corps reprend le message du niveau de relance configuré quand il est
    fourni. NO-OP réseau sans clé (backend console). Renvoie l'EmailLog créé.
    """
    client = getattr(facture, 'client', None)
    dest = (getattr(client, 'email', '') or '').strip()
    reference = getattr(facture, 'reference', '') or ''
    sujet = f'Rappel de paiement — facture {reference}'
    if niveau_nom:
        sujet = f'{niveau_nom} — facture {reference}'

    nom_client = ''
    if client is not None:
        nom_client = f"{client.nom} {getattr(client, 'prenom', '') or ''}".strip()
    salut = f'Bonjour {nom_client},' if nom_client else 'Bonjour,'
    corps_msg = message.strip() if message else (
        f"Sauf erreur de notre part, la facture {reference} reste impayée. "
        f"Nous vous remercions de bien vouloir procéder à son règlement.")
    signature = _signature(
        getattr(facture, 'company', None), reference=reference)
    corps = (
        f"{salut}\n\n{corps_msg}\n\n"
        f"Cordialement,\n{signature}"
    )

    attachment = attachment_name = None
    if attach_pdf:
        attachment, attachment_name = _document_pdf(facture)

    log = EmailLog(
        company=getattr(facture, 'company', None),
        direction=EmailLog.Direction.SORTANT,
        client=client, facture=facture,
        to_email=dest, from_email=_from_email(),
        sujet=sujet[:300], corps=corps, reference=reference[:80],
        piece_jointe=(attachment_name or '')[:255],
        created_by=user if getattr(user, 'is_authenticated', False) else None,
    )

    if not dest:
        log.statut = EmailLog.Statut.ECHEC
        log.erreur = 'Aucune adresse email destinataire.'
        log.save()
        return log

    ok, err = _send(
        dest, sujet, corps, attachment, attachment_name,
        company=getattr(facture, 'company', None))
    log.statut = EmailLog.Statut.ENVOYE if ok else EmailLog.Statut.ECHEC
    log.erreur = err
    log.save()
    return log


def send_pre_echeance_email(facture, *, user=None):
    """XFAC7 — envoie le rappel de courtoisie PRÉ-échéance (J-N avant
    ``date_echeance``, jamais après) et le consigne. Utilise le modèle
    ``EmailTemplate`` (clé ``pre_echeance``), NO-OP réseau sans clé d'envoi
    configurée (backend console) — même patron que ``send_relance_email``.
    Inclut le lien de paiement FG53 quand disponible. Renvoie l'EmailLog créé.
    """
    from apps.parametres.models_email import EmailTemplate

    client = getattr(facture, 'client', None)
    dest = (getattr(client, 'email', '') or '').strip()
    reference = getattr(facture, 'reference', '') or ''
    nom_client = ''
    civilite = ''
    if client is not None:
        nom_client = f"{client.nom} {getattr(client, 'prenom', '') or ''}".strip()

    lien = ''
    try:
        from .services import create_payment_link
        from .payments.providers import get_provider
        link = create_payment_link(facture=facture)
        session = get_provider(link.provider).create_session(link)
        lien = session.get('pay_url') or ''
    except Exception:  # pragma: no cover — lien de paiement best-effort
        lien = ''

    rendered = EmailTemplate.render(
        getattr(facture, 'company', None), 'pre_echeance',
        civilite=civilite, nom=nom_client, reference=reference, lien=lien)
    sujet = rendered['sujet'] or f'Rappel amical — échéance {reference}'
    signature = _signature(
        getattr(facture, 'company', None), reference=reference)
    corps = rendered['corps'] or (
        f"Bonjour {nom_client},\n\nVotre facture {reference} arrive "
        f"prochainement à échéance.\n\nCordialement,\n{signature}")

    log = EmailLog(
        company=getattr(facture, 'company', None),
        direction=EmailLog.Direction.SORTANT,
        client=client, facture=facture,
        to_email=dest, from_email=_from_email(),
        sujet=sujet[:300], corps=corps, reference=reference[:80],
        created_by=user if getattr(user, 'is_authenticated', False) else None,
    )

    if not dest:
        log.statut = EmailLog.Statut.ECHEC
        log.erreur = 'Aucune adresse email destinataire.'
        log.save()
        return log

    ok, err = _send(dest, sujet, corps, company=getattr(facture, 'company', None))
    log.statut = EmailLog.Statut.ENVOYE if ok else EmailLog.Statut.ECHEC
    log.erreur = err
    log.save()
    return log


def send_recu_email(paiement, *, user=None, to_email=None):
    """XFAC9 — envoi OPTIONNEL de la quittance PDF au client, à
    l'enregistrement du paiement. NO-OP réseau sans clé d'envoi configurée
    (backend console) — même patron que ``send_document_email``. Consigne
    ``EmailLog``. Renvoie l'EmailLog créé, ou None si aucun destinataire."""
    from .utils.pdf import generate_recu_pdf

    client = paiement.facture.client if paiement.facture_id else paiement.client
    dest = (to_email or (getattr(client, 'email', '') or '')).strip()
    reference = (paiement.facture.reference if paiement.facture_id
                 else f'avance-{paiement.id}')
    nom_client = ''
    if client is not None:
        nom_client = f"{client.nom} {getattr(client, 'prenom', '') or ''}".strip()
    salut = f'Bonjour {nom_client},' if nom_client else 'Bonjour,'
    sujet = f'Quittance de paiement — {reference}'
    signature = _signature(
        getattr(paiement, 'company', None), reference=reference)
    corps = (
        f"{salut}\n\nVeuillez trouver ci-joint votre quittance pour le "
        f"règlement de {paiement.montant} MAD.\n\n"
        f"Cordialement,\n{signature}"
    )

    log = EmailLog(
        company=getattr(paiement, 'company', None),
        direction=EmailLog.Direction.SORTANT,
        client=client, facture=paiement.facture,
        to_email=dest, from_email=_from_email(),
        sujet=sujet[:300], corps=corps, reference=reference[:80],
        created_by=user if getattr(user, 'is_authenticated', False) else None,
    )

    if not dest:
        log.statut = EmailLog.Statut.ECHEC
        log.erreur = 'Aucune adresse email destinataire.'
        log.save()
        return log

    try:
        pdf_bytes = generate_recu_pdf(paiement)
    except Exception as exc:  # pragma: no cover — rendu best-effort
        logger.warning('Quittance PDF indisponible pour envoi : %s', exc)
        pdf_bytes = None

    ok, err = _send(
        dest, sujet, corps, pdf_bytes,
        f'Quittance_{reference}.pdf' if pdf_bytes else None,
        company=getattr(paiement, 'company', None))
    log.statut = EmailLog.Statut.ENVOYE if ok else EmailLog.Statut.ECHEC
    log.erreur = err
    log.save()
    return log


def send_releve_email(client, releve_data, *, user=None):
    """XFAC25 — envoi (programmé, mensuel) du relevé de compte PDF au client.

    Même patron NO-OP que ``send_recu_email`` (sans clé d'envoi configurée,
    « envoyé » via le backend console). Rendu à la volée depuis
    ``releve_data`` (voir ``recouvrement._releve_data``), jamais stocké.
    Consigne un ``EmailLog`` (client seul — pas de facture unique). Renvoie
    l'EmailLog créé, ou ``None`` si le client n'a pas d'email (rien n'est
    tenté ni consigné dans ce cas — l'appelant filtre déjà sur ce critère)."""
    from .utils.pdf import generate_releve_pdf

    dest = (getattr(client, 'email', '') or '').strip()
    if not dest:
        return None

    nom_client = f"{client.nom} {getattr(client, 'prenom', '') or ''}".strip()
    sujet = f'Relevé de compte — {nom_client}'
    signature = _signature(getattr(client, 'company', None))
    corps = (
        f"Bonjour {nom_client},\n\nVeuillez trouver ci-joint votre relevé "
        f"de compte mensuel.\n\nCordialement,\n{signature}"
    )

    log = EmailLog(
        company=getattr(client, 'company', None),
        direction=EmailLog.Direction.SORTANT,
        client=client, to_email=dest, from_email=_from_email(),
        sujet=sujet[:300], corps=corps,
        created_by=user if getattr(user, 'is_authenticated', False) else None,
    )

    try:
        pdf_bytes = generate_releve_pdf(client, releve_data)
    except Exception as exc:  # pragma: no cover — rendu best-effort
        logger.warning('Relevé PDF indisponible pour envoi : %s', exc)
        pdf_bytes = None

    ok, err = _send(
        dest, sujet, corps, pdf_bytes,
        f'Releve_{client.nom}.pdf' if pdf_bytes else None,
        company=getattr(client, 'company', None))
    log.statut = EmailLog.Statut.ENVOYE if ok else EmailLog.Statut.ECHEC
    log.erreur = err
    log.save()
    return log
