# flake8: noqa  (sonde de contre-visite vérifie AANA du 04/11, rejouable par scripts/sonde.py — AMET93)
"""AANA65 : `apps/crm/leads_views.py::LeadIntakeActionsMixin.roi_sources` sert `win_rate` = signés ÷ leads NON perdus
(règle de `apps/reporting/services.py::taux_gain`) ; même canal lu par `win-loss-by-source` (`by_canal.close_rate_pct`).
Vraies routes, admin. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AANA-VER4-010", "sha": "d54c88db3",
         "attendu": "groupe site_web/mix {1 signé, 1 perdu, 1 ouvert} : win_rate 50.0 (pas 33.3) = close_rate_pct du canal site_web ; groupe tout perdu : win_rate null",
         "modeles": ["authentication.Company", "crm.Lead", "roles.Role"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm import stages
    from apps.crm.models import Lead
    from apps.roles.models import Role
    from apps.roles.permissions_registre import ADMIN_PERMISSIONS
    co = Company.objects.create(nom='Sonde AANA VER4-010', slug='sonde-aana-ver4-010')
    role, _ = Role.objects.get_or_create(company=co, nom='Administrateur',
                                         defaults={'permissions': ADMIN_PERMISSIONS, 'est_systeme': True})
    u = get_user_model().objects.create_user(username='sonde-aana-ver4-010', password='x', company=co,
                                             role=role, role_legacy='admin')
    mk = lambda nom, camp, stage, perdu=False: Lead.objects.create(
        company=co, nom=nom, canal='site_web', utm_campaign=camp, stage=stage, perdu=perdu,
        motif_perte='Prix' if perdu else '', owner=u)
    mk('Signe', 'mix', stages.SIGNED)
    mk('Perdu', 'mix', stages.QUOTE_SENT, perdu=True)
    mk('Ouvert', 'mix', stages.CONTACTED)
    mk('ToutPerdu', 'tout-perdu', stages.QUOTE_SENT, perdu=True)
    api = APIClient()
    api.force_authenticate(u)
    r = api.get('/api/django/crm/leads/roi-sources/', HTTP_HOST='localhost')
    w = api.get('/api/django/reporting/commercial/win-loss-by-source/', HTTP_HOST='localhost')
    rows = r.data if isinstance(getattr(r, 'data', None), list) else (getattr(r, 'data', None) or {}).get('results', [])
    lignes = {(x.get('canal'), x.get('utm_campaign')): x for x in rows}
    mix = lignes.get(('site_web', 'mix'), {})
    tp = lignes.get(('site_web', 'tout-perdu'), {})
    wd = w.data if isinstance(getattr(w, 'data', None), dict) else {}
    canal = next((c for c in wd.get('by_canal', []) if c.get('canal') == 'site_web'), {})
    print(f"roi={r.status_code} mix={ {k: mix.get(k) for k in ('lead_count', 'signed_count', 'win_rate')} } "
          f"tout_perdu.win_rate={tp.get('win_rate')} winloss={w.status_code} close_rate_site_web(4 leads, 2 perdus)={canal.get('close_rate_pct')}")
    ok = (r.status_code == 200 and mix.get('win_rate') == 50.0 and tp.get('win_rate') is None
          and mix.get('lead_count') == 3 and mix.get('signed_count') == 1)
    # repro = l'écart d'origine (perdus au dénominateur) se reproduit
    return {'repro': not ok, 'mix': mix, 'tout_perdu': tp, 'close_rate_site_web': canal.get('close_rate_pct')}
