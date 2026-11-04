// AFAC106 — preuve en direct : `seed_demo` sur une base où la société démo n'existe pas encore (rejoué dans une
// transaction ANNULÉE : la société démo locale existante et ses comptes sont renommés le temps du rejeu), puis
// l'auditeur de cohérence `run_audit(persist=False)` sur la société fraîchement semée — logique de la sonde
// `docs/audits/sondes/AFAC/C-AFAC-VER2-030.py`. Attendu : 0 violation de facturation ; FAC-DEMO-0002 payée par un vrai
// paiement de son TTC, échéance après l'émission ; relancer seed_demo ⇒ toujours un seul paiement.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage } from '../helpers.js'

const etape = groupe('AFAC', ['AFAC106'])
fermerDjangoApresTout()
test.describe.configure({ timeout: 600_000 })

etape('P.seed_demo_frais_oracle10', ['AFAC106'], async ({ page }) => {
  const res = await py(`from collections import Counter
from django.db import transaction
from django.core.management import call_command
from django.utils import timezone as tz
from authentication.models import Company
from apps.ventes.coherence.moteur import run_audit
from apps.ventes.models import Facture, Paiement
res = {}
with transaction.atomic():
    old = Company.objects.get(slug='taqinor-demo')
    Company.objects.filter(pk=old.pk).update(slug='taqinor-demo-ancienne')
    for u in U.objects.filter(company=old):
        U.objects.filter(pk=u.pk).update(username=u.username + '__anc', email=(u.email or '') + '.anc')
    call_command('seed_demo')
    co = Company.objects.get(slug='taqinor-demo')
    res['nouvelle'] = co.pk != old.pk
    rep = run_audit(company=co, persist=False).as_json()
    fact = [v for v in rep['violations'] if v.get('object_type') == 'facture']
    res['violations_facturation'] = [(v['rule'], v.get('reference')) for v in fact]
    res['erreurs_regle_facture'] = [e for e in rep['rule_errors'] if e.get('object_type') == 'facture']
    res['par_regle'] = dict(Counter(v['rule'] for v in rep['violations']))
    res['factures'] = {f.reference: dict(statut=f.statut, emission=str(f.date_emission), echeance=str(f.date_echeance), du=str(f.montant_du), ttc=str(f.total_ttc), paiements=[(str(m), s) for m, s in Paiement.objects.filter(facture=f).values_list('montant', 'statut')]) for f in Facture.objects.filter(company=co)}
    call_command('seed_demo')
    res['paiements_apres_reseed'] = Paiement.objects.filter(facture__company=co, facture__reference='FAC-DEMO-0002').count()
    res['jour'] = str(tz.localdate())
    transaction.set_rollback(True)
res['demo_intacte'] = Company.objects.filter(slug='taqinor-demo').count() == 1 and U.objects.filter(username='demo_admin').exists()
sortie(res)`)
  expect(res.nouvelle, 'seed_demo a semé une société neuve').toBe(true)
  expect(res.violations_facturation, `oracle 10 : 0 violation de facturation (${JSON.stringify(res.par_regle)})`).toEqual([])
  expect(res.erreurs_regle_facture).toEqual([])
  const f2 = res.factures['FAC-DEMO-0002']
  expect([f2.statut, Number(f2.du)]).toEqual(['payee', 0])
  expect(f2.paiements, 'un paiement encaissé du TTC').toEqual([[f2.ttc, 'encaisse']])
  expect(f2.emission <= f2.echeance, `émission ${f2.emission} ≤ échéance ${f2.echeance}`).toBe(true)
  expect(res.factures['FAC-DEMO-0001'].statut, 'FAC-DEMO-0001 inchangée (émise)').toBe('emise')
  expect(res.paiements_apres_reseed, 'relancer seed_demo ⇒ toujours un seul paiement').toBe(1)
  expect(res.demo_intacte, 'transaction annulée : la démo locale est intacte').toBe(true)
  await assurerSessionPage(page)
  await page.goto('/ventes/factures')
  await expect(page.locator('body')).toBeVisible()
})
