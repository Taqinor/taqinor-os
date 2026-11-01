# flake8: noqa  (sonde de contre-visite vérifie AMOT, rejouable par scripts/sonde.py — AMET93)
"""AMOT29 : un palier batterie (économie du balayage HORAIRE, déjà nette du rendement aller-retour) est republié
par `public/payload_batterie.py::_balayage_stockage_publique` et `domain/dimensionnement_devis.py::_payback_publie_palier`
via `pricing.payback_publiable(..., stockage=True)` SANS `part_batterie` : `compute_cashflow_payback` retombe sur
l'abattement forfaitaire (rendement re-déduit sur toute l'économie). Les cartes Éco/Max (`offres_tailles._payback_publie`,
`part_batterie=0.0` en horaire) et le PDF publient l'autre définition : deux paybacks pour le même kit.
Fonctions réelles, aucune écriture en base (une société neuve, annulée avec la transaction)."""
SONDE = {"constat": "C-AMOT-VER-003", "sha": "d57c36964",
         "attendu": "même prix 90 000, même économie horaire 6 500 : payback du curseur / de l'échelle ≠ payback de la carte « avec » / du PDF"}


def sonde(ctx):
    from decimal import Decimal
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.ventes.models import Devis
    from apps.ventes import offres_tailles as ot
    from apps.ventes.public.payload_batterie import _balayage_stockage_publique
    from apps.ventes.domain.dimensionnement_devis import _payback_publie_palier
    from apps.ventes.quote_engine.pricing import payback_publiable
    co = Company.objects.create(nom='Sonde AMOT VER-003', slug='sonde-amot-ver-003')
    cl = Client.objects.create(company=co, nom='Client', prenom='VER003', email='sonde-amot-ver-003@example.invalid')
    dv = Devis.objects.create(company=co, client=cl, reference='DEV-SONDE-AMOT-003', statut='brouillon',
                              taux_tva=Decimal('20'))
    prix, eco, onduleur_ttc = 90000.0, 6500.0, 15000.0
    dim = {'recommandation_avec': {'balayage_stockage': [{
        'lignes_batterie': [{'quantite': 2}], 'capacite_kwh': 10.0, 'cout_ttc': prix,
        'economie_mad': eco, 'payback_annees': 13.85, 'remplissage': {'moyen': 1.0}}]}}
    pub = _balayage_stockage_publique(dim, dv, None) or {}
    paliers = pub.get('paliers') or [{}]
    curseur = paliers[0].get('payback_annees')
    lignes = [{'role': 'onduleur_hybride', 'quantite': 1, 'prix_unitaire_ht': onduleur_ttc / 1.2}]
    echelle = _payback_publie_palier(prix, eco, lignes, 1.0)
    carte = ot._payback_publie(prix, eco, stockage=True, part_batterie=0.0, cout_onduleur_ttc=onduleur_ttc)
    pdf_sans_provision = payback_publiable(prix, eco, stockage=True, part_batterie=0.0)['payback_years']
    print(f'curseur_public={curseur} echelle_palier={echelle} carte_avec={carte} '
          f'definition_pdf_horaire_sans_provision={pdf_sans_provision} paliers_servis={len(paliers)}')
    ecart_echelle = echelle is not None and carte is not None and abs(echelle - carte) > 0.05
    ecart_curseur = curseur is not None and pdf_sans_provision is not None and abs(curseur - pdf_sans_provision) > 0.05
    return {'repro': ecart_echelle or ecart_curseur, 'curseur': curseur, 'echelle': echelle, 'carte_avec': carte,
            'pdf_horaire_sans_provision': pdf_sans_provision}
