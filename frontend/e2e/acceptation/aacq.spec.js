// AACQ89 — acceptation en direct du groupe AACQ (audit acquisition) : rejeu, sur la pile locale, de
// soumission site simulée → lead → payload → écrans publicité, et de l'action approuvée puis modifiée
// refusée. Données `AACQ89 …` d'essai (leads, payloads, actions, expérience) supprimées en fin de spec ;
// le secret du webhook est celui de la pile LOCALE (lu dans le conteneur, jamais écrit ni journalisé).
// Aucune connexion Meta active : aucun appel Meta réel ; seule interception : `alertes/` en 500 (déclarée).
//
// Étapes NON JOUABLES ici (site Astro public non démarré) : la soumission par le formulaire du site
// lui-même (la requête du site est simulée par un POST signé sur le webhook, comme le fait le worker du
// site) ; une PANNE de mapping réelle ne peut pas être injectée dans le conteneur sans modifier le code :
// elle est représentée par la ligne durable qu'elle laisse (payload valide + erreur consignée, sans lead).
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawn } from 'node:child_process'
import { groupe } from './_oracles.js'
import { API_DJANGO, lireJson } from '../helpers.js'

const etape = groupe('AACQ', ['AACQ89', 'AACQ79', 'AACQ30', 'AACQ70', 'AACQ74', 'AACQ1', 'AACQ62', 'AACQ63', 'AACQ64', 'AACQ76', 'AACQ65', 'AACQ66'])
test.describe.configure({ timeout: 600_000 })
const T = { timeout: 120_000 }
const NOM = 'AACQ89'

const SERVEUR = [
  'import sys, json, base64, io, contextlib, traceback',
  'ns = {}',
  "print('@@PRET', flush=True)",
  'for ligne in sys.stdin:',
  '    ligne = ligne.strip()',
  '    if not ligne: continue',
  '    buf = io.StringIO()',
  '    try:',
  '        with contextlib.redirect_stdout(buf):',
  '            exec(base64.b64decode(ligne).decode(), ns)',
  "        sortie = {'ok': True, 'out': buf.getvalue()}",
  '    except BaseException:',
  "        sortie = {'ok': False, 'out': buf.getvalue(), 'err': traceback.format_exc()[-1800:]}",
  "    print('@@R' + json.dumps(sortie), flush=True)",
].join('\n')
let serveur = null
const attentes = []
let tampon = ''
function demarrerServeur() {
  if (serveur) return serveur.pret
  const [cmd, ...args] = (process.env.E2E_DJANGO_EXEC || 'docker compose exec -T django_core').split(' ')
  const proc = spawn(cmd, [...args, 'python', 'manage.py', 'shell', '-c', SERVEUR], { stdio: ['pipe', 'pipe', 'ignore'] })
  let pretOk
  const pret = new Promise((r) => { pretOk = r })
  proc.stdout.on('data', (d) => {
    tampon += d.toString()
    let i
    while ((i = tampon.indexOf('\n')) >= 0) {
      const l = tampon.slice(0, i).trim()
      tampon = tampon.slice(i + 1)
      if (l === '@@PRET') pretOk()
      else if (l.startsWith('@@R')) attentes.shift()?.(JSON.parse(l.slice(3)))
    }
  })
  serveur = { proc, pret }
  return pret
}
async function py(code) {
  await demarrerServeur()
  const rep = await new Promise((resolve) => {
    attentes.push(resolve)
    serveur.proc.stdin.write(`${Buffer.from(`import json\n${code}`).toString('base64')}\n`)
  })
  if (!rep.ok) throw new Error(`shell serveur : ${rep.err}`)
  const l = rep.out.split('\n').filter((x) => x.startsWith('@@')).pop()
  return l ? JSON.parse(l.slice(2)) : null
}
const PRELUDE = `
import datetime
from django.conf import settings
from django.utils import timezone
from apps.crm.models import Lead, WebsiteLeadPayload
from apps.adsengine.models import EngineAction, Experiment, AssumptionNode, DecisionLog
def sortie(o): print('@@' + json.dumps(o, default=str))
`
test.afterAll(async () => {
  try {
    await py(`${PRELUDE}
EngineAction.objects.filter(company_id=1, reason_fr__startswith='${NOM}').delete()
DecisionLog.objects.filter(company_id=1, experiment__name__startswith='${NOM}').delete()
Experiment.objects.filter(company_id=1, name__startswith='${NOM}').delete()
AssumptionNode.objects.filter(company_id=1, enonce_fr__startswith='${NOM}').delete()
WebsiteLeadPayload.objects.filter(company_id=1, payload__fullName__startswith='${NOM}').delete()
try: Lead.objects.filter(company_id=1, nom__startswith='${NOM}').delete()
except Exception as e: print('lead delete', e)
sortie('ok')`)
  } catch { /* nettoyage au mieux */ }
  serveur?.proc.stdin.end()
})

