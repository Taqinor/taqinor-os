"""N100(b) — création d'un tenant depuis la console fondateur (SCA22).

La console savait lister, suspendre et annoter les sociétés, mais pas en CRÉER
une : l'onboarding passait uniquement par l'endpoint PUBLIC
``/auth/register-company/`` (self-service, avec mot de passe choisi par le
visiteur). Cet endpoint-ci est son pendant ADMINISTRÉ : le fondateur provisionne
une société et son premier Administrateur, qui reçoit un mot de passe généré à
changer à la première connexion.

Réutilise EXACTEMENT la même séquence de provisionnement que
``RegisterCompanyView`` — société + ``CompanyProfile`` + rôles système
(``_create_system_roles``, la même fonction que ``init_roles``) + rattachement
XPLT19 + hooks de signup SCA20 — pour qu'un tenant créé ici soit indiscernable
d'un tenant auto-inscrit. Aucune logique dupliquée : les helpers sont importés.

Idempotence : rejouer la MÊME création (même slug + même email) renvoie 200 avec
la société existante sans rien recréer ; un slug déjà pris par une autre société
renvoie 409.
"""
from __future__ import annotations

import logging

from django.utils.crypto import get_random_string
from django.utils.text import slugify
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Company, CustomUser
from .views_console import IsSuperuserConsole, _tenant_payload

logger = logging.getLogger(__name__)

#: Longueur du mot de passe provisoire généré (à changer à la 1re connexion).
LONGUEUR_MOT_DE_PASSE_PROVISOIRE = 16


def _slug_libre(nom):
    """Slug unique dérivé du nom (même algorithme que RegisterCompanyView)."""
    base = slugify(nom) or 'company'
    slug = base
    i = 1
    while Company.objects.filter(slug=slug).exists():
        slug = f'{base}-{i}'
        i += 1
    return slug


def _username_libre(email, nom_societe):
    """Identifiant unique dérivé de l'email (ou du nom de la société)."""
    base = slugify((email or '').split('@')[0]) or slugify(nom_societe) or 'admin'
    username = base
    i = 1
    while CustomUser.objects.filter(username=username).exists():
        username = f'{base}-{i}'
        i += 1
    return username


def generer_mot_de_passe_provisoire():
    """Mot de passe provisoire robuste (majuscules + minuscules + chiffres).

    Jamais stocké en clair : il est renvoyé UNE FOIS au fondateur pour qu'il le
    transmette, et le compte porte ``must_change_password=True``."""
    alphabet = ('abcdefghijkmnopqrstuvwxyz'
                'ABCDEFGHJKLMNPQRSTUVWXYZ'
                '23456789')
    return get_random_string(LONGUEUR_MOT_DE_PASSE_PROVISOIRE, alphabet)


class TenantConsoleCreateView(APIView):
    """POST — provisionne une société + son premier Administrateur (superuser).

    Corps : ``{nom, email, username?}``. Renvoie la société créée et le mot de
    passe provisoire (affiché une seule fois côté console)."""

    permission_classes = [IsSuperuserConsole]

    def post(self, request):
        nom = (request.data.get('nom') or '').strip()
        email = (request.data.get('email') or '').strip()

        erreurs = {}
        if not nom:
            erreurs['nom'] = ['Le nom de la société est requis.']
        if not email:
            erreurs['email'] = ["L'email de l'administrateur est requis."]
        elif '@' not in email or '.' not in email.split('@')[-1]:
            erreurs['email'] = ['Adresse email invalide.']
        if erreurs:
            return Response(erreurs, status=status.HTTP_400_BAD_REQUEST)

        # ── Garde d'idempotence (slug + email) ──────────────────────────────
        slug_demande = slugify(nom) or 'company'
        existante = Company.objects.filter(slug=slug_demande).first()
        if existante is not None:
            deja = CustomUser.objects.filter(
                company=existante, email__iexact=email).exists()
            if deja:
                # Rejeu exact : rien n'est recréé, la console reste sereine.
                return Response(
                    {**_tenant_payload(existante), 'deja_existant': True},
                    status=status.HTTP_200_OK)
            return Response(
                {'detail': f'Une société utilise déjà le slug « {slug_demande} ».'},
                status=status.HTTP_409_CONFLICT)

        if CustomUser.objects.filter(email__iexact=email).exists():
            return Response(
                {'detail': 'Un compte utilise déjà cette adresse email.'},
                status=status.HTTP_409_CONFLICT)

        # ── Provisionnement (même séquence que RegisterCompanyView) ─────────
        company = Company.objects.create(nom=nom, slug=_slug_libre(nom))

        from apps.parametres.models import CompanyProfile
        CompanyProfile.objects.get_or_create(
            company=company, defaults={'nom': nom, 'email': email})

        # Rôles système : la MÊME fonction que la commande `init_roles`.
        from .views import _create_system_roles
        roles = _create_system_roles(company)

        username = (request.data.get('username') or '').strip() \
            or _username_libre(email, nom)
        mot_de_passe = generer_mot_de_passe_provisoire()
        admin = CustomUser.objects.create_user(
            username=username,
            email=email,
            password=mot_de_passe,
            role_legacy=CustomUser.ROLE_ADMIN,
            role=roles.get('Directeur'),
            company=company,
        )
        # Invitation : le mot de passe généré doit être changé à la 1re connexion.
        admin.must_change_password = True
        admin.save(update_fields=['must_change_password'])
        # XPLT19 — la société d'attache est aussi la première société autorisée.
        admin.societes_autorisees.add(company)

        # SCA20 — hooks « nouvelle société » (best-effort, isolés).
        from core.signup_hooks import run_signup_hooks
        run_signup_hooks(company, user=admin)

        _journaliser_creation(company, request.user, admin)

        return Response(
            {
                **_tenant_payload(company),
                'admin': {
                    'id': admin.pk,
                    'username': admin.username,
                    'email': admin.email,
                    'must_change_password': True,
                },
                # Affiché UNE SEULE FOIS côté console : jamais relu ensuite.
                'mot_de_passe_provisoire': mot_de_passe,
            },
            status=status.HTTP_201_CREATED)


def _journaliser_creation(company, user, admin):
    """Trace d'audit posée depuis la VUE (même patron que views_console)."""
    try:
        from apps.audit.models import AuditLog
        from apps.audit.recorder import record
        record(AuditLog.Action.CREATE, user=user, company=company,
               detail=f'Tenant « {company.nom} » créé depuis la console '
                      f'fondateur (admin : {admin.username}).')
    except Exception:  # noqa: BLE001 — best-effort
        logger.debug('audit création tenant échoué', exc_info=True)
