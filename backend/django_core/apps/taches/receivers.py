"""Abonnés de l'app `taches` au bus `core.events` (reference/donnees.md §5 ; conception/spec-6a-erp.md §3.2).

Le module est importé par `TachesConfig.ready()` : chaque `@receiver` s'abonne à l'import. Aucun
signal nouveau (`core/event_coverage.py`) ; chaque abonné est best-effort (`@abonne_best_effort`) :
une erreur ici n'arrête jamais l'émetteur.

TCH74 — première porte de l'effacement 09-08 : `lead_erased` (`company`, `crm_lead_id`, émis par
`crm` après l'anonymisation d'un lead, DSR ou rétention). La seconde porte est le fournisseur DSR
`taches` (`dsr.effacer_sujet`).

TCH71 — les suggestions venues de l'ERP (reference/regles.md §9 « Les suggestions venues de l'ERP »,
A3, A4). Ici, le PUR : gabarit du titre (SANS nom de client), clé anti-doublon et cible du lien ; le
destinataire strict et l'écriture vivent dans `services/erp.py` (`proposer_suggestion`,
`retirer_suggestion`). Les objets émis ne sont lus que par leurs attributs (`lead_id`, `pk`,
`company_id`) : aucun modèle d'une autre app n'est importé.
"""
from django.dispatch import receiver

from apps.taches.choix import CibleLiable, FamilleSuggestion
from core.events import (
    abonne_best_effort,
    chantier_annule,
    chantier_receptionne,
    devis_acceptation_annulee,
    devis_accepted,
    lead_erased,
    visite_validee,
)

#: Titre proposé par famille (regles.md §9 ; A4 : jamais le nom du client, il se lit par le lien).
TITRES = {
    FamilleSuggestion.DEVIS_ACCEPTE: 'Préparer le chantier du devis accepté',
    FamilleSuggestion.CHANTIER_RECEPTIONNE: 'Demander un avis au client : chantier réceptionné',
    FamilleSuggestion.CHANTIER_ANNULE: "Comprendre l'annulation du chantier",
    FamilleSuggestion.VISITE_VALIDEE: 'Préparer le devis : visite validée',
}


def cle_suggestion(famille, pk):
    """Clé anti-doublon `<famille>:<pk de l'objet émis>` (`devis_accepte:512`)."""
    return f'{famille}:{pk}'


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


# --- TCH71 : suggestions venues de l'ERP ---------------------------------------------------------

def _proposer(famille, company_id, objet_pk, lead_id, cible, cible_id):
    from apps.taches.services.erp import proposer_suggestion
    if company_id is None or objet_pk is None or not lead_id:
        return 0
    return proposer_suggestion(
        company_id, famille=famille, cle=cle_suggestion(famille, objet_pk), titre=TITRES[famille],
        lead_id=lead_id, cible=cible, cible_id=cible_id)


@receiver(devis_accepted, dispatch_uid='taches.suggerer_sur_devis_accepte')
@abonne_best_effort
def suggerer_sur_devis_accepte(sender, devis=None, avenant_de=None, **kwargs):
    """Devis accepté → « Préparer le chantier du devis accepté » au responsable du lead STRICT du
    devis (`devis.lead`, jamais le repli « dernier lead du client ») ; un avenant est ignoré."""
    if devis is None or avenant_de:
        return 0
    return _proposer(FamilleSuggestion.DEVIS_ACCEPTE, getattr(devis, 'company_id', None), devis.pk,
                     getattr(devis, 'lead_id', None), CibleLiable.DEVIS, devis.pk)


@receiver(devis_acceptation_annulee, dispatch_uid='taches.retirer_sur_acceptation_annulee')
@abonne_best_effort
def retirer_sur_acceptation_annulee(sender, devis=None, **kwargs):
    """Acceptation annulée → la suggestion ENCORE proposée de ce devis passe `retiree`."""
    if devis is None or getattr(devis, 'company_id', None) is None:
        return 0
    from apps.taches.services.erp import retirer_suggestion
    return retirer_suggestion(devis.company_id, cle_suggestion(FamilleSuggestion.DEVIS_ACCEPTE, devis.pk))


def _chantier(famille, installation):
    """Suggestion d'un chantier : destinataire et lien = le lead du chantier (A3, I16)."""
    if installation is None:
        return 0
    lead_id = getattr(installation, 'lead_id', None)
    return _proposer(famille, getattr(installation, 'company_id', None), installation.pk, lead_id,
                     CibleLiable.LEAD, lead_id)


@receiver(chantier_receptionne, dispatch_uid='taches.suggerer_sur_chantier_receptionne')
@abonne_best_effort
def suggerer_sur_chantier_receptionne(sender, installation=None, **kwargs):
    """Chantier réceptionné → « Demander un avis au client : chantier réceptionné »."""
    return _chantier(FamilleSuggestion.CHANTIER_RECEPTIONNE, installation)


@receiver(chantier_annule, dispatch_uid='taches.suggerer_sur_chantier_annule')
@abonne_best_effort
def suggerer_sur_chantier_annule(sender, installation=None, **kwargs):
    """Chantier annulé → « Comprendre l'annulation du chantier »."""
    return _chantier(FamilleSuggestion.CHANTIER_ANNULE, installation)


@receiver(visite_validee, dispatch_uid='taches.suggerer_sur_visite_validee')
@abonne_best_effort
def suggerer_sur_visite_validee(sender, visite=None, lead_id=None, **kwargs):
    """Visite validée → « Préparer le devis : visite validée » (famille éteinte par défaut)."""
    if visite is None:
        return 0
    return _proposer(FamilleSuggestion.VISITE_VALIDEE, getattr(visite, 'company_id', None), visite.pk,
                     lead_id, CibleLiable.LEAD, lead_id)
