"""Services fins de l'app fondation ``roles``.

Point d'entrée d'écriture pour que les autres apps (identité/SCIM, revue
d'accès, SoD…) appliquent/retirent un rôle SANS importer ``roles.models``
directement (cf. la règle de frontière cross-app). Tout est scopé société :
un rôle n'est jamais appliqué s'il n'appartient pas à la société du compte.
"""
from __future__ import annotations


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
