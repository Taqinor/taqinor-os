"""Révélations serveur créées à LEUR événement (reference/donnees.md I14 ; textes.md « Révélations »).

Une révélation est une carte d'écran `IncitationCoach` (`type='revelation'`, `canal='ecran'`) ; son
texte est rendu à la lecture (`serializers/rythme.py`), rien n'est stocké que des nombres et des ids.
Une par jour au plus, une seule fois chacune :

- `apres_creation` — le crochet que `creer_taches` appelle, dans sa transaction, après chaque création
  réussie : `planifier_projet` (1er projet créé) puis `ranger_copilote` (À trier ≥ 5) ; `mon_iphone`
  (1er collage créé) est branché par TCH109.
- `revelation_revue` — étape de la nuit (`services/rythme._nuit_du_compte`) : fin de la 1re semaine.
"""
import datetime

from django.utils import timezone

from apps.taches.choix import CanalIncitation, StatutTache, TypeIncitationEcran
from apps.taches.models.projets import Projet
from apps.taches.selectors.base import taches_de
from apps.taches.selectors.rythme import cartes_de
from apps.taches.services.rythme import creer_carte

PLANIFIER_PROJET = 'planifier_projet'
RANGER_COPILOTE = 'ranger_copilote'
REVUE = 'revue'
#: « À trier ≥ 5 » (textes.md « Révélations »).
A_TRIER_MIN = 5
#: « Fin de la 1re semaine » : 7 jours après la naissance des réglages (la première tâche, inv. 29).
PREMIERE_SEMAINE = datetime.timedelta(days=7)


def _revelations(user):
    return cartes_de(user).filter(type=TypeIncitationEcran.REVELATION, canal=CanalIncitation.ECRAN)


def _peut_reveler(user, cle, jour):
    """Une seule fois chacune, une par jour au plus."""
    revelations = _revelations(user)
    return not revelations.filter(cle=cle).exists() and not revelations.filter(jour=jour).exists()


def _nb_a_trier(user):
    """Invariant 1 : vivantes, sans parent, sans projet, jamais triées, à faire ou en attente."""
    return taches_de(user).filter(parent__isnull=True, projet__isnull=True, triee_le__isnull=True,
                                  statut__in=(StatutTache.A_FAIRE, StatutTache.EN_ATTENTE)).count()


def _premier_projet(user, projets_crees):
    """Les projets créés sont les SEULS que le compte ait jamais eus (supprimés compris)."""
    if not projets_crees:
        return None
    tous = Projet.all_objects.filter(company_id=user.company_id, proprietaire=user).count()
    return projets_crees[0] if tous == len(projets_crees) else None


def apres_creation(user, creees, projets_crees, *, porte):
    """Après la création de `creees` (et des `projets_crees`) par `user`, par la porte `porte`."""
    jour = timezone.localdate()
    projet = _premier_projet(user, list(projets_crees))
    if projet is not None and _peut_reveler(user, PLANIFIER_PROJET, jour):
        return creer_carte(user, TypeIncitationEcran.REVELATION, PLANIFIER_PROJET, jour, {'projet_id': projet.pk})
    if creees and _peut_reveler(user, RANGER_COPILOTE, jour):
        n = _nb_a_trier(user)
        if n >= A_TRIER_MIN:
            return creer_carte(user, TypeIncitationEcran.REVELATION, RANGER_COPILOTE, jour, {'n': n})
    return None


def revelation_revue(user, reglages, jour):
    """Nuit du `jour` : la révélation `revue` une fois la première semaine écoulée."""
    if reglages.created_at is None or timezone.localtime(reglages.created_at).date() + PREMIERE_SEMAINE > jour:
        return None
    if not _peut_reveler(user, REVUE, jour):
        return None
    return creer_carte(user, TypeIncitationEcran.REVELATION, REVUE, jour, {})
