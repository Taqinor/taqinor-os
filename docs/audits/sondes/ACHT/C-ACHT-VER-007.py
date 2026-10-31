# flake8: noqa  (sonde de contre-visite vérifie ACHT, rejouable par scripts/sonde.py — AMET93)
"""ACHT36 : la réouverture d'une intervention terminée ne doit rejouer aucun effet de clôture ;
`publicapi/signals.py::intervention_post_save` journalise au flux public (et livre en webhook)
« intervention.completed » à CHAQUE passage à terminée. Le journal ApiEvent est écrit dans la
transaction (annulé avec elle) ; la livraison webhook attend le commit (jamais atteint)."""
SONDE = {"constat": "C-ACHT-VER-007", "sha": "db8ca9670",
         "attendu": "terminee, sur_site, terminee : 2 ApiEvent intervention.completed (1 attendu)"}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.installations.models import Installation, Intervention
    from apps.publicapi.models import ApiEvent
    co = Company.objects.create(nom='Sonde ACHT VER-004', slug='sonde-acht-ver-004')
    u = get_user_model().objects.create_user(username='sonde-acht-ver-004', password='x', company=co, role_legacy='admin')
    inst = Installation.objects.create(company=co, reference='CH-SONDE-ACHT-004')
    iv = Intervention.objects.create(company=co, installation=inst, type_intervention='pose', created_by=u,
                                     technicien=u, statut=Intervention.Statut.SUR_SITE)
    api = APIClient()
    api.force_authenticate(u)
    codes = []
    for s in ('terminee', 'sur_site', 'terminee'):
        r = api.patch(f'/api/django/installations/interventions/{iv.id}/', {'statut': s}, format='json',
                      HTTP_HOST='localhost')
        codes.append(r.status_code)
    n = ApiEvent.objects.filter(company=co, type='intervention.completed').count()
    iv.refresh_from_db()
    print(f'patch={codes} statut={iv.statut} ApiEvent intervention.completed={n} (attendu 1)')
    return {'repro': codes == [200, 200, 200] and n >= 2, 'patch': codes, 'evenements': n}
