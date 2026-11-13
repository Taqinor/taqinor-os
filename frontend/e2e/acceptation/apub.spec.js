// Preuves en direct du groupe APUB (parcours PF5 « accès publics et à lien », dossier
// docs/audits/2026-11-11-parcours-PF5.md) — CLAUDE.md étape 3-bis, METHODE §C.4 point 1.
// Une étape par tâche : le visiteur SANS session (contexte de navigateur neuf, aucun cookie) avec le vrai
// lien/jeton, puis le cas refusé ; les rôles sont les rôles LIVRÉS de la société de demo_admin (relus par nom).
// Données propres créées par l'API (ou le shell Django pour l'état « Given » qu'aucune route ne pose) ;
// e-mails lus dans le journal du serveur (backend console, destinataires autorisés par
// EMAIL_DESTINATAIRES_AUTORISES) ; sondes hôte du dossier rejouées quand elles tournent sur l'arbre.
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, connexionApi, assurerSessionPage, telephoneMobileUnique, PNG_1PX, listeDe } from '../helpers.js'

const etape = groupe('APUB', ['APUB12', 'APUB41', 'APUB49', 'APUB52', 'APUB6', 'APUB35', 'APUB45', 'APUB8', 'APUB9', 'APUB40', 'APUB44', 'APUB11'])
fermerDjangoApresTout()
const API = '/api/django'
const DJANGO = process.env.E2E_API_TARGET || 'http://127.0.0.1:8000'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 420_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const SOC = `U.objects.get(username='demo_admin').company_id`
const JOURNAL = process.env.ACCEPTATION_JOURNAL_SERVEUR || '/tmp/gunicorn-error.log'

/** pk d'un rôle (système relu par son nom, ou personnalisé créé/aligné avec `perms`). */
async function role(nom, perms = null) {
  if (!perms) return py(`from apps.roles.models import Role
sortie(Role.objects.get(company_id=${SOC}, nom=${JSON.stringify(nom)}).pk)`)
  return py(`from apps.roles.models import Role
r, _ = Role.objects.get_or_create(company_id=${SOC}, nom=${JSON.stringify(nom)}, defaults=dict(permissions=[]))
r.permissions = ${JSON.stringify(perms)}; r.est_systeme = False; r.save(); sortie(r.pk)`)
}

/** Compte d'essai de la société connecté par la vraie route `/token/` : {ctx (requêtes API), id, username}. */
async function session(testInfo, nom, roleId) {
  const id = await py(`u = compte(${JSON.stringify(nom)}, role=${roleId}, societe=${SOC})
sortie(u.id)`)
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(ctx, { username: nom, password: MDP_ESSAI })
  return { ctx, id, username: nom }
}

/** Contexte de navigateur NEUF (aucun cookie) ; `identifiants` = connexion par la vraie route `/token/`. */
async function navigateur(page, testInfo, suivi, identifiants = null) {
  const ctx = await page.context().browser().newContext({
    baseURL: testInfo.project.use.baseURL, serviceWorkers: 'block', storageState: { cookies: [], origins: [] },
  })
  const p = suivi.surveiller(await ctx.newPage())
  await p.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  if (identifiants) {
    await connexionApi(ctx.request, identifiants)
    // Habitué : visites guidées déjà fermées (même geste que auth.setup.js), sinon la bulle capte le pointeur.
    const visites = await ctx.request.get(`${API}/onboarding/tours/`)
    if (visites.ok()) {
      for (const v of await visites.json()) if (!v.vu) await ctx.request.post(`${API}/onboarding/tours/${v.tour_key}/vu/`)
    }
  }
  return { ctx, page: p }
}

/** Sonde hôte du dossier (vrai code extrait par ast), rejouée sur l'arbre : son dict. */
function sondeHote(nom) {
  const r = spawnSync('python', [`docs/audits/sondes/APUB/${nom}.py`], {
    cwd: RACINE, encoding: 'utf8', maxBuffer: 50_000_000, env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
  })
  expect(r.status, `sonde ${nom} : ${(r.stderr || '').slice(-600)}`).toBe(0)
  return JSON.parse(r.stdout)
}

/** Codes OTP des e-mails remis à `adresse`, lus dans le journal du serveur (backend console). */
function codesRecus(adresse) {
  if (!existsSync(JOURNAL)) return []
  return readFileSync(JOURNAL, 'utf8').split(/-{79}/)
    .filter((b) => b.includes(`To: ${adresse}`))
    .map((b) => (b.match(/Votre code : (\d{6})/) || [])[1] || 'sans-code')
}

