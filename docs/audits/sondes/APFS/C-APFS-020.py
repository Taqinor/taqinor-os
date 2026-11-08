# flake8: noqa  (sonde d'audit de parcours PF1 « Sécurité / multi-société », rejouable par scripts/sonde.py — METHODE §C.4)
"""K02 — le moteur `core.data_explorer` n'a aucun droit par dataset : quatre portes vers `run_query`
(data-explorer/run, saved-queries/run, rapport-definitions + executer, formule/tester) rendent les leads
(nom/telephone/email) et les factures (montants) à des rôles internes que l'écran du module refuse
(Commercial terrain, Admin RH, Technicien) ou borne (Commercial « soi » : ses seuls leads).
Rôles système semés comme `init_roles` (CANONICAL_SYSTEM_ROLES + SYSTEM_ROLE_PERIMETRES), connexion par la
vraie route /api/django/token/ (cookie JWT). Deux sociétés ; aucune ligne de B attendue. Transaction annulée."""
SONDE = {"constat": "C-APFS-020", "sha": "c9e72d5b2",
         "attendu": "repro si une porte du moteur rend 200 + lignes là où l'écran du module (crm/leads/, "
                    "ventes/factures/) rend 403, ou plus de lignes que l'écran pour le Commercial « soi » ; "
                    "aucune ligne de B",
         "modeles": ["authentication.CustomUser", "roles.Role", "crm.Lead", "crm.Client", "ventes.Facture",
                     "reporting.RapportDefinition"]}


