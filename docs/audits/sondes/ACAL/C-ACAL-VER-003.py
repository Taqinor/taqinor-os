SONDE = {"constat": "C-ACAL-VER-003", "sha": "5ea32b58b",
         "attendu": "calepinage vierge (roof_layout NULL) : POST layout/section/ horizonProfile avec la base servie par GET layout/ -> 200 et section écrite"}


def sonde(ctx):
    from rest_framework.test import APIClient
    from authentication.models import Company
    from django.contrib.auth import get_user_model
    from apps.crm.models import Lead
    from apps.calepinage.models import Calepinage
    U = get_user_model()
    co = Company.objects.create(nom='Sonde ACAL VER-003', slug='sonde-acal-ver-003')
    u = U.objects.create_user(username='sonde_acal_ver_003', password='x', company=co, role_legacy='admin')
    lead = Lead.objects.create(company=co, nom='Sonde vierge')
    cal = Calepinage.objects.create(company=co, lead_id=lead.pk, titre='vierge')
    api = APIClient(); api.force_authenticate(u)
    base = '/api/django/calepinage/calepinages/%d/layout/' % cal.pk
    g = api.get(base, HTTP_HOST='localhost')
    emp = (g.data or {}).get('empreinte_document') if hasattr(g, 'data') and isinstance(g.data, dict) else None
    hp = {'source': 'saisie', 'points': [{'azimuthDeg': 0, 'elevationDeg': 2}, {'azimuthDeg': 180, 'elevationDeg': 3}]}
    r = api.post(base + 'section/', {'cle': 'horizonProfile', 'valeur': hp, 'base_empreinte': emp if emp is not None else ''}, format='json', HTTP_HOST='localhost')
    cal.refresh_from_db()
    print(f"GET {g.status_code} empreinte={emp!r} ; section {r.status_code} {str(getattr(r, 'data', ''))[:200]} ; roof_layout={str(cal.roof_layout)[:80]}")
    return {'repro': r.status_code >= 400}