let seq = 0
const tel = () => { seq += 1; return `+2126${String(Date.now() + seq).slice(-8)}` }
async function webhookSite(testInfo, corps) {
  const secret = await py(`${PRELUDE}
sortie(settings.WEBSITE_LEAD_WEBHOOK_SECRET)`)
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  const r = await ctx.post(`${API_DJANGO}/crm/webhooks/website-leads/`, { ...T, data: corps, headers: { 'X-Webhook-Secret': secret } })
  const sortie = { statut: r.status(), corps: await r.json().catch(() => ({})) }
  await ctx.dispose()
  return sortie
}
const leadsParTel = (telephone) => py(`${PRELUDE}
from apps.crm.services import normalize_phone
k = normalize_phone('${telephone}')
sortie([l.id for l in Lead.objects.filter(company_id=1) if normalize_phone(l.telephone) == k])`)

// ── P1.1 — soumission du site simulée : un lead, une ligne durable, aucun doublon (AACQ79) ─────────────────
etape('P1.1', ['AACQ79', 'AACQ89'], async ({ page, testInfo, suivi }) => {
  const telephone = tel()
  const corps = { fullName: `${NOM} Site ${Date.now()}`, consent: true, phoneE164: telephone, city: 'Casablanca' }
  const un = await webhookSite(testInfo, corps)
  expect(un.statut, JSON.stringify(un.corps)).toBe(201)
  expect(un.corps.lead_id, 'lead créé').toBeTruthy()
  expect(un.corps.payload_id, 'ligne brute durable').toBeTruthy()
  const ligne = await py(`${PRELUDE}
p = WebsiteLeadPayload.objects.get(pk=${un.corps.payload_id}); sortie(dict(lead=p.lead_id, processed=p.processed, error=p.error, company=p.company_id))`)
  expect(ligne.lead).toBe(un.corps.lead_id)
  expect(ligne.processed).toBe(true)
  expect(ligne.error).toBe('')
  // Même livraison reçue deux fois : 2xx avec sa ligne, mais toujours UN seul lead.
  const deux = await webhookSite(testInfo, corps)
  expect(deux.statut, JSON.stringify(deux.corps)).toBeLessThan(300)
  expect(deux.corps.payload_id, 'la seconde livraison a aussi sa ligne durable').toBeTruthy()
  expect((await leadsParTel(telephone)).length, 'un seul lead pour la soumission').toBe(1)
  // Relecture par l'ERP : le lead est dans la liste des leads, source site web.
  const lu = await lireJson(await page.request.get(`${API_DJANGO}/crm/leads/${un.corps.lead_id}/`), 'lead relu')
  expect(lu.source).toBe('site_web')
  await page.goto('/crm/payloads-site-web')
  await page.getByLabel(/Voir tous les payloads/).check()
  const ligneUi = page.locator('tr', { has: page.getByRole('cell', { name: String(un.corps.payload_id), exact: true }) })
  await expect(ligneUi, 'la ligne durable de la soumission est listée (tous les payloads)').toBeVisible({ timeout: 30_000 })
  await expect(ligneUi).toContainText(/Oui/)
  await expect(ligneUi.getByRole('link'), 'rattachée au lead créé').toBeVisible()
  suivi.verifie(5)
})

