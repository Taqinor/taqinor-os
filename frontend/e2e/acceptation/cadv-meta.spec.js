// Acceptation en direct — groupe CADV (cadence v4, acquisition Meta) : CADV101 et CADV113. Format : `_format.md`.
// Le webhook Meta Lead Ads est rejoué SIGNÉ (HMAC X-Hub-Signature-256) dans le Django de la pile locale, avec le
// client de test Django : la récupération Graph (`fetch_meta_lead_data`) est la SEULE chose simulée — aucun appel
// sortant. Données persistantes dans la société démo de la base jetable erp_live2.
import { expect, test } from '@playwright/test'
import { groupe } from './_oracles.js'
import { API_DJANGO, assurerSessionPage, executerDansDjango, lireJson } from '../helpers.js'

test.describe.configure({ timeout: 300_000 })
const etape = groupe('CADV', ['CADV101', 'CADV113'])
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })

function py(code) {
  const m = String(executerDansDjango(code)).match(/@@JSON@@(.*)/)
  if (!m) throw new Error('sortie Django sans JSON')
  return JSON.parse(m[1])
}

// Prélude commun : poste une notification signée au webhook, Graph simulé (`field_data` fourni).
const PRELUDE = `
import hashlib, hmac, json
from unittest import mock
from django.contrib.auth import get_user_model
from django.test import Client as TestClient, override_settings
from django.utils import timezone
from apps.crm.models import Lead
co = get_user_model().objects.get(username='demo_admin').company
tag = timezone.now().strftime('%H%M%S%f')
SECRET = 'acc-live-app-secret'
def poster(leadgen_id, field_data):
    corps = json.dumps({'entry': [{'changes': [{'field': 'leadgen', 'value': {'leadgen_id': leadgen_id, 'ad_id': '', 'adgroup_id': '', 'form_id': ''}}]}]}).encode()
    sig = 'sha256=' + hmac.new(SECRET.encode(), corps, hashlib.sha256).hexdigest()
    with override_settings(META_LEAD_ADS_APP_SECRET=SECRET, META_LEAD_ADS_ACCESS_TOKEN='acc-live-token',
                           META_LEAD_ADS_COMPANY_ID=co.pk, ALLOWED_HOSTS=['*']), \\
         mock.patch('apps.crm.webhooks.fetch_meta_lead_data', return_value={'field_data': field_data}):
        r = TestClient().post('/api/django/crm/webhooks/meta-lead-ads/', data=corps, content_type='application/json',
                              HTTP_X_HUB_SIGNATURE_256=sig, HTTP_HOST='localhost')
    return r.status_code, (r.json() if r.status_code == 200 else None)
`

etape('PA1.1', ['CADV101'], async ({ page }) => {
  const r = py(`${PRELUDE}
from apps.crm import stages
tel = '+2126' + tag[-8:]
owner, _ = get_user_model().objects.get_or_create(username='acc_cadv101_owner', defaults={'company': co, 'role_legacy': 'responsable'})
froid = Lead.objects.create(company=co, nom='Yassine Ennaji ACC' + tag, telephone=tel, canal=Lead.Canal.TELEPHONE,
    owner=owner, stage=stages.COLD, parc_etat='nurture', parc_raison='injoignable', ville='Rabat')
avant = Lead.objects.filter(company=co).count()
fd = [{'name': 'full_name', 'values': ['Yassine Ennaji']}, {'name': 'phone_number', 'values': [tel]}, {'name': 'city', 'values': ['Casablanca']}]
codes = [poster('7002' + tag[-6:], fd)[0] for _ in range(2)]
froid.refresh_from_db()
chatter = froid.activites.filter(body__contains='Nouvelle demande Meta').count()
passages = froid.activites.filter(field='stage').count()
print('@@JSON@@' + json.dumps({'id': froid.pk, 'codes': codes, 'nouveaux': Lead.objects.filter(company=co).count() - avant,
    'stage': froid.stage, 'contacted': stages.CONTACTED, 'parc_etat': froid.parc_etat, 'ville': froid.ville,
    'chatter': chatter, 'passages': passages}))
`)
  expect(r.codes).toEqual([200, 200])
  expect(r.nouveaux, 'aucun nouveau lead (pas de doublon)').toBe(0)
  expect(r.stage, 'le lead Froid passe « Contacté »').toBe(r.contacted)
  expect(r.parc_etat).toBeNull()
  expect(r.ville, 'enrichi sans écraser').toBe('Rabat')
  expect(r.chatter, 'le même leadgen rejoué : un seul chatter').toBe(1)
  expect(r.passages, 'un seul passage Froid → Contacté').toBe(1)
  const lead = await lireJson(await page.request.get(`${API_DJANGO}/crm/leads/${r.id}/`), 'lead relu')
  expect(lead.stage).toBe(r.contacted)
})

