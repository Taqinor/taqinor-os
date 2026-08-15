"""NTADM22 — cycle de vie d'une session d'impersonation SOUS CONSENTEMENT.

Règle unique et non contournable de ce module : **sans consentement explicite
de l'Administrateur du tenant cible, aucune session n'existe.** Une demande est
créée inerte (`consentement_donne=False`) ; seule `donner_consentement()` la
rend exploitable, et seulement avant `expire_le`. Une demande périmée
(NTADM37) ne peut JAMAIS être autorisée rétroactivement.

Mécanique de session — volontairement la plus simple qui soit sûre : on REUTILISE
la machinerie JWT existante (`rest_framework_simplejwt`), on n'en invente pas une
seconde. `emettre_jeton_impersonation()` émet un jeton d'ACCÈS (jamais de
refresh : la session ne peut donc pas se prolonger toute seule) pour
l'utilisateur cible, portant deux revendications supplémentaires :

* ``imp``    — id de la ``SessionImpersonation`` ;
* ``imp_by`` — id du compte support qui assiste.

Sa durée de vie est bornée par `expire_le` : le jeton meurt AVEC la session.
L'authentification des utilisateurs normaux n'est ni modifiée ni affaiblie —
aucun jeton ordinaire ne porte ces revendications, et `cookie_auth` continue de
faire foi.
"""
from __future__ import annotations

import logging

from django.utils import timezone

logger = logging.getLogger(__name__)

#: Revendications JWT ajoutées à un jeton d'impersonation.
CLAIM_SESSION = 'imp'
CLAIM_SUPPORT = 'imp_by'


class ImpersonationRefusee(Exception):
    """Action impossible dans l'état courant de la demande (français)."""


# ---------------------------------------------------------------------------
# Destinataires du consentement
# ---------------------------------------------------------------------------

def administrateurs_du_tenant(company):
    """Comptes habilités à CONSENTIR pour `company` (Administrateurs actifs).

    Un Administrateur = superuser, rôle métier admin (`role_legacy='admin'`) ou
    porteur du palier admin (`is_admin_role`). Best-effort : renvoie toujours un
    queryset (jamais d'exception) — un tenant sans administrateur donne un
    queryset vide, et la demande reste alors simplement sans consentement."""
    from authentication.models import CustomUser
    try:
        qs = CustomUser.objects.filter(company=company, is_active=True)
        # `is_admin_role` est une propriété Python (pas un champ) : on filtre
        # sur ce qui est interrogeable en base, puis on affine en Python.
        candidats = qs.filter(role_legacy='admin') | qs.filter(is_superuser=True)
        candidats = candidats.distinct()
        if candidats.exists():
            return candidats
        return qs.none()
    except Exception:  # noqa: BLE001 — best-effort
        logger.warning('adminops: résolution des administrateurs échouée',
                       exc_info=True)
        from authentication.models import CustomUser as _U
        return _U.objects.none()


# ---------------------------------------------------------------------------
# Création de la demande
# ---------------------------------------------------------------------------

def demander_impersonation(*, utilisateur_cible, initiee_par, motif):
    """Crée une demande INERTE puis notifie le tenant cible.

    Le motif est OBLIGATOIRE (NTADM32) : une chaîne vide lève. La demande naît
    `consentement_donne=False` — à ce stade aucune session n'est possible."""
    from .models import SessionImpersonation

    motif = (motif or '').strip()
    if not motif:
        raise ImpersonationRefusee('Le motif est obligatoire.')
    if utilisateur_cible is None or getattr(utilisateur_cible, 'company_id', None) is None:
        raise ImpersonationRefusee(
            "L'utilisateur cible doit appartenir à une société.")
    if not getattr(initiee_par, 'is_taqinor_support', False) and \
            not getattr(initiee_par, 'is_superuser', False):
        raise ImpersonationRefusee(
            'Réservé au staff support de l\'éditeur.')

    demande = SessionImpersonation.objects.create(
        company=utilisateur_cible.company,
        utilisateur_cible=utilisateur_cible,
        initiee_par=initiee_par,
        motif=motif,
    )
    _notifier_demande(demande)
    return demande


