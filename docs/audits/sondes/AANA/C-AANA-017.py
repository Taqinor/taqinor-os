"""Sonde AANA, rejouable par scripts/sonde.py : transaction annulée. Jamais contre la prod.
Rejoue C-AANA-017 (audit analyse du 05/10, §6) : valorisation_achat servie sans prix_achat_voir.
"""
SONDE = {
    'constat': 'C-AANA-017',
    'sha': '5908d43bb',
    'attendu': "défaut absent : GET /reporting/reports/stock/ sans valorisation_achat pour un responsable sans prix_achat_voir ; présente (300.00) pour l'admin",
}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.roles.models import Role
    from apps.stock.models import Produit
    from authentication.models import Company
    U = get_user_model()
    co = Company.objects.create(nom='Sonde AANA-017', slug='sonde-aana-017')
    Produit.objects.create(company=co, nom='Panneau', sku='SONDE-AANA-017', prix_vente=Decimal('150'), prix_achat=Decimal('100'), quantite_stock=3)
    role = Role.objects.create(company=co, nom='Resp stock sans achat', permissions=['stock_gerer', 'reporting_voir'])
    resp_u = U.objects.create_user(username='sonde-aana-017-r', password='x', company=co, role=role)
    adm = U.objects.create_user(username='sonde-aana-017-a', password='x', role_legacy='admin', company=co)
    url = '/api/django/reporting/reports/stock/'

    def get(u):
        api = APIClient()
        api.force_authenticate(u)
        return api.get(url, HTTP_HOST='localhost')
    r1, r2 = get(resp_u), get(adm)
    absent = r1.status_code == 200 and 'valorisation_achat' not in r1.data
    present = r2.status_code == 200 and r2.data.get('valorisation_achat') == '300.00'
    print('responsable=%s clé présente=%s ; admin=%s valorisation_achat=%s' % (r1.status_code, 'valorisation_achat' in r1.data, r2.status_code, r2.data.get('valorisation_achat')))
    return {'repro': absent and present, 'resp_status': r1.status_code, 'resp_fuite': 'valorisation_achat' in r1.data, 'admin_val': r2.data.get('valorisation_achat')}
