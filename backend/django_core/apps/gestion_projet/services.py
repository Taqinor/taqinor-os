"""Services (écritures/orchestration) de la Gestion de projet.

Point d'entrée des écritures internes au module. ``company`` est toujours
dérivée du ``projet`` (jamais lue d'un corps de requête) ; aucun import
cross-app (on reste dans ``gestion_projet``).
"""
from datetime import timedelta

from django.db import transaction

from .models import DependanceTache, PhaseProjet, Projet, Tache


# Décomposition standard d'un projet d'installation solaire (WBS), dans l'ordre
# de réalisation. PROPRE à ce module — ne réutilise aucune clé de STAGES.py.
PHASES_STANDARD = [
    (PhaseProjet.TypePhase.ETUDE, 'Étude'),
    (PhaseProjet.TypePhase.APPRO, 'Approvisionnement'),
    (PhaseProjet.TypePhase.POSE, 'Pose'),
    (PhaseProjet.TypePhase.MES, 'Mise en service'),
    (PhaseProjet.TypePhase.RECEPTION, 'Réception'),
]


def instancier_phases_standard(projet):
    """Crée les 5 phases standard d'un ``Projet``, dans l'ordre — IDEMPOTENT.

    Une phase n'est créée que si elle n'existe pas déjà (clé
    ``(projet, type_phase)``) : un second appel ne duplique rien et laisse
    intactes les phases déjà présentes (statut/dates/avancement édités). La
    société est toujours celle du ``projet`` (jamais lue d'un corps de requête).
    Renvoie la liste complète des phases du projet, ordonnée par ``ordre``.
    """
    if not isinstance(projet, Projet):  # pragma: no cover - garde-fou
        raise TypeError('projet doit être une instance de Projet.')
    existants = set(
        projet.phases.values_list('type_phase', flat=True))
    a_creer = []
    for ordre, (type_phase, libelle) in enumerate(PHASES_STANDARD, start=1):
        if type_phase in existants:
            continue
        a_creer.append(PhaseProjet(
            company=projet.company,
            projet=projet,
            type_phase=type_phase,
            libelle=libelle,
            ordre=ordre,
        ))
    if a_creer:
        PhaseProjet.objects.bulk_create(a_creer)
    return list(projet.phases.order_by('ordre', 'id'))
