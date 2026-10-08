"""Source unique de vérité : Role → palier de menu hérité.

Module volontairement PUR (aucun import de modèle Django) pour pouvoir être
réutilisé sans cycle par les modèles, les serializers, les permissions ET les
migrations de données.

Les trois rôles système canoniques mappent 1:1 sur les paliers hérités ;
tout autre rôle (Utilisateur ou rôle personnalisé type « Commercial »)
relève du palier limité 'normal'. Le palier ainsi calculé est le signal qui
fait autorité — jamais le champ ``role_legacy`` qui peut dériver.
"""

ROLE_ADMIN = 'admin'
ROLE_RESPONSABLE = 'responsable'
ROLE_NORMAL = 'normal'

# Rôles système faisant autorité par palier. « Directeur » et « Administrateur »
# (= Admin) ouvrent les écrans d'administration au même titre ; les deux rôles
# « responsable » (commercial/technicien) sont promus comme l'ancien
# « Responsable ». Tout autre rôle (Commercial, Technicien, Viewer, Utilisateur,
# ou rôle personnalisé) relève du palier limité 'normal'.
_ADMIN_ROLE_NAMES = {'Administrateur', 'Directeur'}
_RESPONSABLE_ROLE_NAMES = {
    'Responsable', 'Commercial responsable', 'Technicien responsable',
}

# Signaux de permission FAISANT AUTORITÉ pour le palier (N103). Le palier ne doit
# pas dépendre uniquement du nom + ``est_systeme`` du rôle : un Directeur/
# Administrateur réel dont la ligne Role a dérivé (mapping rétroactif laissant
# ``est_systeme=False`` ou un nom légèrement différent) doit RESTER admin, sinon
# il perd l'accès aux écrans Utilisateurs/Rôles et ne peut plus changer les rôles.
# - ``roles_gerer`` est porté UNIQUEMENT par Directeur et Administrateur ⇒ palier
#   admin. Aucun rôle limité (Commercial/Technicien/Viewer/Utilisateur) ne l'a,
#   donc ce signal n'élargit jamais l'accès des rôles restreints.
# - ``users_voir`` distingue les rôles « responsable » promus (Responsable,
#   Commercial/Technicien responsable) du palier limité, sans porter ``roles_gerer``.
_ADMIN_PERMISSION = 'roles_gerer'
_RESPONSABLE_PERMISSION = 'users_voir'


def tier_for_role_fields(nom, est_systeme, permissions=None):
    """Palier hérité ('admin' / 'responsable' / 'normal') pour un rôle décrit
    par son nom, son drapeau système et — optionnellement — ses permissions.

    Fonction pure, sans accès base. Quand ``permissions`` est fourni, le palier
    dérive d'ABORD du signal de permission faisant autorité (``roles_gerer`` →
    admin, ``users_voir`` → responsable), robuste à toute dérive de nom/
    ``est_systeme`` du rôle laissée par un mapping rétroactif. À défaut (les
    migrations historiques ne passent que nom + drapeau), on retombe sur le
    mapping par nom système, au comportement inchangé."""
    if permissions:
        if _ADMIN_PERMISSION in permissions:
            return ROLE_ADMIN
        if _RESPONSABLE_PERMISSION in permissions:
            return ROLE_RESPONSABLE
        return ROLE_NORMAL
    if est_systeme and nom in _ADMIN_ROLE_NAMES:
        return ROLE_ADMIN
    if est_systeme and nom in _RESPONSABLE_ROLE_NAMES:
        return ROLE_RESPONSABLE
    return ROLE_NORMAL


def sync_role_legacy(user_model):
    """Réaligne ``role_legacy`` sur le palier du Role assigné, pour tous les
    comptes portant un rôle. Idempotente et NON destructive : ne touche qu'au
    champ legacy quand il diverge, ne supprime ni ne crée rien.

    Reçoit la classe de modèle (réel ou historique via ``apps.get_model``) pour
    être appelable depuis une migration comme depuis les tests. Retourne le
    nombre de comptes réalignés.
    """
    updated = 0
    qs = user_model.objects.filter(role__isnull=False).select_related('role')
    for user in qs:
        # Passe les permissions : un Directeur/Administrateur dont la ligne Role
        # a dérivé (nom/``est_systeme``) est tout de même réaligné sur 'admin'
        # via le signal ``roles_gerer`` (N103).
        tier = tier_for_role_fields(
            user.role.nom, user.role.est_systeme, user.role.permissions or [])
        if tier and user.role_legacy != tier:
            user.role_legacy = tier
            user.save(update_fields=['role_legacy'])
            updated += 1
    return updated


# ── ASEC2 — garde de RANG sur la gestion des comptes ────────────────────────
# ``validate_role`` (ERR21/NTADM21) garde le RÔLE assigné ; cette garde-ci garde
# le RANG de la CIBLE : un acteur ne gère jamais (mot de passe, e-mail, état,
# rôle, avatar, rotation forcée, suppression) un compte de palier supérieur au
# sien, un compte propriétaire protégé ou le dernier propriétaire de la société.
# UNE seule fonction, appelée par update/partial_update/destroy/avatar — aucune
# copie de la logique de palier ailleurs.
CODE_RANG_CIBLE = 'rang_cible'
CODE_ROLE_PLUS_LARGE = 'role_plus_large'

_RANG = {ROLE_NORMAL: 1, ROLE_RESPONSABLE: 2, ROLE_ADMIN: 3}


def rang(user):
    """Rang numérique du palier de ``user`` (superuser au-dessus de tout)."""
    if getattr(user, 'is_superuser', False):
        return 4
    return _RANG.get(getattr(user, 'menu_tier', None), 1)


def peut_gerer(acteur, cible):
    """``(True, None)`` si ``acteur`` peut gérer le compte ``cible``, sinon
    ``(False, CODE_RANG_CIBLE)``.

    - un superuser gère tout ; personne d'autre ne gère un superuser ;
    - on se gère soi-même (les gardes propriétaire existantes restent) ;
    - un compte ``is_protected`` ou dernier propriétaire n'est géré que par
      lui-même ;
    - sinon le rang de la cible ne dépasse jamais celui de l'acteur."""
    if getattr(acteur, 'is_superuser', False):
        return True, None
    if getattr(cible, 'is_superuser', False):
        return False, CODE_RANG_CIBLE
    if getattr(acteur, 'pk', None) is not None \
            and acteur.pk == getattr(cible, 'pk', None):
        return True, None
    if getattr(cible, 'is_protected', False):
        return False, CODE_RANG_CIBLE
    est_dernier = getattr(cible, 'est_dernier_proprietaire', None)
    if callable(est_dernier) and est_dernier():
        return False, CODE_RANG_CIBLE
    if rang(cible) > rang(acteur):
        return False, CODE_RANG_CIBLE
    return True, None


def codes_plus_larges(permissions_acteur, permissions_role):
    """Codes du rôle ``permissions_role`` que l'acteur ne porte PAS lui-même,
    triés. Les marqueurs qui RESTREIGNENT (portée ``records_scope_*``,
    visibilité d'app ``app_<clé>_voir``) ne comptent jamais comme plus larges."""
    a = set(permissions_acteur or [])
    return sorted(
        c for c in set(permissions_role or [])
        if c not in a
        and not c.startswith('records_scope')
        and not (c.startswith('app_') and c.endswith('_voir'))
    )
