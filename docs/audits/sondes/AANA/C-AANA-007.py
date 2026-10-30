"""Sonde AANA50 : rejoue C-AANA-007 (audit analyse du 05/10, U4 + R5) : un responsable de A posait un rôle de B sur sa vue
enregistrée, ajoutait un utilisateur de B aux destinataires d'une alerte KPI, créait une config de tableau de bord pour un utilisateur de B."""
SONDE = {
    'constat': 'C-AANA-007',
    'sha': '5908d43bb',
    'attendu': "défaut absent : les trois écritures inter-société sont refusées (4xx) et rien n'est écrit",
}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.roles.models import Role
    from apps.uxviews.models import SavedView
    from apps.reporting.models import DashboardConfig, KpiAlerte
    U = get_user_model()
    a = Company.objects.create(nom='Sonde 007 A', slug='sonde-aana-007-a')
    b = Company.objects.create(nom='Sonde 007 B', slug='sonde-aana-007-b')
    resp = U.objects.create_user(username='sonde-aana-007-r', password='x', company=a, role_legacy='responsable')
    etr = U.objects.create_user(username='sonde-aana-007-e', password='x', company=b, role_legacy='normal')
    role_b = Role.objects.create(company=b, nom='Commercial B', permissions=[])
    vue = SavedView.objects.create(company=a, owner=resp, ecran='crm.leads', nom='Ma vue')
    api = APIClient()
    api.force_authenticate(resp)
    h = {'HTTP_HOST': 'localhost'}
    r1 = api.post('/api/django/uxviews/saved-views/%s/definir-par-defaut-role/' % vue.pk, {'role': role_b.pk}, format='json', **h)
    r1b = api.patch('/api/django/uxviews/saved-views/%s/' % vue.pk, {'role': role_b.pk}, format='json', **h)
    vue.refresh_from_db()
    r2 = api.post('/api/django/reporting/kpi-alertes/', {
        'nom': 'Stock', 'kpi': KpiAlerte.Kpi.VALEUR_STOCK_TOTALE, 'operateur': KpiAlerte.Operateur.SUP,
        'seuil': '60', 'destinataires_utilisateurs': [etr.pk]}, format='json', **h)
    r3 = api.post('/api/django/reporting/dashboard-config/', {'user': etr.pk, 'cards': []}, format='json', **h)
    ecrits = {
        'vue_role_B': vue.role_id == role_b.pk,
        'alerte': KpiAlerte.objects.filter(company=a).exists(),
        'config': DashboardConfig.objects.filter(user=etr).exists(),
    }
    refus = all(s in (400, 403, 404) for s in (r1.status_code, r1b.status_code, r2.status_code, r3.status_code))
    print('vue(def-role/patch)=%s/%s alerte=%s config=%s ecrits=%s' % (r1.status_code, r1b.status_code, r2.status_code, r3.status_code, ecrits))
    return {'repro': refus and not any(ecrits.values()), 'statuts': [r1.status_code, r1b.status_code, r2.status_code, r3.status_code], 'ecrits': ecrits}
