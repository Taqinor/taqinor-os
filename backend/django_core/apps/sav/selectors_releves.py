"""ACAL845 — volumes d'eau MENSUELS mesurés, lus sur les index m³ du SAV.

Module frère de ``selectors.py`` (≥ 2 000 lignes, non touché) : l'appelant
(calepinage, ACAL846) importe ``apps.sav.selectors_releves``. Lecture seule,
bornée à la SOCIÉTÉ ; seul le type ``m3`` est lu (``kwh`` = production d'un
onduleur, autre grandeur). Aucun volume inventé : un mois sans ses deux
bornes vaut ``None`` et son motif le nomme.
"""
from datetime import date

#: Libellés des mois (motifs « aucun relevé en <mois> »).
MOIS_FR = ('janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet',
           'août', 'septembre', 'octobre', 'novembre', 'décembre')


def _derniers_index(company, equipement_ids, annee):
    """``{equipement_id: {mois: index}}`` — mois 0 = décembre de l'année
    précédente, 1..12 = l'année ; la valeur du DERNIER relevé du mois."""
    from .models import ReleveCompteurEquipement

    releves = (ReleveCompteurEquipement.objects
               .filter(company=company, equipement_id__in=equipement_ids,
                       type=ReleveCompteurEquipement.Type.M3,
                       date__gte=date(annee - 1, 12, 1),
                       date__lte=date(annee, 12, 31))
               .order_by('date', 'date_creation', 'pk')
               .values_list('equipement_id', 'date', 'valeur'))
    index = {}
    for equipement_id, jour, valeur in releves:
        mois = 0 if jour.year < annee else jour.month
        index.setdefault(equipement_id, {})[mois] = float(valeur)
    return index


def volumes_mensuels_mesures(company, equipement_ids, annee):
    """12 volumes m³ : index du dernier relevé du mois − celui du dernier relevé
    du mois précédent (décembre précédent pour janvier), les deux exigés ;
    plusieurs équipements = somme de ceux qui ont les deux bornes."""
    ids = [i for i in (equipement_ids or ()) if i is not None]
    m3, motifs = [None] * 12, []
    if not ids:
        return {'annee': annee, 'm3': m3, 'equipements': 0,
                'motifs': ['aucun équipement relevé']}
    index = _derniers_index(company, ids, annee)
    for mois in range(1, 13):
        volumes = [bornes[mois] - bornes[mois - 1] for bornes in index.values()
                   if mois in bornes and mois - 1 in bornes]
        if volumes:
            m3[mois - 1] = round(sum(volumes), 1)
            continue
        manquant = mois if not any(mois in b for b in index.values()) else mois - 1
        motifs.append('aucun relevé en %s' % (
            MOIS_FR[manquant - 1] if manquant else 'décembre %d' % (annee - 1)))
    return {'annee': annee, 'm3': m3, 'equipements': len(ids), 'motifs': motifs}


def volumes_mensuels_du_devis(company, devis_id, annee=None):
    """Les volumes mesurés des équipements du chantier du devis (année par
    défaut : l'année civile précédente) ; devis sans chantier : douze ``None``."""
    from apps.installations.selectors import installation_for_devis

    from .models import Equipement

    from django.utils import timezone

    annee = annee or timezone.localdate().year - 1
    chantier = installation_for_devis(devis_id, company=company)
    if chantier is None:
        return {'annee': annee, 'm3': [None] * 12, 'equipements': 0,
                'motifs': ['aucun chantier lié à ce devis']}
    ids = list(Equipement.objects.filter(company=company, installation=chantier)
               .values_list('pk', flat=True))
    return volumes_mensuels_mesures(company, ids, annee)
