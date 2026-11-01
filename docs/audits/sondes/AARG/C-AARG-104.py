# flake8: noqa  (seconde lentille PA4 « Argent » sur K04, rejouable par scripts/sonde.py — AMET93)
"""K04, reproduction INDÉPENDANTE : rôle canonique Directeur (porteur d'`encaisser`), DEUX factures à ligne produit
(A et B, 1 200 TTC chacune) dans le lot, vraie route `factures/encaissement-groupe/`, montant 2 400 et répartition
{"<A>": 1200, "00<A>": 1200} (zéros de tête : la garde `cle.isdigit() and int(cle) in ids_lot` l'accepte).
Mesure : A reçoit-elle 2 × 1 200 (sur-paiement) pendant que B reste due ? Témoin : la même répartition construite
par l'écran (`Object.fromEntries` sur les ids, clés uniques) ne peut pas porter deux fois A. Transaction annulée."""
SONDE = {"constat": "C-AARG-104", "sha": "56d5b623a",
         "attendu": "répartition {'<A>':'1200', '00<A>':'1200'} → refus 409/400, jamais 2 paiements sur A",
         "modeles": ["ventes.Facture", "ventes.LigneFacture", "ventes.Paiement"]}


def sonde(ctx):
    from datetime import date
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.roles.models import Role
    from apps.roles import permissions_registre as reg
    from apps.stock.models import Produit
    from apps.ventes.models import Facture, LigneFacture, Paiement
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AARG 104', slug='sonde-aarg-104')
    r_dir = Role.objects.create(company=co, nom='Directeur', permissions=list(reg.DIRECTEUR_PERMISSIONS),
                                est_systeme=True)
    u = get_user_model().objects.create_user(username='sonde-aarg104-dir', password='x', company=co, role=r_dir)
    cl = Client.objects.create(company=co, nom='Groupe', prenom='K04bis', email='sonde-aarg-104@example.invalid')
    p = Produit.objects.create(company=co, nom='Kit K04', sku='SONDE-AARG-104', prix_vente=Decimal('1000'),
                               quantite_stock=10)
    fs = []
    for k in ('A', 'B'):
        f = Facture.objects.create(company=co, reference=f'FAC-SONDE-AARG-104-{k}', client=cl,
                                   statut=Facture.Statut.EMISE, taux_tva=Decimal('20.00'),
                                   date_emission=date.today(), created_by=u)
        LigneFacture.objects.create(facture=f, produit=p, designation='Kit', quantite=Decimal('1'),
                                    prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))
        fs.append(Facture.objects.get(pk=f.pk))
    a, b = fs
    api = APIClient()
    api.force_authenticate(u)
    r = api.post('/api/django/ventes/factures/encaissement-groupe/', {
        'client': cl.id, 'montant': '2400', 'mode': 'virement', 'date_paiement': date.today().isoformat(),
        'factures': [a.id, b.id], 'repartition': {str(a.id): '1200.00', '00' + str(a.id): '1200.00'}},
        format='json', **H)
    a, b = Facture.objects.get(pk=a.pk), Facture.objects.get(pk=b.pk)
    obs = {'http': r.status_code, 'detail': (r.data if r.status_code >= 400 else None),
           'A_paiements': [str(x.montant) for x in Paiement.objects.filter(facture=a)],
           'A_ttc': str(a.total_ttc), 'A_paye': str(a.montant_paye), 'A_du': str(a.montant_du), 'A_statut': a.statut,
           'B_paye': str(b.montant_paye), 'B_du': str(b.montant_du), 'B_statut': b.statut,
           'avances': [str(x.montant) for x in Paiement.objects.filter(company=co, facture__isnull=True)]}
    print(obs)
    obs['repro'] = r.status_code in (200, 201) and a.montant_paye > a.total_ttc
    return obs
