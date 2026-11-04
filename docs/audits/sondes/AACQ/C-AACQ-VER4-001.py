# flake8: noqa  (sonde de contre-visite vérifie AACQ du 04/11, rejouable par scripts/sonde.py)
"""AACQ6 — chemin RÉEL, sans mock : le test `test_aacq_consentement_chantier.py` simule
`installations.selectors.chantier_client_id` ; ici un vrai chantier (Installation) du client A, un
consentement photo actif du client B, POST `creatifs/import-chantier/` avec client_id=B puis client_id=A,
puis PATCH du `client_id` d'un consentement. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AACQ-VER4-001", "sha": "8fb8ba32b",
         "attendu": "client_id=B (consentement de B, chantier de A) -> 400 consentement_manquant, 0 CreativeAsset ; "
                    "client_id=A (consentement de A) -> le contrôle de propriétaire passe (400 photo_introuvable "
                    "car aucune pièce jointe, jamais consentement_manquant) ; PATCH consentement client_id -> 400, inchangé",
         "modeles": ["adsengine.ConsentRecord", "adsengine.CreativeAsset", "installations.Installation",
                     "crm.Client", "roles.Role", "authentication.Company", "authentication.CustomUser"]}


def sonde(ctx):
    import datetime
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.roles.models import Role
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.adsengine.models import ConsentRecord, CreativeAsset
    U = get_user_model()
    co = Company.objects.create(nom='sonde-aacq-ver4-001', slug='sonde-aacq-ver4-001')
    r = Role.objects.create(company=co, nom='sonde-aacq-ver4-001-role',
                            permissions=['adsengine_view', 'adsengine_manage'])
    u = U.objects.create_user(username='sonde-aacq-ver4-001', password='x', company=co,
                              role_legacy='normal', role=r)
    a = Client.objects.create(company=co, nom='A', prenom='Client', email='a-ver4-001@example.invalid')
    b = Client.objects.create(company=co, nom='B', prenom='Client', email='b-ver4-001@example.invalid')
    ch = Installation.objects.create(company=co, reference='CH-SONDE-VER4-001', client=a)
    jour = datetime.date.today() - datetime.timedelta(days=1)
    cb = ConsentRecord.objects.create(company=co, client_id=b.pk, client_nom='B', portee_photo=True,
                                      date_consentement=jour)
    ConsentRecord.objects.create(company=co, client_id=a.pk, client_nom='A', portee_photo=True,
                                 date_consentement=jour)
    api = APIClient(); api.force_authenticate(u)
    url = '/api/django/adsengine/creatifs/import-chantier/'
    avant = CreativeAsset.objects.filter(company=co).count()
    rb = api.post(url, {'chantier_id': ch.pk, 'attachment_id': 999999, 'client_id': b.pk},
                  format='json', HTTP_HOST='localhost')
    ra = api.post(url, {'chantier_id': ch.pk, 'attachment_id': 999999, 'client_id': a.pk},
                  format='json', HTTP_HOST='localhost')
    apres = CreativeAsset.objects.filter(company=co).count()
    rp = api.patch(f'/api/django/adsengine/consentements/{cb.pk}/', {'client_id': 999999},
                   format='json', HTTP_HOST='localhost')
    cb.refresh_from_db()
    jb = rb.json() if rb.status_code < 500 else {}
    ja = ra.json() if ra.status_code < 500 else {}
    print(f"B: {rb.status_code} {jb.get('blocked_reason')!r} {jb.get('detail') or jb.get('message')!r} ; "
          f"A: {ra.status_code} {ja.get('blocked_reason')!r} ; assets {avant}->{apres} ; "
          f"PATCH client_id {rp.status_code} -> {cb.client_id} (B={b.pk})")
    return {'repro': (rb.status_code == 400 and jb.get('blocked_reason') == 'consentement_manquant'
                      and ra.status_code == 400 and ja.get('blocked_reason') == 'photo_introuvable'
                      and apres == avant and rp.status_code == 400 and cb.client_id == b.pk)}
