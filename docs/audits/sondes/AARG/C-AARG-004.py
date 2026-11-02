# flake8: noqa  (sonde PA4 « Argent », rejouable par scripts/sonde.py — AMET93)
"""K04 : encaissement groupé (`views/facture_encaissement.py::encaissement_groupe` →
`domain/encaissements.py::affecter_encaissement_groupe`) : la garde de lot accepte toute clé ASCII numérique dont
`int(clé)` est dans le lot, et chaque part n'est bornée qu'au reste dû INDIVIDUEL. Les clés "<id>" et "0<id>"
désignent la même facture : deux paiements, sur-paiement silencieux. Vraie API, société neuve, transaction annulée."""
SONDE = {"constat": "C-AARG-004", "sha": "56d5b623a",
         "attendu": "facture dû 1 000 ; montant 2 000, repartition {'<id>':'1000.00','0<id>':'1000.00'} → refus (409/400), jamais 2 paiements",
         "modeles": ["ventes.Facture", "ventes.Paiement"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.ventes.models import Facture, Paiement
    co = Company.objects.create(nom='Sonde AARG 004', slug='sonde-aarg-004')
    u = get_user_model().objects.create_user(username='sonde_aarg_004', password='x', role_legacy='admin', company=co)
    cl = Client.objects.create(company=co, nom='Client', prenom='AARG004', email='sonde-aarg-004@example.invalid')
    f = Facture.objects.create(company=co, reference='FAC-SONDE-AARG-004', client=cl, statut='emise',
                               taux_tva=Decimal('20'), montant_ht=Decimal('833.33'), montant_tva=Decimal('166.67'),
                               montant_ttc=Decimal('1000'), date_emission=timezone.now().date())
    du_avant = f.montant_du
    api = APIClient()
    api.force_authenticate(u)
    r = api.post('/api/django/ventes/factures/encaissement-groupe/', {
        'client': cl.id, 'montant': '2000', 'mode': 'virement', 'factures': [f.id],
        'repartition': {str(f.id): '1000.00', '0' + str(f.id): '1000.00'}}, format='json')
    f = Facture.objects.get(pk=f.pk)
    pays = [str(p.montant) for p in Paiement.objects.filter(company=co, facture=f)]
    obs = {'du_avant': str(du_avant), 'http': r.status_code,
           'detail': r.json() if r.status_code >= 400 else None,
           'paiements_sur_facture': pays, 'montant_paye': str(f.montant_paye),
           'montant_du': str(f.montant_du), 'statut': f.statut}
    print(obs)
    obs['repro'] = r.status_code == 201 and f.montant_paye > f.total_ttc
    return obs