/** Vente envoyée (lead + produit + devis + lien client) par demo_admin ; `accepter` la signe. */
async function vente(r, m, { accepter = false } = {}) {
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `APUB ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `apub${m}@example.invalid` } }), 'lead')
  const p = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur APUB ${m}`, prix_vente: '1000.00', prix_achat: '400.00' } }), 'produit')
  const devis = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, lignes: [{ produit: p.id, designation: p.nom, quantite: '1', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  const lien = await lireJson(await r.post(`${API}/ventes/devis/${devis.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  if (accepter) await lireJson(await r.post(`${API}/ventes/devis/${devis.id}/accepter/`, { ...T, data: { nom: 'Client APUB' } }), 'accepter')
  return { lead, devis, jeton: lien.token }
}

// ── PF5.4 — APUB12 : plans de vol écrits seulement avec `adsengine_flightplan_manage` ───────────────────
etape('PF5.4-APUB12', ['APUB12'], async ({ page, suivi, testInfo }) => {
  const s = sondeHote('C-APUB-009')
  expect([s.repro, s.observe.roles_livres_qui_ecrivent_sans_le_code], 'sonde C-APUB-009 : aucun rôle livré n’écrit sans le code').toEqual([false, []])
  const m = marque()
  const co = await session(testInfo, `apub12co_${m}`, await role('Commercial'))
  const cr = await session(testInfo, `apub12cr_${m}`, await role('Commercial responsable'))
  const rs = await session(testInfo, `apub12rs_${m}`, await role('Responsable'))
  // Commercial responsable (porte le code) : 201 / 200 / 201 (phase) / 200 / 200.
  const plan = await cr.ctx.post(`${API}/adsengine/plans-vol/`, { ...T, data: { name: `APUB12 ${m}`, objective: 'leads' } })
  expect(plan.status(), `CR POST plans-vol : ${(await plan.text()).slice(0, 200)}`).toBe(201)
  const p = await plan.json()
  const phase = await cr.ctx.post(`${API}/adsengine/phases-vol/`, { ...T, data: { plan: p.id, order: 1, name: 'Phase A', num_arms: 2, week_span: 3 } })
  expect(phase.status(), `CR POST phases-vol : ${(await phase.text()).slice(0, 200)}`).toBe(201)
  const ph = await phase.json()
  expect((await cr.ctx.patch(`${API}/adsengine/plans-vol/${p.id}/`, { ...T, data: { notes: 'CR' } })).status(), 'CR PATCH plan').toBe(200)
  expect((await cr.ctx.patch(`${API}/adsengine/phases-vol/${ph.id}/`, { ...T, data: { name: 'Phase A (CR)' } })).status(), 'CR PATCH phase').toBe(200)
  const etat = () => py(`from apps.adsengine.models import FlightPlan, FlightPhase
sortie(dict(plans=FlightPlan.objects.filter(company_id=${SOC}, name__startswith='APUB12 ${m}').count(), plan=list(FlightPlan.objects.filter(pk=${p.id}).values_list('name', 'notes')), phases=list(FlightPhase.objects.filter(plan_id=${p.id}).values_list('id', 'name'))))`)
  const avant = await etat()
  // Commercial et Responsable (sans le code) : 403 aux quatre portes, rien d'écrit.
  for (const [qui, x] of [['Commercial', co], ['Responsable', rs]]) {
    const portes = [
      await x.ctx.post(`${API}/adsengine/plans-vol/`, { ...T, data: { name: `APUB12 ${m} pirate`, objective: 'leads' } }),
      await x.ctx.patch(`${API}/adsengine/plans-vol/${p.id}/`, { ...T, data: { notes: 'pirate' } }),
      await x.ctx.patch(`${API}/adsengine/phases-vol/${ph.id}/`, { ...T, data: { name: 'pirate' } }),
      await x.ctx.delete(`${API}/adsengine/phases-vol/${ph.id}/`, T),
    ]
    expect(portes.map((r) => r.status()), `${qui} : 403 aux quatre portes`).toEqual([403, 403, 403, 403])
  }
  expect(await etat(), 'plan et phases relus inchangés après les refus').toEqual(avant)
  // validate/, simulate/, templates/ inchangés pour le Commercial (garde propre `adsengine_manage` / `adsengine_view`).
  expect((await co.ctx.get(`${API}/adsengine/plans-vol/templates/`, T)).status(), 'Commercial templates/').toBe(200)
  for (const [act, corps] of [['validate', { phases: [], bras: [] }], ['simulate', { scenario: 'clear_winner' }]]) {
    const r = await co.ctx.post(`${API}/adsengine/plans-vol/${act}/`, { ...T, data: corps })
    expect(r.status(), `Commercial ${act}/ passe sa garde propre : ${(await r.text()).slice(0, 200)}`).toBe(200)
  }
  // Écran : Responsable (palier qui ouvre l'écran, sans le code) → « Enregistrer le plan » grisé, même après rechargement.
  const vr = await navigateur(page, testInfo, suivi, { username: rs.username, password: MDP_ESSAI })
  await vr.page.goto('/publicite/plan-de-vol')
  await expect(vr.page.getByTestId('ae-fp-compose')).toBeVisible({ timeout: 60_000 })
  await expect(vr.page.getByTestId('ae-fp-phase').first(), 'plan enregistré relu (phases)').toBeVisible({ timeout: 30_000 })
  await vr.page.getByTestId('ae-fp-nom').fill(`APUB12 écran ${m}`)
  const bouton = vr.page.getByTestId('ae-fp-save')
  await expect(bouton).toBeDisabled()
  await expect(bouton).toHaveAttribute('title', /adsengine_flightplan_manage/)
  await vr.page.reload()
  await expect(vr.page.getByTestId('ae-fp-phase').first()).toBeVisible({ timeout: 60_000 })
  await expect(vr.page.getByTestId('ae-fp-save'), 'toujours grisé après rechargement').toBeDisabled()
  // Commercial responsable : le même bouton est actif.
  const vc = await navigateur(page, testInfo, suivi, { username: cr.username, password: MDP_ESSAI })
  await vc.page.goto('/publicite/plan-de-vol')
  await expect(vc.page.getByTestId('ae-fp-phase').first()).toBeVisible({ timeout: 60_000 })
  await expect(vc.page.getByTestId('ae-fp-save'), 'Commercial responsable : actif').toBeEnabled()
  // Le Commercial responsable supprime sa phase : 204.
  expect((await cr.ctx.delete(`${API}/adsengine/phases-vol/${ph.id}/`, T)).status(), 'CR DELETE phase').toBe(204)
  await vr.ctx.close(); await vc.ctx.close()
  for (const x of [co, cr, rs]) await x.ctx.dispose()
  await py(`from apps.adsengine.models import FlightPlan
FlightPlan.objects.filter(pk=${p.id}).delete(); sortie(1)`)
})

// ── PF5.2 — APUB41 : « Couper le lien public » d'un rapport programmé ─────────────────────────────────
etape('PF5.2-APUB41', ['APUB41'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const rap = await py(`from apps.reporting.models import SavedReport
from apps.reporting.diffusion_views import make_report_token
a = U.objects.get(username='demo_admin')
r = SavedReport.objects.create(company_id=a.company_id, owner=a, name='APUB41 ${m}', target_kind='stock', schedule='weekly', canal='whatsapp', destinataires_whatsapp='+212600000041')
sortie(dict(id=r.pk, jeton=make_report_token(r)))`)
  const traces = () => py(`from apps.reporting.models import AccesRapportPartage
sortie(AccesRapportPartage.objects.filter(saved_report_id=${rap.id}).count())`)
  const revoque = () => py(`from apps.reporting.models import SavedReport
sortie(str(SavedReport.objects.get(pk=${rap.id}).partage_revoque_le))`)
  const visiteur = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  const lien = `${API}/reporting/rapports-partages/${rap.jeton}/`
  expect((await visiteur.get(lien, T)).status(), 'lien public servi avant la coupure').toBe(200)
  expect(await traces(), 'la lecture laisse une trace').toBe(1)
  // Responsable de B : 404 sur le rapport de A, rien d'écrit.
  const b = await py(`from authentication.models import Company
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
co = Company.objects.create(slug='apub41-${m}', nom='APUB41 ${m} B')
rd = Role.objects.create(company=co, nom='Directeur', permissions=list(DIRECTEUR_PERMISSIONS), est_systeme=True)
u = U.objects.create_user(username='apub41b_${m}', password=${JSON.stringify(MDP_ESSAI)}, company=co, role=rd, role_legacy='admin', email='apub41b${m}@example.invalid')
sortie(u.username)`)
  const ctxB = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(ctxB, { username: b, password: MDP_ESSAI })
  expect((await ctxB.post(`${API}/reporting/saved-reports/${rap.id}/couper-partage/`, { ...T, data: {} })).status(), 'responsable de B : 404').toBe(404)
  expect(await revoque(), 'rien d’écrit par B').toBe('None')
  // Écran Envois programmés (responsable de A) : bouton, confirmation, toast.
  await page.goto('/reporting/envois-programmes')
  const ligne = page.getByTestId(`envoi-programme-${rap.id}`)
  await expect(ligne).toBeVisible({ timeout: 60_000 })
  await ligne.getByRole('button', { name: `Couper le lien public de APUB41 ${m}` }).click()
  await page.getByRole('button', { name: 'Couper le lien', exact: true }).click()
  await expect(page.getByText('Lien public coupé.')).toBeVisible({ timeout: 30_000 })
  const date = await revoque()
  expect(date, 'partage_revoque_le posé').not.toBe('None')
  await page.reload()
  await expect(page.getByTestId(`envoi-programme-${rap.id}`), 'rapport relu après rechargement').toBeVisible({ timeout: 60_000 })
  // Visiteur : l'ancien lien rend 404 neutre, sans nouvelle trace.
  const apres = await visiteur.get(lien, T)
  expect([apres.status(), (await apres.json()).detail], 'ancien lien : 404 neutre').toEqual([404, 'Lien invalide ou expiré.'])
  expect(await traces(), 'aucune trace sur le lien coupé').toBe(1)
  // Second POST idempotent : date inchangée.
  const second = await lireJson(await page.request.post(`${API}/reporting/saved-reports/${rap.id}/couper-partage/`, { ...T, data: {} }), 'second couper-partage')
  expect(second.partage_revoque_le, 'idempotent : réponse porte la date').toBeTruthy()
  expect(await revoque(), 'second POST : date inchangée').toBe(date)
  await visiteur.dispose(); await ctxB.dispose()
  await py(`from apps.reporting.models import SavedReport
SavedReport.objects.filter(pk=${rap.id}).delete(); sortie(1)`)
})

// ── PF5.3 — APUB49 : désabonnement des e-mails d'incident par lien absolu + confirmation ────────────────
etape('PF5.3-APUB49', ['APUB49'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const base = new URL(testInfo.project.use.baseURL).origin
  // L'e-mail réel du receiver (signal post_save d'un incident SYSTÈME), boîte locmem le temps de l'appel.
  const mail = await py(`from django.core import mail
from django.test.utils import override_settings
from apps.statuspage.models import IncidentPublic, StatusSubscriber
StatusSubscriber.objects.filter(email__startswith='apub49').delete()
ab = StatusSubscriber.objects.create(email='apub49-${m}@example.invalid', confirme=True)
res = dict(jeton=ab.token_desabonnement, id=ab.pk)
with override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', PUBLIC_BASE_URL=${JSON.stringify(base)}):
    mail.outbox = []
    inc = IncidentPublic.objects.create(company=None, titre='APUB49 ${m}', severite='mineure', statut='investigating')
    res['corps'] = [x.body for x in mail.outbox if 'apub49-${m}@example.invalid' in x.to]
with override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', PUBLIC_BASE_URL=''):
    mail.outbox = []
    inc2 = IncidentPublic.objects.create(company=None, titre='APUB49 ${m} sans base', severite='mineure', statut='investigating')
    res['corps_sans_base'] = [x.body for x in mail.outbox if 'apub49-${m}@example.invalid' in x.to]
IncidentPublic.objects.filter(pk__in=[inc.pk, inc2.pk]).delete()
sortie(res)`)
  expect(mail.corps.length, 'un e-mail d’incident à l’abonné').toBe(1)
  const attendu = `${base}/api/django/statuspage/public/desabonner/${mail.jeton}/`
  expect(mail.corps[0], 'lien ABSOLU dans le corps').toContain(`Se désabonner : ${attendu}`)
  expect(mail.corps_sans_base[0], 'sans PUBLIC_BASE_URL : ligne omise, jamais relative').not.toContain('desabonner')
  const present = () => py(`from apps.statuspage.models import StatusSubscriber
sortie(StatusSubscriber.objects.filter(pk=${mail.id}).exists())`)
  // Visiteur sans session : le lien de l'e-mail ouvre une confirmation SANS effet.
  const v = await navigateur(page, testInfo, suivi)
  const rep = await v.page.goto(attendu)
  expect(rep.status(), 'GET : 200').toBe(200)
  expect(rep.headers()['x-robots-tag'], 'noindex').toBe('noindex')
  await expect(v.page.getByText('Ne plus recevoir les e-mails d’incident ?')).toBeVisible()
  expect(await present(), 'GET : abonné toujours présent').toBe(true)
  await v.page.reload()
  expect(await present(), 'GET rejoué : abonné toujours présent').toBe(true)
  // Le bouton POSTe : désabonné.
  await v.page.getByRole('button', { name: 'Me désabonner' }).click()
  await expect(v.page.locator('body')).toContainText('Désabonnement effectué.', { timeout: 30_000 })
  expect(await present(), 'POST : abonné supprimé').toBe(false)
  // Jeton inconnu (dont le jeton consommé) : 404.
  const anon = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  expect((await anon.get(`${API}/statuspage/public/desabonner/${mail.jeton}/`, T)).status(), 'jeton consommé : GET 404').toBe(404)
  expect((await anon.post(`${API}/statuspage/public/desabonner/inconnu${m}/`, T)).status(), 'jeton inconnu : POST 404').toBe(404)
  await anon.dispose(); await v.ctx.close()
})

// ── PF5.3 — APUB52 : modifier un webhook compare ses évènements aux codes de l'acteur ───────────────────
etape('PF5.3-APUB52', ['APUB52'], async ({ page, testInfo }) => {
  const m = marque()
  const perso = await session(testInfo, `apub52_${m}`, await role(`APUB52 intégrateur ${m}`, ['users_voir', 'integrations_gerer', 'crm_voir']))
  const cree = await perso.ctx.post(`${API}/publicapi/webhooks/`, { ...T, data: { target_url: 'https://example.com/apub52-hook', label: `APUB52 ${m}`, events: ['lead.created'] } })
  expect(cree.status(), `création lead.created : ${(await cree.text()).slice(0, 300)}`).toBe(201)
  const h = await cree.json()
  const evenements = () => py(`from apps.publicapi.models import Webhook
sortie(Webhook.objects.get(pk=${h.id}).events)`)
  const patch = await perso.ctx.patch(`${API}/publicapi/webhooks/${h.id}/`, { ...T, data: { events: ['facture.created'] } })
  const corpsPatch = await patch.json()
  expect([patch.status(), corpsPatch.events], `PATCH facture.created : 400 nommé (${JSON.stringify(corpsPatch).slice(0, 300)})`).toEqual([400, ['Évènement non détenu : facture.created']])
  expect(await evenements(), 'relu après le PATCH refusé').toEqual(['lead.created'])
  const put = await perso.ctx.put(`${API}/publicapi/webhooks/${h.id}/`, { ...T, data: { target_url: 'https://example.com/apub52-hook', label: `APUB52 ${m}`, events: ['facture.created'], enabled: true } })
  const corpsPut = await put.json()
  expect([put.status(), corpsPut.events], `PUT facture.created : 400 nommé (${JSON.stringify(corpsPut).slice(0, 300)})`).toEqual([400, ['Évènement non détenu : facture.created']])
  expect(await evenements(), 'relu après le PUT refusé').toEqual(['lead.created'])
  const ok = await perso.ctx.patch(`${API}/publicapi/webhooks/${h.id}/`, { ...T, data: { events: ['lead.stage_changed'] } })
  expect(ok.status(), `PATCH lead.stage_changed : ${(await ok.text()).slice(0, 200)}`).toBe(200)
  expect(await evenements(), 'évènement détenu écrit').toEqual(['lead.stage_changed'])
  // Écran Paramètres → API & webhooks : le webhook relu porte lead.stage_changed, jamais facture.created.
  await page.goto('/parametres?onglet=api')
  const carte = page.getByText(`APUB52 ${m}`, { exact: true })
  await expect(carte).toBeVisible({ timeout: 60_000 })
  await expect(page.getByText('https://example.com/apub52-hook · lead.stage_changed')).toBeVisible()
  await expect(page.getByText(/apub52-hook · .*facture\.created/)).toHaveCount(0)
  await perso.ctx.delete(`${API}/publicapi/webhooks/${h.id}/`, T)
  await perso.ctx.dispose()
})

// ── PF5.1 — APUB6 : couper le lien public du compte-rendu d'intervention ────────────────────────────────
etape('PF5.1-APUB6', ['APUB6'], async ({ page, suivi, testInfo }) => {
  const s = sondeHote('C-APUB-004')
  expect(s.repro, `sonde C-APUB-004 : ${JSON.stringify(s.observe).slice(0, 400)}`).toBe(false)
  const r = page.request
  const m = marque()
  const tr = await session(testInfo, `apub6tr_${m}`, await role('Technicien responsable'))
  const vw = await session(testInfo, `apub6vw_${m}`, await role('Viewer'))
  const i = await py(`from apps.installations.models import Installation, Intervention, ShotListSlot
co = ${SOC}
ins = Installation.objects.filter(company_id=co).order_by('pk').first()
slot, _ = ShotListSlot.objects.get_or_create(company_id=co, cle='apub6-avant', defaults=dict(libelle='Avant APUB6', phase='avant', ordre=99, actif=True))
it = Intervention.objects.create(company_id=co, installation=ins, type_intervention='controle', statut='a_preparer', technicien_id=${tr.id})
sortie(dict(id=it.pk, slot=slot.cle, slot_id=slot.pk))`)
  const photo = await lireJson(await r.post(`${API}/installations/interventions/${i.id}/ajouter-photo/`, { ...T, multipart: { file: { name: 'avant.png', mimeType: 'image/png', buffer: PNG_1PX }, slot: i.slot, phase: 'avant' } }), 'photo')
  await py(`from apps.installations.models import Intervention
Intervention.objects.filter(pk=${i.id}).update(statut='validee'); sortie(1)`)
  const jeton = () => py(`from apps.installations.models import Intervention
sortie(Intervention.objects.get(pk=${i.id}).lien_rapport_token)`)
  const t1 = (await lireJson(await r.get(`${API}/installations/interventions/${i.id}/lien-rapport/`, T), 'lien-rapport')).token
  const anon = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  const pub = (t) => [`${API}/public/installations/intervention-rapport/${t}/`, `${API}/public/installations/intervention-rapport/${t}/pdf/`, `${API}/public/installations/intervention-rapport/${t}/photo/${photo.id}/`]
  const statuts = async (t) => Promise.all(pub(t).map(async (u) => (await anon.get(u, T)).status()))
  expect(await statuts(t1), 'page, PDF et photo servis avant la coupure').toEqual([200, 200, 200])
  // Viewer : 403, jeton inchangé.
  expect((await vw.ctx.post(`${API}/installations/interventions/${i.id}/couper-lien-rapport/`, { ...T, data: {} })).status(), 'Viewer : 403').toBe(403)
  expect(await jeton(), 'jeton inchangé après le refus').toBe(t1)
  // Technicien responsable : 200, les trois vues publiques rendent 404.
  const coupe = await tr.ctx.post(`${API}/installations/interventions/${i.id}/couper-lien-rapport/`, { ...T, data: {} })
  expect(coupe.status(), `Technicien responsable : ${(await coupe.text()).slice(0, 200)}`).toBe(200)
  expect(await jeton(), 'jeton vidé').toBeNull()
  expect(await statuts(t1), 'ancien jeton : 404 aux trois vues').toEqual([404, 404, 404])
  // Fiche intervention (écran) : « Générer » pose un jeton NEUF, « Couper le lien » le coupe.
  await page.goto(`/interventions?id=${i.id}`)
  await page.getByRole('tab', { name: 'Outils' }).click({ timeout: 60_000 })
  const bloc = page.getByTestId('lien-rapport-intervention')
  await bloc.getByRole('button', { name: 'Générer le lien du compte-rendu' }).click()
  const champ = bloc.getByRole('textbox', { name: 'Partager le compte-rendu signé' })
  await expect(champ).toHaveValue(/intervention-rapport\//, { timeout: 30_000 })
  const t2 = (await champ.inputValue()).split('/').filter(Boolean).pop()
  expect(t2, 'jeton neuf ≠ ancien').not.toBe(t1)
  expect(await jeton(), 'jeton neuf persisté').toBe(t2)
  const v = await navigateur(page, testInfo, suivi)
  await v.page.goto(`/intervention-rapport/${t2}`)
  await expect(v.page.getByRole('heading', { name: 'Compte-rendu d’intervention' })).toBeVisible({ timeout: 60_000 })
  await expect(v.page.locator('.page-error')).toHaveCount(0)
  await bloc.getByTestId('lien-rapport-intervention-couper').click()
  await expect(page.getByText('Lien coupé — l’ancien lien ne s’ouvre plus.')).toBeVisible({ timeout: 30_000 })
  expect(await jeton(), 'coupé depuis l’écran').toBeNull()
  suivi.attendre(new RegExp(`intervention-rapport/${t2}`), 404)
  await v.page.reload()
  await expect(v.page.locator('.page-error')).toContainText('introuvable ou a été révoqué', { timeout: 60_000 })
  expect(await statuts(t2), 'jeton coupé à l’écran : 404 aux trois vues').toEqual([404, 404, 404])
  // `lien-rapport` rend ensuite un jeton neuf.
  const t3 = (await lireJson(await r.get(`${API}/installations/interventions/${i.id}/lien-rapport/`, T), 'lien-rapport après coupure')).token
  expect([t3 !== t1, t3 !== t2, await jeton()], 'troisième jeton neuf, persisté').toEqual([true, true, t3])
  await v.ctx.close(); await anon.dispose()
  for (const x of [tr, vw]) await x.ctx.dispose()
  await py(`from apps.installations.models import Intervention, ShotListSlot
Intervention.objects.filter(pk=${i.id}).delete(); ShotListSlot.objects.filter(pk=${i.slot_id}).delete(); sortie(1)`)
})

// ── PF5.1 — APUB35 : lien « technicien en route » sans date prévue expiré à la clôture ──────────────────
etape('PF5.1-APUB35', ['APUB35'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const ids = await py(`from apps.installations.models import Installation, Intervention
co = ${SOC}
ins = Installation.objects.filter(company_id=co).order_by('pk').first()
a = Intervention.objects.create(company_id=co, installation=ins, type_intervention='controle', statut='a_preparer')
b = Intervention.objects.create(company_id=co, installation=ins, type_intervention='controle', statut='a_preparer', date_prevue=timezone.localdate())
sortie(dict(sans=a.pk, datee=b.pk))`)
  const jSans = (await lireJson(await r.get(`${API}/installations/interventions/${ids.sans}/lien-client/`, T), 'lien-client sans date')).token
  const jDatee = (await lireJson(await r.get(`${API}/installations/interventions/${ids.datee}/lien-client/`, T), 'lien-client datée')).token
  const statut = (id, s) => py(`from apps.installations.models import Intervention
Intervention.objects.filter(pk=${id}).update(statut='${s}'); sortie(1)`)
  const anon = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  const api = async (t) => (await anon.get(`${API}/public/installations/intervention/${t}/`, T)).status()
  // Avant clôture : la page publique est servie au visiteur sans compte.
  const v = await navigateur(page, testInfo, suivi)
  await v.page.goto(`/intervention/${jSans}`)
  await expect(v.page.getByRole('heading', { name: 'Suivi de votre intervention' })).toBeVisible({ timeout: 60_000 })
  await expect(v.page.locator('.page-error')).toHaveCount(0)
  expect(await api(jSans), 'à préparer : 200').toBe(200)
  // Terminée puis validée : 404 « Lien invalide ou expiré. », la page le dit.
  suivi.attendre(new RegExp(`intervention/${jSans}`), 404)
  for (const s of ['terminee', 'validee']) {
    await statut(ids.sans, s)
    const rep = await anon.get(`${API}/public/installations/intervention/${jSans}/`, T)
    expect([rep.status(), (await rep.json()).detail], `${s} : 404`).toEqual([404, 'Lien invalide ou expiré.'])
    await v.page.reload()
    await expect(v.page.locator('.page-error')).toContainText('introuvable ou a expiré', { timeout: 60_000 })
  }
  // Intervention datée (aujourd'hui) terminée : règle « lendemain de la date prévue » inchangée.
  await statut(ids.datee, 'terminee')
  expect(await api(jDatee), 'datée du jour, terminée : toujours 200').toBe(200)
  await v.ctx.close(); await anon.dispose()
  await py(`from apps.installations.models import Intervention
Intervention.objects.filter(pk__in=[${ids.sans}, ${ids.datee}]).delete(); sortie(1)`)
})

// ── PF5.2 — APUB45 : garde des surfaces portail étendue (fournisseur, partenaire, routes publiques) ─────
etape('PF5.2-APUB45', ['APUB45'], async ({ page }) => {
  const g = spawnSync('python', ['scripts/check_portail_surfaces.py'], { cwd: RACINE, encoding: 'utf8', env: { ...process.env, PYTHONIOENCODING: 'utf-8' } })
  expect(g.status, `garde sur la tête : ${(g.stdout || '').slice(-800)} ${(g.stderr || '').slice(-400)}`).toBe(0)
  const src = readFileSync(`${RACINE}scripts/check_portail_surfaces.py`, 'utf8')
  expect(src, 'lit public_urls.py').toMatch(/public_urls\.py/)
  expect(src, 'motif élargi fournisseur/partenaire').toMatch(/fournisseur/)
  const t = spawnSync('python', ['-m', 'unittest', 'discover', '-s', 'scripts/tests', '-p', 'test_check_portail_surfaces.py'], { cwd: RACINE, encoding: 'utf8', env: { ...process.env, PYTHONIOENCODING: 'utf-8' } })
  expect(t.status, `tests de la garde (dont route publique et fournisseur sans écran ⇒ rouge) : ${(t.stderr || '').slice(-800)}`).toBe(0)
  expect(t.stderr, 'le test rouge-d’abord APUB45 est joué').toMatch(/Ran \d+ tests/)
  await page.goto('/apps')
  await expect(page.locator('body')).toBeVisible()
})

// ── PF5.1 — APUB8 : « Contacter mon conseiller » n'accepte que les canaux du site ───────────────────────
etape('PF5.1-APUB8', ['APUB8'], async ({ page, testInfo }) => {
  const m = marque()
  const v = await vente(page.request, m)
  expect(v.jeton, 'jeton du lien client').toBeTruthy()
  const compte = () => py(`from apps.crm.models import LeadActivity
from apps.notifications.models import Notification
sortie(dict(notes=LeadActivity.objects.filter(lead_id=${v.lead.id}, body__contains='demande à être contacté').count(), notifs=Notification.objects.filter(event_type='client_contact_request', title__contains=${JSON.stringify(v.devis.reference)}).count()))`)
  const avant = await compte()
  const anon = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  const url = `${API}/public/proposal/${v.jeton}/contact/`
  for (let k = 0; k < 10; k += 1) {
    const x = await anon.post(url, { ...T, data: { channel: `c${k}`, message: 'rappelez-moi' } })
    expect([x.status(), Object.keys(await x.json())], `canal c${k} : 400 sous canal`).toEqual([400, ['canal']])
  }
  expect(await compte(), 'aucune note ni notification après les dix refus').toEqual(avant)
  const wa = await anon.post(url, { ...T, data: { channel: 'whatsapp', message: 'par whatsapp' } })
  expect(wa.status(), 'whatsapp : 200').toBe(200)
  const apresWa = await compte()
  expect(apresWa.notes - avant.notes, 'whatsapp : 1 note').toBe(1)
  expect(apresWa.notifs - avant.notifs, 'whatsapp : notifications').toBeGreaterThan(0)
  const sans = await anon.post(url, { ...T, data: { message: 'sans canal' } })
  expect([sans.status(), (await sans.json()).already_sent], 'sans canal : 200 (clé default)').toEqual([200, false])
  expect((await compte()).notes - avant.notes, 'chatter relu : 2 notes').toBe(2)
  await anon.dispose()
})

// ── PF5.2 — APUB9 : 60 s entre deux envois de code de signature ─────────────────────────────────────────
const ADRESSE_OTP9 = 'otp9.apub@accept-apub.ma'
const ADRESSE_OTP40 = 'otp40.apub@accept-apub.ma'

async function demandeMulti(r, m, adresse) {
  const dossiers = listeDe(await lireJson(await r.get(`${API}/ged/dossiers/?page_size=5`, T), 'dossiers'))
  let dossier = dossiers[0]?.id
  if (!dossier) {
    const cabinets = listeDe(await lireJson(await r.get(`${API}/ged/cabinets/?page_size=5`, T), 'cabinets'))
    const cabinet = cabinets[0]?.id ?? (await lireJson(await r.post(`${API}/ged/cabinets/`, { ...T, data: { nom: `APUB ${m}` } }), 'cabinet')).id
    dossier = (await lireJson(await r.post(`${API}/ged/dossiers/`, { ...T, data: { nom: `APUB ${m}`, cabinet } }), 'dossier')).id
  }
  const fichier = { name: `apub${m}.pdf`, mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 1 0 obj<</Type/Catalog>>endobj trailer<</Root 1 0 R>> %%EOF') }
  const doc = await lireJson(await r.post(`${API}/ged/documents/televerser/`, { ...T, multipart: { folder: String(dossier), nom: `APUB signature ${m}.pdf`, file: fichier } }), 'dépôt')
  const dem = await lireJson(await r.post(`${API}/ged/demandes-signature/creer-multi/`, {
    ...T, data: { document: doc.id, destinataires: [{ nom: 'Un', email: `un${m}@example.invalid`, role: 'signataire' }, { nom: 'Deux', email: `deux${m}@example.invalid`, role: 'signataire' }] },
  }), 'demande multi')
  const un = dem.signataires[0]
  const jeton = un.lien_signature.split('/').filter(Boolean).pop()
  // Given : destinataire à code par e-mail (auth_extra) à une adresse autorisée — posé après la notification initiale.
  await py(`from apps.ged.models import SignataireDemande
SignataireDemande.objects.filter(token=${JSON.stringify(jeton)}).update(auth_extra='email_otp', email=${JSON.stringify(adresse)}); sortie(1)`)
  return { demande: dem.id, jeton }
}

etape('PF5.2-APUB9', ['APUB9'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const { jeton } = await demandeMulti(page.request, m, ADRESSE_OTP9)
  const etat = () => py(`from apps.ged.models import SignataireDemande
s = SignataireDemande.objects.get(token=${JSON.stringify(jeton)})
sortie(dict(essais=s.otp_essais, expire=str(s.otp_expires_at)))`)
  expect(codesRecus(ADRESSE_OTP9), 'boîte vide au départ').toEqual([])
  const v = await navigateur(page, testInfo, suivi)
  await v.page.goto(`/ged/signataire/${jeton}`)
  await expect(v.page.getByText('Un code de vérification est requis avant de signer.')).toBeVisible({ timeout: 60_000 })
  await v.page.getByRole('button', { name: 'Recevoir un code' }).click()
  const t0 = Date.now()
  await expect(v.page.getByLabel('Code reçu')).toBeVisible({ timeout: 30_000 })
  await expect.poll(() => codesRecus(ADRESSE_OTP9).length, { message: '1er envoi : un e-mail', timeout: 20_000 }).toBe(1)
  const code = codesRecus(ADRESSE_OTP9)[0]
  // Un mauvais code : un essai consommé.
  suivi.attendre(new RegExp(`ged/signataire/${jeton}`), 400)
  await v.page.getByLabel('Code reçu').fill(code === '000000' ? '111111' : '000000')
  await v.page.getByRole('button', { name: 'Valider le code' }).click()
  await expect(v.page.locator('.page-error')).toBeVisible({ timeout: 30_000 })
  const apresEssai = await etat()
  expect(apresEssai.essais, 'un essai consommé').toBe(1)
  // Renvoi dans la minute (on recharge, « Recevoir un code ») : 429 nommant l'attente, aucun e-mail, essais intacts.
  suivi.attendre(new RegExp(`ged/signataire/${jeton}`), 429)
  await v.page.reload()
  const refus = v.page.waitForResponse((x) => x.url().includes(`/ged/signataire/${jeton}/`) && x.request().method() === 'POST')
  await v.page.getByRole('button', { name: 'Recevoir un code' }).click()
  const r429 = await refus
  const corps = await r429.json()
  expect(r429.status(), 'renvoi dans la minute : 429').toBe(429)
  expect(corps.attente_s, 'attente_s').toBeGreaterThan(0)
  expect(corps.attente_s, 'attente_s ≤ 60').toBeLessThanOrEqual(60)
  expect(corps.detail).toBe(`Code déjà envoyé : réessayez dans ${corps.attente_s} s.`)
  await expect(v.page.locator('.page-error')).toContainText('réessayez dans', { timeout: 30_000 })
  expect(codesRecus(ADRESSE_OTP9).length, 'aucun e-mail au refus').toBe(1)
  expect(await etat(), 'destinataire relu : essais = 1, expiration inchangée').toEqual(apresEssai)
  // 61 s après le premier envoi : nouvel envoi accepté.
  await v.page.waitForTimeout(Math.max(0, 61_500 - (Date.now() - t0)))
  await v.page.reload()
  const ok = v.page.waitForResponse((x) => x.url().includes(`/ged/signataire/${jeton}/`) && x.request().method() === 'POST')
  await v.page.getByRole('button', { name: 'Recevoir un code' }).click()
  expect((await ok).status(), 'après 61 s : 200').toBe(200)
  await expect.poll(() => codesRecus(ADRESSE_OTP9).length, { message: 'après 61 s : un second e-mail', timeout: 20_000 }).toBe(2)
  await v.ctx.close()
})

// ── PF5.2 — APUB40 : code exigé avant de refuser et avant de lire le document ───────────────────────────
etape('PF5.2-APUB40', ['APUB40'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const { demande, jeton } = await demandeMulti(page.request, m, ADRESSE_OTP40)
  void demande
  const statutDemande = () => py(`from apps.ged.models import SignataireDemande
sortie(SignataireDemande.objects.select_related('demande').get(token=${JSON.stringify(jeton)}).demande.statut)`)
  const anon = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  const ceremonie = await lireJson(await anon.get(`${API}/ged/signataire/${jeton}/`, T), 'cérémonie')
  expect([ceremonie.otp_requis, ceremonie.apercu_url ?? null], 'code requis, aperçu nul').toEqual([true, null])
  // Sans code : refus 400 (demande intacte), document 403 otp_required.
  const refus = await anon.post(`${API}/ged/signataire/${jeton}/`, { ...T, data: { action: 'refuser', motif: 'x' } })
  expect([refus.status(), (await refus.json()).detail], 'refuser sans code : 400').toEqual([400, 'Authentification supplémentaire requise avant de refuser : saisissez le code reçu.'])
  expect(await statutDemande(), 'demande relue : en attente').toBe('en_attente')
  const doc = await anon.get(`${API}/ged/signataire/${jeton}/document/`, T)
  expect([doc.status(), (await doc.text()).includes('otp_required')], 'document sans code : 403 otp_required').toEqual([403, true])
  // Écran du destinataire : ni document ni « Refuser » avant le code.
  const v = await navigateur(page, testInfo, suivi)
  await v.page.goto(`/ged/signataire/${jeton}`)
  await expect(v.page.getByText('Un code de vérification est requis avant de signer.')).toBeVisible({ timeout: 60_000 })
  await expect(v.page.getByText('L’aperçu du document n’est pas disponible', { exact: false })).toBeVisible()
  await expect(v.page.getByRole('button', { name: 'Refuser' })).toHaveCount(0)
  await expect(v.page.locator('iframe, img[alt]')).toHaveCount(0)
  // Le bon code (e-mail reçu) débloque document et refus.
  await v.page.getByRole('button', { name: 'Recevoir un code' }).click()
  await expect.poll(() => codesRecus(ADRESSE_OTP40).length, { message: 'code reçu par e-mail', timeout: 20_000 }).toBe(1)
  await v.page.getByLabel('Code reçu').fill(codesRecus(ADRESSE_OTP40)[0])
  await v.page.getByRole('button', { name: 'Valider le code' }).click()
  await expect(v.page.getByRole('button', { name: 'Refuser' })).toBeVisible({ timeout: 30_000 })
  await expect(v.page.locator('iframe')).toHaveCount(1)
  expect((await anon.get(`${API}/ged/signataire/${jeton}/document/`, T)).status(), 'document après le code : 200').toBe(200)
  await v.page.getByRole('button', { name: 'Refuser' }).click()
  await v.page.getByLabel('Motif du refus').fill('APUB40 refus après code')
  await v.page.getByRole('button', { name: 'Confirmer le refus' }).click()
  await expect(v.page.getByText('Vous avez refusé de signer ce document.', { exact: false })).toBeVisible({ timeout: 30_000 })
  expect(await statutDemande(), 'refus après le code : demande refusée').toBe('refuse')
  await v.ctx.close(); await anon.dispose()
})

// ── PF5.2 — APUB44 : un membre « lecture seule » du portail client ne saisit pas de relevé ──────────────
etape('PF5.2-APUB44', ['APUB44'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const MDP_PORTAIL = `Portail-APUB44-${m}!x9`
  const f = await py(`from decimal import Decimal
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Equipement
from apps.stock.models import Produit
from apps.ventes.models import Devis
from apps.portail.services import accepter_invitation_portail, inviter_membre_portail, provisionner_compte_portail_client
co = ${SOC}
cl = Client.objects.create(company_id=co, nom='APUB44', prenom='${m}', email='apub44-${m}@example.invalid')
dv = Devis.objects.create(company_id=co, reference='DEV-APUB44-${m}', client=cl, statut='accepte', taux_tva=Decimal('20'), mode_installation='agricole', etude_params={'m3_jour': 134.2, 'debit_hmt_m3h': 30.5})
ch = Installation.objects.create(company_id=co, reference='CH-APUB44-${m}', client=cl, devis=dv, type_installation='agricole')
pr = Produit.objects.create(company_id=co, nom='Pompe APUB44 ${m}', role_pompage='pompe', prix_vente=Decimal('1000'), prix_achat=Decimal('600'))
eq = Equipement.objects.create(company_id=co, produit=pr, installation=ch)
adm, _ = provisionner_compte_portail_client(cl.company, cl.id)
adm.set_password(${JSON.stringify(MDP_PORTAIL)}); adm.must_change_password = False; adm.save()
mem = {}
for role in ('lecture', 'ecriture'):
    inv = inviter_membre_portail(cl.company, cl.id, f'apub44{role}-${m}@example.invalid', role)
    u = accepter_invitation_portail(inv.token_invitation, ${JSON.stringify(MDP_PORTAIL)})
    U.objects.filter(pk=u.pk).update(must_change_password=False)
    mem[role] = u.username
sortie(dict(chantier=ch.pk, ref=ch.reference, eq=eq.pk, admin=adm.username, **mem))`)
  const nb = () => py(`from apps.sav.models import ReleveCompteurEquipement
sortie(ReleveCompteurEquipement.objects.filter(equipement_id=${f.eq}).count())`)
  const url = `${API}/portail/mes-chantiers/${f.chantier}/releves/`
  // Écran du portail, membre « lecture » : la saisie est refusée avec le message, rien d'écrit.
  const v = await navigateur(page, testInfo, suivi, { username: f.lecture, password: MDP_PORTAIL })
  await v.page.goto('/portail/client/chantiers')
  await expect(v.page.getByText(f.ref)).toBeVisible({ timeout: 60_000 })
  await v.page.getByRole('button', { name: 'Voir le suivi' }).click()
  await expect(v.page.getByTestId('releves-pompe')).toBeVisible({ timeout: 60_000 })
  suivi.attendre(new RegExp(`mes-chantiers/${f.chantier}/releves/`), 403)
  await v.page.locator(`#rel-val-${f.chantier}`).fill('12')
  await v.page.getByRole('button', { name: 'Enregistrer le relevé' }).click()
  await expect(v.page.getByTestId('releve-erreur-valeur')).toHaveText('Votre accès est en lecture seule : vous ne pouvez pas saisir de relevé.', { timeout: 30_000 })
  expect(await nb(), 'aucun relevé écrit').toBe(0)
  await v.page.reload()
  await v.page.getByRole('button', { name: 'Voir le suivi' }).click()
  await expect(v.page.getByText('Aucun relevé pour le moment.')).toBeVisible({ timeout: 60_000 })
  // API : lecture 403 nommé, GET 200 ; écriture et admin 201.
  const api = async (u) => { const c = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL }); await connexionApi(c, { username: u, password: MDP_PORTAIL }); return c }
  const lec = await api(f.lecture)
  const x = await lec.post(url, { ...T, data: { equipement: f.eq, type: 'm3', valeur: '12' } })
  expect([x.status(), (await x.json()).detail], 'lecture : 403 nommé').toEqual([403, 'Votre accès est en lecture seule : vous ne pouvez pas saisir de relevé.'])
  expect((await lec.get(url, T)).status(), 'lecture : GET 200').toBe(200)
  const ecr = await api(f.ecriture)
  const y = await ecr.post(url, { ...T, data: { equipement: f.eq, type: 'm3', valeur: '12' } })
  expect(y.status(), `écriture : 201 (${(await y.text()).slice(0, 200)})`).toBe(201)
  const adm = await api(f.admin)
  const z = await adm.post(url, { ...T, data: { equipement: f.eq, type: 'm3', valeur: '13' } })
  expect(z.status(), `admin portail : 201 (${(await z.text()).slice(0, 200)})`).toBe(201)
  expect(await nb(), 'relevés relus : 2 (écriture + admin)').toBe(2)
  for (const c of [lec, ecr, adm]) await c.dispose()
  await v.ctx.close()
})

