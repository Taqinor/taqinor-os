# flake8: noqa  (sonde d'audit parcours PA4, rejouable par scripts/sonde.py — AMET93)
"""G3 : `domain/encaissements.py::encaisser_sur_facture` abandonne le résiduel sous la tolérance société
(`abandonner_solde_facture(..., auto=True)` → `AbandonCreance`) ; `domain/recouvrement.py::rejeter_paiement` rouvre
la facture sans annuler cet abandon automatique. Chaîne API réelle (responsable) : encaissement, rejet, puis
nouvelle présentation du montant intégral. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AARG-062", "sha": "56d5b623a",
         "attendu": "tolérance 0,10 ; facture 1 200 ; paiement 1 199,95 → payee + abandon auto 0,05 ; rejet du paiement → sain : montant_du 1 200, abandon annulé ; observé : montant_du 1 199,95, abandon 0,05 toujours actif ; re-paiement 1 200 refusé (dépasse le reste)",
         "modeles": ["authentication.Company", "facturation.Facture", "facturation.Paiement", "ventes.AbandonCreance",
                     "parametres.CompanyProfile"]}


def sonde(ctx):
    from datetime import timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.parametres.models import CompanyProfile
    from apps.stock.models import Produit
    from apps.ventes.models import Facture, LigneFacture, Paiement, AbandonCreance
    from apps.ventes import scheduled
    co = Company.objects.create(nom='Sonde AARG-062', slug='sonde-aarg-062')
    u = get_user_model().objects.create_user(username='sonde-aarg-062', password='x', role_legacy='responsable', company=co)
    adm = get_user_model().objects.create_user(username='sonde-aarg-062-adm', password='x', role_legacy='admin', company=co)
    prof = CompanyProfile.get(company=co)
    prof.tolerance_ecart_reglement = Decimal('0.10')
    prof.save()
    cl = Client.objects.create(company=co, nom='Idrissi', prenom='Nadia', email='g3-aarg062@example.invalid')
    p = Produit.objects.create(company=co, nom='Kit', sku='SONDE-AARG-062', prix_vente=Decimal('1000'), quantite_stock=0)
    today = scheduled.casablanca_today()
    f = Facture.objects.create(company=co, reference='FAC-SONDE-AARG62', client=cl, statut=Facture.Statut.EMISE,
                               date_emission=today - timedelta(days=10), date_echeance=today + timedelta(days=20))
    LigneFacture.objects.create(facture=f, produit=p, designation='Kit', quantite=Decimal('1'),
                                prix_unitaire=Decimal('1000'), taux_tva=Decimal('20'))
    api = APIClient()
    api.force_authenticate(u)
    api_adm = APIClient()
    api_adm.force_authenticate(adm)
    B = '/api/django/ventes'

    def etat():
        g = Facture.objects.get(pk=f.pk)
        ab = list(AbandonCreance.objects.filter(facture=g).values_list('montant', 'auto', 'annule_le'))
        return {'statut': g.statut, 'montant_du': str(g.montant_du), 'abandon_montant': str(g.abandon_montant),
                'abandons': [(str(m), a, str(x)) for m, a, x in ab]}

    def payer(montant):
        r = api.post(f'{B}/factures/{f.pk}/enregistrer-paiement/',
                     {'montant': montant, 'date_paiement': today.isoformat(), 'mode': 'cheque'},
                     format='json', HTTP_HOST='localhost')
        return r.status_code, (r.data.get('detail') if r.status_code >= 400 else None)

    obs = {'tolerance': str(CompanyProfile.get(company=co).tolerance_ecart_reglement),
           'total_ttc': str(Facture.objects.get(pk=f.pk).total_ttc)}
    obs['paiement'] = payer('1199.95')
    obs['apres_paiement'] = etat()
    pay = Paiement.objects.filter(facture=f).order_by('-pk').first()
    rejet = {}
    for nom, client in (('responsable', api), ('admin', api_adm)):
        r = client.post(f'{B}/paiements/{pay.pk}/rejeter/', {'motif': 'Cheque impaye'}, format='json', HTTP_HOST='localhost')
        rejet[nom] = (r.status_code, (r.data.get('detail') if r.status_code >= 400 else None))
        if r.status_code == 200:
            break
    obs['rejet'] = rejet
    obs['apres_rejet'] = etat()
    obs['repaiement_1200'] = payer('1200.00')
    obs['apres_repaiement'] = etat()
    print(obs)
    a = obs['apres_rejet']
    repro = a['statut'] != 'payee' and Decimal(a['montant_du']) < Decimal('1200') and any(x[2] == 'None' for x in a['abandons'])
    return {'repro': repro, **obs}
