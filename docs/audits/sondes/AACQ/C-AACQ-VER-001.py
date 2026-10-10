SONDE = {"constat": "C-AACQ-VER-001", "sha": "5ea32b58b",
         "attendu": "compte Meta en USD : armer une règle sans saisir de seuil ne la rend pas applicable avec 250 « MAD » lus comme 250 USD ; le garde-fou expose sa devise"}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.roles.models import Role
    from apps.adsengine.models import MetaConnection, RulePolicy, GuardrailConfig
    from apps.adsengine import guardrails, rule_templates
    U = get_user_model()
    c = Company.objects.create(nom='sonde-aacq-ver-001', slug='sonde-aacq-ver-001')
    MetaConnection.objects.create(company=c, ad_account_id='act_sonde', currency='USD', enabled=True, credentials={'access_token': 'tok'})
    r = Role.objects.create(company=c, nom='sonde-aacq-role', permissions=['adsengine_view', 'adsengine_manage', 'adsengine_approve'])
    u = U.objects.create_user(username='sonde-aacq-ver-001', password='x', company=c, role_legacy='normal', role=r)
    api = APIClient(); api.force_authenticate(u)
    resp = api.post('/api/django/adsengine/regles/', {'template_key': 'stop_loss_cpl', 'enabled': True, 'dry_run': False}, format='json', HTTP_HOST='localhost')
    if resp.status_code >= 400:
        print('création règle', resp.status_code, str(resp.data)[:300]); return {'repro': False}
    p = RulePolicy.objects.get(pk=resp.data['id'])
    seuil = rule_templates.resolve_params('stop_loss_cpl', p.params).get('threshold_mad')
    applicable = guardrails.mad_threshold_blocked_reason(c, p.threshold_currency) is None
    pr = api.patch('/api/django/adsengine/guardrail/', {'max_daily_budget_mad': 250}, format='json', HTTP_HOST='localhost')
    g = api.get('/api/django/adsengine/guardrail/', HTTP_HOST='localhost').data
    cfg = GuardrailConfig.objects.get(company=c)
    print(f"règle {resp.status_code} devise={p.threshold_currency!r} seuil_par_défaut={seuil} applicable={applicable} ; "
          f"garde-fou PATCH {pr.status_code} devise_base={cfg.ceiling_currency!r} devise_exposée_GET={'ceiling_currency' in (g or {})}")
    return {'repro': applicable and p.threshold_currency == 'USD'}