// ── PF5.3 — APUB11 : l'API publique qui sort un lead de « Signé » dés-accepte, ou 409 ───────────────────
etape('PF5.3-APUB11', ['APUB11'], async ({ page }) => {
  const r = page.request
  const m = marque()
  const a = await vente(r, `${m}a`, { accepter: true })
  const b = await vente(r, `${m}b`, { accepter: true })
  const fac = await r.post(`${API}/ventes/devis/${b.devis.id}/generer-facture/`, { ...T, data: {} })
  expect(fac.status(), `facture du devis B : ${(await fac.text()).slice(0, 200)}`).toBe(201)
  const etat = (l, d) => py(`from apps.crm.models import Lead
from apps.ventes.models import Devis
from apps.facturation.models import Facture
sortie(dict(stage=Lead.objects.get(pk=${l}).stage, devis=Devis.objects.get(pk=${d}).statut, factures=list(Facture.objects.filter(devis_id=${d}).values_list('reference', flat=True))))`)
  const eb = await etat(b.lead.id, b.devis.id)
  expect([(await etat(a.lead.id, a.devis.id)).stage, eb.stage, eb.devis], 'Given : deux leads Signés, devis acceptés').toEqual(['SIGNED', 'SIGNED', 'accepte'])
  const refFacture = eb.factures[0]
  expect(refFacture, 'facture du devis B').toBeTruthy()
  const cle = await lireJson(await r.post(`${API}/publicapi/keys/`, { ...T, data: { label: `APUB11 ${m}`, scopes: ['leads:write'] } }), 'clé API')
  const pub = await pwRequest.newContext({ baseURL: DJANGO, extraHTTPHeaders: { Authorization: `Api-Key ${cle.key}` } })
  // Raison d'archive sans touche exigée (lead d'essai) : « injoignable » exigerait 5 appels tracés (CADV22), hors sujet ici.
  const corps = { stage: 'COLD', parc_raison: 'test' }
  // Lead A : 200, Froid, devis repassé « envoyé ».
  const pa = await pub.patch(`/api/public/v1/leads-write/${a.lead.id}/`, { ...T, data: corps, headers: { 'Idempotency-Key': `apub11a-${m}` } })
  expect(pa.status(), `PATCH A : ${(await pa.text()).slice(0, 300)}`).toBe(200)
  expect(await etat(a.lead.id, a.devis.id), 'A relu : Froid, devis envoyé').toMatchObject({ stage: 'COLD', devis: 'envoye' })
  // Lead B : 409 nommant la facture, rien d'écrit.
  const pb = await pub.patch(`/api/public/v1/leads-write/${b.lead.id}/`, { ...T, data: corps, headers: { 'Idempotency-Key': `apub11b-${m}` } })
  const texteB = await pb.text()
  expect(pb.status(), `PATCH B : ${texteB.slice(0, 300)}`).toBe(409)
  expect(texteB, '409 nomme la facture').toContain(refFacture)
  expect(await etat(b.lead.id, b.devis.id), 'B relu : Signé, devis accepté').toMatchObject({ stage: 'SIGNED', devis: 'accepte' })
  // Import upsert : la ligne de B en erreur au même message, la suivante passe.
  const nouveau = `apub11n${m}@example.invalid`
  const lignes = [{ nom: `APUB ${m}b`, email: b.lead.email, ...corps }, { nom: `APUB11 nouveau ${m}`, email: nouveau, telephone: telephoneMobileUnique() }]
  const imp = await pub.post('/api/public/v1/imports/', { ...T, multipart: { file: { name: 'leads.jsonl', mimeType: 'application/x-ndjson', buffer: Buffer.from(`${lignes.map((l) => JSON.stringify(l)).join('\n')}\n`) }, entite: 'leads', mode: 'upsert', dedup_key: 'email' } })
  expect(imp.status(), `import : ${(await imp.text()).slice(0, 300)}`).toBe(202)
  const job = (await imp.json()).id
  // Pas de worker Celery sur la pile : la tâche du worker est exécutée telle quelle (idempotente par curseur).
  const res = await py(`import json as _j
from apps.publicapi.bulk import run_import_job, _fetch_bytes
from apps.publicapi.models import BulkJob
from apps.crm.models import Lead
run_import_job(${job})
j = BulkJob.objects.get(pk=${job})
err = _fetch_bytes(j.erreurs_file_key).decode() if j.erreurs_file_key else ''
sortie(dict(statut=j.statut, succes=j.succes, erreurs=j.erreurs, journal=err, nouveau=Lead.objects.filter(company_id=${SOC}, email=${JSON.stringify(nouveau)}).count()))`)
  expect([res.statut, res.succes, res.erreurs, res.nouveau], `import : 1 erreur, 1 succès (${res.journal.slice(0, 400)})`).toEqual(['termine', 1, 1, 1])
  expect(res.journal, 'ligne en erreur : même message (facture)').toContain(refFacture)
  expect(await etat(b.lead.id, b.devis.id), 'B relu après import : inchangé').toMatchObject({ stage: 'SIGNED', devis: 'accepte' })
  await pub.dispose()
})
