# flake8: noqa  (sonde d'audit de parcours PA5, rejouable par scripts/sonde.py — METHODE §C.4)
"""K22 — synchro terrain : une op qui lève hors des 3 exceptions prévues (FieldOpConflit, FieldOpError,
IntegrityError) fait échouer TOUT le lot. Vraie route POST installations/sync/ :
(A) [réserve ok, série de 141 signes (colonne 120), réserve ok2] → 500 attendu ; op1 appliquée et
mémorisée (FieldOp), op3 jamais appliquée. (B) [réserve ok3, réserve avec NUL, réserve ok4] → 400 de lot
(ValueError psycopg2) ; op1 appliquée, op3 absente. (T) témoin : [réserve ok5, série 20 signes] → 200,
2 appliquées."""
SONDE = {"constat": "C-ACSV-022", "sha": "f57951e87",
         "attendu": "repro si A = 500 et B = 400 avec, pour chacun, op1 mémorisée et op3 absente ; T = 200",
         "modeles": ["installations.FieldOp", "installations.Reserve", "installations.ComponentSerial"]}


def sonde(ctx):
    import uuid
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation, Intervention, Reserve, FieldOp

    H = {'HTTP_HOST': 'localhost'}
    URL = '/api/django/installations/sync/'
    co = Company.objects.create(nom='Sonde ACSV 022', slug='sonde-acsv-022')
    u = get_user_model().objects.create_user(username='sonde_acsv_022', password='x',
                                             role_legacy='admin', company=co)
    api = APIClient(raise_request_exception=False)
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client', prenom='A022', email='a022@example.invalid')
    inst = Installation.objects.create(company=co, reference='CHT-A022', client=cl)
    iv = Intervention.objects.create(company=co, installation=inst, type_intervention='pose',
                                     created_by=u, statut='sur_site')

    def op(t, **p):
        p['intervention'] = iv.id
        return {'client_op_id': 'a022-' + uuid.uuid4().hex, 'op_type': t, 'payload': p}

    def lot(ops):
        r = api.post(URL, {'ops': ops}, format='json', **H)
        memo = [FieldOp.objects.filter(company=co, client_op_id=o['client_op_id'], ok=True).exists()
                for o in ops]
        return {'http': r.status_code, 'memorisees': memo,
                'corps': str(r.content[:200], 'utf-8', 'replace')}

    obs = {}
    obs['A'] = lot([op('intervention.reserve', description='ok1'),
                    op('intervention.serial', numero_serie='X' * 141),
                    op('intervention.reserve', description='ok2')])
    obs['B'] = lot([op('intervention.reserve', description='ok3'),
                    op('intervention.reserve', description='nul\x00ici'),
                    op('intervention.reserve', description='ok4')])
    obs['T'] = lot([op('intervention.reserve', description='ok5'),
                    op('intervention.serial', numero_serie='SN-TEMOIN-0000000001')])
    obs['reserves'] = sorted(Reserve.objects.filter(intervention=iv).values_list('description', flat=True))
    print(obs)
    a, b, t = obs['A'], obs['B'], obs['T']
    obs['repro'] = bool(a['http'] == 500 and a['memorisees'] == [True, False, False]
                        and b['http'] == 400 and b['memorisees'] == [True, False, False]
                        and t['http'] == 200 and t['memorisees'] == [True, True])
    return obs
