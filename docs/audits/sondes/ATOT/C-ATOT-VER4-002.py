# flake8: noqa  (sonde d'audit vérifie ATOT 04/11, rejouable par scripts/sonde.py — AMET93)
"""ATOT2 (garde de classe « une vente ne se facture qu'une fois », tenue à l'ÉMISSION depuis VNT20) :
`domain/facturation_ops.py::emettre_facture` lit `vente_facturation.motif_emission_hors_prix` (Σ émis de la vente
+ cette facture ≤ prix convenu) SANS verrou de la vente, et `views/facture_cycle.py::FactureCycleActionsMixin.emettre`
(POST factures/<id>/emettre/) comme `views/facture_lot.py` (bulk) l'appellent sans `verrouiller_vente` ni
`select_for_update` — alors que les portes tranche / complète / consolidée verrouillent la vente avant d'émettre.
VNT20 autorise expressément DEUX brouillons concurrents (BC + complète) : deux POST emettre simultanés lisent chacun
« rien d'émis » et passent tous deux. Une sonde (une transaction, un fil) ne peut pas jouer la course : elle lit le
code EXÉCUTÉ dans le conteneur et prouve l'absence de verrou (verdict STATIQUE). La course elle-même reste à
reproduire par un TransactionTestCase à deux fils. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ATOT-VER4-002", "sha": "64c9c7317",
         "attendu": "emettre_facture : motif_emission_hors_prix lu avant tout select_for_update / verrouiller_vente ; facture_cycle.emettre et facture_lot sans verrou de vente ; portes tranche/complète/consolidée verrouillées",
         "modeles": ["facturation.Facture"]}


def sonde(ctx):
    import inspect
    from apps.ventes.domain import facturation_ops, encaissements
    from apps.ventes.domain import facturation_vente
    from apps.ventes.utils import echeancier
    from apps.ventes.views import facture_cycle, facture_lot

    src_em = inspect.getsource(facturation_ops.emettre_facture)
    corps = src_em.split('"""', 2)[-1]  # sans la docstring
    i_motif = corps.find('motif_emission_hors_prix(')
    avant_motif = corps[:i_motif]
    em_verrou = ('select_for_update' in avant_motif) or ('verrouiller_vente' in avant_motif)
    src_vue = inspect.getsource(facture_cycle.FactureCycleActionsMixin.emettre)
    vue_verrou = ('select_for_update' in src_vue) or ('verrouiller_vente' in src_vue)
    src_lot = inspect.getsource(facture_lot)
    lot_verrou = 'verrouiller_vente' in src_lot
    tranche_verrou = 'verrouiller_vente(' in inspect.getsource(echeancier.creer_facture_tranche)
    conso_verrou = 'verrouiller_vente(' in inspect.getsource(encaissements.consolider_factures)
    src_fv = inspect.getsource(facturation_vente)
    fv_verrou = src_fv.count('verrouiller_vente(')
    obs = {'emettre_facture_verrou_avant_motif': em_verrou, 'vue_emettre_verrou': vue_verrou,
           'bulk_verrou_vente': lot_verrou, 'porte_tranche_verrou': tranche_verrou,
           'porte_consolidee_verrou': conso_verrou, 'facturation_vente_appels_verrou': fv_verrou,
           'position_motif_dans_corps': i_motif}
    print(obs)
    trou = (i_motif > 0 and not em_verrou and not vue_verrou and not lot_verrou
            and tranche_verrou and conso_verrou)
    return ('STATIQUE — ' + ('trou confirmé : ' if trou else 'trou NON confirmé : ') + repr(obs))
