"""Sélecteurs (lecture seule) du module ``apps.sante``.

Fonctions utilitaires que d'autres apps peuvent importer **via import local**
(dans le corps d'une fonction, jamais au niveau module) pour éviter les
dépendances cycliques et respecter les contrats d'import CI-enforced.
"""


def statistiques_actes_et_conventions(company, *, date_debut=None, date_fin=None):
    """NTSAN28 — rapport agrégé : actes les plus facturés (volume + CA) et
    répartition du CA par convention (CNOPS/CNSS/mutuelle/cash), utile pour
    négocier les grilles tarifaires. ``date_debut``/``date_fin`` (optionnels,
    ``date``) filtrent respectivement sur ``ActeRealise.date_realisation``
    (par acte) et ``FactureSante.date_emission`` (par convention).

    Les totaux par convention correspondent EXACTEMENT à la somme de
    ``FactureSante.part_tiers_payant_ttc`` groupée par convention (garde
    testée) — jamais un recalcul indépendant qui pourrait diverger."""
    from django.db.models import Count, F, Sum

    from .models import ActeRealise, FactureSante

    actes_qs = ActeRealise.objects.filter(company=company)
    if date_debut:
        actes_qs = actes_qs.filter(date_realisation__date__gte=date_debut)
    if date_fin:
        actes_qs = actes_qs.filter(date_realisation__date__lte=date_fin)

    par_acte = list(
        actes_qs.annotate(ligne_ttc=F('tarif_applique_ttc') * F('quantite'))
        .values('acte_id', 'acte__libelle')
        .annotate(volume=Count('id'), chiffre_affaires=Sum('ligne_ttc'))
        .order_by('-chiffre_affaires'))

    factures_qs = FactureSante.objects.filter(company=company)
    if date_debut:
        factures_qs = factures_qs.filter(date_emission__date__gte=date_debut)
    if date_fin:
        factures_qs = factures_qs.filter(date_emission__date__lte=date_fin)

    par_convention = list(
        factures_qs.values('convention_id', 'convention__nom')
        .annotate(
            ca_tiers_payant=Sum('part_tiers_payant_ttc'),
            ca_total=Sum('total_ttc'),
            nb_factures=Count('id'))
        .order_by('-ca_total'))

    return {'par_acte': par_acte, 'par_convention': par_convention}


def tarif_applicable(acte, convention):
    """NTSAN8 — tarif TTC applicable pour un acte, pour une convention
    donnée (ou ``None``).

    Lit ``GrilleTarifaire`` pour (convention, acte) si une ligne existe,
    sinon retombe sur ``ActeMedical.tarif_base_ttc``. Renvoie un dict
    ``{'tarif_ttc': Decimal, 'taux_prise_charge_pct': Decimal, 'source':
    'grille'|'base'}``.
    """
    from .models import GrilleTarifaire

    if convention is not None:
        grille = GrilleTarifaire.objects.filter(
            company=acte.company, convention=convention, acte=acte).first()
        if grille is not None:
            return {
                'tarif_ttc': grille.tarif_convention_ttc,
                'taux_prise_charge_pct': grille.taux_prise_charge_pct,
                'source': 'grille',
            }
    return {
        'tarif_ttc': acte.tarif_base_ttc,
        'taux_prise_charge_pct': 0,
        'source': 'base',
    }
