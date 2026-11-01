# flake8: noqa  (sonde de contre-visite vérifie ATOT, rejouable par scripts/sonde.py — AMET93)
"""ATOT10 (jumeau) : `apps/ventes/public/payload_variantes.py::_variant_total_ttc` (bande « autres tailles » de la page
publique) affiche le TTC AVEC d'un devis à deux options sans lire `option_effective`, alors que le pro-forma, le BC, la
facture et le PDF suivent `option_effective` (CIQ302 : un C&I « Les deux » sert SANS). Fonctions réelles."""
SONDE = {"constat": "C-ATOT-VER-003", "sha": "b72cda218",
         "attendu": "devis industriel à deux options non accepté : bande variantes ≠ option_totaux(devis)['ttc']"}


def sonde(ctx):
    from decimal import Decimal
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis
    from apps.ventes.public.payload_variantes import _variant_total_ttc
    from apps.ventes.utils.options import option_effective, option_totaux
    c = Company.objects.create(nom='Sonde ATOT VER-003', slug='sonde-atot-ver-003')
    cl = Client.objects.create(company=c, nom='Sonde', prenom='ATOTB', email='sonde-atot-ver-003@example.invalid')
    d = Devis.objects.create(company=c, reference='DEV-SONDE-ATOT-003', client=cl, statut=Devis.Statut.ENVOYE,
                             taux_tva=Decimal('20.00'), mode_installation='industriel', etude_params={})
    for desig, q, pu, var in [('Panneau Jinko 550W (sans)', 8, 1000, 'sans'),
                              ('Onduleur réseau Huawei 5kW Monophasé', 1, 5000, 'sans'),
                              ('Panneau Jinko 550W (avec)', 10, 1000, 'avec'),
                              ('Onduleur hybride Deye 5kW Monophasé', 1, 7000, 'avec'),
                              ('Batterie Dyness 10 kWh', 1, 12000, 'avec'),
                              ('Transport et mise en service', 1, 1000, '')]:
        p = Produit.objects.create(company=c, nom=desig, prix_vente=Decimal(pu), quantite_stock=100)
        LigneDevis.objects.create(devis=d, produit=p, designation=desig, quantite=Decimal(q), prix_unitaire=Decimal(pu),
                                  remise=Decimal('0'), taux_tva=Decimal('20.00'), variante=var)
    d = Devis.objects.get(pk=d.pk)
    bande = Decimal(str(_variant_total_ttc(d)))
    attendu = Decimal(str(option_totaux(d)['ttc']))
    print(f'option_effective={option_effective(d)!r} bande={bande} attendu={attendu} total_ttc={d.total_ttc}')
    return {'repro': bande != attendu, 'bande': str(bande), 'attendu': str(attendu)}