def _notifier_demande(demande):
    """Notification in-app + email aux Administrateurs du tenant cible.

    Best-effort de bout en bout : un canal en échec n'empêche ni l'autre ni la
    création de la demande (qui, elle, reste inerte tant que personne n'a
    cliqué « Autoriser »)."""
    # WIR176 — `/admin/impersonation/<pk>` n'est PAS une route déclarée (le
    # front n'expose que `/admin/impersonation`, l'écran de consentement, qui
    # liste les demandes en attente) : le lien atterrissait en 404.
    lien = '/admin/impersonation'
    titre = 'Demande de session support'
    corps = (
        f"Le support de l'éditeur demande à assister "
        f"« {demande.utilisateur_cible} » .\n\n"
        f"Motif : {demande.motif}\n\n"
        f"Sans votre autorisation explicite, aucune session ne sera ouverte. "
        f"La demande expire le "
        f"{timezone.localtime(demande.expire_le):%d/%m/%Y à %H:%M}."
    )
    destinataires = list(administrateurs_du_tenant(demande.company))

    for admin in destinataires:
        try:
            from apps.notifications.models import EventType
            from apps.notifications.services import notify
            notify(admin, EventType.IMPERSONATION_REQUESTED, titre,
                   body=corps, link=lien, company=demande.company)
        except Exception:  # noqa: BLE001 — best-effort
            logger.warning('adminops: notification impersonation échouée '
                           '(user %s)', getattr(admin, 'pk', None))

    emails = [a.email for a in destinataires if getattr(a, 'email', '')]
    if emails:
        try:
            from django.conf import settings
            from django.core.mail import send_mail
            send_mail(
                subject=f'[Support] {titre}',
                message=corps,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                recipient_list=emails,
                fail_silently=True,
            )
        except Exception:  # noqa: BLE001 — best-effort
            logger.warning('adminops: email impersonation échoué', exc_info=True)


# ---------------------------------------------------------------------------
# Consentement / refus / clôture
# ---------------------------------------------------------------------------

def donner_consentement(demande, *, par, now=None):
    """Autorise la demande. SEULE porte vers une session exploitable.

    Refuse (et ne modifie rien) si la demande est déjà refusée, close, périmée
    ou hors délai — une demande expirée n'est JAMAIS ré-ouvrable."""
    now = now or timezone.now()
    if demande.consentement_donne:
        return demande
    if demande.refusee:
        raise ImpersonationRefusee('Cette demande a été refusée.')
    if demande.terminee_le is not None:
        raise ImpersonationRefusee('Cette demande est close.')
    if demande.expiree or demande.est_perimee(now):
        # Marque la péremption au passage (idempotent) pour que l'état lu
        # corresponde à l'état stocké, même si NTADM37 n'est pas encore passé.
        if not demande.expiree:
            demande.expiree = True
            demande.save(update_fields=['expiree', 'updated_at'])
        raise ImpersonationRefusee(
            "Cette demande a expiré : elle ne peut plus être autorisée.")

    demande.consentement_donne = True
    demande.consentement_le = now
    demande.consentement_par = par
    demande.save(update_fields=[
        'consentement_donne', 'consentement_le', 'consentement_par',
        'updated_at'])
    return demande


def refuser(demande, *, par=None, now=None):
    """Refuse la demande (définitif : plus aucun consentement possible)."""
    now = now or timezone.now()
    if demande.consentement_donne:
        raise ImpersonationRefusee(
            'Cette demande a déjà été autorisée ; terminez la session.')
    if demande.refusee:
        return demande
    demande.refusee = True
    demande.refus_le = now
    demande.consentement_par = par
    demande.save(update_fields=[
        'refusee', 'refus_le', 'consentement_par', 'updated_at'])
    return demande


def terminer(demande, *, now=None):
    """Clôt la session (idempotent). Le jeton émis meurt avec `expire_le`."""
    if demande.terminee_le is None:
        demande.terminee_le = now or timezone.now()
        demande.save(update_fields=['terminee_le', 'updated_at'])
    return demande


# ---------------------------------------------------------------------------
# Jeton de session
# ---------------------------------------------------------------------------

def emettre_jeton_impersonation(demande, *, now=None):
    """Jeton d'ACCÈS borné pour l'utilisateur cible (jamais de refresh).

    Lève si la session n'est pas active : c'est ici que l'invariant
    « pas de consentement ⇒ pas de session » devient concret."""
    now = now or timezone.now()
    if not demande.est_active(now):
        raise ImpersonationRefusee(
            "Aucune session active : consentement absent, refusé, expiré ou "
            "session déjà terminée.")

    from rest_framework_simplejwt.tokens import AccessToken

    token = AccessToken.for_user(demande.utilisateur_cible)
    token[CLAIM_SESSION] = demande.pk
    token[CLAIM_SUPPORT] = demande.initiee_par_id
    # La session ne survit jamais à son échéance, même si la durée de vie
    # standard des jetons est plus longue.
    token.set_exp(from_time=now, lifetime=(demande.expire_le - now))

    if demande.demarree_le is None:
        demande.demarree_le = now
        demande.save(update_fields=['demarree_le', 'updated_at'])
    return str(token)


def session_depuis_requete(request):
    """`SessionImpersonation` ACTIVE portée par la requête, sinon None.

    Lit les revendications du jeton validé (`request.auth`). Best-effort : une
    requête ordinaire (sans revendication) renvoie None sans jamais lever."""
    from .models import SessionImpersonation

    try:
        auth = getattr(request, 'auth', None)
        if auth is None:
            return None
        session_id = auth.get(CLAIM_SESSION) if hasattr(auth, 'get') else None
        if not session_id:
            return None
        demande = SessionImpersonation.objects.filter(pk=session_id).first()
        if demande is not None and demande.est_active():
            return demande
        return None
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        return None