// ── P1.5 — rejeu d'un payload en erreur depuis /crm/payloads-site-web, deux fois : un seul lead (AACQ30) ────
etape('P1.5', ['AACQ30', 'AACQ89'], async ({ page }) => {
  const telephone = tel()
  const erreur = `RuntimeError: panne de mapping ${NOM}`
  const nom = `${NOM} Rejeu ${Date.now()}`
  const pid = await py(`${PRELUDE}
p = WebsiteLeadPayload.objects.create(company_id=1, payload=dict(fullName='${nom}', consent=True, phoneE164='${telephone}', city='Casablanca'), error='${erreur}')
sortie(p.id)`)
  await page.goto('/crm/payloads-site-web')
  const rangee = page.locator('tr', { hasText: erreur })
  await expect(rangee, 'le payload en erreur est listé « à traiter »').toBeVisible({ timeout: 30_000 })
  await rangee.getByRole('button', { name: /Rejouer/ }).click()
  await expect(page.locator('tr', { hasText: erreur }), 'l\'erreur disparaît après rejeu réussi').toHaveCount(0, { timeout: 30_000 })
  const apres = await py(`${PRELUDE}
p = WebsiteLeadPayload.objects.get(pk=${pid}); sortie(dict(lead=p.lead_id, error=p.error, processed=p.processed))`)
  expect(apres.lead, 'lead rattaché').toBeTruthy()
  expect(apres.error).toBe('')
  expect((await leadsParTel(telephone)).length).toBe(1)
  // Deuxième rejeu (API) : « déjà rattaché », aucun nouveau lead.
  const r2 = await page.request.post(`${API_DJANGO}/crm/website-lead-payloads/${pid}/replay/`)
  expect(r2.status(), await r2.text()).toBe(200)
  expect((await r2.json()).payload.lead ?? apres.lead).toBe(apres.lead)
  expect((await leadsParTel(telephone)).length, 'aucun doublon après deux rejeux').toBe(1)
  // F5 : la liste ne montre plus l'erreur.
  await page.reload()
  await expect(page.locator('tr', { hasText: erreur })).toHaveCount(0, { timeout: 30_000 })
})

const ECRANS = ['', '/tableau-de-bord', '/cockpit', '/approbations', '/campagnes', '/creatifs', '/commentaires', '/instagram',
  '/experimentations', '/plan-de-vol', '/backlog', '/regles', '/simulation', '/reporting', '/brief', '/journal', '/connexion',
  '/arbre', '/table-des-faits', '/comparateur', '/consentements', '/kit-marque', '/veille', '/import-chantier', '/tests-terrain']

// ── P3.1 — les 25 écrans /publicite/* sans console.error ni 4xx/5xx ; Synchroniser sans connexion (AACQ70) ──
etape('P3.1', ['AACQ70', 'AACQ89'], async ({ page }) => {
  expect(ECRANS.length).toBe(25)
  for (const e of ECRANS) {
    await page.goto(`/publicite${e}`)
    await expect(page.locator('main, #root').first()).toBeVisible({ timeout: 30_000 })
    await page.waitForLoadState('networkidle', { timeout: 30_000 }).catch(() => undefined)
    await expect(page.getByText('Une erreur est survenue'), `écran /publicite${e} cassé`).toHaveCount(0)
  }
  // (e) Synchroniser sans connexion Meta active.
  await page.goto('/publicite/campagnes')
  await page.getByRole('button', { name: 'Synchroniser', exact: true }).click()
  await expect(page.getByText(/Connexion Meta non active/)).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('Synchronisation lancée.')).toHaveCount(0)
})