def sonde(ctx):
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from authentication.throttles import LoginRateThrottle
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES, SYSTEM_ROLE_PERIMETRES
    from apps.crm.models import Client, Lead
    from apps.ventes.models import Facture
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    today = timezone.now().date()

    def societe(tag):
        co = Company.objects.create(nom=f'Sonde APFS020 {tag}', slug=f'sonde-apfs020-{tag.lower()}')
        for nom, perms in CANONICAL_SYSTEM_ROLES:
            r, _ = Role.objects.get_or_create(company=co, nom=nom,
                                              defaults={'permissions': list(perms), 'est_systeme': True})
            r.permissions, r.est_systeme, r.perimetre = list(perms), True, SYSTEM_ROLE_PERIMETRES.get(nom)
            r.save()
        return co

    def compte(co, nom_role, username):
        r = Role.objects.get(company=co, nom=nom_role)
        u = U.objects.create_user(username=username, password='Sonde-APFS020-x9', company=co, role=r,
                                  role_legacy=U.tier_for_role(r) or 'normal')
        a = APIClient()
        with mock.patch.object(LoginRateThrottle, 'allow_request', return_value=True):
            rr = a.post('/api/django/token/', {'username': username, 'password': 'Sonde-APFS020-x9'}, format='json', **H)
        assert rr.status_code == 200 and a.cookies.get('access_token') is not None, (username, rr.status_code)
        return u, a

    A, B = societe('A'), societe('B')
    c1, api_c1 = compte(A, 'Commercial', 'apfs020-c1')
    c2, api_c2 = compte(A, 'Commercial', 'apfs020-c2')
    _, api_ter = compte(A, 'Commercial terrain', 'apfs020-terrain')
    _, api_rh = compte(A, 'Admin RH', 'apfs020-rh')
    _, api_tech = compte(A, 'Technicien', 'apfs020-tech')
    _, api_dir = compte(A, 'Directeur', 'apfs020-dir')
    for i in range(3):
        Lead.objects.create(company=A, nom=f'LeadC1n{i}', telephone=f'066102000{i}', email=f'c1n{i}@sonde.invalid', owner=c1)
    Lead.objects.create(company=A, nom='LeadC2', telephone='0661020099', email='c2@sonde.invalid', owner=c2)
    Lead.objects.create(company=B, nom='LeadB-APFS020', telephone='0661029999', email='b@sonde.invalid')
    for co, tag in ((A, 'A'), (B, 'B')):
        cl = Client.objects.create(company=co, nom=f'Cl{tag}020', email=f'cl{tag}@sonde.invalid', telephone='0600000020')
        Facture.objects.create(company=co, reference=f'FAC-APFS020-{tag}', client=cl, statut='emise', taux_tva=Decimal('20'),
                               montant_ht=Decimal('1000'), montant_tva=Decimal('200'), montant_ttc=Decimal('1200'),
                               date_emission=today)

    def n_lignes(r):
        try:
            d = r.json()
        except Exception:
            return None
        if isinstance(d, list):
            return len(d)
        for k in ('rows', 'lignes', 'results'):
            if isinstance(d.get(k), list):
                return len(d[k])
        return d.get('count')

    def contient(r, mot):
        return mot in (r.content.decode('utf-8', 'replace') if hasattr(r, 'content') else '')

    SEL_L = ['nom', 'telephone', 'email', 'owner_username']
    out = {}
    roles = {'terrain': api_ter, 'rh': api_rh, 'tech': api_tech, 'c2_soi': api_c2, 'directeur': api_dir}
    for nom, a in roles.items():
        o = {}
        r = a.get('/api/django/crm/leads/', **H)
        o['ecran_leads'] = [r.status_code, n_lignes(r) if r.status_code == 200 else None]
        r = a.get('/api/django/ventes/factures/', **H)
        o['ecran_factures'] = [r.status_code, n_lignes(r) if r.status_code == 200 else None]
        r = a.post('/api/django/core/data-explorer/run/', {'dataset': 'crm_leads', 'select': SEL_L, 'limit': 100},
                   format='json', **H)
        o['dx_run_leads'] = [r.status_code, n_lignes(r), contient(r, '0661020001'), contient(r, 'LeadB-APFS020')]
        r = a.post('/api/django/core/saved-queries/run/', {'dataset': 'crm_leads', 'spec': {'select': SEL_L, 'limit': 100}},
                   format='json', **H)
        o['saved_run_leads'] = [r.status_code, n_lignes(r), contient(r, '0661020001'), contient(r, 'LeadB-APFS020')]
        r = a.post('/api/django/reporting/rapport-definitions/',
                   {'titre': f'r-{nom}', 'dataset': 'crm_leads', 'spec': {'select': SEL_L, 'limit': 100}}, format='json', **H)
        o['rapport_create'] = r.status_code
        if r.status_code == 201:
            r2 = a.post(f"/api/django/reporting/rapport-definitions/{r.json()['id']}/executer/", {}, format='json', **H)
            o['rapport_executer_leads'] = [r2.status_code, n_lignes(r2), contient(r2, '0661020001'),
                                           contient(r2, 'LeadB-APFS020')]
        r = a.post('/api/django/core/formule/tester/', {'dataset': 'ventes_factures', 'expression': 'montant_ttc',
                                                        'limite': 50}, format='json', **H)
        o['formule_tester_factures'] = [r.status_code, n_lignes(r), contient(r, '1200')]
        r = a.post('/api/django/core/data-explorer/run/', {'dataset': 'ventes_factures',
                   'select': ['id', 'montant_ttc', 'client'], 'limit': 100}, format='json', **H)
        o['dx_run_factures'] = [r.status_code, n_lignes(r)]
        out[nom] = o
    # verdict : une porte 200 + lignes là où l'écran refuse (rôles sans module) ; c2 : plus de lignes que l'écran
    ecarts = []
    for nom in ('terrain', 'rh', 'tech'):
        o = out[nom]
        if o['ecran_leads'][0] in (403, 404):
            for k in ('dx_run_leads', 'saved_run_leads', 'rapport_executer_leads'):
                v = o.get(k)
                if v and v[0] == 200 and (v[1] or 0) > 0:
                    ecarts.append(f'{nom}:{k}')
        if o['ecran_factures'][0] in (403, 404):
            for k in ('formule_tester_factures', 'dx_run_factures'):
                v = o.get(k)
                if v and v[0] == 200 and (v[1] or 0) > 0:
                    ecarts.append(f'{nom}:{k}')
    o = out['c2_soi']
    ecran = o['ecran_leads'][1] or 0
    for k in ('dx_run_leads', 'saved_run_leads', 'rapport_executer_leads'):
        v = o.get(k)
        if v and v[0] == 200 and (v[1] or 0) > ecran:
            ecarts.append(f'c2_soi:{k} ({v[1]} > écran {ecran})')
    fuite_b = any(isinstance(v, list) and len(v) > 3 and v[3] for o in out.values() for v in o.values())
    out['ecarts'] = ecarts
    out['fuite_B'] = fuite_b
    out['temoin_directeur'] = out['directeur']['ecran_leads'][0] == 200
    return {'repro': bool(ecarts) and out['temoin_directeur'], 'observe': out}
