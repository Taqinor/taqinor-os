// APRF42 (après ERR-PERF-DEVIS-LISTE-CI-N1) — liste des devis (lignes C&I comprises) et des leads : même nombre de requêtes pour N et
// 3N lignes, mesuré à chaud (3e lecture) et en transaction annulée (clause persistance d'APRF42). Le 1er appel d'une route charge
// ses caches : c'est lui qui faisait tomber l'oracle `plat_page_leads` de la sonde C-APRF-ACC-CRM (11→6→6), jamais une pente.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'

const etape = groupe('APRF', ['APRF42'])
fermerDjangoApresTout()
test.describe.configure({ timeout: 300_000 })

const mesurer = (url) => py(`from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
c = APIClient(); c.force_authenticate(U.objects.get(username='demo_admin'))
res = {}
with transaction.atomic():
    for n in (30, 90):
        for _ in range(3):
            with CaptureQueriesContext(connection) as q:
                r = c.get(f'${url}?page_size={n}', HTTP_HOST='localhost')
        lignes = r.data.get('results', r.data) if isinstance(r.data, dict) else r.data
        res[str(n)] = dict(st=r.status_code, n=len(lignes), q=len(q), ci=sum(1 for x in lignes if x.get('mode_installation') in ('commercial', 'industriel')))
    transaction.set_rollback(True)
sortie(res)`)

etape('P2.3.devis_N_3N', ['APRF42'], async () => {
  const m = await mesurer('/api/django/ventes/devis/')
  expect([m['30'].st, m['90'].st], '200').toEqual([200, 200])
  expect([m['30'].n, m['90'].n], 'N et 3N lignes').toEqual([30, 90])
  expect(m['90'].ci, `lignes C&I dans la page (${JSON.stringify(m)})`).toBeGreaterThan(m['30'].ci)
  expect(Math.abs(m['90'].q - m['30'].q), `pente plate (${JSON.stringify(m)})`).toBeLessThanOrEqual(1)
})

etape('P2.3.leads_N_3N', ['APRF42'], async () => {
  const m = await mesurer('/api/django/crm/leads/')
  expect([m['30'].n, m['90'].n], 'N et 3N lignes').toEqual([30, 90])
  expect(Math.abs(m['90'].q - m['30'].q), `pente plate (${JSON.stringify(m)})`).toBeLessThanOrEqual(1)
})