// ── P3.2 — alertes en 500 (écart d'environnement déclaré) : « Alertes indisponibles » (AACQ74) ─────────────
etape('P3.2', ['AACQ74', 'AACQ89'], async ({ page, suivi }) => {
  suivi.attendre(/\/adsengine\/alertes\//, 500)
  await page.route(/\/adsengine\/alertes\//, (route) => route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"panne simulée"}' }))
  await page.goto('/publicite/tableau-de-bord')
  await expect(page.getByText(/Alertes indisponibles/).first()).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('Aucune alerte.')).toHaveCount(0)
})

// ── P3.3 — boîte d'approbation : montant, rejet motivé, approbation puis modification refusée (AACQ…) ───────
etape('P3.3', ['AACQ1', 'AACQ62', 'AACQ63', 'AACQ64', 'AACQ76', 'AACQ89'], async ({ page, suivi }) => {
  const ids = await py(`${PRELUDE}
EngineAction.objects.filter(company_id=1, reason_fr__startswith='${NOM}').delete()
def mk(nom, courant, cible):
    return EngineAction.objects.create(company_id=1, kind='rebalance_adset_budget', reason_fr='${NOM} ' + nom, status='proposee',
      payload=dict(adset_id='PRB_' + nom, daily_budget=10000, current_budget=courant, new_daily_budget_mad=100.0, target_daily_budget_mad=cible)).id
sortie(dict(rejet=mk('REJET', 20000, 230.0), appro=mk('APPRO', 20000, 230.0)))`)
  suivi.attendre(/\/adsengine\/actions\/\d+\/(apply|reject)\//, 409)
  const act = (id) => `${API_DJANGO}/adsengine/actions/${id}/`
  // AACQ1 : une action proposée n'accepte plus PUT/PATCH/DELETE.
  suivi.attendre(/\/adsengine\/actions\/\d+\/$/, 405)
  for (const m of ['patch', 'put', 'delete']) {
    const r = await page.request[m](act(ids.rejet), { data: { payload: { adset_id: 'X' } } })
    expect(r.status(), `${m.toUpperCase()} sur une action refusé`).toBe(405)
  }
  await page.goto('/publicite/approbations')
  const carteRejet = page.locator('[data-testid="ae-action-card"]', { hasText: `${NOM} REJET` })
  await expect(carteRejet, 'action proposée visible dans la boîte').toBeVisible({ timeout: 30_000 })
  // Le montant avant → après est lu sur la carte (clés RÉELLES du payload).
  const diff = carteRejet.getByTestId('ae-artifact-budget')
  await expect(diff).toBeVisible()
  const texteDiff = (await diff.innerText()).replace(/\s+/g, ' ')
  expect(texteDiff, 'avant (200) → après (100)').toMatch(/200/)
  expect(texteDiff).toMatch(/100/)
  expect(texteDiff).toContain('→')
  // Rejet avec motif structuré.
  await page.getByTestId(`ae-reject-${ids.rejet}`).click()
  const select = page.getByTestId(`ae-reject-reason-${ids.rejet}`)
  await select.selectOption({ index: 1 })
  const motif = (await select.locator('option:checked').innerText()).trim()
  await page.getByTestId(`ae-reject-confirm-${ids.rejet}`).click()
  await expect(page.locator('[data-testid="ae-action-card"]', { hasText: `${NOM} REJET` })).toHaveCount(0, { timeout: 30_000 })
  const rejetee = await lireJson(await page.request.get(act(ids.rejet)), 'action rejetée relue')
  expect(rejetee.status).toBe('rejetee')
  expect(JSON.stringify(rejetee), 'le motif choisi est consigné').toContain(motif)
  await page.goto('/publicite/journal')
  await expect(page.getByText(motif).first(), 'motif lu au Journal d\'actions').toBeVisible({ timeout: 30_000 })
  // Approbation d'une autre action, puis modification en shell, puis « Appliquer ».
  await page.goto('/publicite/approbations')
  await page.getByTestId(`ae-approve-${ids.appro}`).click()
  await expect(page.getByTestId(`ae-approved-badge-${ids.appro}`)).toBeVisible({ timeout: 30_000 })
  const approuvee = await lireJson(await page.request.get(act(ids.appro)), 'action approuvée relue')
  expect(approuvee.status).toBe('approuvee')
  await py(`${PRELUDE}
a = EngineAction.objects.get(pk=${ids.appro}); EngineAction.objects.filter(pk=a.pk).update(payload=dict(a.payload, daily_budget=99999)); sortie('ok')`)
  // (i) Sans connexion Meta active (précondition du parcours) : « Appliquer » est refusé AVANT tout appel,
  // l'action reste approuvée. Le garde de version (AACQ76) n'est pas atteignable sans connexion.
  suivi.attendre(/\/adsengine\/actions\/\d+\/apply\//, 409)
  await page.goto('/publicite/approbations')
  await page.getByTestId(`ae-apply-${ids.appro}`).click()
  await expect(page.getByText(/Aucune connexion Meta active/).first()).toBeVisible({ timeout: 30_000 })
  const sansConnexion = await lireJson(await page.request.get(act(ids.appro)), 'action relue (sans connexion)')
  expect(sansConnexion.status, 'sans connexion : action approuvée inchangée, rien appliqué').toBe('approuvee')
  expect(sansConnexion.applied_at ?? null).toBeNull()
  // (ii) Avec une connexion de substitution LOCALE (jeton factice, supprimée aussitôt) : le contenu modifié depuis
  // l'approbation est refusé, l'action revient « proposée », aucun appel Meta ne part (refus avant dispatch).
  await py(`${PRELUDE}
from apps.adsengine.models import MetaConnection
MetaConnection.objects.filter(company_id=1).delete()
MetaConnection.objects.create(company_id=1, enabled=True, ad_account_id='act_000000', credentials={'access_token': 'ACCEPTATION-AACQ89-FAUX'}); sortie('ok')`)
  try {
    await page.goto('/publicite/approbations')
    await page.getByTestId(`ae-apply-${ids.appro}`).click()
    await expect(page.getByText(/Contenu modifié depuis l.approbation|nouvelle approbation/).first()).toBeVisible({ timeout: 30_000 })
  } finally {
    await py(`${PRELUDE}
from apps.adsengine.models import MetaConnection
MetaConnection.objects.filter(company_id=1, ad_account_id='act_000000').delete(); sortie('ok')`)
  }
  const apres = await lireJson(await page.request.get(act(ids.appro)), 'action relue après Appliquer')
  expect(apres.status, 'action modifiée refusée et revenue en proposée').toBe('proposee')
  expect(apres.applied_at ?? null).toBeNull()
  expect(apres.error).toMatch(/Contenu modifié depuis l.approbation/)
  expect(JSON.stringify(apres.payload)).toContain('99999')
})

// ── P3.3b — clôture d'expérience deux fois, verdicts contraires : 409 et verdict serveur affiché (AACQ65/66) ──
etape('P3.3b', ['AACQ65', 'AACQ66', 'AACQ89'], async ({ page, suivi }) => {
  const e = await py(`${PRELUDE}
exp = Experiment.objects.create(company_id=1, name='${NOM} Hook prix', status=Experiment.Statut.EN_COURS)
node = AssumptionNode.objects.create(company_id=1, classe=AssumptionNode.Classe.CREATIF, enonce_fr='${NOM} Le hook prix marche mieux.',
  enjeux_s=0.5, pertinence_r=0.5, alpha=1.0, beta=1.0, alpha0=1.0, beta0=1.0)
DecisionLog.objects.create(company_id=1, experiment=exp, allocations={'winner_node_id': node.pk}, summary_fr='Slot ouvert (VoI).')
sortie(dict(exp=exp.id, node=node.id))`)
  suivi.attendre(/\/adsengine\/experiences\/\d+\/conclure\//, 409)
  await page.goto('/publicite/experimentations')
  await page.getByTestId(`ae-exp-select-${e.exp}`).click()
  const clore = async (testid) => {
    await page.getByTestId(testid).click()
    await expect(page.getByTestId('ae-exp-conclude-confirm-panel')).toBeVisible()
    await page.getByTestId('ae-exp-conclude-confirm').click()
  }
  await clore('ae-exp-conclude-validated')
  await expect(page.getByTestId('ae-exp-closure-msg')).toContainText(/VALIDÉE/, { timeout: 30_000 })
  await clore('ae-exp-conclude-invalidated')
  const msg = await page.getByTestId('ae-exp-closure-msg').innerText()
  expect(msg, `le verdict serveur (validé) reste affiché : « ${msg} »`).toMatch(/VALIDÉE|CONFIRMÉE|déjà clôturée/i)
  expect(msg).not.toMatch(/INVALIDÉE : verdict enregistré/)
  // Serveur : 409 + verdict inchangé, posterior touché une seule fois.
  const r = await page.request.post(`${API_DJANGO}/adsengine/experiences/${e.exp}/conclure/`, { data: { validated: false } })
  expect(r.status()).toBe(409)
  expect((await r.json()).validated).toBe(true)
  const p = await py(`${PRELUDE}
n = AssumptionNode.objects.get(pk=${e.node}); sortie([n.alpha, n.beta])`)
  expect(p).toEqual([2, 1])
  await page.reload()
  await page.getByTestId(`ae-exp-select-${e.exp}`).click()
})
