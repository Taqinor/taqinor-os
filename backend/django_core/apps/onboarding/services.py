"""Services onboarding (NTDMO11-13) — écritures / orchestration.

``core`` reste fondation : ce module ne dépend d'aucune app métier (il ne fait
que lire/écrire ses propres modèles ``onboarding`` + résoudre le rôle via
l'utilisateur porté par la requête/le signal).
"""
from django.utils import timezone


# Catalogue par défaut des items « Premiers pas » (globaux, company=None).
# (key, libellé, ordre, rôles cibles [vide = tous], lien, event_key).
#
# WIR59 — sur les 6 items, seuls premier_devis/premier_paiement avaient un
# event_key : configurer_societe/import_clients/inviter_coequipier/
# premier_chantier ne se complétaient JAMAIS (seul « Ignorer » les masquait).
# premier_chantier gagne ici un event_key réel ('chantier', câblé sur
# core.events.intervention_completed dans receivers.py — un jalon observable
# du cycle de vie chantier, même patron que devis/paiement). Les 3 autres
# n'ont AUCUN événement core.events approprié sans importer une app métier
# depuis onboarding (violerait la frontière cross-app) : ils restent
# complétables via l'action manuelle explicite « Marquer comme fait »
# (marquer_fait_manuel ci-dessous, alternative EXPLICITEMENT prévue par le
# founder quand aucun jalon de bus n'existe).
DEFAULT_ITEMS = [
    # NTDMO26 — item de suivi de l'assistant first-run « Configurez votre
    # société en 5 minutes » (/onboarding/demarrage, société RÉELLE non-démo
    # fraîchement créée). `ignore_le` posé = « Passer » a été cliqué : le
    # wizard ne se redéclenche plus jamais automatiquement pour cet
    # utilisateur (réutilise `ignorer_item` existant, aucun nouveau modèle).
    ('assistant_demarrage', 'Assistant de démarrage rapide (5 min)', 5,
     ['Administrateur', 'Directeur'], '/onboarding/demarrage', ''),
    ('configurer_societe', 'Configurer votre société', 10,
     ['Administrateur', 'Directeur'], '/parametres', ''),
    # NTDMO26 — sous-étape « premier produit du catalogue » de l'assistant
    # first-run (aucun event_key adapté sans importer `stock` — complétion
    # manuelle explicite, même patron que les items sans event_key ci-dessous).
    ('premier_produit', 'Ajouter votre premier produit', 15,
     ['Administrateur', 'Directeur'], '/stock', ''),
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
     '/chantiers', 'chantier'),
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


def marquer_fait_manuel(company, user, item_id):
    """WIR59 — coche manuellement un item PAR SON ID, SANS événement de bus
    correspondant (alternative explicite quand aucun ``core.events`` adapté
    n'existe pour ce jalon — ex. configurer_societe/import_clients/
    inviter_coequipier). Idempotent, ne dé-coche jamais. Renvoie le
    ``OnboardingProgress`` ou None (item inconnu/inactif ou company/user
    manquant)."""
    if company is None or user is None or not getattr(user, 'pk', None):
        return None
    from .models import OnboardingChecklistItem
    item = OnboardingChecklistItem.objects.filter(
        pk=item_id, actif=True).first()
    if item is None:
        return None
    return marquer_item_complete(company, user, item.key)


def completer_par_evenement(event_key, company, user):
    """Coche tous les items dont ``event_key`` correspond (NTDMO12)."""
    if not event_key or company is None or user is None:
        return
    from .models import OnboardingChecklistItem
    keys = OnboardingChecklistItem.objects.filter(
        event_key=event_key, actif=True).values_list('key', flat=True)
    for key in keys:
        marquer_item_complete(company, user, key)


