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

    Chaque entrée : dict {key, libelle, ordre, lien, fait (bool), complete_le,
    event_key}. Filtrée par rôle (``roles_cibles`` vide = tous) et
    company-scopée via le progrès de l'utilisateur courant.

    WIR59 — ``event_key`` est exposé pour que le frontend sache quels items
    n'ont AUCUN déclencheur automatique (``core.events``) : ceux-là seuls
    proposent un bouton « Marquer comme fait » manuel (l'alternative
    explicitement autorisée quand aucun événement de bus n'existe pour ce
    jalon, ex. configurer_societe/import_clients/inviter_coequipier)."""
    from .models import OnboardingChecklistItem, OnboardingProgress
    role_nom = _role_nom(user)
    # NTDMO28 — un item masqué PAR CETTE société (table de jonction
    # ``masque_pour``) n'apparaît jamais dans SA checklist, mais reste
    # inchangé pour toute autre société (jamais supprimé du catalogue).
    masques = set()
    if company is not None:
        masques = set(
            OnboardingChecklistItem.objects.filter(masque_pour=company)
            .values_list('id', flat=True))
    items = [
        it for it in OnboardingChecklistItem.objects.filter(actif=True)
        if it.concerne_role(role_nom) and it.id not in masques
    ]
    progress = {
        p.item_id: p for p in OnboardingProgress.objects.filter(
            company=company, user=user,
            item__in=[it.id for it in items])
    }
    resolved = []
    for it in items:
        p = progress.get(it.id)
        # Un item IGNORÉ (masqué manuellement) est retiré de la liste.
        if p is not None and p.ignore_le is not None:
            continue
        resolved.append({
            'id': it.id,
            'key': it.key,
            'libelle': it.libelle,
            'ordre': it.ordre,
            'lien': it.lien,
            'fait': bool(p and p.complete_le is not None),
            'complete_le': p.complete_le if p else None,
            'event_key': it.event_key,
        })
    return resolved


# ── NTDMO14/16 — catalogue des visites guidées (product tours) ─────────────
def tours_pour_utilisateur(company, user):
    """Retourne les 6 tours (catalogue NTDMO14) résolus pour ``user`` :
    liste de dicts {tour_key, ecran_cible, vu (bool), vu_le, etapes:
    [{ordre, selecteur, titre, texte}, ...]}, chargeable en UN seul appel
    réseau (NTDMO14 — pas de requête bloquante par tour)."""
    from .models import ProductTourStep, TourProgress
    steps = ProductTourStep.objects.all().order_by('tour_key', 'ordre')
    by_tour = {}
    for s in steps:
        by_tour.setdefault(s.tour_key, {
            'tour_key': s.tour_key,
            'ecran_cible': s.ecran_cible,
            'etapes': [],
        })
        by_tour[s.tour_key]['etapes'].append({
            'ordre': s.ordre,
            'selecteur': s.selecteur,
            'titre': s.titre,
            'texte': s.texte,
        })
    progress = {}
    if company is not None and user is not None and getattr(user, 'pk', None):
        progress = {
            p.tour_key: p for p in TourProgress.objects.filter(
                company=company, user=user, tour_key__in=list(by_tour))
        }
    resolved = []
    for tour_key, tour in by_tour.items():
        p = progress.get(tour_key)
        resolved.append({
            **tour,
            'vu': bool(p and p.vu_le is not None),
            'vu_le': p.vu_le if p else None,
        })
    return resolved


# ── NTDMO28 — items masquables (écran Paramètres → Démo & Onboarding) ──────
def items_masquables_pour_societe(company):
    """Retourne le catalogue GLOBAL (``company`` NULL) : liste de dicts
    {id, key, libelle, masque (bool)} — ``masque`` = cette société a masqué
    cet item (jamais une suppression, réversible). Utilisé par l'écran
    Paramètres qui permet à un admin de masquer un item non pertinent pour
    son activité (ex. « pompage agricole » pour une société 100 %
    résidentielle)."""
    from .models import OnboardingChecklistItem
    items = (
        OnboardingChecklistItem.objects
        .filter(company__isnull=True)
        .order_by('ordre', 'key'))
    masques = set()
    if company is not None:
        masques = set(
            items.filter(masque_pour=company).values_list('id', flat=True))
    return [
        {'id': it.id, 'key': it.key, 'libelle': it.libelle,
         'masque': it.id in masques}
        for it in items
    ]


# ── NTDMO22/23 — catalogue des tours (sans progression) pour le kit démo ───
def catalogue_ecrans_money_path():
    """Retourne les 6 tours (catalogue NTDMO14), un dict par tour_key :
    {tour_key, ecran_cible, titre} (titre = 1re étape). Utilisé par le kit de
    démonstration (NTDMO22/23) — jamais de progression utilisateur ici."""
    from .models import ProductTourStep
    steps = ProductTourStep.objects.all().order_by('tour_key', 'ordre')
    by_tour = {}
    for s in steps:
        by_tour.setdefault(s.tour_key, {
            'tour_key': s.tour_key, 'ecran_cible': s.ecran_cible,
            'titre': s.titre,
        })
    return list(by_tour.values())


def resume_pour_utilisateur(company, user):
    """Résumé pour le widget « Premiers pas » : {items, faits, total, pourcentage,
    termine}. ``termine`` = plus aucun item à faire (100 % ou tout ignoré)."""
    items = checklist_pour_utilisateur(company, user)
    total = len(items)
    faits = sum(1 for it in items if it['fait'])
    pourcentage = round(100 * faits / total) if total else 100
    return {
        'items': items,
        'faits': faits,
        'total': total,
        'pourcentage': pourcentage,
        'termine': total == 0 or faits == total,
        # NTDMO26 — vrai seulement pour une société RÉELLE (jamais démo)
        # fraîchement créée (< 30 j) dont l'assistant first-run
        # (/onboarding/demarrage) n'a ni été complété ni passé. Le frontend
        # (``PremiersPasWidget``) y navigue alors automatiquement, une fois —
        # même fenêtre de 30 j que les visites guidées (NTDMO15).
        'assistant_demarrage_auto': _assistant_demarrage_auto(company, items),
    }


def _assistant_demarrage_auto(company, items):
    """NTDMO26 — voir ``resume_pour_utilisateur``. Jamais sur une société
    de démonstration, jamais si l'item a déjà été fait/ignoré (dans ce cas il
    n'apparaît plus dans ``items``, cf. ``checklist_pour_utilisateur``)."""
    if company is None or getattr(company, 'est_demo', False):
        return False
    date_creation = getattr(company, 'date_creation', None)
    if date_creation is None:
        return False
    from django.utils import timezone
    age_jours = (timezone.now() - date_creation).days
    if age_jours < 0 or age_jours >= 30:
        return False
    return any(
        it['key'] == 'assistant_demarrage' and not it['fait'] for it in items)
