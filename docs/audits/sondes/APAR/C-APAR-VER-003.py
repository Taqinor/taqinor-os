SONDE = {"constat": "C-APAR-VER-003", "sha": "b3c7e4065",
         "attendu": "société à TVA standard 14 %, onduleur sans Produit.tva à 10 000 HT : le lecteur de composition des cartes Éco/Max (offres_tailles, repli _TVA_REPLI) compte 11 400 TTC comme le devis, pas 12 000"}


def sonde(ctx):
    from decimal import Decimal
    from authentication.models import Company
    from apps.parametres.models_company import CompanyProfile
    from apps.stock.models import Produit
    from apps.ventes import offres_tailles
    from apps.ventes.dimensionnement import _lire_composition
    from apps.ventes.utils.company_settings import tva_standard
    co = Company.objects.create(nom='Sonde APAR VER-003', slug='sonde-apar-ver-003')
    profil, _ = CompanyProfile.objects.get_or_create(company=co)
    CompanyProfile.objects.filter(pk=profil.pk).update(tva_standard=Decimal('14'))
    taux_societe = tva_standard(co)
    p = Produit.objects.create(company=co, nom='Onduleur sonde', sku='SONDE-APAR-003', prix_achat=Decimal('8000'),
                               prix_vente=Decimal('10000'), tva=None)

    class Ligne:
        produit = p
        quantite = Decimal('1')
        prix_unitaire = Decimal('10000')
        designation = 'Onduleur sonde'

    cartes = _lire_composition([Ligne()], offres_tailles._TVA_REPLI)
    attendu = _lire_composition([Ligne()], taux_societe)
    sans_tva = Produit.objects.filter(tva__isnull=True, is_archived=False).count()
    print(f'tva_standard société={taux_societe} ; repli des cartes _TVA_REPLI={offres_tailles._TVA_REPLI} ; '
          f'TTC lu par les cartes={cartes["cout_ttc"]:.2f} ; TTC au taux société={attendu["cout_ttc"]:.2f} ; '
          f'produits actifs sans Produit.tva dans la base de démo : {sans_tva}')
    return {'repro': round(cartes['cout_ttc'], 2) != round(attendu['cout_ttc'], 2),
            'ttc_cartes': round(cartes['cout_ttc'], 2), 'ttc_attendu': round(attendu['cout_ttc'], 2),
            'produits_sans_tva': sans_tva}
