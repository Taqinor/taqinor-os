"""Abonnés de l'app `taches` au bus `core.events` (reference/donnees.md §5 ; conception/spec-6a-erp.md §3.2).

Le module est importé par `TachesConfig.ready()` : chaque `@receiver` s'abonne à l'import. Aucun
signal nouveau (`core/event_coverage.py`) ; chaque abonné est best-effort (`@abonne_best_effort`) :
une erreur ici n'arrête jamais l'émetteur.

TCH74 — première porte de l'effacement 09-08 : `lead_erased` (`company`, `crm_lead_id`, émis par
`crm` après l'anonymisation d'un lead, DSR ou rétention). La seconde porte est le fournisseur DSR
`taches` (`dsr.effacer_sujet`).
"""
from django.dispatch import receiver

from core.events import abonne_best_effort, lead_erased


@receiver(lead_erased, dispatch_uid='taches.sur_lead_efface')
@abonne_best_effort
def sur_lead_efface(sender, company=None, crm_lead_id=None, **kwargs):
    """Le lead `crm_lead_id` est effacé : ses tâches liées perdent leur libellé (« Lead effacé »),
    ses suggestions sont supprimées, dans SA société seulement."""
    company_id = getattr(company, 'pk', company)
    if company_id is None or not crm_lead_id:
        return 0
    from apps.taches.services.donnees import effacer_cibles
    return effacer_cibles(company_id, leads=[crm_lead_id])
