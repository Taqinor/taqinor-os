SONDE = {"constat": "C-ALEA-VER2-001", "sha": "b01fa172f",
         "attendu": "société aux 8 forfaits C&I réglés + coffret DC/AC, protection AC, compteur tarifés mais SANS article "
                    "portant un rôle de prestation : devis_auto.catalogue_ci.pret == True alors que le moteur "
                    "(lignes_chiffrees_sans_article, refus CORC6 de refus_devis_auto_ci) nomme 8 prestations orphelines",
         "modeles": ["authentication.Company", "parametres.CompanyProfile", "stock.Produit", "crm.Lead"]}


def sonde(ctx):
    from decimal import Decimal
    from django.core.cache import cache
    from apps.parametres.models import CompanyProfile
    from apps.stock.models import Produit
    from apps.stock.selectors import produits_ci
    from apps.crm.models import Lead
    from apps.crm.devis_auto import catalogue_ci
    from apps.ventes.tests._quote_engine_common import make_company
    from apps.ventes.moteur_ci.composition import PRESTATIONS_CI, _prestation, _du_role
    from apps.ventes.domain.etude_ci import lignes_chiffrees_sans_article, MESSAGE_PRESTATION_SANS_ARTICLE

    co = make_company(slug='sonde-alea-ver2-001', nom='Sonde ALEA VER2 001')
    CompanyProfile.objects.update_or_create(company=co, defaults={'forfaits_ci': {
        cle: {'fixe_ht': '500', 'source': 'grille sonde'} for cle, _l in PRESTATIONS_CI}})
    for role in ('coffret_dc', 'coffret_ac', 'protection_ac', 'compteur_injection'):
        Produit.objects.create(company=co, nom='Poste %s' % role, role_ci=role,
                               prix_vente=Decimal('900'), prix_achat=Decimal('400'))
    cache.delete('ventes:catalogue_ci_pret:%s' % co.id)
    lead = Lead.objects.create(company=co, nom='Usine sonde', type_installation='commercial')
    bloc = catalogue_ci(lead)
    # Le moteur : la ligne de prestation telle que composer_ci la construit (même catalogue, mêmes forfaits).
    catalogue = produits_ci(co)
    forfaits = CompanyProfile.objects.get(company=co).forfaits_ci
    lignes = [_prestation(cle, lib, forfaits.get(cle), _du_role(catalogue, cle), 50, 100)
              for cle, lib in PRESTATIONS_CI]
    orphelines = lignes_chiffrees_sans_article({'lignes': lignes})
    print('catalogue_ci =', bloc)
    print('orphelines moteur =', orphelines)
    if orphelines:
        print('refus moteur =', MESSAGE_PRESTATION_SANS_ARTICLE % ', '.join(orphelines))
    return {'repro': bool(bloc and bloc.get('pret')) and bool(orphelines),
            'catalogue_pret': bool(bloc and bloc.get('pret')), 'orphelines': len(orphelines)}
