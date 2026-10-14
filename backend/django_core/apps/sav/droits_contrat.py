"""Droits inclus d'un contrat de maintenance (XCTR3/ASAV5) — feuille PURE (ENF20).

Ce module ne lit que ``sav.Ticket`` : aucun import d'un autre domaine. C'est ce
qui permet à ``Ticket.couverture`` (sav/models.py) de l'appeler sans passer par
``sav.selectors``, dont la couche traverse les domaines (contrat import-linter
``core-domain-models-decoupled`` : un models.py ne tire jamais son selectors).
``sav.selectors`` ré-exporte ``droits_restants`` pour ses appelants historiques.
"""
from django.utils import timezone

from .models import Ticket


def droits_restants(contrat, annee=None, *, ticket=None, cache=None):
    """XCTR3 — Compteurs de droits inclus (entitlements) consommés/restants
    pour ``contrat`` sur l'année civile ``annee`` (défaut : année courante).

    Compte les tickets PREVENTIF (visites) et CORRECTIF (déplacements) NON
    ANNULÉS dont ``date_ouverture`` tombe dans l'année demandée, rattachés au
    contrat par son chantier, ou — ASAV5 — par son CLIENT quand le contrat n'a
    pas de chantier. Un quota NULL sur le contrat = illimité : le champ
    ``restant`` renvoie ``None`` (pas de division/quota calculée).

    ASAV5 — avec ``ticket`` (le ticket ÉVALUÉ) on ne compte que les tickets
    ANTÉRIEURS : le ticket lui-même est exclu et seuls ceux ouverts au plus
    tard à sa date (à date égale, créés avant lui) consomment un droit — un
    quota de N couvre donc exactement les N premiers tickets. Sans ``ticket``
    (écran des contrats) : compteur de l'année, tous tickets non annulés.

    APRF31 — ``cache`` (dict ``{(contrat_id, année): lignes}`` fourni par la
    liste) : les tickets de l'année du contrat sont lus UNE fois par page et
    comptés en Python — jamais deux ``count()`` par ticket.
    """
    from datetime import date as _date

    annee = annee or timezone.localdate().year
    debut = _date(annee, 1, 1)
    fin = _date(annee, 12, 31)

    cle = (contrat.pk, annee)
    lignes = cache.get(cle) if cache is not None else None
    if lignes is None:
        base_qs = Ticket.objects.filter(
            company_id=contrat.company_id, annule=False,
            date_ouverture__gte=debut, date_ouverture__lte=fin,
        )
        if contrat.installation_id:
            base_qs = base_qs.filter(installation_id=contrat.installation_id)
        elif contrat.client_id:
            base_qs = base_qs.filter(client_id=contrat.client_id)
        else:
            base_qs = base_qs.none()
        lignes = list(base_qs.values_list('type', 'date_ouverture', 'pk'))
        if cache is not None:
            cache[cle] = lignes
    if ticket is not None:
        ref = ticket.date_reference_couverture
        lignes = [
            (t, d, pk) for t, d, pk in lignes
            if pk != ticket.pk and (
                d < ref or (d == ref and (not ticket.pk or pk < ticket.pk)))
        ]
    visites_consommees = sum(
        1 for t, _d, _pk in lignes if t == Ticket.Type.PREVENTIF)
    deplacements_consommes = sum(
        1 for t, _d, _pk in lignes if t == Ticket.Type.CORRECTIF)

    def _restant(inclus, consomme):
        if inclus is None:
            return None
        return max(0, inclus - consomme)

    return {
        'annee': annee,
        'visites_incluses_an': contrat.visites_incluses_an,
        'visites_consommees': visites_consommees,
        'visites_restantes': _restant(
            contrat.visites_incluses_an, visites_consommees),
        'deplacements_inclus_an': contrat.deplacements_inclus_an,
        'deplacements_consommes': deplacements_consommes,
        'deplacements_restants': _restant(
            contrat.deplacements_inclus_an, deplacements_consommes),
    }
