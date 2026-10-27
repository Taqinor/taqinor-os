"""Services fins de l'app fondation ``roles``.

Point d'entrée d'écriture pour que les autres apps (identité/SCIM, revue
d'accès, SoD…) appliquent/retirent un rôle SANS importer ``roles.models``
directement (cf. la règle de frontière cross-app). Tout est scopé société :
un rôle n'est jamais appliqué s'il n'appartient pas à la société du compte.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def role_for_company(role_id, company_id):
    """Renvoie le ``Role`` d'id ``role_id`` s'il appartient à ``company_id``.

    Renvoie ``None`` si l'id est vide, inconnu, ou appartient à une autre
    société (jamais de fuite cross-tenant)."""
    if not role_id or not company_id:
        return None
    from .models import Role
    try:
        return Role.objects.filter(pk=role_id, company_id=company_id).first()
    except (ValueError, TypeError):
        return None


def apply_role_to_user(user, role_id) -> bool:
    """Attribue le rôle ``role_id`` à ``user`` (scopé à sa société).

    No-op (renvoie ``False``) si le rôle est inconnu / d'une autre société, ou
    si l'utilisateur porte déjà ce rôle. Renvoie ``True`` si le rôle a changé.
    """
    if user is None or not getattr(user, 'pk', None):
        return False
    role = role_for_company(role_id, getattr(user, 'company_id', None))
    if role is None or user.role_id == role.id:
        return False
    # NTSEC20 — séparation des tâches : une règle SoD CRITIQUE bloque
    # l'attribution qui créerait le cumul interdit. Optionnel & fail-open :
    # sans app ``accessreview`` / sans règle critique, aucune restriction.
    try:
        from apps.accessreview.sod import would_cumulate_critical
        if would_cumulate_critical(user, role):
            return False
    except Exception:
        logger.warning("services.apply_role_to_user : erreur ignorée (mode dégradé)", exc_info=True)
    user.role = role
    user.save(update_fields=['role'])
    return True


def remove_role_from_user(user, role_id) -> bool:
    """Retire le rôle ``role_id`` de ``user`` s'il le porte actuellement.

    Le modèle ``CustomUser`` ne porte qu'UN rôle : retirer = repasser à
    « aucun rôle » (``None``) uniquement quand le rôle courant est bien celui
    demandé. Renvoie ``True`` si un retrait a eu lieu, sinon ``False``.
    """
    if user is None or not getattr(user, 'pk', None):
        return False
    if not role_id or str(user.role_id) != str(role_id):
        return False
    user.role = None
    user.save(update_fields=['role'])
    return True


# ── Organigramme (fondateur, 27/10/2026) — rôle par défaut d'une fonction ──


def role_par_defaut_applicable(user, role):
    """Le rôle par défaut d'une fonction peut-il remplacer celui de ``user`` ?

    Jamais une rétrogradation silencieuse d'un compte protégé ou du DERNIER
    propriétaire (même garde que la vue des comptes) : ces comptes gardent
    leur rôle, seul un choix explicite le change."""
    if role is None:
        return False
    if user is None or not getattr(user, 'pk', None):
        return True
    if user.role_id == role.pk:
        return False
    perd_admin = user.is_admin_role and 'roles_gerer' not in (
        role.permissions or [])
    if perd_admin and (user.is_protected or user.est_dernier_proprietaire()):
        return False
    return True


def propager_poste(poste, ancien_role_id):
    """Après modification d'une fonction : recopie son intitulé dans le
    ``poste`` (texte) de ses titulaires, et donne le NOUVEAU rôle par défaut
    aux titulaires qui portaient encore l'ANCIEN (un rôle choisi à la main
    reste). Renvoie le nombre de rôles changés."""
    from authentication.models import CustomUser

    titulaires = CustomUser.objects.filter(
        company_id=poste.company_id, fonction=poste)
    titulaires.exclude(poste=poste.intitule[:120]).update(
        poste=poste.intitule[:120])
    if poste.role_id is None or poste.role_id == ancien_role_id \
            or ancien_role_id is None:
        return 0
    palier = CustomUser.tier_for_role(poste.role) or CustomUser.ROLE_NORMAL
    changes = 0
    for user in titulaires.filter(role_id=ancien_role_id).select_related('role'):
        if role_par_defaut_applicable(user, poste.role):
            CustomUser.objects.filter(pk=user.pk).update(
                role=poste.role, role_legacy=palier)
            changes += 1
    return changes
