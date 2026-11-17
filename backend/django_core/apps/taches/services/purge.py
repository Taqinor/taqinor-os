"""Purges et rétention (reference/donnees.md §8 ; conception/arbitrages.md A15).

Étape de nuit appelée par `nocturne.executer` (TCH37) ; remplie par TCH75. Suppressions DURES, par
date, pour UNE société : rejouer la nuit ne supprime rien de plus (idempotent). Rien ne passe par la
corbeille de l'ERP (invariant 26) : aucune ligne `taches` n'y est jamais inscrite.

« Comprendre mon rythme » coupé efface son profil au moment où il est coupé (`PATCH reglages/`,
TCH69), pas ici ; les événements des agendas externes ne sont jamais en base (cache seul).
"""
import datetime

from django.db.models import Exists, OuterRef
from django.utils import timezone

from apps.taches.choix import StatutRappel
from apps.taches.models.erp import SuggestionTache
from apps.taches.models.gestes import GesteAnnulable
from apps.taches.models.journee import LignePlanJour, PlanJour
from apps.taches.models.projets import Projet
from apps.taches.models.rythme import IncitationCoach
from apps.taches.models.taches import Rappel, Tache

#: Durées de conservation en jours (reference/donnees.md §8).
JOURS_PLAN_JOUR = 400
JOURS_LIGNE_PLAN = 90
JOURS_INCITATION = 90
JOURS_RAPPEL_CLOS = 30
JOURS_GESTE = 7
JOURS_SUGGESTION = 30
JOURS_SUPPRIME = 30


def _avant(jour, jours):
    """Le jour `jour` − `jours` : tout ce qui est strictement avant est purgé."""
    return jour - datetime.timedelta(days=jours)


def _instant(jour, jours):
    """Minuit (heure murale de la société) du jour `jour` − `jours`."""
    return timezone.make_aware(datetime.datetime.combine(_avant(jour, jours), datetime.time.min))


def _supprimes(company_id, jour):
    """Tâches puis projets supprimés depuis plus de 30 jours ; un projet qui porte encore une tâche
    vivante (restaurée seule) n'est jamais emporté avec elle."""
    limite = _instant(jour, JOURS_SUPPRIME)
    taches, _ = Tache.all_objects.filter(
        company_id=company_id, is_deleted=True, deleted_at__lt=limite).delete()
    vivantes = Tache.objects.filter(projet=OuterRef('pk'))
    projets, _ = (Projet.all_objects.filter(company_id=company_id, is_deleted=True, deleted_at__lt=limite)
                  .exclude(Exists(vivantes)).delete())
    return {'taches_supprimees': taches, 'projets_supprimes': projets}


def purger(company_id, jour):
    """Nuit du `jour` : rétentions de donnees.md §8 pour la société (PlanJour 400 j, LignePlanJour et
    IncitationCoach 90 j, Rappel clos 30 j, GesteAnnulable 7 j, SuggestionTache 30 j, tâche ou projet
    supprimé 30 j puis suppression dure) → nombre de lignes supprimées par famille."""
    purges = {
        'lignes_plan': LignePlanJour.objects.filter(
            company_id=company_id, plan__jour__lt=_avant(jour, JOURS_LIGNE_PLAN)),
        'plans_jour': PlanJour.objects.filter(company_id=company_id, jour__lt=_avant(jour, JOURS_PLAN_JOUR)),
        'incitations': IncitationCoach.objects.filter(
            company_id=company_id, jour__lt=_avant(jour, JOURS_INCITATION)),
        'rappels_clos': Rappel.objects.filter(
            company_id=company_id, jour__lt=_avant(jour, JOURS_RAPPEL_CLOS),
        ).exclude(statut=StatutRappel.EN_ATTENTE),
        'gestes': GesteAnnulable.objects.filter(
            company_id=company_id, created_at__lt=_instant(jour, JOURS_GESTE)),
        'suggestions': SuggestionTache.objects.filter(
            company_id=company_id, created_at__lt=_instant(jour, JOURS_SUGGESTION)),
    }
    comptes = {nom: qs.delete()[0] for nom, qs in purges.items()}
    comptes.update(_supprimes(company_id, jour))
    return comptes
