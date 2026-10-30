SONDE = {"constat": "C-ASEC-017", "sha": "5908d43bb",
         "attendu": "refusé / inchangé : Viewer et compte portail client POST automation-draft -> 403, aucune "
                    "AutomationRule créée ; vues agent actions/logs fermées au portail (403) ; administrateur -> 201 "
                    "(règle de sa société, enabled=False)"}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.roles.models import Role
    from apps.roles.permissions_registre import VIEWER_PERMISSIONS
    from apps.automation.models import AutomationRule
    User = get_user_model()
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde ASEC017', slug='sonde-asec017-a')
    Company.objects.create(nom='Sonde ASEC017 B', slug='sonde-asec017-b')
    viewer_role = Role.objects.create(company=co, nom='Viewer', permissions=list(VIEWER_PERMISSIONS),
                                      est_systeme=True)
    viewer = User.objects.create_user(username='sonde-asec017-viewer', password='x', role=viewer_role, company=co)
    portail = User.objects.create_user(username='sonde-asec017-portail', password='x', role_legacy='admin',
                                       company=co, portee=User.PORTEE_PORTAIL_CLIENT, portail_client_id=1)
    admin = User.objects.create_user(username='sonde-asec017-admin', password='x', role_legacy='admin', company=co)
    URL = '/api/django/agent/actions/automation-draft/'
    corps = {'nom': 'Sonde relance J+2', 'trigger_type': 'devis_accepted', 'trigger_config': {},
             'action_type': 'create_activity', 'action_config': {'delai_jours': 2}}

    def api_de(u):
        api = APIClient()
        api.force_authenticate(u)
        return api

    obs, refus_ok = {}, True
    for nom, u in (('viewer', viewer), ('portail', portail)):
        avant = AutomationRule.objects.count()
        r = api_de(u).post(URL, corps, format='json', **H)
        apres = AutomationRule.objects.count()
        obs[nom] = {'post': r.status_code, 'regles_avant_apres': [avant, apres]}
        refus_ok &= r.status_code == 403 and avant == apres
    api = api_de(portail)
    portail_vues = [api.get('/api/django/agent/actions/', **H).status_code,
                    api.get('/api/django/agent/logs/', **H).status_code,
                    api.post('/api/django/agent/logs/confirmer/', {}, format='json', **H).status_code]
    obs['portail_autres_vues_agent'] = portail_vues
    refus_ok &= portail_vues == [403, 403, 403]
    r = api_de(admin).post(URL, corps, format='json', **H)
    regle = AutomationRule.objects.filter(pk=r.data.get('id')).first() if r.status_code == 201 else None
    leg_ok = r.status_code == 201 and regle is not None and regle.company_id == co.id and not regle.enabled
    obs['admin'] = {'post': r.status_code, 'societe_ok': bool(regle and regle.company_id == co.id),
                    'enabled': getattr(regle, 'enabled', None)}
    obs['repro'] = bool(refus_ok and leg_ok)
    return obs