# ── NTDMO14 — catalogue des 6 visites guidées (product tours) ──────────────
# Un tour par écran money-path déjà construit. Chaque tuple :
# (tour_key, ordre, sélecteur CSS, titre, texte FR, écran_cible).
# ``écran_cible`` est répété sur chaque étape (dénormalisé, lecture simple) —
# toutes les étapes d'un même ``tour_key`` portent le même écran.
DEFAULT_TOUR_STEPS = [
    # Tour « devis » — création de devis.
    ('devis', 10, '', 'Créer un devis',
     'Composez votre devis solaire en quelques clics : marché, produits, '
     'remise — tout se calcule automatiquement.', '/ventes/devis/nouveau'),
    ('devis', 20, '[data-tour="devis-marche"]', 'Choisissez le marché',
     'Résidentiel, Industriel/Commercial ou Agricole : chaque mode adapte '
     'les champs et les calculs à votre client.', '/ventes/devis/nouveau'),
    ('devis', 30, '[data-tour="devis-lignes"]', 'Ajoutez vos produits',
     'Chaque ligne calcule son total HT ; la remise et la TVA se répercutent '
     'automatiquement jusqu\'au total TTC.', '/ventes/devis/nouveau'),
    # Tour « leads » — kanban CRM.
    ('leads', 10, '', 'Suivre vos prospects',
     "Le kanban CRM affiche vos leads classés par étape du pipeline, de "
     "nouveau à signé.", '/crm/leads'),
    ('leads', 20, '[data-tour="leads-kanban"]', 'Faites glisser une carte',
     'Déplacez un lead entre les colonnes pour faire avancer son étape — '
     'chaque mouvement est journalisé.', '/crm/leads'),
    # Tour « factures » — facturation.
    ('factures', 10, '', 'Facturer un client',
     'Retrouvez ici toutes vos factures, leur statut de paiement et les '
     'relances en retard.', '/ventes/factures'),
    ('factures', 20, '[data-tour="factures-liste"]', 'Suivez les encaissements',
     'Le statut de chaque facture (payée, en retard, partielle) est visible '
     'd\'un coup d\'œil.', '/ventes/factures'),
    # Tour « chantiers » — suivi chantier.
    ('chantiers', 10, '', 'Suivre un chantier',
     'De la planification à la réception, suivez chaque étape de vos '
     'installations.', '/chantiers'),
    ('chantiers', 20, '[data-tour="chantiers-liste"]', 'Consultez le planning',
     "Chaque chantier affiche son avancement et l'équipe assignée.",
     '/chantiers'),
    # Tour « stock » — catalogue.
    ('stock', 10, '', 'Gérer votre catalogue',
     'Panneaux, onduleurs, batteries : gérez vos produits et leurs prix '
     'depuis cet écran.', '/stock'),
    ('stock', 20, '[data-tour="stock-liste"]', 'Ajoutez un produit',
     'Un nouveau produit apparaît immédiatement dans le générateur de '
     'devis.', '/stock'),
    # Tour « dashboard » — lecture des KPI.
    ('dashboard', 10, '', 'Votre tableau de bord',
     'Vue d\'ensemble de votre activité : devis envoyés, chantiers en cours, '
     'chiffre d\'affaires.', '/dashboard'),
    ('dashboard', 20, '[data-tour="dashboard-kpi"]', 'Lisez vos indicateurs',
     'Chaque tuile résume un indicateur clé — cliquez pour le détail.',
     '/dashboard'),
]


def seed_default_tour_steps(model=None):
    """Crée/complète le catalogue global des étapes de tours (idempotent, par
    ``(tour_key, ordre)``)."""
    if model is None:
        from .models import ProductTourStep as model
    for tour_key, ordre, selecteur, titre, texte, ecran_cible in DEFAULT_TOUR_STEPS:
        obj = model.objects.filter(tour_key=tour_key, ordre=ordre).first()
        values = {
            'company': None, 'selecteur': selecteur, 'titre': titre,
            'texte': texte, 'ecran_cible': ecran_cible,
        }
        if obj is None:
            model.objects.create(tour_key=tour_key, ordre=ordre, **values)
        else:
            for field, val in values.items():
                setattr(obj, field, val)
            obj.save()


def marquer_tour_vu(company, user, tour_key):
    """NTDMO16 — marque un tour comme vu/fermé pour ``user`` (idempotent,
    company-scopé). Renvoie le ``TourProgress`` ou None si company/user
    manquent."""
    if company is None or user is None or not getattr(user, 'pk', None):
        return None
    from django.utils import timezone

    from .models import TourProgress
    progress = TourProgress.objects.filter(user=user, tour_key=tour_key).first()
    if progress is None:
        progress = TourProgress.objects.create(
            company=company, user=user, tour_key=tour_key)
    if progress.vu_le is None:
        progress.vu_le = timezone.now()
        progress.save(update_fields=['vu_le'])
    return progress


def reinitialiser_tour(company, user, tour_key):
    """NTDMO16 — bouton « Revoir » : remet le tour à zéro (``vu_le=None``)
    pour cet utilisateur SEULEMENT, afin qu'il réapparaisse à la prochaine
    visite de l'écran cible."""
    if company is None or user is None or not getattr(user, 'pk', None):
        return None
    from .models import TourProgress
    progress = TourProgress.objects.filter(
        company=company, user=user, tour_key=tour_key).first()
    if progress is not None and progress.vu_le is not None:
        progress.vu_le = None
        progress.save(update_fields=['vu_le'])
    return progress
