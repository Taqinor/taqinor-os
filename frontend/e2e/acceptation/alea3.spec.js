// ALEA61, ALEA65 — rejeu en direct : le Froid réveillé par le site sort du parcage ; « en retard » lu en jours ouvrés
// par la file Relances et Ma file (dimanche non, lundi oui, férié société respecté).
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { lireJson, listeDe, telephoneMobileUnique, assurerSessionPage } from '../helpers.js'

const etape = groupe('ALEA', ['ALEA61', 'ALEA65'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 300_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`

etape('VER3-11', ['ALEA61'], async ({ page, testInfo }) => {
  const m = marque()
  const tel = telephoneMobileUnique()
  const id = await py(`from apps.crm.models import Lead
from apps.crm import stages
l = Lead.objects.create(company_id=1, nom='ALEA61 ${m}', telephone=${JSON.stringify(tel)}, source=Lead.Source.SITE_WEB, canal=Lead.Canal.SITE_WEB, stage=stages.COLD, parc_etat='nurture', parc_raison='budget')
Lead.objects.filter(pk=l.pk).update(date_creation=timezone.now() - datetime.timedelta(days=40))
sortie(l.id)`)
  const secret = await py(`from django.conf import settings
sortie(settings.WEBSITE_LEAD_WEBHOOK_SECRET)`)
  const pub = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  const r = await pub.post(`${API}/crm/webhooks/website-leads/`, {
    ...T,
    data: { idempotencyKey: globalThis.crypto.randomUUID(), consent: true, fullName: `ALEA61 ${m}`, phoneE164: tel },
    headers: { 'X-Webhook-Secret': secret },
  })
  expect(r.status(), `webhook signé : ${await r.text()}`).toBeLessThan(300)
  await pub.dispose()
  const relu = await lireJson(await page.request.get(`${API}/crm/leads/${id}/`, T), 'lead relu')
  expect(relu.stage, 'lead revenu en NEW').toBe('NEW')
  expect([relu.parc_etat, relu.parc_raison], 'parcage vidé').toEqual([null, null])
  const hist = listeDe(await lireJson(await page.request.get(`${API}/crm/leads/${id}/historique/`, T), 'historique'))
  expect(JSON.stringify(hist), 'chatter : parc_raison budget → vide').toContain('parc_raison')
  const ouvertes = listeDe(await lireJson(await page.request.get(`${API}/crm/relance-etapes/?lead=${id}`, T), 'touches')).filter((t) => t.statut === 'a_faire')
  expect(ouvertes.length, 'reprise CAD107 ouverte').toBeGreaterThanOrEqual(1)
})

etape('VER3-31', ['ALEA65'], async () => {
  // Lecture à date passée : les sélecteurs prennent `today` ; transaction annulée, société neuve au calendrier par défaut.
  const r = await py(`from django.db import transaction
from authentication.models import Company
from apps.crm.models import Lead
from apps.crm import stages
from apps.crm.models_cadence import RelanceEtape
from apps.crm.cadence_selectors import relances_du_jour, ma_file_commercial_items
from apps.parametres.models import CompanyProfile
from apps.roles.models import Role
from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS
res = {}
with transaction.atomic():
    co = Company.objects.create(nom='Accept ALEA65', slug='accept-alea65')
    pf, _ = CompanyProfile.objects.get_or_create(company=co)
    role = Role.objects.create(company=co, nom='Commercial A65', permissions=list(COMMERCIAL_PERMISSIONS))
    u = U.objects.create_user(username='accept-alea65', password='x', company=co, role=role)
    lead = Lead.objects.create(company=co, nom='Retard', prenom='R', owner=u, stage=stages.CONTACTED, telephone='+212661000965')
    RelanceEtape.objects.filter(lead=lead).delete()
    Lead.objects.filter(pk=lead.pk).update(relance_date=datetime.date(2026, 10, 9))
    def lu(j):
        return [lead.pk in set(relances_du_jour(co, u, scope='overdue', today=j).values_list('pk', flat=True)),
                any(i['kind'] == 'relance' and i['link'].endswith(f'lead={lead.pk}') and i['urgency'] == 'overdue' for i in ma_file_commercial_items(co, u, today=j))]
    res['dimanche'] = lu(datetime.date(2026, 10, 11))
    res['lundi'] = lu(datetime.date(2026, 10, 12))
    from apps.crm.controle_suivi import seuil_retard
    import inspect
    res['source_ferie'] = inspect.getsource(seuil_retard)[:600]
    transaction.set_rollback(True)
sortie(res)`)
  expect(r.dimanche, 'dimanche 11/10 : ni Relances ni Ma file').toEqual([false, false])
  expect(r.lundi, 'lundi 12/10 : Relances et Ma file').toEqual([true, true])
})
