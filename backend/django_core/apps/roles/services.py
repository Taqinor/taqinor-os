"""Services d'écriture/orchestration du module ``roles``.

Point d'entrée WRITE unique pour que les apps de FONDATION (ex. ``identity``,
NTSEC6/7/19/20) appliquent/retirent un rôle à un compte SANS importer les
modèles ``roles`` ni manipuler le FK ``role`` directement. Ces fonctions sont
volontairement fines et scopées société.
"""
import logging

logger = logging.getLogger(__name__)


def assign_role(user, role, *, actor=None):
    """Attribue ``role`` à ``user`` (FK unique ``CustomUser.role``).

    Sécurité multi-tenant : refuse si le rôle n'appartient pas à la société de
    l'utilisateur. Retourne True si le rôle a changé, False sinon. N'élève pas
    (best-effort) : toute erreur inattendue est journalisée et renvoie False.
    """
    try:
        if user is None or role is None:
            return False
        if getattr(user, 'company_id', None) and \
                role.company_id != user.company_id:
            return False
        if user.role_id == role.id:
            return False
        user.role = role
        user.save(update_fields=['role'])
        return True
    except Exception:  # noqa: BLE001 — best-effort
        logger.debug('assign_role failed', exc_info=True)
        return False


def revoke_role(user, role, *, fallback_role=None, actor=None):
    """Retire ``role`` de ``user`` s'il le porte actuellement.

    ``CustomUser.role`` étant un FK unique, « retirer » signifie remettre le
    rôle à ``fallback_role`` (ou None). No-op si l'utilisateur ne porte pas
    ``role`` (on ne touche jamais un rôle attribué par un autre canal). Retourne
    True si le rôle a changé.
    """
    try:
        if user is None or role is None:
            return False
        if user.role_id != role.id:
            return False
        user.role = fallback_role
        user.save(update_fields=['role'])
        return True
    except Exception:  # noqa: BLE001 — best-effort
        logger.debug('revoke_role failed', exc_info=True)
        return False


def role_for_scim_group(company, scim_group_name):
    """Rôle mappé à un groupe SCIM/SSO d'une société (NTSEC6/7), ou None.

    Lit ``identity.ScimGroupMapping`` — c'est ``identity`` qui possède ce
    modèle ; on l'interroge ici via une importation function-locale pour offrir
    aux appelants un point unique côté ``roles`` sans qu'ils touchent le FK.
    Best-effort : modèle absent / erreur → None.
    """
    try:
        from apps.identity.models import ScimGroupMapping
        mapping = ScimGroupMapping.objects.filter(
            company=company, scim_group_name=scim_group_name
        ).select_related('role').first()
        return mapping.role if mapping else None
    except Exception:  # noqa: BLE001
        return None
