# flake8: noqa  (sonde de contre-visite vérifie AANA, rejouable par scripts/sonde.py — AMET93)
"""AANA21 : deux taux de gain sur la même page Commercial — `win_rate_pct` (gagnés ÷ non perdus, `services.taux_gain`)
et `reporting/commercial.py::win_loss_by_source` `overall_close_rate_pct` (gagnés ÷ TOUS, perdus compris). Vraies routes."""
SONDE = {"constat": "C-AANA-VER-003", "sha": "32375fe65",
         "attendu": "1 lead signé + 1 lead perdu : win_rate_pct différent de overall_close_rate_pct (un seul taux attendu)"}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm import stages
    from apps.crm.models import Lead
    co = Company.objects.create(nom='Sonde AANA VER-003', slug='sonde-aana-ver-003')
    u = get_user_model().objects.create_user(username='sonde-aana-ver-003', password='x', company=co, role_legacy='admin')
    Lead.objects.create(company=co, nom='Gagne', stage=stages.SIGNED, owner=u)
    Lead.objects.create(company=co, nom='Perdu', stage=stages.NEW, perdu=True, owner=u)
    api = APIClient()
    api.force_authenticate(u)
    d = api.get('/api/django/reporting/commercial/dashboard/', HTTP_HOST='localhost')
    w = api.get('/api/django/reporting/commercial/win-loss-by-source/', HTTP_HOST='localhost')
    dd = d.data if isinstance(getattr(d, 'data', None), dict) else {}
    wd = w.data if isinstance(getattr(w, 'data', None), dict) else {}
    a = dd.get('win_rate_pct')
    b = (wd.get('summary') or {}).get('overall_close_rate_pct')
    print(f'dashboard={d.status_code} win_rate_pct={a} winloss={w.status_code} overall_close_rate_pct={b} (attendu égaux)')
    return {'repro': d.status_code == 200 and w.status_code == 200 and a is not None and b is not None and a != b,
            'win_rate_pct': a, 'overall_close_rate_pct': b}
