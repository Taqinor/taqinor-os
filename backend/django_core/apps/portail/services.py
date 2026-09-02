"""Services du module Portail client (``apps.portail``).

ODX12 — ré-export TRANSITOIRE des fonctions de service portail qui vivent encore
physiquement dans ``apps.compta.services`` (elles y étaient interleavées avec la
logique comptable et l'acceptation de devis qui appelle le service ventes
existant). Ce module donne au reste du code (urls, appelants cross-app) un point
d'accès ``apps.portail.services`` stable ; ODX22 re-logera le corps des fonctions
ici et retirera ce shim.

``portail`` ne lit ventes/crm/sav QUE via leurs selectors/services ou par
référence opaque — jamais leurs ``models`` (les fonctions ré-exportées
référencent devis_id/facture_id opaques et passent par le service ventes pour
l'acceptation). ``/proposal`` reste l'unique voie PDF devis (règle #4).
"""

from apps.compta.services import (  # noqa: F401
    cmi_actif,
    initier_paiement_facture,
    rapprocher_paiement_facture,
    signer_acceptation_devis,
)


# ── NTPRT2 — Provisionnement d'un VRAI compte utilisateur portail client ─────
#
# Avant NTPRT2 l'accès portail d'un client reposait UNIQUEMENT sur
# ``ComptePortailClient.token_acces`` (jeton opaque dans un lien email). NTPRT2
# fait du compte utilisateur RÉEL le mécanisme PRIMAIRE : un ``CustomUser``
# ``portee=portail_client`` rattaché au client par ``portail_client_id``
# (fondation NTPRT1), qui se connecte par le login JWT STANDARD — jamais un
# second système d'auth. Le ``token_acces`` est CONSERVÉ tel quel (aucun lien
# email existant n'est cassé) mais devient un « magic-link » COMPLÉMENTAIRE.
#
# Décisions de sécurité (volontairement STRICTES) :
#   * Le mot de passe temporaire n'est JAMAIS renvoyé dans la réponse HTTP : il
#     part uniquement par email au client (backend console en local, SendGrid
#     gated en prod — no-op silencieux sans clé). Le compte est créé avec
#     ``must_change_password=True`` (N96) : le client DOIT le changer à sa
#     première session. AUD139 — cette garantie est désormais APPLIQUÉE côté
#     serveur : ``roles.permissions.exiger_mot_de_passe_change`` refuse toute
#     route portail (403, code ``mot_de_passe_a_changer``) tant que le mot de
#     passe temporaire n'est pas remplacé ; seuls ``/auth/me/``,
#     ``/auth/logout/`` et ``/auth/change-password/`` restent joignables.
#   * Idempotent SANS effet de bord : re-provisionner ne réinitialise pas le mot
#     de passe et NE RÉACTIVE JAMAIS un compte désactivé (révoqué). Réactiver
#     silencieusement un accès retiré serait un élargissement d'accès non
#     demandé — la réactivation reste une action admin explicite.
#   * Le compte porte le rôle système « Portail client » (permissions
#     ``portail_*`` uniquement, aucun code interne) : par construction il
#     n'atteint aucun endpoint interne (NTPRT1 + NTPRT5).

#: Longueur du mot de passe temporaire généré (jamais journalisé, jamais rendu).
LONGUEUR_MOT_DE_PASSE_TEMPORAIRE = 16


def _username_portail_disponible(base):
    """Renvoie un ``username`` LIBRE dérivé de ``base``.

    ``CustomUser.username`` est unique GLOBALEMENT (tous tenants confondus) :
    deux sociétés peuvent avoir un client avec le même email. On suffixe donc
    ``-2``, ``-3``… jusqu'à trouver un identifiant libre, sans jamais voler
    celui d'un compte existant.
    """
    from authentication.models import CustomUser

    base = (base or '').strip().lower()[:140] or 'portail-client'
    candidat = base
    suffixe = 1
    while CustomUser.objects.filter(username=candidat).exists():
        suffixe += 1
        candidat = f'{base}-{suffixe}'[:150]
    return candidat


