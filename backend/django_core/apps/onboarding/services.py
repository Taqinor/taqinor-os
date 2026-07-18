"""Services onboarding (NTDMO11-13) — écritures / orchestration.

``core`` reste fondation : ce module ne dépend d'aucune app métier (il ne fait
que lire/écrire ses propres modèles ``onboarding`` + résoudre le rôle via
l'utilisateur porté par la requête/le signal).
"""
from django.utils import timezone


# Catalogue par défaut des items « Premiers pas » (globaux, company=None).
# (key, libellé, ordre, rôles cibles [vide = tous], lien, event_key).
DEFAULT_ITEMS = [
    ('configurer_societe', 'Configurer votre société', 10,
     ['Administrateur', 'Directeur'], '/parametres', ''),
    ('import_clients', 'Importer vos clients', 20,
     [], '/crm/clients', ''),
    ('premier_devis', 'Créer votre 1er devis', 30,
     ['Commercial', 'Commercial responsable', 'Administrateur', 'Directeur'],
     '/ventes/devis/nouveau', 'devis'),
    ('premier_paiement', 'Encaisser votre 1er paiement', 40,
     ['Commercial responsable', 'Administrateur', 'Directeur'],
     '/ventes/factures', 'paiement'),
    ('inviter_coequipier', 'Inviter un coéquipier', 50,
     ['Administrateur', 'Directeur'], '/admin/users', ''),
    ('premier_chantier', 'Suivre votre 1er chantier', 60,
     ['Technicien', 'Technicien responsable', 'Administrateur'],
     '/chantiers', ''),
]


def seed_default_items(model=None):
    """Crée/complète le catalogue global d'items (idempotent, par ``key``).

    ``model`` permet de passer le modèle historique dans une migration de
    données ; en usage normal on importe le modèle réel.
    """
    if model is None:
        from .models import OnboardingChecklistItem as model
    for key, libelle, ordre, roles, lien, event_key in DEFAULT_ITEMS:
        # Idempotent par ``key`` (unique) sans get_or_create : met à jour le
        # catalogue global existant, sinon le crée.
        obj = model.objects.filter(key=key).first()
        values = {
            'company': None, 'libelle': libelle, 'ordre': ordre,
            'roles_cibles': roles, 'lien': lien, 'event_key': event_key,
            'actif': True,
        }
        if obj is None:
            model.objects.create(key=key, **values)
        else:
            for field, val in values.items():
                setattr(obj, field, val)
            obj.save()


def marquer_item_complete(company, user, item_key):
    """Coche un item pour ``user`` (idempotent, ne dé-coche jamais).

    No-op si l'item est inconnu/inactif ou si company/user manque. Renvoie le
    ``OnboardingProgress`` (ou None)."""
    if company is None or user is None or not getattr(user, 'pk', None):
        return None
    from .models import OnboardingChecklistItem, OnboardingProgress
    item = OnboardingChecklistItem.objects.filter(
        key=item_key, actif=True).first()
    if item is None:
        return None
    # Idempotent sur l'unique (user, item) sans get_or_create.
    progress = OnboardingProgress.objects.filter(user=user, item=item).first()
    if progress is None:
        progress = OnboardingProgress.objects.create(
            company=company, user=user, item=item)
    if progress.complete_le is None:
        progress.complete_le = timezone.now()
        progress.save(update_fields=['complete_le'])
    return progress


def ignorer_item(company, user, item_id):
    """NTDMO13 — masque manuellement un item pour ``user`` (persistant), sans le
    marquer fait. Idempotent. Renvoie le ``OnboardingProgress`` ou None."""
    if company is None or user is None or not getattr(user, 'pk', None):
        return None
    from .models import OnboardingChecklistItem, OnboardingProgress
    item = OnboardingChecklistItem.objects.filter(
        pk=item_id, actif=True).first()
    if item is None:
        return None
    progress = OnboardingProgress.objects.filter(user=user, item=item).first()
    if progress is None:
        progress = OnboardingProgress.objects.create(
            company=company, user=user, item=item)
    if progress.ignore_le is None:
        progress.ignore_le = timezone.now()
        progress.save(update_fields=['ignore_le'])
    return progress


def ignorer_tout(company, user):
    """NTDMO13 — masque TOUS les items restants (à faire) de l'utilisateur."""
    from .selectors import checklist_pour_utilisateur
    for it in checklist_pour_utilisateur(company, user):
        if not it['fait']:
            ignorer_item(company, user, it['id'])


def completer_par_evenement(event_key, company, user):
    """Coche tous les items dont ``event_key`` correspond (NTDMO12)."""
    if not event_key or company is None or user is None:
        return
    from .models import OnboardingChecklistItem
    keys = OnboardingChecklistItem.objects.filter(
        event_key=event_key, actif=True).values_list('key', flat=True)
    for key in keys:
        marquer_item_complete(company, user, key)
