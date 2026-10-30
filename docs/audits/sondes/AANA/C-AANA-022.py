"""Sonde AANA, rejouable par scripts/sonde.py : transaction annulée. Jamais contre la prod.
Rejoue C-AANA-022 (audit analyse du 05/10, §6) : le taux « conversion » était calculé au front (factures ÷ devis, > 100 %).
"""
SONDE = {
    'constat': 'C-AANA-022',
    'sha': '5908d43bb',
    'attendu': "défaut absent : 10 devis dont 3 acceptés + 15 factures → dashboard conversion.taux_acceptation_pct = 30.0 (jamais 150)",
}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.crm.models import Client
    from apps.ventes.models import Devis, Facture
    from authentication.models import Company
    co = Company.objects.create(nom='Sonde AANA-022', slug='sonde-aana-022')
    u = get_user_model().objects.create_user(username='sonde-aana-022', password='x', role_legacy='responsable', company=co)
    cl = Client.objects.create(company=co, nom='Cli AANA22')
    for i in range(10):
        Devis.objects.create(company=co, reference='DEV-SONDE-AANA22-%d' % i, client=cl,
                             statut=Devis.Statut.ACCEPTE if i < 3 else Devis.Statut.ENVOYE)
    for i in range(15):
        Facture.objects.create(company=co, reference='FAC-SONDE-AANA22-%d' % i, client=cl, statut=Facture.Statut.EMISE)
    api = APIClient()
    api.force_authenticate(u)
    r = api.get('/api/django/reporting/dashboard/', HTTP_HOST='localhost')
    c = r.data['conversion']
    taux = c.get('taux_acceptation_pct', 'ABSENT')
    print('conversion=%s' % dict(c))
    return {'repro': taux == 30.0 and c.get('nb_devis') == 10 and c.get('nb_acceptes') == 3, 'taux_acceptation_pct': taux, 'nb_devis': c.get('nb_devis'), 'nb_acceptes': c.get('nb_acceptes'), 'nb_factures': c.get('nb_factures')}