def _envoyer_identifiants_portail(user, mot_de_passe, company):
    """Envoie le mot de passe temporaire au client. Best-effort, jamais fatal.

    Sans ``SENDGRID_API_KEY`` le backend email est la console (local) ou un
    no-op : le provisionnement RÉUSSIT quand même (le mot de passe est alors
    redéfini par le flux « mot de passe oublié » standard). On ne renvoie
    jamais le mot de passe à l'appelant HTTP.
    """
    if not user.email:
        return False
    try:
        from django.conf import settings
        from django.core.mail import send_mail

        # NTPRT19 — l'email portail porte la marque du TENANT (nom affiché de
        # ``TenantTheme``, repli ``CompanyProfile`` puis raison sociale) et
        # jamais le branding ERP par défaut.
        from .branding import marque_portail
        societe = (marque_portail(company).get('nom_affichage')
                   or 'votre prestataire')
        send_mail(
            subject=f'Votre accès au portail client {societe}',
            message=(
                f'Bonjour,\n\n'
                f'Votre accès au portail client de {societe} est ouvert.\n\n'
                f'Identifiant : {user.username}\n'
                f'Mot de passe temporaire : {mot_de_passe}\n\n'
                f'Il vous sera demandé de le changer à la première '
                f'connexion.\n'
            ),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            recipient_list=[user.email],
            fail_silently=True,
        )
        return True
    except Exception:  # noqa: BLE001 - un email KO ne casse jamais l'accès
        return False


def provisionner_compte_portail_client(company, client_id):
    """NTPRT2 — Crée (ou relie) le compte utilisateur portail d'un client.

    Renvoie ``(user, cree)`` où ``cree`` dit si un ``CustomUser`` a été créé
    par CET appel. Le ``ComptePortailClient`` (avec son ``token_acces``) est
    créé au besoin et laissé INTACT s'il existe déjà.

    Le client est résolu via ``apps.crm.selectors`` (jamais un import de
    ``apps.crm.models`` — frontière cross-app CLAUDE.md) et doit appartenir à
    ``company`` : un id d'une autre société renvoie ``(None, False)``, jamais
    un compte croisé.
    """
    import secrets

    from django.db import transaction
    from django.utils.crypto import get_random_string

    from apps.crm.selectors import get_company_client
    from apps.roles.models import (
        PORTAIL_CLIENT_PERMISSIONS,
        ROLE_PORTAIL_CLIENT,
        Role,
    )
    from authentication.models import CustomUser

    from .models import ComptePortailClient

    if company is None or not client_id:
        return None, False
    client = get_company_client(company, client_id)
    if client is None:
        return None, False

    with transaction.atomic():
        # Le compte portail (porteur du token magic-link) reste la trace
        # métier ; on ne régénère JAMAIS un token déjà distribué.
        compte, _ = ComptePortailClient.objects.get_or_create(
            company=company,
            client=client,
            defaults={'token_acces': secrets.token_urlsafe(32)},
        )

        # Idempotence : un compte utilisateur déjà rattaché à CE client dans
        # CETTE société est renvoyé tel quel (ni mot de passe réinitialisé, ni
        # réactivation silencieuse d'un accès révoqué).
        existant = CustomUser.objects.filter(
            company=company,
            portee=CustomUser.PORTEE_PORTAIL_CLIENT,
            portail_client_id=client.id,
        ).first()
        if existant is not None:
            return existant, False

        role, _ = Role.objects.get_or_create(
            company=company,
            nom=ROLE_PORTAIL_CLIENT,
            defaults={
                'permissions': list(PORTAIL_CLIENT_PERMISSIONS),
                'est_systeme': True,
            },
        )

        email = (getattr(client, 'email', '') or '').strip()
        mot_de_passe = get_random_string(LONGUEUR_MOT_DE_PASSE_TEMPORAIRE)
        user = CustomUser(
            username=_username_portail_disponible(email or f'client-{client.id}'),
            email=email,
            company=company,
            role=role,
            portee=CustomUser.PORTEE_PORTAIL_CLIENT,
            portail_client_id=client.id,
            must_change_password=True,
            is_staff=False,
            is_superuser=False,
        )
        user.set_password(mot_de_passe)
        user.save()

    _envoyer_identifiants_portail(user, mot_de_passe, company)
    return user, True


