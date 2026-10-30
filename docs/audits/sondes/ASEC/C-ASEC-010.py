SONDE = {"constat": "C-ASEC-010", "sha": "5908d43bb",
         "attendu": "refusé / inchangé : ODOO_COMPANY_ID = A ; un titulaire adsengine_view de B appelle "
                    "MetricsLeadsView -> 200 sans aucun deal source=odoo et AUCUN appel au client Odoo ; "
                    "l'utilisateur de A reçoit le deal Odoo (contre-épreuve) ; sans ODOO_COMPANY_ID -> inactif "
                    "pour tous (aucun appel)"}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from django.test import override_settings
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.roles.models import Role
    from apps.adsengine import odoo_client
    User = get_user_model()
    H = {'HTTP_HOST': 'localhost'}
    URL = '/api/django/adsengine/metrics/leads/'
    lead_gagne = {
        'id': 7, 'name': 'Client Odoo Signé', 'phone': '+212600000777', 'mobile': False,
        'contact_name': 'Client Odoo Signé', 'partner_name': False, 'email_from': False,
        'expected_revenue': 5000, 'probability': 100, 'stage_id': [4, 'Won'], 'user_id': False,
        'partner_id': False, 'date_closed': '2026-10-01 10:00:00', 'active': True,
        'create_date': '2026-09-01 10:00:00'}
    appels = []

    # Odoo simulé au niveau du transport JSON-RPC du client (le lanceur bloque tout socket sortant) :
    # chaque appel est ENREGISTRÉ, la réponse imite le serveur factice du test nommé.
    def faux_rpc(self, service, method, args):
        appels.append(method)
        if method == 'authenticate':
            return 1
        if method == 'execute_kw':
            modele, methode = args[3], args[4]
            kwargs = args[6] if len(args) > 6 else {}
            if methode == 'fields_get':
                return {}
            if methode == 'search_read':
                return [dict(lead_gagne)] if modele == 'crm.lead' and not kwargs.get('offset') else []
            return []
        return None

    def societe(tag):
        co = Company.objects.create(nom=f'Sonde ASEC010 {tag}', slug=f'sonde-asec010-{tag}')
        role = Role.objects.create(company=co, nom='Lecteur pub', permissions=['adsengine_view'], est_systeme=True)
        u = User.objects.create_user(username=f'sonde-asec010-{tag}', password='x',
                                     email=f'asec010{tag}@sonde.invalid', company=co, role=role)
        return co, u

    a, ua = societe('a')
    b, ub = societe('b')

    def reglages(cid):
        return override_settings(ODOO_URL='http://odoo.sonde.invalid', ODOO_DB='test', ODOO_USERNAME='lecteur',
                                 ODOO_API_KEY='cle-sonde', ODOO_COMPANY_ID=cid)

    def get(u):
        api = APIClient()
        api.force_authenticate(u)
        r = api.get(URL, {'metric': 'signature'}, **H)
        data = r.data if isinstance(r.data, list) else []
        return r.status_code, [d for d in data if isinstance(d, dict) and d.get('source') == 'odoo']

    orig = odoo_client.OdooClient._rpc
    odoo_client.OdooClient._rpc = faux_rpc
    try:
        with reglages(str(a.pk)):
            code_b, odoo_b = get(ub)
            appels_b = list(appels)
            del appels[:]
            code_a, odoo_a = get(ua)
            appels_a = list(appels)
            del appels[:]
        with reglages(''):
            inactif = (odoo_client.is_configured(), odoo_client.is_configured(a),
                       odoo_client.OdooClient.from_env(company=a))
            code_a2, odoo_a2 = get(ua)
            appels_sans = list(appels)
    finally:
        odoo_client.OdooClient._rpc = orig
    out = {
        'b_adsengine_view': {'http': code_b, 'deals_odoo': len(odoo_b), 'appels_odoo': appels_b},
        'a_proprietaire': {'http': code_a, 'deals_odoo': [d.get('nom') for d in odoo_a], 'appels_odoo': appels_a},
        'sans_company_id': {'is_configured': [inactif[0], inactif[1]], 'from_env': repr(inactif[2]),
                            'http_a': code_a2, 'deals_odoo': len(odoo_a2), 'appels_odoo': appels_sans},
    }
    out['repro'] = bool(code_b == 200 and not odoo_b and not appels_b
                        and code_a == 200 and [d.get('nom') for d in odoo_a] == ['Client Odoo Signé']
                        and 'authenticate' in appels_a
                        and inactif == (False, False, None) and not odoo_a2 and not appels_sans)
    return out
