# flake8: noqa  (sonde de contre-visite « vérifie AFAC » 2e clôture, rejouable par scripts/sonde.py — AMET93)
"""AFAC67 : `frontend/src/pages/ventes/FactureForm.jsx::creerDepuisBc` affiche
« Facture <ref> créée — Total TTC {formatMAD(factureCreee.montant_ttc)}, identique au devis signé ».
`montant_ttc` est le champ FIGÉ des tranches (`apps/facturation/models.py::Facture.montant_ttc`, NULL pour une
facture à lignes) ; le total vrai est `total_ttc`. Le test `FactureForm.bonCommande.test.jsx` sert une réponse
inventée `{montant_ttc: '10800.00'}`. On mesure la forme RÉELLE servie par `bons-commande/<id>/creer-facture/`
(`FactureSerializer`). Chaîne API réelle (responsable). Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AFAC-VER2-020", "sha": "1dfa7986c",
         "attendu": "creer-facture → 201 avec total_ttc = 12000.00 et montant_ttc = None : l'écran AFAC67 affiche « Total TTC — » au lieu du TTC du devis",
         "modeles": ["authentication.Company", "ventes.BonCommande", "facturation.Facture", "ventes.Devis"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis, Facture
    co = Company.objects.create(nom='Sonde AFAC-VER2-020', slug='sonde-afac-ver2-020')
    u = get_user_model().objects.create_user(username='sonde-afac-ver2-020', password='x', role_legacy='responsable', company=co)
    c = Client.objects.create(company=co, nom='Client V2-020', email='v2020@example.invalid')
    p = Produit.objects.create(company=co, nom='Onduleur', sku='SONDE-AFAC-V2-020', prix_vente=Decimal('5000'), quantite_stock=0)
    d = Devis.objects.create(company=co, reference='DEV-SONDE-AFACV2-020', client=c, statut=Devis.Statut.ACCEPTE,
                             taux_tva=Decimal('20'))
    LigneDevis.objects.create(devis=d, produit=p, designation='Onduleur', quantite=Decimal('2'), prix_unitaire=Decimal('5000'))
    api = APIClient()
    api.force_authenticate(u)
    B = '/api/django/ventes'
    etapes = {}
    r = api.post(B + '/bons-commande/', {'client': c.pk, 'devis': d.pk}, format='json', HTTP_HOST='localhost')
    etapes['creer_bc'] = (r.status_code, (r.data if r.status_code >= 400 else None))
    if r.status_code != 201:
        return {'repro': False, 'etapes': etapes}
    bc_id = r.data['id']
    r = api.post(f'{B}/bons-commande/{bc_id}/confirmer/', HTTP_HOST='localhost')
    etapes['confirmer'] = (r.status_code, (r.data if r.status_code >= 400 else None))
    r = api.post(f'{B}/bons-commande/{bc_id}/creer-facture/', HTTP_HOST='localhost')
    etapes['creer_facture'] = (r.status_code, (r.data if r.status_code >= 400 else None))
    if r.status_code != 201:
        return {'repro': False, 'etapes': etapes}
    servi = {'reference': r.data.get('reference'), 'montant_ttc': r.data.get('montant_ttc'),
             'total_ttc': r.data.get('total_ttc'), 'cle_montant_ttc_presente': 'montant_ttc' in r.data}
    f = Facture.objects.get(pk=r.data['id'])
    obs = {'servi': servi, 'base_total_ttc': str(f.total_ttc), 'base_montant_ttc': f.montant_ttc}
    print(f'etapes={etapes} obs={obs}')
    repro = servi['montant_ttc'] in (None, '') and str(servi['total_ttc']) not in ('None', '', '0', '0.00')
    return {'repro': repro, 'etapes': etapes, **obs}