# ── AUD138 — Révocation RÉELLE de l'accès portail d'un client ───────────────
#
# Avant AUD138, « révoquer » un compte portail ne posait que
# ``ComptePortailClient.actif = False``. Or ce drapeau n'était lu QUE par le
# chemin magic-link tokenisé (``compta.selectors.compte_portail_par_token``) :
# le mécanisme d'accès PRIMAIRE depuis NTPRT2 est le ``CustomUser``
# ``portee=portail_client`` + JWT, dont la garde ne le lisait jamais. Un client
# « révoqué » continuait donc de consulter ses devis et ses factures avec le
# jeton déjà émis.
#
# La révocation est désormais UNE action serveur qui, dans une transaction,
# ferme les DEUX portes : le drapeau ``actif`` (magic-link) ET
# ``CustomUser.is_active`` (JWT — SimpleJWT refuse un utilisateur inactif dès
# l'authentification, y compris sur un jeton déjà distribué). La réactivation
# est SYMÉTRIQUE et EXPLICITE : elle n'a lieu que sur cet appel-là, jamais en
# effet de bord d'un re-provisionnement (cf. la politique ci-dessus).


def _basculer_acces_portail_client(company, client_id, *, actif):
    """Pose ``actif`` sur le compte portail ET ``is_active`` sur ses comptes
    utilisateur portail, atomiquement. Renvoie ``(compte, nb_utilisateurs)``."""
    from django.db import transaction

    from authentication.models import CustomUser

    from .models import ComptePortailClient

    if company is None or not client_id:
        return None, 0

    with transaction.atomic():
        compte = (
            ComptePortailClient.objects
            .select_for_update()
            .filter(company=company, client_id=client_id)
            .first()
        )
        if compte is not None and compte.actif != actif:
            compte.actif = actif
            compte.save(update_fields=['actif'])
        nb = CustomUser.objects.filter(
            company=company,
            portee=CustomUser.PORTEE_PORTAIL_CLIENT,
            portail_client_id=client_id,
        ).update(is_active=actif)
    return compte, nb


# ── AUD148 (a) — ``derniere_connexion`` n'était écrite par AUCUN code ───────
#
# La colonne existe (``portail/models.py``), l'écran ERP l'affiche, et grep sur
# ``backend/django_core`` ne rendait que le modèle et le serializer en lecture
# seule : ni le chemin tokenisé ni le login JWT ne la posaient. La colonne
# d'audit d'accès était donc vide le jour où l'on cherche qui a consulté quoi —
# alors que le patron existe déjà dans le dépôt (``education/public_views.py``
# met bien à jour SON équivalent).
#
# On écrit au plus une fois par PÉRIODE : une écriture par requête portail
# transformerait chaque GET en UPDATE (et « dernière connexion » n'a pas besoin
# d'une précision à la seconde).

#: Granularité de l'horodatage de connexion portail.
PERIODE_HORODATAGE_CONNEXION = 3600  # secondes


def enregistrer_connexion_portail(compte_id, derniere_connexion=None,
                                  maintenant=None):
    """AUD148 — Horodate ``derniere_connexion``, au plus une fois par période.

    ``compte_id`` / ``derniere_connexion`` viennent d'une lecture DÉJÀ faite
    par l'appelant (``selectors.etat_compte_portail_client``, ou le compte
    résolu par token) : cette fonction n'ajoute JAMAIS de SELECT, seulement un
    UPDATE ciblé quand il est utile. Renvoie l'horodatage posé, ou ``None``.
    """
    from datetime import timedelta

    from django.utils import timezone

    from .models import ComptePortailClient

    if not compte_id:
        return None
    maintenant = maintenant or timezone.now()
    if derniere_connexion is not None and (
            maintenant - derniere_connexion
            < timedelta(seconds=PERIODE_HORODATAGE_CONNEXION)):
        return None
    (ComptePortailClient.objects
     .filter(pk=compte_id)
     .update(derniere_connexion=maintenant))
    return maintenant


def revoquer_acces_client(company, client_id):
    """AUD138 — Ferme l'accès portail d'un client : magic-link ET compte JWT."""
    return _basculer_acces_portail_client(company, client_id, actif=False)


def reactiver_acces_client(company, client_id):
    """AUD138 — Rouvre l'accès portail d'un client (action ADMIN explicite).

    Symétrique de ``revoquer_acces_client`` : c'est le SEUL chemin qui
    réactive un accès retiré — jamais un re-provisionnement silencieux.
    """
    return _basculer_acces_portail_client(company, client_id, actif=True)
