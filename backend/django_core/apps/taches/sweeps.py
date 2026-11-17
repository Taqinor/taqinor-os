"""Tâches planifiées de l'app `taches` (reference/api.md §9), file `scheduled`.

- `taches.nocturne` — 03:00 `Africa/Casablanca` (beat `taches-nocturne`, `_expire_dans(3600)`) :
  `nocturne.executer(company_id, jour)` pour chaque société ACTIVE (`active_companies()`, SCA19) où le
  module `taches` est actif (`core.feature_flags.module_actif`) et dont le coupe-circuit
  `ReglagesSociete.balayage_actif` n'est pas coupé (relu à chaque passage ; absent = actif). Une
  société exclue n'a RIEN de fait.
- `taches.balayer` — chaque minute : TCH174 (F3).
"""
import logging

from celery import shared_task
from django.utils import timezone

from apps.taches import nocturne
from apps.taches.models.presence import ReglagesSociete
from authentication.selectors import active_companies
from core.feature_flags import module_actif

logger = logging.getLogger(__name__)

#: Clé `ModuleToggle` du module (`apps.py` `module_manifest['key']`).
MODULE = 'taches'
#: Limites du passage de nuit : sous l'expiration du message beat (`_expire_dans(3600)`).
LIMITE_DOUCE_SECONDES = 3300
LIMITE_DURE_SECONDES = 3500


def societes_a_balayer():
    """Ids des sociétés actives dont le module est actif et le balayage non coupé, par id croissant."""
    societes = [societe for societe in active_companies() if module_actif(societe, MODULE)]
    coupees = set(ReglagesSociete.objects
                  .filter(company_id__in=[s.pk for s in societes], balayage_actif=False)
                  .values_list('company_id', flat=True))
    return [societe.pk for societe in societes if societe.pk not in coupees]


@shared_task(name='taches.nocturne', soft_time_limit=LIMITE_DOUCE_SECONDES, time_limit=LIMITE_DURE_SECONDES)
def nocturne_quotidienne():
    """La nuit des tâches personnelles : une `nocturne.executer` par société balayable (le jour local
    du passage) ; chaque étape est journalisée et isolée par `nocturne`."""
    jour = timezone.localdate()
    societes = societes_a_balayer()
    for company_id in societes:
        nocturne.executer(company_id, jour)
    logger.info('taches.nocturne : %s société(s) balayée(s) pour le %s', len(societes), jour)
    return {'societes': len(societes), 'jour': jour.isoformat()}
