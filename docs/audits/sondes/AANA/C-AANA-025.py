"""Sonde AANA, rejouable par scripts/sonde.py : transaction annulée. Jamais contre la prod.
Rejoue C-AANA-025 (audit analyse du 05/10, §6) : récidive SAV, tickets annulés comptés d'un côté seulement.
"""
SONDE = {
    'constat': 'C-AANA-025',
    'sha': '5908d43bb',
    'attendu': "défaut absent : ticket récidive ANNULÉ exclu — scorecard technicien et rapport terrain donnent le même taux_recidive_pct (0.0)",
}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.crm.models import Client
    from apps.sav.models import Ticket
    from authentication.models import Company
    U = get_user_model()
    co = Company.objects.create(nom='Sonde AANA-025', slug='sonde-aana-025')
    resp_u = U.objects.create_user(username='sonde-aana-025-r', password='x', role_legacy='responsable', company=co)
    tech = U.objects.create_user(username='sonde-aana-025-t', password='x', company=co)
    cl = Client.objects.create(company=co, nom='Cli R11')
    Ticket.objects.create(company=co, reference='T-SONDE-AANA25-1', client=cl, technicien_responsable=tech)
    Ticket.objects.create(company=co, reference='T-SONDE-AANA25-2', client=cl, technicien_responsable=tech, est_recidive=True, annule=True)
    api = APIClient()
    api.force_authenticate(resp_u)
    B = '/api/django/reporting'
    r1 = api.get('%s/insights/technicien-scorecard/?technicien=%s' % (B, tech.id), HTTP_HOST='localhost')
    r2 = api.get('%s/reports/field/?technicien=%s' % (B, tech.id), HTTP_HOST='localhost')
    sc = r1.data['scorecard']
    terrain = r2.data['recidive']['taux_pct']
    ok = sc['nb_recidives'] == 0 and sc['taux_recidive_pct'] == 0.0 and sc['taux_recidive_pct'] == terrain
    print('scorecard nb_recidives=%s taux=%s ; terrain taux=%s' % (sc['nb_recidives'], sc['taux_recidive_pct'], terrain))
    return {'repro': ok, 'scorecard_taux': sc['taux_recidive_pct'], 'terrain_taux': terrain, 'nb_recidives': sc['nb_recidives']}
