"""Portée de visibilité des enregistrements & hiérarchie d'équipe (Features E+F).

Source unique de vérité du « qui voit quoi ». Conçu pour être ADDITIF et ne
JAMAIS verrouiller personne :

* Un rôle SANS marqueur de portée (``records_scope_*``) voit TOUS les
  enregistrements de sa société — comportement historique, préservé pour les
  comptes légacy (sans rôle fin), les rôles personnalisés, et les rôles
  Directeur/Administrateur.
* ``records_scope_sous_arbre`` (responsables) → soi-même + tout le sous-arbre
  (toute personne remontant à soi, récursivement via ``supervisor``).
* ``records_scope_equipe`` (Commercial/Technicien/Viewer) → soi-même + ses
  pairs (même superviseur direct) + son propre sous-arbre éventuel.

Un utilisateur voit TOUJOURS les enregistrements qu'il possède / lui sont
assignés / qu'il a créés : ``visible_user_ids`` inclut toujours son propre id, et
le narrowing par queryset filtre sur ``owner|created_by|assigné ∈ visible_ids``.
Liste vide = rendu propre (aucune fuite, aucune erreur).
"""
from django.db.models import Q

from apps.roles.models import SCOPE_TEAM, SCOPE_SUBTREE


def record_scope_for(user):
    """'all' | 'subtree' | 'team' pour un utilisateur."""
    if user is None or not user.is_authenticated:
        return 'all'
    if user.is_superuser:
        return 'all'
    # Un rôle administrateur (Directeur/Admin — porte 'roles_gerer') voit
    # TOUJOURS tout, même si la liste de permissions porte un marqueur de
    # portée (cas d'un rôle bâti sur ALL_PERMISSIONS). Le narrowing ne vaut
    # que pour les rôles non-admins.
    if getattr(user, 'is_admin_role', False):
        return 'all'
    role = getattr(user, 'role', None)
    if not role:
        return 'all'  # compte légacy sans rôle fin → tout (historique)
    perms = role.permissions or []
    if SCOPE_SUBTREE in perms:
        return 'subtree'
    if SCOPE_TEAM in perms:
        return 'team'
    return 'all'


def _company_user_model():
    from authentication.models import CustomUser
    return CustomUser


def subtree_user_ids(user):
    """Ids de l'utilisateur + tout son sous-arbre (subordonnés récursifs),
    bornés à sa société. Itératif (pas de récursion SQL)."""
    User = _company_user_model()
    seen = {user.id}
    frontier = {user.id}
    company_id = user.company_id
    # Garde-fou : au plus autant d'itérations que d'utilisateurs de la société.
    base = User.objects.all()
    if company_id:
        base = base.filter(company_id=company_id)
    max_depth = base.count() + 1
    for _ in range(max_depth):
        children = set(
            base.filter(supervisor_id__in=frontier)
            .exclude(id__in=seen)
            .values_list('id', flat=True)
        )
        if not children:
            break
        seen |= children
        frontier = children
    return seen


def peer_user_ids(user):
    """Ids des pairs (même superviseur direct), soi-même inclus. Sans
    superviseur, l'arbre est plat → uniquement soi-même."""
    ids = {user.id}
    if user.supervisor_id:
        User = _company_user_model()
        base = User.objects.filter(supervisor_id=user.supervisor_id)
        if user.company_id:
            base = base.filter(company_id=user.company_id)
        ids |= set(base.values_list('id', flat=True))
    return ids


def visible_user_ids(user):
    """Ensemble d'ids dont ``user`` peut voir les enregistrements (soi inclus)."""
    scope = record_scope_for(user)
    if scope == 'all':
        return None  # None = aucun filtrage par propriétaire (voit tout)
    if scope == 'subtree':
        return subtree_user_ids(user)
    # team : pairs + son propre sous-arbre (au cas où il a des subordonnés).
    return peer_user_ids(user) | subtree_user_ids(user)


def scope_queryset(qs, user, owner_fields):
    """Restreint ``qs`` aux enregistrements dont l'un des ``owner_fields`` est
    dans la portée visible de ``user``. ``owner_fields`` = noms de FK
    propriétaire/assigné (ex. ['owner'], ['created_by', 'technicien_responsable']).

    Renvoie ``qs`` inchangé pour la portée 'all'. La société est déjà filtrée en
    amont (TenantMixin / _company_qs) ; on n'ajoute QUE le narrowing par
    propriétaire — jamais un re-filtrage société."""
    ids = visible_user_ids(user)
    if ids is None:
        return qs
    cond = Q()
    for field in owner_fields:
        cond |= Q(**{f'{field}__in': ids})
    return qs.filter(cond).distinct()


def scope_client_queryset(qs, user):
    """Le Client n'a pas de propriétaire propre : on le rattache aux documents
    visibles (devis/factures/avoirs créés par un utilisateur visible, ou leads
    dont le responsable est visible). Portée 'all' → inchangé."""
    ids = visible_user_ids(user)
    if ids is None:
        return qs
    return qs.filter(
        Q(devis__created_by_id__in=ids)
        | Q(factures__created_by_id__in=ids)
        | Q(avoirs__created_by_id__in=ids)
        | Q(leads__owner_id__in=ids)
    ).distinct()
