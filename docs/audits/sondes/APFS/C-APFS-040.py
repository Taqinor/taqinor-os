# flake8: noqa  (sonde d'audit de parcours PF1 « Sécurité / multi-société », rejouable par scripts/sonde.py — METHODE §C.4)
"""K04 + K41 + K44 — le palier « responsable » (`IsAdminOrResponsableTier` SEUL, `menu_tier`, `users_voir`) ouvre
les gestes d'administration à Admin RH / Admin Ventes / Technicien responsable / Commercial responsable sans aucun
code de module. Par rôle système (bâti comme `init_roles`, JWT réel) dans la société A :
  (1) `POST publicapi/keys/` clé LIVE `read:leads`+`read:factures`+`devis:write`, puis lecture `/api/public/v1/leads/`
      avec la clé (Api-Key) ; (2) `POST publicapi/webhooks/` abonné à `facture.created`/`lead.created` ;
  (3) `POST core/modules/<feuille>/desactiver/` (module coupé pour toute la société) ;
  (4) K44 : `PATCH core/api-usage/plan/` quotas 0 + inactif (= illimité) — témoin `PATCH publicapi/plan/` (ASEC44, 403) ;
  (5) passage de garde (403 vs 400 sur corps vide) : matrices d'approbation, workflows, thème, gabarits de marque ;
  (6) `POST automation/approval-requests/<id>/approve/` d'une demande dont le type exige le palier ADMIN.
Témoin ASEC31 : `PUT parametres/update/` (palier + `parametres_modifier`) refusé à Admin RH / Technicien responsable.
Société B : aucune clé, aucun webhook, aucun module, aucun plan ne bouge. Le claim `role` du vrai jeton (K67) est noté."""
SONDE = {"constat": "C-APFS-040", "sha": "57d3fd371d",
         "attendu": "repro si Admin RH et Technicien responsable (sans code CRM/ventes/parametres) obtiennent 201 clé + "
                    "lecture des leads par la clé, 201 webhook, 200 désactivation de module, 200 plan core, 200 "
                    "approbation d'une demande palier admin, alors que le témoin ASEC31 (parametres/update) leur "
                    "répond 403 ; Commercial/Technicien 403 partout",
         "modeles": ["publicapi.ApiKey", "publicapi.Webhook", "core.ModuleToggle", "core.ApiUsagePlan",
                     "automation.ApprovalRequest", "crm.Lead", "roles.Role", "authentication.Company"]}


