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
