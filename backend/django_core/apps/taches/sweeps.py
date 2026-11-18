"""Tâches planifiées de l'app `taches` (reference/api.md §9), file `scheduled`.

- `taches.nocturne` — 03:00 `Africa/Casablanca` (beat `taches-nocturne`, `_expire_dans(3600)`) :
  `nocturne.executer(company_id, jour)` pour chaque société ACTIVE (`active_companies()`, SCA19) où le
  module `taches` est actif (`core.feature_flags.module_actif`) — coupe-circuit compris : la clôture
  d'hier, le rythme (cartes d'écran, rien n'est envoyé), la revérification des liens et les purges de
  rétention tournent TOUJOURS (décision de la fusion 2 ; regles.md §13 ne lie le coupe-circuit qu'à
  l'ENVOI). Société inactive ou module éteint : RIEN.
- `taches.balayer` — chaque minute (beat `taches-balayer`, `_expire_dans(60)`) : `balayage.executer()`,
  seul ENVOI de sollicitations et de rappels, pour `societes_a_balayer()` (coupe-circuit
  `ReglagesSociete.balayage_actif` relu à chaque passage ; absent = actif).
"""
import logging

from celery import shared_task
from django.utils import timezone

from apps.taches import balayage, nocturne
from apps.taches.models.presence import ReglagesSociete
from authentication.selectors import active_companies
from core.feature_flags import module_actif

logger = logging.getLogger(__name__)

#: Clé `ModuleToggle` du module (`apps.py` `module_manifest['key']`).
MODULE = 'taches'
#: Limites du passage de nuit : sous l'expiration du message beat (`_expire_dans(3600)`).
LIMITE_DOUCE_SECONDES = 3300
LIMITE_DURE_SECONDES = 3500
#: Limites du balayage de chaque minute : sous l'expiration du message beat (`_expire_dans(60)`).
BALAYAGE_LIMITE_DOUCE_SECONDES = 50
BALAYAGE_LIMITE_DURE_SECONDES = 58


def societes_du_module():
    """Ids des sociétés actives dont le module `taches` est actif, par id croissant (la nuit)."""
    return [societe.pk for societe in active_companies() if module_actif(societe, MODULE)]


def societes_a_balayer():
    """Ids des sociétés du module dont le balayage (ENVOI de sollicitations et de rappels) n'est pas
    coupé, par id croissant."""
    societes = societes_du_module()
    coupees = set(ReglagesSociete.objects.filter(company_id__in=societes, balayage_actif=False)
                  .values_list('company_id', flat=True))
    return [company_id for company_id in societes if company_id not in coupees]


@shared_task(name='taches.nocturne', soft_time_limit=LIMITE_DOUCE_SECONDES, time_limit=LIMITE_DURE_SECONDES)
def nocturne_quotidienne():
    """La nuit des tâches personnelles : une `nocturne.executer` par société du module (le jour local
    du passage), coupe-circuit compris (la nuit n'envoie rien) ; chaque étape est journalisée et isolée
    par `nocturne`."""
    jour = timezone.localdate()
    societes = societes_du_module()
    for company_id in societes:
        nocturne.executer(company_id, jour)
    logger.info('taches.nocturne : %s société(s) traitée(s) pour le %s', len(societes), jour)
    return {'societes': len(societes), 'jour': jour.isoformat()}


@shared_task(name='taches.balayer', soft_time_limit=BALAYAGE_LIMITE_DOUCE_SECONDES,
             time_limit=BALAYAGE_LIMITE_DURE_SECONDES)
def balayer():
    """Le balayage de chaque minute : rappels posés et sollicitations des sociétés à balayer
    (`balayage.executer`, qui relit le coupe-circuit à chaque passage) ; rejouer n'envoie rien de plus."""
    bilan = balayage.executer()
    logger.info('taches.balayer : %s', bilan)
    return bilan