def sonde(ctx):
    from unittest import mock
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import AccessToken
    from authentication.models import Company
    from authentication.role_tiers import tier_for_role_fields
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
    from apps.publicapi.models import ApiKey, Webhook
    from apps.automation.models import ApprovalRequestType, ApprovalRequest
    from apps.crm.models import Lead
    from core.models import ApiUsagePlan, ModuleToggle
    from core import feature_flags, modules as modules_infra, api_usage
    try:
        from authentication.serializers import CustomTokenObtainPairSerializer as TokSer
    except Exception:  # noqa
        TokSer = None
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    R = dict(CANONICAL_SYSTEM_ROLES)
    coA = Company.objects.create(nom='Sonde APFS 040 A', slug='sonde-apfs-040-a')
    coB = Company.objects.create(nom='Sonde APFS 040 B', slug='sonde-apfs-040-b')

    def compte(co, nom, suffixe):
        perms = list(R[nom])
        role, _ = Role.objects.get_or_create(company=co, nom=nom,
                                             defaults={'permissions': perms, 'est_systeme': True})
        u = U.objects.create_user(username=f's040{suffixe}-' + nom.lower().replace(' ', '-'), password='x',
                                  company=co, role=role, role_legacy=tier_for_role_fields(nom, True, perms))
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(AccessToken.for_user(u)))
        return u, c

    noms = ['Directeur', 'Administrateur', 'Responsable', 'Admin RH', 'Admin Ventes', 'Technicien responsable',
            'Commercial responsable', 'Commercial', 'Technicien']
    comptes = {n: compte(coA, n, 'a') for n in noms}
    dirB, _ = compte(coB, 'Directeur', 'b')
    Lead.objects.create(company=coA, nom='Prospect A confidentiel', email='prospect-a@example.invalid')
    Lead.objects.create(company=coB, nom='Prospect B', email='prospect-b@example.invalid')

    # module feuille (aucun dépendant), hors couches utilisées par la sonde
    manifests = modules_infra.collect_manifests()
    deps = set()
    for m in manifests.values():
        deps.update(m.get('depends') or [])
    exclus = {'publicapi', 'automation', 'crm', 'core', 'parametres', 'roles'}
    feuilles = sorted(k for k, m in manifests.items()
                      if m.get('installable', True) and k not in deps and k not in exclus
                      and feature_flags.module_actif(coA, k))
    feuille = 'sav' if 'sav' in feuilles else (feuilles[0] if feuilles else None)
    plan0 = api_usage.plan_pour_societe(coA)
    plan0_vals = {k: getattr(plan0, k) for k in ('code', 'quota_par_minute', 'quota_par_jour', 'quota_par_mois', 'actif')}
    planB = api_usage.plan_pour_societe(coB)
    planB_vals = {k: getattr(planB, k) for k in ('code', 'quota_par_minute', 'quota_par_jour', 'quota_par_mois', 'actif')}
    typ = ApprovalRequestType.objects.create(company=coA, nom='Remise exceptionnelle', palier_approbateur='admin')
    demandeur = comptes['Commercial'][0]

    def perms_cles(nom):
        p = set(R[nom])
        return {'users_voir': 'users_voir' in p, 'roles_gerer': 'roles_gerer' in p,
                'parametres_modifier': 'parametres_modifier' in p,
                'crm_codes': sorted(c for c in p if c.startswith(('crm_', 'lead')))[:3],
                'facture_codes': sorted(c for c in p if 'factur' in c)[:3]}

    obs = {'feuille': feuille, 'roles': {}}
    for nom in noms:
        u, c = comptes[nom]
        r = {'menu_tier': u.menu_tier, 'perms': perms_cles(nom)}
        if TokSer is not None:
            try:
                r['jwt_role_claim'] = TokSer.get_token(u).get('role')
            except Exception as exc:  # noqa
                r['jwt_role_claim'] = f'err {exc!r}'[:60]
        # témoin ASEC31
        t = c.patch('/api/django/parametres/update/', {}, format='json', **H)
        r['temoin_asec31_profile'] = t.status_code
        # (1) clé d'API LIVE
        k = c.post('/api/django/publicapi/keys/', {'label': f'cle {nom}',
                                                   'scopes': ['read:leads', 'read:factures', 'devis:write']},
                   format='json', **H)
        r['cle_http'] = k.status_code
        raw = (k.data or {}).get('key') if k.status_code == 201 else None
        if raw:
            pub = APIClient()
            lr = pub.get('/api/public/v1/leads/', HTTP_AUTHORIZATION='Api-Key ' + raw, **H)
            fr = pub.get('/api/public/v1/factures/', HTTP_AUTHORIZATION='Api-Key ' + raw, **H)
            noms_lus = []
            try:
                data = lr.json()
                rows = data.get('results', data) if isinstance(data, dict) else data
                noms_lus = sorted({str(x.get('nom')) for x in rows if isinstance(x, dict)})[:5]
            except Exception:  # noqa
                pass
            r['cle_lecture_leads'] = {'http': lr.status_code, 'noms': noms_lus}
            r['cle_lecture_factures_http'] = fr.status_code
        # (2) webhook sortant
        with mock.patch('apps.publicapi.serializers.validate_webhook_target_url', side_effect=lambda v: v):
            w = c.post('/api/django/publicapi/webhooks/', {'label': f'wh {nom}',
                                                           'target_url': 'https://hooks.example.com/x',
                                                           'events': ['facture.created', 'lead.created']},
                       format='json', **H)
        r['webhook_http'] = w.status_code
        # (3) désactivation d'un module pour toute la société
        if feuille:
            d = c.post(f'/api/django/core/modules/{feuille}/desactiver/', {}, format='json', **H)
            r['module_desactiver_http'] = d.status_code
            r['module_coupe'] = not feature_flags.module_actif(coA, feuille)
            if r['module_coupe']:
                feature_flags.activer_module(coA, feuille)
        # (4) K44 — plan de quotas core (jumeau d'ASEC44)
        corps = {'quota_par_minute': 0, 'quota_par_jour': 0, 'quota_par_mois': 0, 'actif': False}
        tw = c.patch('/api/django/publicapi/plan/', corps, format='json', **H)
        p = c.patch('/api/django/core/api-usage/plan/', corps, format='json', **H)
        pl = ApiUsagePlan.objects.get(pk=plan0.pk)
        r['plan_temoin_publicapi_http'] = tw.status_code
        r['plan_core_http'] = p.status_code
        r['plan_ecrit'] = {'actif': pl.actif, 'quota_par_jour': pl.quota_par_jour}
        ApiUsagePlan.objects.filter(pk=plan0.pk).update(**plan0_vals)
        # (5) passage de garde (corps vide : 403 = refusé, 400 = garde franchie)
        r['garde'] = {
            'matrices': c.post('/api/django/core/matrices-approbation/', {}, format='json', **H).status_code,
            'workflows': c.post('/api/django/core/workflow-definitions/', {}, format='json', **H).status_code,
            'theme': c.patch('/api/django/core/theme/courant/', {}, format='json', **H).status_code,
            'gabarits': c.post('/api/django/core/branded-templates/', {}, format='json', **H).status_code,
        }
        # (6) décision d'une demande dont le type exige le palier ADMIN
        req = ApprovalRequest.objects.create(company=coA, request_type=typ, demandeur=demandeur,
                                             payload={'taux': 5})
        a = c.post(f'/api/django/automation/approval-requests/{req.id}/approve/', {'note': 'ok'}, format='json', **H)
        req.refresh_from_db()
        r['approbation_palier_admin'] = {'http': a.status_code, 'statut': req.status}
        obs['roles'][nom] = r

    obs['B'] = {'cles': ApiKey.objects.filter(company=coB).count(),
                'webhooks': Webhook.objects.filter(company=coB).count(),
                'toggles': ModuleToggle.objects.filter(company=coB).count(),
                'plan_inchange': {k: getattr(ApiUsagePlan.objects.get(pk=planB.pk), k) for k in planB_vals} == planB_vals}
    obs['A_cles_emises'] = ApiKey.objects.filter(company=coA).count()
    print(obs)
    ro = obs['roles']

    def ouvert(nom):
        x = ro[nom]
        return (x['cle_http'] == 201 and x.get('cle_lecture_leads', {}).get('http') == 200
                and 'Prospect A confidentiel' in x.get('cle_lecture_leads', {}).get('noms', [])
                and x['webhook_http'] == 201 and x.get('module_coupe') is True
                and x['plan_core_http'] == 200 and x['plan_ecrit']['actif'] is False
                and x['approbation_palier_admin']['statut'] == 'approved')
    temoin_ok = (ro['Directeur']['cle_http'] == 201
                 and ro['Admin RH']['temoin_asec31_profile'] == 403
                 and ro['Technicien responsable']['temoin_asec31_profile'] == 403
                 and ro['Commercial']['cle_http'] == 403 and ro['Technicien']['cle_http'] == 403
                 and all(ro[n]['plan_temoin_publicapi_http'] == 403 for n in noms)
                 and obs['B']['cles'] == 0 and obs['B']['webhooks'] == 0 and obs['B']['plan_inchange'])
    obs['temoin_ok'] = temoin_ok
    obs['ouverts'] = [n for n in noms if ouvert(n)]
    obs['repro'] = bool(temoin_ok and ouvert('Admin RH') and ouvert('Technicien responsable'))
    return obs