etape('PA1.2', ['CADV113'], async ({ page }) => {
  const r = py(`${PRELUDE}
from apps.crm.models import Lead
def lead_de(rep):
    return Lead.objects.get(pk=rep[1]['lead_ids'][0])
def champs(l):
    l.refresh_from_db()
    return {'id': l.pk, 'opt_in': l.whatsapp_opt_in, 'ts': str(l.consent_timestamp) if l.consent_timestamp else None}
base = [{'name': 'full_name', 'values': ['Oui ACC' + tag]}, {'name': 'phone_number', 'values': ['+2126' + tag[-8:]]}]
oui = base + [{'name': 'consentement_whatsapp', 'values': ['Oui, vous pouvez me contacter sur WhatsApp et par téléphone']}]
rep_oui = poster('8101' + tag[-6:], oui)
l_oui = lead_de(rep_oui)
from core.models import ConsentRecord
def reg(l):
    return ConsentRecord.objects.filter(company=co, subject_identifier=l.telephone, source__contains='case WhatsApp', granted=True).count()
reg1 = reg(l_oui)
rep_oui2 = poster('8101' + tag[-6:], oui)   # rejeu du même webhook
sans = [{'name': 'full_name', 'values': ['Sans ACC' + tag]}, {'name': 'phone_number', 'values': ['+2126' + str(int(tag[-8:]) + 1).zfill(8)]}]
l_sans = lead_de(poster('8102' + tag[-6:], sans))
non = [{'name': 'full_name', 'values': ['Non ACC' + tag]}, {'name': 'phone_number', 'values': ['+2126' + str(int(tag[-8:]) + 2).zfill(8)]},
       {'name': 'consentement_whatsapp', 'values': ['Non']}]
l_non = lead_de(poster('8103' + tag[-6:], non))
print('@@JSON@@' + json.dumps({'oui': champs(l_oui), 'sans': champs(l_sans), 'non': champs(l_non), 'rejeu': rep_oui2[0],
      'rejeu_meme_lead': lead_de(rep_oui2).pk == l_oui.pk, 'registre_avant': reg1, 'registre_apres': reg(l_oui)}))
`)
  expect(r.oui.opt_in, 'case cochée : opt-in posé').toBe(true)
  expect(r.oui.ts, 'consent_timestamp posé').toBeTruthy()
  expect(r.sans.opt_in, 'sans la question : None').toBeNull()
  expect(r.non.opt_in, 'réponse non : False').toBe(false)
  expect(r.rejeu_meme_lead, 'rejeu : même lead').toBe(true)
  expect(r.registre_avant, 'entrée de registre accordée').toBeGreaterThan(0)
  expect(r.registre_apres, 'rejeu : pas de seconde entrée').toBe(r.registre_avant)
  const lu = await lireJson(await page.request.get(`${API_DJANGO}/crm/leads/${r.oui.id}/`), 'lead relu')
  expect(lu.whatsapp_opt_in, 'lu sur la fiche').toBe(true)
})
