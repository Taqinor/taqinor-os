SONDE = {"constat": "C-AACQ-VER-301", "sha": "c6ab9b58e",
         "attendu": "compte Meta en USD, garde-fous jamais saisis (plafond 100, devise '') : l'écran Connexion dit "
                    "« Plafond saisi en MAD … non appliqué — ressaisissez-le » ; ressaisir la MÊME valeur 100 et "
                    "enregistrer (corps complet du formulaire, ConnectionScreen.jsx::saveGuard) pose ceiling_currency "
                    "= 'USD' — le plafond devient appliqué",
         "modeles": ["adsengine.GuardrailConfig", "adsengine.MetaConnection", "roles.Role",
                     "authentication.Company", "authentication.CustomUser"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.roles.models import Role
    from apps.adsengine.models import MetaConnection, GuardrailConfig
    U = get_user_model()
    c = Company.objects.create(nom='sonde-aacq-ver-301', slug='sonde-aacq-ver-301')
    MetaConnection.objects.create(company=c, ad_account_id='act_sonde_301', currency='USD', enabled=True,
                                  credentials={'access_token': 'tok'})
    r = Role.objects.create(company=c, nom='sonde-aacq-301-role',
                            permissions=['adsengine_view', 'adsengine_manage', 'adsengine_approve'])
    u = U.objects.create_user(username='sonde-aacq-ver-301', password='x', company=c, role_legacy='normal', role=r)
    api = APIClient(); api.force_authenticate(u)
    url = '/api/django/adsengine/guardrail/'
    g0 = api.get(url, HTTP_HOST='localhost').data
    # Corps complet tel que saveGuard l'envoie : tous les champs numériques non vides + bascules.
    corps = {k: v for k, v in g0.items()
             if k not in ('ceiling_currency', 'require_approval_above_mad') and v not in (None, '')}
    # « ressaisissez-le » : le responsable retape la même valeur affichée (100) et enregistre.
    p1 = api.patch(url, corps, format='json', HTTP_HOST='localhost')
    apres_ressaisie = GuardrailConfig.objects.get(company=c).ceiling_currency
    # Variante : seul le plancher d'exploration change ; le plafond quotidien (défaut MAD, jamais retapé) suit.
    corps2 = dict(corps, exploration_floor_mad=(corps.get('exploration_floor_mad') or 20) + 5)
    p2 = api.patch(url, corps2, format='json', HTTP_HOST='localhost')
    cfg = GuardrailConfig.objects.get(company=c)
    print(f"GET0 plafond={g0.get('max_daily_budget_mad')} devise={g0.get('ceiling_currency')!r} ; "
          f"PATCH même valeur {p1.status_code} -> devise={apres_ressaisie!r} ; "
          f"PATCH plancher seul {p2.status_code} -> devise={cfg.ceiling_currency!r} plafond_quotidien={cfg.daily_budget_ceiling_mad}")
    return {'repro': p1.status_code == 200 and apres_ressaisie == ''}
