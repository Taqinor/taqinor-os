"""Sélecteurs onboarding (lectures) — NTDMO11/13.

Résout la checklist « Premiers pas » pour un utilisateur : items du catalogue
filtrés par rôle, annotés du statut (fait/à faire) via ``OnboardingProgress``
company-scopé. Aucune dépendance app métier.
"""


def _role_nom(user):
    """Nom de rôle de l'utilisateur (``roles.Role.nom``), repli sur le legacy."""
    role = getattr(user, 'role', None)
    if role is not None:
        return getattr(role, 'nom', None)
    return getattr(user, 'role_legacy', None)


def checklist_pour_utilisateur(company, user):
    """Retourne la liste ordonnée d'items résolus pour ``user`` dans ``company``.

    Chaque entrée : dict {key, libelle, ordre, lien, fait (bool), complete_le}.
    Filtrée par rôle (``roles_cibles`` vide = tous) et company-scopée via le
    progrès de l'utilisateur courant.
    """
    from .models import OnboardingChecklistItem, OnboardingProgress
    role_nom = _role_nom(user)
    items = [
        it for it in OnboardingChecklistItem.objects.filter(actif=True)
        if it.concerne_role(role_nom)
    ]
    progress = {
        p.item_id: p for p in OnboardingProgress.objects.filter(
            company=company, user=user,
            item__in=[it.id for it in items])
    }
    resolved = []
    for it in items:
        p = progress.get(it.id)
        resolved.append({
            'id': it.id,
            'key': it.key,
            'libelle': it.libelle,
            'ordre': it.ordre,
            'lien': it.lien,
            'fait': bool(p and p.complete_le is not None),
            'complete_le': p.complete_le if p else None,
        })
    return resolved
