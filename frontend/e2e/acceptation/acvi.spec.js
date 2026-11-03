// ACVI — rejeu en direct du parcours PA1 (CLAUDE.md 3-bis, METHODE §C.4) sur la pile locale : les gestes passent par
// l'API réelle (ou l'écran pour le glisser vers Froid et la revue des visites) ; le shell Django (`_django.js`) ne pose
// que ce qu'aucun geste ne peut poser (rôle sur mesure, doublon d'un même numéro, date du passé) et relit le registre.
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { uniq, lireJson, listeDe, telephoneMobileUnique, connexionApi, assurerSessionPage, PNG_1PX, isoDansJours, mesuresContratVisite, remplirVisiteCi } from '../helpers.js'

const etape = groupe('ACVI', [
  'ACVI1', 'ACVI4', 'ACVI7', 'ACVI9', 'ACVI12', 'ACVI15', 'ACVI17', 'ACVI18', 'ACVI21', 'ACVI22', 'ACVI25', 'ACVI33', 'ACVI44', 'ACVI50', 'ACVI58',
  'ACVI55', 'ACVI56', 'ACVI61', 'ACVI66', 'ACVI93', 'ACVI96', 'ACVI67', 'ACVI16', 'ACVI27', 'ACVI79', 'ACVI84', 'ACVI49', 'ACVI71', 'ACVI23', 'ACVI69', 'ACVI62', 'ACVI14', 'ACVI68',
])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 300_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})

const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const courriel = () => `${uniq('acvi').toLowerCase().replace(/[^a-z0-9]/g, '')}@example.invalid`

// Comptes d'essai à rôle réel (pk du rôle de la société démo), une connexion par compte : le plafond de connexion
// (5/min/IP) n'est pas un sujet de cette spec.
const sessions = new Map()
async function compteSession(testInfo, nom, role) {
  const dej = sessions.get(nom)
  if (dej && Date.now() - dej.quand < 20 * 60_000) return dej
  const id = await py(`u = compte(${JSON.stringify(nom)}, role=${role}); sortie(u.id)`)
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(ctx, { username: nom, password: MDP_ESSAI })
  const s = { ctx, id, quand: Date.now() }
  sessions.set(nom, s)
  return s
}
const ROLE = { DIRECTEUR: 1, COMMERCIAL: 4, TECHNICIEN: 6, ADMIN_RH: 71 }

const nouveauLead = async (request, nom, extra = {}) => lireJson(await request.post(`${API}/crm/leads/`, {
  ...T, data: { nom, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: courriel(), ...extra },
}), 'lead')
const relu = async (request, id) => lireJson(await request.get(`${API}/crm/leads/${id}/`, T), 'lead relu')
const touches = async (request, lid) => listeDe(await lireJson(await request.get(`${API}/crm/relance-etapes/?lead=${lid}`, T), 'touches'))
const historique = async (request, lid) => listeDe(await lireJson(await request.get(`${API}/crm/leads/${lid}/historique/`, T), 'historique'))
const csv = (texte) => ({ name: 'leads.csv', mimeType: 'text/csv', buffer: Buffer.from(texte, 'utf-8') })

let secretWebhook = null
async function webhookSite(testInfo, corps, entetes = {}) {
  secretWebhook ??= await py(`from django.conf import settings; sortie(settings.WEBSITE_LEAD_WEBHOOK_SECRET)`)
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  const r = await ctx.post(`${API}/crm/webhooks/website-leads/`, {
    ...T, data: { idempotencyKey: globalThis.crypto.randomUUID(), consent: true, ...corps }, headers: { 'X-Webhook-Secret': secretWebhook, ...entetes },
  })
  const sortie = { statut: r.status(), corps: await r.json().catch(() => ({})) }
  await ctx.dispose()
  return sortie
}
const registre = (leadId) => py(`from core.models import ConsentRecord
from apps.crm.models import Lead
l = Lead.objects.get(pk=${leadId})
ids = [x for x in (l.email, l.telephone, l.whatsapp) if x]
sortie([dict(granted=c.granted, source=c.source, identifiant=c.subject_identifier) for c in ConsentRecord.objects.filter(company_id=l.company_id, subject_identifier__in=ids)])`)
const toucheWhatsapp = (leadId, ordre, extra = '') => py(`from apps.crm.models_cadence import RelanceEtape
sortie(RelanceEtape.objects.create(company_id=1, lead_id=${leadId}, cadence='contact', ordre=${ordre}, due_date=timezone.localdate(), due_at=timezone.now(), canal='whatsapp', libelle='Message'${extra}).id)`)

// ── gestes de visite (mêmes mesures que `alea.spec.js`) ────────────────────────────────────────
const MESURES = {
  toiture: { longueur_m: 12.5, largeur_m: 8, pente_deg: 15, toit_plat: false, orientation: 'sud', type_couverture: 'tuile', etat_couverture: 'bon' },
  tableau: { calibre_disjoncteur_a: 63, type_alimentation: 'mono', emplacements_libres: 4 },
  local_onduleur: { largeur_mur_cm: 200, hauteur_mur_cm: 250, profondeur_degagement_cm: 80, distance_tableau_m: 5, local_abrite: true, local_ventile: true },
}
const V = `${API}/visites/visites`
const photo = async (ctx, id, slot, nom) => lireJson(await ctx.post(`${V}/${id}/photos/`, {
  ...T, multipart: { slot_code: slot, fichier: { name: nom, mimeType: 'image/png', buffer: PNG_1PX } },
}), `photo ${slot}`)
async function remplir(ctx, id) {
  for (const [categorie, valeurs] of Object.entries(MESURES)) {
    await lireJson(await ctx.patch(`${V}/${id}/mesures/`, { ...T, data: { categorie, valeurs } }), `mesures ${categorie}`)
  }
  const visite = await lireJson(await ctx.get(`${V}/${id}/`, T), 'visite')
  for (const bloc of visite.checklist) {
    for (const slot of bloc.slots.filter((s) => s.requis)) {
      for (let i = 0; i < (slot.min_photos || 1); i += 1) await photo(ctx, id, slot.code, `${slot.code}-${i}.png`)
    }
  }
  return lireJson(await ctx.get(`${V}/${id}/`, T), 'visite remplie')
}
const visiteRelue = async (ctx, id) => lireJson(await ctx.get(`${V}/${id}/`, T), 'visite relue')
async function visiteTerminee(ctx, leadId, data = {}) {
  const cree = await lireJson(await ctx.post(`${V}/`, { ...T, data: { lead: leadId, ...data } }), 'créer la visite')
  const v = await remplir(ctx, cree.id)
  expect(v.completude.complet, `visite complète (${JSON.stringify(v.completude.manquants)})`).toBe(true)
  const t = await lireJson(await ctx.post(`${V}/${cree.id}/terminer/`, { ...T, data: {} }), 'terminer')
  expect(t.statut).toBe('terminee')
  return cree.id
}

// ── ACVI1 — import de leads borné : droit et portée ────────────────────────────────────────────
etape('PA1.01.import_borne', ['ACVI1'], async ({ page, testInfo }) => {
  const rh = await compteSession(testInfo, 'acvi_rh', ROLE.ADMIN_RH)
  const tech = await compteSession(testInfo, 'acvi_tech', ROLE.TECHNICIEN)
  const c1 = await compteSession(testInfo, 'acvi_c1', ROLE.COMMERCIAL)
  const c2 = await compteSession(testInfo, 'acvi_c2', ROLE.COMMERCIAL)
  const m = marque()
  const email = `a${m}@example.invalid`
  const tel = telephoneMobileUnique()
  const l = await nouveauLead(c1.ctx, `ACVI1 ${m}`, { telephone: tel, email })
  expect(l.owner, 'le lead appartient à C1').toBe(c1.id)
  const fichier = () => csv(`telephone,email\n${tel},b${m}@example.invalid\n`)
  const options = { target: 'leads', mode: 'maj', ecraser: 'true' }
  // Témoin : un administrateur voit bien la cible (l'aperçu n'est pas vide pour une autre raison).
  const temoin = await lireJson(await page.request.post(`${API}/imports/dry-run/`, { ...T, multipart: { ...options, file: fichier() } }), 'aperçu admin')
  expect(temoin.conflits?.[0]?.cible_id, 'témoin admin : cible servie').toBe(l.id)
  for (const [qui, s] of [['Admin RH', rh], ['Technicien', tech]]) {
    for (const route of ['commit', 'dry-run']) {
      const r = await s.ctx.post(`${API}/imports/${route}/`, { ...T, multipart: { ...options, file: fichier() } })
      expect(r.status(), `${qui} ${route}`).toBe(403)
      expect(await r.text(), `${qui} ${route} : droit nommé`).toContain('droit_manquant')
    }
  }
  const apercu = await c2.ctx.post(`${API}/imports/dry-run/`, { ...T, multipart: { ...options, file: fichier() } })
  expect(apercu.status(), 'C2 aperçu').toBe(200)
  const apercuTxt = await apercu.text()
  expect(apercuTxt, 'aucune identité du lead du collègue').not.toContain(email)
  expect(apercuTxt, 'sans cible_id').not.toContain(`"cible_id":${l.id}`)
  expect(apercuTxt, 'sans ancienne').not.toContain('"ancienne"')
  const commit = await c2.ctx.post(`${API}/imports/commit/`, { ...T, multipart: { ...options, file: fichier() } })
  expect(commit.status(), 'C2 commit').toBe(200)
  expect((await commit.json()).updated ?? 0, 'aucune réécriture').toBe(0)
  expect((await relu(c1.ctx, l.id)).email, 'persistance : L inchangé').toBe(email)
})

// ── ACVI4 — numéro masqué sans `client_pii_voir` ───────────────────────────────────────────────
etape('PA1.04.numero_masque', ['ACVI4'], async ({ page, testInfo }) => {
  const roleId = await py(`from apps.roles.models import Role
r, _ = Role.objects.get_or_create(company_id=1, nom='ACVI4 CRM sans PII', defaults=dict(permissions=['crm_voir', 'crm_modifier']))
r.permissions = ['crm_voir', 'crm_modifier']; r.save(); sortie(r.id)`)
  const sans = await compteSession(testInfo, 'acvi_sanspii', roleId)
  const m = marque()
  const lead = await nouveauLead(page.request, `ACVI4 ${m}`)
  // Une touche WhatsApp à faire : la cadence pose un appel d'abord, seul le shell donne le canal voulu tout de suite.
  const t = await toucheWhatsapp(lead.id, 90)
  const chiffres = lead.telephone.replace(/\D/g, '').slice(-9)
  const tpl = await lireJson(await page.request.post(`${API}/crm/message-templates/`, { ...T, data: { nom: `ACVI4 ${m}`, langue: 'fr', corps: 'Bonjour {prenom}.' } }), 'modèle')
  // Témoin : un administrateur reçoit bien le numéro.
  const temoin = await lireJson(await page.request.get(`${API}/crm/relance-etapes/${t}/message/`, T), 'message admin')
  expect(temoin.phone, 'témoin admin').toContain(chiffres)
  const msg = await lireJson(await sans.ctx.get(`${API}/crm/relance-etapes/${t}/message/`, T), 'message sans PII')
  expect(msg.phone, 'phone vide').toBe('')
  expect(msg.wa_url, 'wa_url null').toBeNull()
  expect(JSON.stringify(msg), 'aucun numéro dans la réponse').not.toContain(chiffres)
  const lot = await sans.ctx.post(`${API}/crm/leads/bulk/`, { ...T, data: { action: 'prepare_whatsapp', ids: [lead.id], template_id: tpl.id } })
  expect(lot.status(), await lot.text()).toBe(200)
  const q = (await lot.json()).queue
  expect(q, 'file servie').toHaveLength(1)
  expect(q[0].phone, 'queue[].phone vide').toBe('')
  expect(JSON.stringify(q[0]), 'aucun numéro dans la file').not.toContain(chiffres)
  const rdv = await lireJson(await page.request.post(`${API}/crm/appointments/`, { ...T, data: { lead: lead.id, scheduled_at: `${isoDansJours(3)}T10:00:00+01:00` } }), 'rendez-vous')
  const conf = await sans.ctx.post(`${API}/crm/appointments/${rdv.id}/confirmer-whatsapp/`, { ...T, data: {} })
  expect(conf.status(), 'confirmer-whatsapp').toBe(403)
  expect(await conf.text(), 'droit nommé').toContain('droit_manquant')
})

// ── ACVI7 — créer un lead affecté à un collègue exige `crm_reassign` ───────────────────────────
etape('PA1.01.owner_a_la_creation', ['ACVI7'], async ({ page, testInfo }) => {
  const c = await compteSession(testInfo, 'acvi_c1', ROLE.COMMERCIAL)
  const d = await compteSession(testInfo, 'acvi_c2', ROLE.COMMERCIAL)
  const m = marque()
  const refus = await c.ctx.post(`${API}/crm/leads/`, { ...T, data: { nom: `ACVI7 ${m} X`, telephone: telephoneMobileUnique(), owner: d.id } })
  expect(refus.status(), 'collègue : 403').toBe(403)
  expect(await refus.text()).toContain('crm_reassign')
  const ok = await lireJson(await c.ctx.post(`${API}/crm/leads/`, { ...T, data: { nom: `ACVI7 ${m} Y`, telephone: telephoneMobileUnique(), owner: c.id } }), 'soi : 201')
  expect(ok.owner).toBe(c.id)
  const liste = listeDe(await lireJson(await page.request.get(`${API}/crm/leads/?search=${encodeURIComponent(`ACVI7 ${m}`)}`, T), 'relire'))
  expect(liste.map((x) => x.nom), 'persistance : aucun lead X').toEqual([`ACVI7 ${m} Y`])
})

// ── ACVI9 — Froid : raison exigée au PATCH et sur le glisser du kanban ─────────────────────────
etape('PA1.08.froid_patch_raison', ['ACVI9'], async ({ page }) => {
  const m = marque()
  const l = await nouveauLead(page.request, `ACVI9 ${m}`)
  const appel = (await touches(page.request, l.id)).find((x) => x.statut === 'a_faire')
  expect(appel, 'touche ouverte').toBeTruthy()
  await lireJson(await page.request.post(`${API}/crm/relance-etapes/${appel.id}/fait/`, { ...T, data: { outcome: 'non_joint', note: 'rejeu ACVI9' } }), 'appel tracé')
  const sans = await page.request.patch(`${API}/crm/leads/${l.id}/`, { ...T, data: { stage: 'COLD' } })
  expect(sans.status(), 'sans raison').toBe(409)
  expect((await sans.json()).parc_raison, 'nomme parc_raison').toEqual(['Raison de mise au Froid obligatoire.'])
  expect((await relu(page.request, l.id)).stage, 'étape inchangée').not.toBe('COLD')
  const avant = (await historique(page.request, l.id)).length
  const avec = await lireJson(await page.request.patch(`${API}/crm/leads/${l.id}/`, { ...T, data: { stage: 'COLD', parc_raison: 'budget' } }), 'avec raison')
  expect(avec.parc_etat).toBe('nurture')
  const apres = await relu(page.request, l.id)
  expect([apres.stage, apres.parc_etat, apres.parc_raison], 'persistance').toEqual(['COLD', 'nurture', 'budget'])
  expect((await historique(page.request, l.id)).length, 'ligne au chatter').toBeGreaterThan(avant)
})

etape('PA1.08.froid_kanban_dialogue', ['ACVI9'], async ({ page, suivi }) => {
  const m = marque()
  const nom = `ACVI9K ${m}`
  const l = await nouveauLead(page.request, nom)
  await page.goto(`/crm/leads?view=kanban&q=${encodeURIComponent(nom)}`)
  const carte = page.locator(`[data-lead-id="${l.id}"]`)
  await expect(carte).toBeVisible({ timeout: 60_000 })
  const colonne = page.locator('[aria-label^="Étape Froid"]').first()
  await expect(colonne).toBeVisible()
  const glisser = async () => {
    await carte.scrollIntoViewIfNeeded()
    const a = await carte.boundingBox()
    await page.mouse.move(a.x + a.width / 2, a.y + a.height / 2)
    await page.mouse.down()
    await page.mouse.move(a.x + a.width / 2 + 15, a.y + a.height / 2 + 5, { steps: 4 })
    await colonne.evaluate((el) => el.scrollIntoView({ inline: 'center', block: 'nearest' }))
    const b = await colonne.boundingBox()
    await page.mouse.move(b.x + b.width / 2, b.y + 60, { steps: 12 })
    await page.mouse.up()
  }
  const dialogue = page.getByRole('dialog').filter({ hasText: `Mettre « ${nom} » au Froid` })
  const patchs = []
  page.on('request', (r) => { if (r.method() === 'PATCH' && r.url().includes(`/crm/leads/${l.id}/`)) patchs.push(r.postDataJSON()) })
  // Annuler : aucun PATCH, le lead reste où il est.
  await glisser()
  await expect(dialogue).toBeVisible({ timeout: 15_000 })
  await expect(dialogue.getByRole('button', { name: 'Mettre au Froid' }), 'inactif sans raison').toBeDisabled()
  await dialogue.getByRole('button', { name: 'Annuler' }).click()
  await expect(dialogue).toBeHidden()
  expect(patchs, 'Annuler : aucun PATCH').toEqual([])
  expect((await relu(page.request, l.id)).stage).toBe('NEW')
  // Avec la raison mais sans aucune touche tracée : le refus du serveur (409) s'affiche, le lead revient.
  suivi.attendre(new RegExp(`/crm/leads/${l.id}/`), 409)
  await glisser()
  await expect(dialogue).toBeVisible({ timeout: 15_000 })
  await dialogue.getByLabel('Raison de mise au Froid').selectOption('budget')
  const [refus] = await Promise.all([
    page.waitForResponse((r) => r.url().includes(`/crm/leads/${l.id}/`) && r.request().method() === 'PATCH', T),
    dialogue.getByRole('button', { name: 'Mettre au Froid' }).click(),
  ])
  expect(refus.status(), 'aucun parcage à 0 touche').toBe(409)
  const motif = (await refus.json()).detail
  await expect(page.getByText(motif).first(), 'le 409 est affiché').toBeVisible()
  expect((await relu(page.request, l.id)).parc_etat || '', 'rien de parqué').not.toBe('nurture')
  // Un appel tracé : le glisser range le lead au Froid, le PATCH porte la raison, l'écran l'annonce, le serveur la garde.
  const appel = (await touches(page.request, l.id)).find((x) => x.statut === 'a_faire')
  await lireJson(await page.request.post(`${API}/crm/relance-etapes/${appel.id}/fait/`, { ...T, data: { outcome: 'non_joint', note: 'rejeu ACVI9' } }), 'appel tracé')
  await page.reload()
  await expect(carte).toBeVisible({ timeout: 60_000 })
  await glisser()
  await expect(dialogue).toBeVisible({ timeout: 15_000 })
  await dialogue.getByLabel('Raison de mise au Froid').selectOption('budget')
  const [rep] = await Promise.all([
    page.waitForResponse((r) => r.url().includes(`/crm/leads/${l.id}/`) && r.request().method() === 'PATCH', T),
    dialogue.getByRole('button', { name: 'Mettre au Froid' }).click(),
  ])
  expect(rep.status(), await rep.text()).toBe(200)
  expect(patchs.at(-1), 'raison dans le PATCH').toMatchObject({ stage: 'COLD', parc_raison: 'budget' })
  await expect(page.getByText('Lead rangé au Froid.')).toBeVisible()
  await page.reload()
  await expect(colonne.locator(`[data-lead-id="${l.id}"]`), 'persistance à l\'écran : colonne Froid').toBeVisible({ timeout: 60_000 })
  const apres = await relu(page.request, l.id)
  expect([apres.stage, apres.parc_etat, apres.parc_raison]).toEqual(['COLD', 'nurture', 'budget'])
  suivi.verifie(5)
})

// ── ACVI12 — même finalisation d'arrivée : API publique, ticket SAV, import fichier ────────────
etape('PA1.01.finalisation_arrivee', ['ACVI12'], async ({ page }) => {
  const m = marque()
  const etat = async (id) => py(`from apps.crm.models import Lead
l = Lead.objects.get(pk=${id})
sortie(dict(owner=l.owner_id, score=l.score))`)
  // API publique : le service réel de la route à clé d'API (l'énoncé de la tâche le joue ainsi).
  const pub = await py(`from apps.crm.fiche_api_publique import create_lead_from_public_api
from authentication.models import Company
l = create_lead_from_public_api(company=Company.objects.get(pk=1), fields={'nom': 'ACVI12 ${m} Partenaire', 'telephone': '${telephoneMobileUnique()}'})
sortie(getattr(l, 'id', l))`)
  // Ticket SAV : la vraie route.
  const client = await lireJson(await page.request.post(`${API}/crm/clients/`, { ...T, data: { nom: `ACVI12 ${m} Client`, prenom: 'Sonde', telephone: telephoneMobileUnique(), email: courriel() } }), 'client')
  const ticket = await lireJson(await page.request.post(`${API}/sav/tickets/`, { ...T, data: { client: client.id, type: 'correctif', description: `ACVI12 ${m}` } }), 'ticket SAV')
  const sav = await lireJson(await page.request.post(`${API}/sav/tickets/${ticket.id}/creer-lead/`, { ...T, data: {} }), 'creer-lead')
  const savId = sav.lead_id ?? sav.lead?.id ?? sav.id
  // Import fichier : la vraie route.
  const nomImport = `ACVI12 ${m} Import`
  await lireJson(await page.request.post(`${API}/imports/commit/`, { ...T, multipart: { target: 'leads', mode: 'creer', file: csv(`nom,telephone,email\n${nomImport},${telephoneMobileUnique()},${courriel()}\n`) } }), 'import')
  const imp = listeDe(await lireJson(await page.request.get(`${API}/crm/leads/?search=${encodeURIComponent(nomImport)}`, T), 'relire import'))[0]
  expect(imp, 'lead importé').toBeTruthy()
  for (const [qui, id] of [['API publique', pub], ['ticket SAV', savId], ['import', imp.id]]) {
    const e = await etat(id)
    expect(e.owner, `${qui} : responsable`).toBeTruthy()
    expect(e.score, `${qui} : score recalculé`).not.toBeNull()
    const reg = await registre(id)
    expect(reg.length, `${qui} : registre`).toBeGreaterThanOrEqual(1)
    expect(reg.every((x) => x.granted === false), `${qui} : granted false`).toBe(true)
  }
  // BASE_LEGALE_SOLLICITATION : « relation précontractuelle à la demande de la personne ».
  expect((await registre(savId)).map((x) => x.source).join(' ').toLowerCase(), 'ticket : base « sollicitation »').toContain('à la demande de la personne')
})

// ── ACVI15 — date impossible du webhook = absente ──────────────────────────────────────────────
etape('PA1.01.webhook_date_impossible', ['ACVI15'], async ({ testInfo }) => {
  const m = marque()
  const un = await webhookSite(testInfo, { fullName: `ACVI15 ${m} A`, phoneE164: telephoneMobileUnique(), city: 'Casablanca' }, { 'X-Webhook-Timestamp': '2026-02-30T00:00:00' })
  expect(un.statut, JSON.stringify(un.corps)).toBe(201)
  expect(un.corps.lead_id, 'un lead').toBeTruthy()
  expect(un.corps.payload_id, 'un brut').toBeTruthy()
  const deux = await webhookSite(testInfo, { fullName: `ACVI15 ${m} B`, phoneE164: telephoneMobileUnique(), city: 'Casablanca', consentTimestamp: '2026-02-30T00:00:00' })
  expect(deux.statut, JSON.stringify(deux.corps)).toBe(201)
  const rel = await py(`from apps.crm.models import Lead, WebsiteLeadPayload
p = WebsiteLeadPayload.objects.get(pk=${un.corps.payload_id})
sortie(dict(champs={f.name: str(getattr(p, f.name)) for f in p._meta.fields if f.name in ('processed', 'statut', 'status', 'processed_at')}, consent=str(Lead.objects.get(pk=${deux.corps.lead_id}).consent_timestamp)))`)
  expect(JSON.stringify(rel.champs), 'persistance : brut traité').toMatch(/processed|True|\d{4}-/)
  expect(rel.consent, 'consent_timestamp null').toBe('None')
})

// ── ACVI17 — renvoi < 60 s : les défauts du mapping ne remplissent qu'un champ vide ────────────
etape('PA1.02.webhook_renvoi_defauts', ['ACVI17'], async ({ page, testInfo }) => {
  const m = marque()
  const tel = telephoneMobileUnique()
  const un = await webhookSite(testInfo, { fullName: `Amina ACVI17 ${m}`, phoneE164: tel, city: 'Casablanca', gclid: 'G1' })
  expect(un.statut, JSON.stringify(un.corps)).toBe(201)
  expect((await relu(page.request, un.corps.lead_id)).canal, 'canal du 1er envoi').toBe('google_ads')
  const deux = await webhookSite(testInfo, { phoneE164: tel, city: 'Casablanca' })
  expect(deux.statut, JSON.stringify(deux.corps)).toBe(200)
  expect(deux.corps.lead_id, 'un seul lead').toBe(un.corps.lead_id)
  const l = await relu(page.request, un.corps.lead_id)
  expect(`${l.prenom || ''} ${l.nom}`, 'persistance : nom').toContain('ACVI17')
  expect(l.canal, 'persistance : canal').toBe('google_ads')
})

// ── ACVI18 — registre : propriétaire désigné, livechat, événement marketing ────────────────────
etape('PA1.01.registre_base_legale', ['ACVI18'], async ({ page }) => {
  const m = marque()
  const t = await nouveauLead(page.request, `ACVI18 ${m} Locataire`)
  await lireJson(await page.request.post(`${API}/crm/leads/${t.id}/locataire/`, { ...T, data: { proprietaire: { nom: `ACVI18 ${m} Proprio`, telephone: telephoneMobileUnique() } } }), 'locataire')
  const proprio = listeDe(await lireJson(await page.request.get(`${API}/crm/leads/?search=${encodeURIComponent(`ACVI18 ${m} Proprio`)}`, T), 'relire'))[0]
  expect(proprio, 'lead du propriétaire').toBeTruthy()
  const regP = await registre(proprio.id)
  expect(regP.length, 'propriétaire : 1 entrée').toBe(1)
  expect(regP[0].granted).toBe(false)
  expect(regP[0].source, 'base « non collectée »').toContain('art. 34')
  // Livechat et événement marketing : aucune route de la pile locale, le service réel.
  const autres = await py(`from authentication.models import Company
from apps.crm.leads_intake import create_lead_from_livechat, create_lead_from_evenement_marketing
co = Company.objects.get(pk=1)
chat = create_lead_from_livechat(company=co, nom='ACVI18 ${m} Chat', telephone='${telephoneMobileUnique()}')
evt = create_lead_from_evenement_marketing(company=co, nom='ACVI18 ${m} Salon', telephone='${telephoneMobileUnique()}', evenement_nom='Salon')
sortie(dict(chat=chat.id, evt=evt.id))`)
  const regC = await registre(autres.chat)
  expect(regC.length, 'livechat : 1 entrée').toBe(1)
  expect(regC[0].granted).toBe(false)
  expect(regC[0].source.toLowerCase(), 'base « sollicitation »').toContain('à la demande de la personne')
  const regE = await registre(autres.evt)
  expect(regE.length, 'événement : 1 entrée').toBe(1)
  expect(regE[0].granted).toBe(false)
  expect(regE[0].source, 'base « non collectée »').toContain('art. 34')
})

// ── Fusions — doublons d'un même numéro : seul le shell les pose sans passer par la garde de doublon ─
const doublonsMemeNumero = async (a, b) => py(`from apps.crm.models import Lead
adm = U.objects.get(username='demo_admin')
tel = '${telephoneMobileUnique()}'
sortie(dict(a=Lead.objects.create(company_id=1, nom=${JSON.stringify(a)}, owner=adm, telephone=tel, ville='Casablanca').id, b=Lead.objects.create(company_id=1, nom=${JSON.stringify(b)}, owner=adm, telephone=tel, ville='Casablanca').id))`)

// ── ACVI21 — fusion : l'opposition passe au survivant ──────────────────────────────────────────
etape('PA1.08.fusion_opposition', ['ACVI21'], async ({ page }) => {
  const m = marque()
  const { a, b } = await doublonsMemeNumero(`ACVI21 ${m} A`, `ACVI21 ${m} B`)
  await lireJson(await page.request.post(`${API}/crm/leads/${b}/relance/initialiser/`, { ...T, data: { cadence: 'contact' } }), 'cadence de B')
  await lireJson(await page.request.patch(`${API}/crm/leads/${a}/`, { ...T, data: { ne_plus_contacter: true } }), 'A opposé')
  expect((await touches(page.request, b)).filter((t) => t.statut === 'a_faire').length, 'B a une touche à faire').toBeGreaterThan(0)
  await lireJson(await page.request.post(`${API}/crm/leads/${b}/merge/`, { ...T, data: { others: [a] } }), 'fusion')
  const l = await relu(page.request, b)
  expect(l.ne_plus_contacter, 'persistance : B opposé').toBe(true)
  expect((await touches(page.request, b)).filter((t) => t.statut === 'a_faire'), '0 touche à faire').toEqual([])
  expect(JSON.stringify(await historique(page.request, b)), 'ligne old→new').toContain('ne_plus_contacter')
  const opposition = await py(`from core.models import ConsentRecord
from apps.crm.models import Lead
l = Lead.objects.get(pk=${b})
sortie(ConsentRecord.objects.filter(company_id=1, subject_identifier__in=[x for x in (l.telephone, l.email) if x], granted=False).count())`)
  expect(opposition, 'opposition au registre sous les identifiants de B').toBeGreaterThan(0)
})

// ── ACVI22 — fusion : visites, rendez-vous, points rattachés au survivant ──────────────────────
etape('PA1.08.fusion_rattachements', ['ACVI22'], async ({ page }) => {
  const m = marque()
  const { a, b } = await doublonsMemeNumero(`ACVI22 ${m} A`, `ACVI22 ${m} B`)
  const date = isoDansJours(5)
  const visite = await lireJson(await page.request.post(`${V}/`, { ...T, data: { lead: a, date_prevue: date } }), 'visite de A')
  const rdv = await lireJson(await page.request.post(`${API}/crm/appointments/`, { ...T, data: { lead: a, scheduled_at: `${isoDansJours(6)}T10:00:00+01:00` } }), 'rendez-vous de A')
  await py(`from apps.crm.models import PointContact
PointContact.objects.create(company_id=1, lead_id=${a}, canal='meta_ads', source='rejeu ACVI22', date_contact=timezone.now())
sortie(1)`)
  const affichee = (await relu(page.request, a)).visite_prevue_le
  expect(affichee, 'A affiche une date').toBeTruthy()
  await lireJson(await page.request.post(`${API}/crm/leads/${b}/merge/`, { ...T, data: { others: [a] } }), 'fusion')
  const rel = await py(`from apps.crm.models import Appointment, PointContact
from apps.visites.models import VisiteTerrain
compter = lambda lid: dict(v=VisiteTerrain.objects.filter(lead_id=lid).count(), r=Appointment.objects.filter(lead_id=lid).count(), p=PointContact.objects.filter(lead_id=lid).count())
sortie(dict(a=compter(${a}), b=compter(${b}), vid=VisiteTerrain.objects.get(pk=${visite.id}).lead_id, rid=Appointment.objects.get(pk=${rdv.id}).lead_id))`)
  expect(rel.vid, 'la visite suit le survivant').toBe(b)
  expect(rel.rid, 'le rendez-vous suit le survivant').toBe(b)
  expect(rel.a, 'A : 0').toEqual({ v: 0, r: 0, p: 0 })
  expect(rel.b.p, 'B : point de contact').toBeGreaterThanOrEqual(1)
  expect((await relu(page.request, b)).visite_prevue_le, 'persistance : le survivant porte la date').toBe(affichee)
})

// ── ACVI25 — champs tapés à la création : saisie humaine ───────────────────────────────────────
etape('PA1.01.saisies_humaines_creation', ['ACVI25'], async ({ testInfo }) => {
  const c = await compteSession(testInfo, 'acvi_c1', ROLE.COMMERCIAL)
  const m = marque()
  const date = isoDansJours(10)
  const l = await lireJson(await c.ctx.post(`${API}/crm/leads/`, { ...T, data: { nom: `ACVI25 ${m}`, telephone: telephoneMobileUnique(), relance_date: date } }), 'POST')
  const r = await relu(c.ctx, l.id)
  expect(r.relance_date, 'la relance saisie survit au démarrage de la cadence').toBe(date)
  const sh = await py(`from apps.crm.models import Lead; sortie(Lead.objects.get(pk=${l.id}).saisies_humaines)`)
  const cles = Array.isArray(sh) ? sh : Object.keys(sh)
  for (const champ of ['nom', 'telephone', 'relance_date']) expect(cles, `${champ} marqué`).toContain(champ)
  for (const champ of ['owner', 'company']) expect(cles, `${champ} non marqué`).not.toContain(champ)
})

// ── ACVI33 — fusion : l'étape la plus avancée, annoncée dans l'aperçu ──────────────────────────
etape('PA1.08.fusion_etape', ['ACVI33'], async ({ page }) => {
  const m = marque()
  const { a, b } = await doublonsMemeNumero(`ACVI33 ${m} A`, `ACVI33 ${m} B`)
  await py(`from apps.crm.models import Lead; Lead.objects.filter(pk=${a}).update(stage='SIGNED'); sortie(1)`)
  const doublons = await lireJson(await page.request.get(`${API}/crm/leads/doublons/`, T), 'doublons')
  const groupeAB = listeDe(doublons).find((g) => JSON.stringify(g).includes(`ACVI33 ${m} A`))
  expect(groupeAB, 'groupe de doublons servi').toBeTruthy()
  expect(groupeAB.merge_preview?.stage_apres_fusion, 'aperçu').toBe('SIGNED')
  await lireJson(await page.request.post(`${API}/crm/leads/${b}/merge/`, { ...T, data: { others: [a] } }), 'fusion')
  expect((await relu(page.request, b)).stage, 'persistance : SIGNED').toBe('SIGNED')
})

// ── ACVI44 — WhatsApp refusé sur une touche annulée par le STOP ────────────────────────────────
etape('PA1.04.whatsapp_touche_annulee', ['ACVI44'], async ({ page }) => {
  const m = marque()
  const l = await nouveauLead(page.request, `ACVI44 ${m}`)
  const t1 = (await touches(page.request, l.id)).find((x) => x.statut === 'a_faire')
  const t2 = await toucheWhatsapp(l.id, 91)
  await lireJson(await page.request.post(`${API}/crm/relance-etapes/${t1.id}/fait/`, { ...T, data: { reponse: 'ne_plus_contacter' } }), 'STOP')
  const lignes = (await historique(page.request, l.id)).length
  const r = await page.request.post(`${API}/crm/relance-etapes/${t2}/whatsapp/`, { ...T, data: {} })
  expect(r.status(), 'touche annulée : 409').toBe(409)
  expect((await r.text()).toLowerCase(), 'nomme l\'opposition').toMatch(/oppos|ne plus (me )?contacter/)
  expect((await historique(page.request, l.id)).length, '0 activité').toBe(lignes)
  const relue = (await touches(page.request, l.id)).find((x) => x.id === t2)
  expect(relue.statut, 'persistance : annulée').toBe('annulee')
})

// ── ACVI50 — le numéro joignable choisit le wa_url ─────────────────────────────────────────────
etape('PA1.04.numero_joignable', ['ACVI50'], async ({ page }) => {
  const m = marque()
  const tel = telephoneMobileUnique()
  const l = await nouveauLead(page.request, `ACVI50 ${m}`, { telephone: tel })
  await py(`from apps.crm.models import Lead
Lead.objects.filter(pk=${l.id}).update(whatsapp='12'); sortie(1)`)
  const t = await toucheWhatsapp(l.id, 92, ", template_cle='identite'")
  const r = await lireJson(await page.request.post(`${API}/crm/relance-etapes/${t}/whatsapp/`, { ...T, data: {} }), 'whatsapp')
  expect(r.wa_url, 'wa_url sur le téléphone').toContain(`https://wa.me/${tel.replace(/\D/g, '')}`)
})

// ── ACVI58 — visite terminée gelée : mesures, photos, hors-ligne ───────────────────────────────
etape('PA1.07.visite_terminee_gelee', ['ACVI58'], async ({ page }) => {
  const m = marque()
  const l = await nouveauLead(page.request, `ACVI58 ${m}`)
  const id = await visiteTerminee(page.request, l.id)
  const avant = await visiteRelue(page.request, id)
  const media = avant.checklist.flatMap((b) => b.slots).flatMap((x) => x.photos)[0]?.id
  expect(media, 'une photo à retirer').toBeTruthy()
  const pm = await page.request.patch(`${V}/${id}/mesures/`, { ...T, data: { categorie: 'toiture', valeurs: { longueur_m: 99 } } })
  expect(pm.status(), 'PATCH mesures').toBe(400)
  expect(await pm.json(), 'nomme statut').toHaveProperty('statut')
  const pp = await page.request.post(`${V}/${id}/photos/`, { ...T, multipart: { slot_code: 'toiture_vue_generale', fichier: { name: 'x.png', mimeType: 'image/png', buffer: PNG_1PX } } })
  expect(pp.status(), 'POST photo').toBe(400)
  const pd = await page.request.delete(`${V}/${id}/photos/${media}/`, T)
  expect(pd.status(), 'DELETE photo').toBe(400)
  await py(`from authentication.models import Company
from apps.visites import services as vs
try:
    vs.appliquer_mesures_hors_ligne(Company.objects.get(pk=1), U.objects.get(username='demo_admin'), ${id}, 'toiture', {'longueur_m': 77})
except Exception:
    pass
sortie(1)`)
  const apres = await visiteRelue(page.request, id)
  expect(apres.mesures.toiture.longueur_m, 'persistance : mesure identique, rejeu hors-ligne compris').toBe(avant.mesures.toiture.longueur_m)
  expect(apres.checklist.flatMap((b) => b.slots).flatMap((x) => x.photos).map((x) => x.id), 'médias identiques').toEqual(avant.checklist.flatMap((b) => b.slots).flatMap((x) => x.photos).map((x) => x.id))
  // `a_refaire` : accepté (le gel ne vaut que pour une visite terminée).
  await lireJson(await page.request.post(`${V}/${id}/renvoyer/`, { ...T, data: { photos: [], mesures: [], motif: 'Reprendre la longueur.' } }), 'renvoyer')
  const ok = await page.request.patch(`${V}/${id}/mesures/`, { ...T, data: { categorie: 'toiture', valeurs: { longueur_m: 13 } } })
  expect(ok.status(), 'a_refaire : accepté').toBe(200)
})

// ── ACVI55 — le retour terrain ne cite jamais la note de planification ─────────────────────────
etape('PA1.06.retour_terrain', ['ACVI55'], async ({ page }) => {
  const m = marque()
  const l = await nouveauLead(page.request, `ACVI55 ${m}`)
  await lireJson(await page.request.post(`${API}/crm/leads/${l.id}/visites/planifier/`, { ...T, data: { date_prevue: isoDansJours(3), notes: 'Sonner au portail' } }), 'planifier')
  const id = listeDe(await lireJson(await page.request.get(`${V}/?lead=${l.id}`, T), 'visites'))[0].id
  await remplir(page.request, id)
  await lireJson(await page.request.patch(`${V}/${id}/`, { ...T, data: { retour_terrain: 'Tableau saturé' } }), 'retour saisi')
  await lireJson(await page.request.post(`${V}/${id}/terminer/`, { ...T, data: {} }), 'terminer')
  const lignes = (await historique(page.request, l.id)).map((x) => x.body || '')
  expect(lignes.some((b) => b.includes('Tableau saturé')), `la note cite le retour ${JSON.stringify(lignes)}`).toBe(true)
  expect(lignes.filter((b) => /retour/i.test(b) && b.includes('Sonner au portail')), 'jamais la note de planification').toEqual([])
  const v = await visiteRelue(page.request, id)
  expect([v.retour_terrain, v.notes], 'persistance').toEqual(['Tableau saturé', 'Sonner au portail'])
})

// ── ACVI56 — booléens de mesure tri-état ───────────────────────────────────────────────────────
etape('PA1.06.booleens_tri_etat', ['ACVI56'], async ({ page }) => {
  const { payloadDepuisForm, formDepuisValeurs, schemaMesures } = await import('../../src/pages/visites/visiteHelpers.js')
  const schema = schemaMesures('local_onduleur', 'toiture')
  const vierge = payloadDepuisForm(schema, formDepuisValeurs(schema, {}))
  expect([vierge.local_abrite, vierge.local_ventile], 'formulaire vierge : null').toEqual([null, null])
  const m = marque()
  const l = await nouveauLead(page.request, `ACVI56 ${m}`)
  const cree = await lireJson(await page.request.post(`${V}/`, { ...T, data: { lead: l.id } }), 'visite')
  await remplir(page.request, cree.id)
  await lireJson(await page.request.patch(`${V}/${cree.id}/mesures/`, { ...T, data: { categorie: 'local_onduleur', valeurs: { ...MESURES.local_onduleur, local_abrite: vierge.local_abrite, local_ventile: vierge.local_ventile } } }), 'enregistré sans toucher')
  const relue = await visiteRelue(page.request, cree.id)
  expect(relue.mesures.local_onduleur.local_abrite, 'persistance : null').toBeNull()
  expect(JSON.stringify(relue.completude.manquants), 'cité dans les manquants').toContain('local_abrite')
  expect(JSON.stringify(relue.completude.manquants)).toContain('local_ventile')
  const refus = await page.request.post(`${V}/${cree.id}/terminer/`, { ...T, data: {} })
  expect(refus.status(), 'terminer refusé tant que non répondu').toBe(409)
  await lireJson(await page.request.patch(`${V}/${cree.id}/mesures/`, { ...T, data: { categorie: 'local_onduleur', valeurs: MESURES.local_onduleur } }), 'répondu')
  expect((await visiteRelue(page.request, cree.id)).completude.complet, 'répondu : complet').toBe(true)
})

// ── Visite C&I complète (mesures du contrat `visite_terrain.json`) ─────────────────────────────
async function visiteCiTerminee(ctx, leadId, tech) {
  const base = mesuresContratVisite('exemple_ci')
  const commerce = mesuresContratVisite('exemple_ci_commerce')
  const cree = await lireJson(await ctx.post(`${V}/`, { ...T, data: { lead: leadId, date_prevue: isoDansJours(1), commercial: tech } }), 'visite C&I')
  const z1 = base.toiture_ci.zones_toiture[0]
  const cle = 'zones_toiture[z1].charge_admissible_declaree_kg_m2'
  const v = await remplirVisiteCi(ctx, cree.id, {
    ...base,
    site_commerce: commerce.site_commerce,
    comptage: { ...base.comptage, niveau_tension_constate: 'bt', puissance_souscrite_kva_constatee: 36 },
    toiture_ci: { zones_toiture: [z1], _non_releves: { [cle]: 'non_applicable' } },
  })
  expect(v.completude.manquants, 'rien ne manque').toEqual([])
  await lireJson(await ctx.post(`${V}/${cree.id}/terminer/`, { ...T, data: {} }), 'terminer')
  return cree.id
}
const leadCi = async (request, nom) => nouveauLead(request, nom, { type_installation: 'commercial' })

// ── ACVI61 — re-terminer après renvoi : idempotent côté lead ───────────────────────────────────
etape('PA1.07.reterminer_idempotent', ['ACVI61'], async ({ page }) => {
  const m = marque()
  const l = await leadCi(page.request, `ACVI61 ${m}`)
  const techId = await py(`sortie(U.objects.get(username='demo_tech').id)`)
  const id = await visiteCiTerminee(page.request, l.id, techId)
  await lireJson(await page.request.post(`${V}/${id}/valider/`, { ...T, data: {} }), 'valider')
  // « touche devis du 1er retour `fait` » : le commercial l'a traitée (état posé, la réponse n'est pas le sujet).
  await py(`from apps.crm.models_cadence import RelanceEtape
RelanceEtape.objects.filter(lead_id=${l.id}, statut='a_faire').update(statut='fait', traite_le=timezone.now()); sortie(1)`)
  await lireJson(await page.request.post(`${V}/${id}/renvoyer/`, { ...T, data: { photos: [], mesures: [], motif: 'Refaire le comptage' } }), 'renvoyer')
  const compter = async () => py(`from apps.notifications.models import Notification
from apps.crm.models import LeadActivity
from apps.crm.models_cadence import RelanceEtape
sortie(dict(valider=Notification.objects.filter(company_id=1, event_type='visite_terrain_a_valider').count(), retour=Notification.objects.filter(company_id=1, event_type='visite_retour_terrain').count(), devis=RelanceEtape.objects.filter(lead_id=${l.id}, statut='a_faire', libelle__icontains='devis').count(), note=LeadActivity.objects.filter(lead_id=${l.id}, body__icontains='de nouveau après renvoi').count()))`)
  const avant = await compter()
  await lireJson(await page.request.post(`${V}/${id}/terminer/`, { ...T, data: {} }), 're-terminer')
  const apres = await compter()
  expect(apres.valider - avant.valider, 'bureau d\'études re-notifié').toBeGreaterThanOrEqual(1)
  expect(apres.retour - avant.retour, 'visite_retour_terrain +0').toBe(0)
  expect(apres.devis - avant.devis, 'aucune touche devis nouvelle').toBe(0)
  expect(apres.note - avant.note, 'une note').toBe(1)
  expect(await compter(), 'persistance : 2e lecture identique').toEqual(apres)
})

// ── ACVI62 — une colonne corrigée par un humain survit à la revalidation ───────────────────────
etape('PA1.07.correction_humaine_survit', ['ACVI62'], async ({ page }) => {
  const m = marque()
  const l = await leadCi(page.request, `ACVI62 ${m}`)
  const techId = await py(`sortie(U.objects.get(username='demo_tech').id)`)
  const id = await visiteCiTerminee(page.request, l.id, techId)
  await lireJson(await page.request.post(`${V}/${id}/valider/`, { ...T, data: {} }), 'valider')
  const fv = await relu(page.request, l.id)
  expect([Number(fv.compteur_puissance_kva), fv.puissance_souscrite_source], '1er feu vert : la mesure remplace').toEqual([36, 'mesure_visite'])
  await lireJson(await page.request.patch(`${API}/crm/leads/${l.id}/`, { ...T, data: { compteur_puissance_kva: '30' } }), 'correction humaine')
  await lireJson(await page.request.post(`${V}/${id}/renvoyer/`, { ...T, data: { photos: [], mesures: [], motif: 'Refaire' } }), 'renvoyer')
  await lireJson(await page.request.post(`${V}/${id}/terminer/`, { ...T, data: {} }), 'terminer')
  await lireJson(await page.request.post(`${V}/${id}/valider/`, { ...T, data: {} }), 'revalider')
  const r = await relu(page.request, l.id)
  expect([Number(r.compteur_puissance_kva), r.puissance_souscrite_source], 'persistance : 30, déclaré').toEqual([30, 'declare'])
  expect((await historique(page.request, l.id)).filter((x) => /non recopi/i.test(x.body || '')).length, 'une ligne « non recopié »').toBe(1)
})

// ── ACVI66 — visite annulée : état visible et gelé ─────────────────────────────────────────────
etape('PA1.05.visite_annulee', ['ACVI66'], async ({ page }) => {
  const m = marque()
  const l = await nouveauLead(page.request, `ACVI66 ${m}`)
  const date = isoDansJours(3)
  await lireJson(await page.request.post(`${API}/crm/leads/${l.id}/visites/planifier/`, { ...T, data: { date_prevue: date, notes: 'Note de planification' } }), 'planifier')
  const id = listeDe(await lireJson(await page.request.get(`${V}/?lead=${l.id}`, T), 'visites'))[0].id
  const t = (await touches(page.request, l.id)).find((x) => x.statut === 'a_faire')
  expect(t, 'une touche ouverte').toBeTruthy()
  await lireJson(await page.request.post(`${API}/crm/relance-etapes/${t.id}/fait/`, { ...T, data: { reponse: 'visite_abandonnee' } }), 'visite abandonnée')
  const v = await visiteRelue(page.request, id)
  expect(v.statut, 'annulée').toBe('annulee')
  // SUIVI E4 : la date quitte `date_prevue` et reste dans la ligne ajoutée aux notes ; une 2e lecture est identique.
  const [y, mo, j] = date.split('-')
  expect(v.date_prevue, 'date vidée (SUIVI E4)').toBeNull()
  expect(v.notes, 'note initiale gardée').toContain('Note de planification')
  expect(v.notes, 'la date reste lisible').toContain(`Rendez-vous du ${j}/${mo}/${y} annulé`)
  const bis = await visiteRelue(page.request, id)
  expect([bis.statut, bis.date_prevue, bis.notes], 'persistance').toEqual([v.statut, v.date_prevue, v.notes])
  const refus = await page.request.post(`${V}/${id}/terminer/`, { ...T, data: {} })
  expect(refus.status(), 'terminer refusé').toBe(400)
  expect((await refus.json()).erreurs?.statut, 'nomme statut').toContain('annulée')
  expect((await relu(page.request, l.id)).visite_effectuee, 'visite_effectuee reste faux').toBe(false)
})

// ── ACVI93 — la vraie cause d'un refus d'état, à l'écran ───────────────────────────────────────
etape('PA1.07.refus_valider_ecran', ['ACVI93'], async ({ page, suivi }) => {
  const m = marque()
  const l = await nouveauLead(page.request, `ACVI93 ${m}`)
  const id = await visiteTerminee(page.request, l.id)
  // Le gel interdit de retirer une photo d'une visite terminée (ACVI58) : seul le shell pose « redevenue incomplète ».
  await py(`from apps.visites.models import VisiteMedia
VisiteMedia.objects.filter(visite_id=${id}).first().delete(); sortie(1)`)
  suivi.attendre(new RegExp(`/visites/visites/${id}/valider/`), 409)
  await page.goto('/visites/revue')
  await page.getByText(`ACVI93 ${m}`).first().click({ timeout: 60_000 })
  const [rep] = await Promise.all([
    page.waitForResponse((r) => r.url().includes(`/visites/visites/${id}/valider/`), T),
    page.getByRole('button', { name: 'Valider (feu vert)' }).click(),
  ])
  expect(rep.status(), 'refus').toBe(409)
  const corps = await rep.json()
  expect(corps.detail, 'detail = message').toBe(corps.message)
  await expect(page.getByText(corps.message).first(), 'toast = message').toBeVisible()
  await expect(page.getByTestId('visite-refus-manquants').locator('li').first(), 'libellé manquant sous le bouton').toHaveText(corps.manquants[0].libelle)
  await expect(page.getByText('vérifiez votre connexion')).toHaveCount(0)
  await expect(page.getByText('[object Object]')).toHaveCount(0)
  // Kanban : un lead perdu entre-temps et glissé ⇒ bandeau = detail.
  const nom = `ACVI93K ${m}`
  const k = await nouveauLead(page.request, nom)
  await page.goto(`/crm/leads?view=kanban&q=${encodeURIComponent(nom)}`)
  const carte = page.locator(`[data-lead-id="${k.id}"]`)
  await expect(carte).toBeVisible({ timeout: 60_000 })
  await lireJson(await page.request.patch(`${API}/crm/leads/${k.id}/`, { ...T, data: { perdu: true, motif_perte: 'Budget' } }), 'perdu entre-temps')
  suivi.attendre(new RegExp(`/crm/leads/${k.id}/`), 409)
  const a = await carte.boundingBox()
  const colonne = page.locator('[aria-label^="Étape Contacté"]').first()
  const b = await colonne.boundingBox()
  await page.mouse.move(a.x + a.width / 2, a.y + a.height / 2)
  await page.mouse.down()
  await page.mouse.move(a.x + a.width / 2 + 15, a.y + a.height / 2 + 5, { steps: 4 })
  await page.mouse.move(b.x + b.width / 2, b.y + 60, { steps: 12 })
  const [r2] = await Promise.all([
    page.waitForResponse((r) => r.url().includes(`/crm/leads/${k.id}/`) && r.request().method() === 'PATCH', T),
    page.mouse.up(),
  ])
  expect(r2.status(), 'lead perdu glissé').toBe(409)
  await expect(page.getByText((await r2.json()).detail).first(), 'bandeau = detail').toBeVisible()
})

// ── ACVI96 — questionnaire public fermé sur une fiche close, re-lié au survivant ───────────────
etape('PA1.02.questionnaire_fiche_close', ['ACVI96'], async ({ page, testInfo }) => {
  const m = marque()
  const lien = async (id) => lireJson(await page.request.post(`${API}/crm/leads/${id}/questionnaire-lien/`, { ...T, data: {} }), 'lien')
  const jeton = (x) => (x.token || x.url.split('/').filter(Boolean).pop())
  const pub = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  const q = (t) => `${API}/crm/public/questionnaire/${t}/`
  const section = { section: 'energie', reponses: { facture_hiver: 1500 } }
  const { a, b } = await doublonsMemeNumero(`ACVI96 ${m} A`, `ACVI96 ${m} B`)
  const p = await nouveauLead(page.request, `ACVI96 ${m} P`)
  const o = await nouveauLead(page.request, `ACVI96 ${m} O`)
  const w = await nouveauLead(page.request, `ACVI96 ${m} Témoin`)
  const ta = jeton(await lien(a))
  const tp = jeton(await lien(p.id))
  const to = jeton(await lien(o.id))
  const tw = jeton(await lien(w.id))
  // Témoin : un lead vivant répond 200 et écrit.
  expect((await pub.get(q(tw), T)).status(), 'témoin GET').toBe(200)
  const postT = await pub.post(q(tw), { ...T, data: section })
  expect(postT.status(), await postT.text()).toBe(200)
  expect(Number((await relu(page.request, w.id)).facture_hiver), 'témoin écrit').toBe(1500)
  await lireJson(await page.request.post(`${API}/crm/leads/${b}/merge/`, { ...T, data: { others: [a] } }), 'fusion')
  await lireJson(await page.request.patch(`${API}/crm/leads/${p.id}/`, { ...T, data: { perdu: true, motif_perte: 'Budget' } }), 'perdu')
  await lireJson(await page.request.patch(`${API}/crm/leads/${o.id}/`, { ...T, data: { ne_plus_contacter: true } }), 'opposé')
  for (const [qui, t, id] of [['perdu', tp, p.id], ['opposé', to, o.id]]) {
    const lignes = (await historique(page.request, id)).length
    expect((await pub.get(q(t), T)).status(), `${qui} GET`).toBe(404)
    expect((await pub.post(q(t), { ...T, data: section })).status(), `${qui} POST`).toBe(404)
    expect((await relu(page.request, id)).facture_hiver, `${qui} : aucune écriture`).toBeFalsy()
    expect((await historique(page.request, id)).length, `${qui} : 0 activité`).toBe(lignes)
  }
  expect((await pub.get(q(ta), T)).status(), 'absorbé GET : le lien vit, re-lié').toBe(200)
  const postA = await pub.post(q(ta), { ...T, data: section })
  expect(postA.status(), await postA.text()).toBe(200)
  expect(Number((await relu(page.request, b)).facture_hiver), 'les réponses écrivent le survivant').toBe(1500)
  await pub.dispose()
})

// ── ACVI67 — « Renvoyer » sur une visite validée, depuis la revue ──────────────────────────────
etape('PA1.07.renvoyer_validee_ecran', ['ACVI67'], async ({ page }) => {
  const m = marque()
  const l = await nouveauLead(page.request, `ACVI67 ${m}`)
  const id = await visiteTerminee(page.request, l.id)
  await lireJson(await page.request.post(`${V}/${id}/valider/`, { ...T, data: {} }), 'valider')
  await page.goto('/visites/revue')
  await page.getByText(`ACVI67 ${m}`).first().click({ timeout: 60_000 })
  await expect(page.getByRole('button', { name: 'Renvoyer', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Valider (feu vert)' }), 'aucun « Valider » sur une validée').toHaveCount(0)
  await page.getByRole('button', { name: 'Renvoyer', exact: true }).click()
  const dlg = page.getByRole('dialog')
  await dlg.getByRole('checkbox').first().check()
  await dlg.getByRole('textbox').first().fill('Validée par erreur')
  const [rep] = await Promise.all([
    page.waitForResponse((r) => r.url().includes(`/visites/visites/${id}/renvoyer/`), T),
    dlg.getByRole('button', { name: /Renvoyer/ }).last().click(),
  ])
  expect(rep.status(), await rep.text()).toBe(200)
  expect(rep.request().postDataJSON().motif).toBe('Validée par erreur')
  expect((await visiteRelue(page.request, id)).statut, 'persistance : rouverte').toBe('a_refaire')
})

// ── ACVI16 — le réveil du doublon perdu : une seule cadence ouverte pour la personne ───────────
etape('PA1.03.reveil_avant_cadence', ['ACVI16'], async ({ page, testInfo }) => {
  const m = marque()
  const tel = telephoneMobileUnique()
  const p = await nouveauLead(page.request, `ACVI16 ${m} P`, { telephone: tel })
  const t = (await touches(page.request, p.id)).find((x) => x.statut === 'a_faire')
  await lireJson(await page.request.post(`${API}/crm/relance-etapes/${t.id}/fait/`, { ...T, data: { outcome: 'joint', note: 'rejeu ACVI16' } }), 'appel joint')
  await lireJson(await page.request.patch(`${API}/crm/leads/${p.id}/`, { ...T, data: { perdu: true, motif_perte: 'Budget' } }), 'perdu')
  await py(`from apps.crm.models import Lead; Lead.objects.filter(pk=${p.id}).update(stage='COLD'); sortie(1)`)
  const r = await webhookSite(testInfo, { fullName: `ACVI16 ${m} N`, phoneE164: tel, city: 'Casablanca' })
  expect([200, 201], JSON.stringify(r.corps)).toContain(r.statut)
  const nid = r.corps.lead_id
  const ouvertes = async (id) => (await touches(page.request, id)).filter((x) => x.statut === 'a_faire')
  expect((await ouvertes(p.id)).map((x) => x.cadence), 'P réveillé (cadence reveil)').toContain('reveil')
  expect(nid, 'un lead distinct pour la nouvelle demande').not.toBe(p.id)
  expect((await ouvertes(nid)).filter((x) => x.cadence === 'contact'), 'nouveau lead : 0 touche contact').toEqual([])
  expect(JSON.stringify(await historique(page.request, nid)), 'refus tracé').toContain(`doublon possible de #${p.id}`)
  // Témoin : sans doublon, le lead du site a sa cadence.
  const sans = await webhookSite(testInfo, { fullName: `ACVI16 ${m} Sans`, phoneE164: telephoneMobileUnique(), city: 'Casablanca' })
  expect((await ouvertes(sans.corps.lead_id)).filter((x) => x.cadence === 'contact').length, 'témoin : cadence contact').toBeGreaterThan(0)
})

// ── ACVI27 — un PATCH rend joignable : la cadence repart, ou le refus est tracé ────────────────
etape('PA1.03.patch_numero_cadence', ['ACVI27'], async ({ page }) => {
  const m = marque()
  const ouvertes = async (id) => (await touches(page.request, id)).filter((x) => x.statut === 'a_faire')
  const y = await lireJson(await page.request.post(`${API}/crm/leads/`, { ...T, data: { nom: `ACVI27 ${m} Y` } }), 'sans numéro')
  expect(await ouvertes(y.id), 'sans numéro : 0 touche').toEqual([])
  expect(JSON.stringify(await historique(page.request, y.id)), 'refus « sans numéro » tracé').toContain('aucun numéro exploitable')
  await lireJson(await page.request.patch(`${API}/crm/leads/${y.id}/`, { ...T, data: { telephone: telephoneMobileUnique() } }), 'PATCH numéro')
  const poses = await ouvertes(y.id)
  expect(poses.length, 'touche contact posée').toBeGreaterThan(0)
  expect(poses.every((x) => x.cadence === 'contact')).toBe(true)
  // Numéro d'un doublon vivant : refus tracé, 0 touche.
  const vivant = await nouveauLead(page.request, `ACVI27 ${m} Vivant`)
  const z = await lireJson(await page.request.post(`${API}/crm/leads/`, { ...T, data: { nom: `ACVI27 ${m} Z` } }), 'sans numéro')
  await lireJson(await page.request.patch(`${API}/crm/leads/${z.id}/`, { ...T, data: { telephone: vivant.telephone } }), 'PATCH numéro doublon')
  expect(await ouvertes(z.id), 'doublon : 0 touche').toEqual([])
  expect(JSON.stringify(await historique(page.request, z.id)), 'refus nommé').toContain(`doublon possible de #${vivant.id}`)
})

// ── ACVI79 — KPI premier contact : requêtes indépendantes du nombre de leads ───────────────────
etape('PA1.02.kpi_premier_contact_requetes', ['ACVI79'], async () => {
  const r = await py(`from apps.crm.models import Lead
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
c = APIClient(); c.force_authenticate(U.objects.get(username='demo_admin'))
def mesure():
    with CaptureQueriesContext(connection) as q:
        rep = c.get('/api/django/crm/leads/kpi-premier-contact/?jours=30', HTTP_HOST='localhost')
    return rep.status_code, len(q)
def poser(n):
    for i in range(n):
        l = Lead.objects.create(company_id=1, nom='ACVI79 %d' % i, canal=Lead.Canal.AUTRE)
        Lead.objects.filter(pk=l.pk).update(date_creation=timezone.now() - datetime.timedelta(days=5), first_contacted_at=timezone.now() - datetime.timedelta(days=3))
res = {}
try:
    with transaction.atomic():
        poser(3); mesure(); res['a'] = mesure()
        poser(6); res['b'] = mesure()
        raise KeyError('rollback')
except KeyError:
    pass
sortie(res)`)
  expect(r.a[0], 'HTTP').toBe(200)
  expect(r.b[1], `même nombre de requêtes (${r.a[1]} / ${r.b[1]})`).toBe(r.a[1])
})

// ── ACVI84 — bilan hebdomadaire idempotent par semaine ISO ─────────────────────────────────────
etape('PA1.bilan_hebdo_idempotent', ['ACVI84'], async () => {
  // Beat hors parcours HTTP : la fonction réelle, tout annulé à la fin (aucune notification ne reste).
  const r = await py(`from apps.crm.management.commands.bilan_hebdo_relances import bilan_hebdo_relances
from apps.notifications.models import Notification
from django.db import transaction
compter = lambda: Notification.objects.filter(company_id=1, event_type='crm_bilan_hebdo').count()
res = {}
try:
    with transaction.atomic():
        bilan_hebdo_relances(dry_run=True); res['dry0'] = compter()
        bilan_hebdo_relances(); res['un'] = compter()
        bilan_hebdo_relances(); res['deux'] = compter()
        semaine = timezone.now() + datetime.timedelta(days=7)
        with mock.patch('django.utils.timezone.now', return_value=semaine):
            bilan_hebdo_relances()
        res['suivante'] = compter()
        raise KeyError('rollback')
except KeyError:
    pass
sortie(res)`)
  expect(r.un, `1re exécution ${JSON.stringify(r)}`).toBeGreaterThanOrEqual(r.dry0)
  expect(r.un, 'une notification de la semaine').toBeGreaterThanOrEqual(1)
  expect(r.deux, '2e exécution, même semaine : aucune de plus').toBe(r.un)
  expect(r.suivante, 'semaine suivante : une nouvelle').toBeGreaterThan(r.deux)
})

// ── ACVI49 — phrase de validité omise quand la validité est passée ─────────────────────────────
etape('PA1.04.j9_validite_passee', ['ACVI49'], async ({ page }) => {
  const m = marque()
  const l = await nouveauLead(page.request, `ACVI49 ${m}`)
  const prod = await lireJson(await page.request.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur ACVI49 ${m}`, prix_vente: '10000.00', prix_achat: '4321.09' } }), 'produit')
  const d = await lireJson(await page.request.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: l.id, lignes: [{ produit: prod.id, designation: 'Onduleur', quantite: '1', prix_unitaire: '10000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  await lireJson(await page.request.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  const passee = isoDansJours(-3)
  const t = await py(`from apps.ventes.models import Devis
from apps.crm.models_cadence import RelanceEtape
Devis.objects.filter(pk=${d.id}).update(date_validite='${passee}')
sortie(RelanceEtape.objects.create(company_id=1, lead_id=${l.id}, cadence='apres_devis', ordre=93, due_date=timezone.localdate(), due_at=timezone.now(), canal='whatsapp', libelle='J9', template_cle='j9_validite').id)`)
  const msg = await lireJson(await page.request.get(`${API}/crm/relance-etapes/${t}/message/`, T), 'message')
  const texte = JSON.stringify(msg)
  expect(texte, 'ni « valable jusqu\'au »').not.toContain('valable jusqu')
  const [y, mo, j] = passee.split('-')
  expect(texte, 'ni la date').not.toContain(`${j}/${mo}/${y}`)
  expect(msg.placeholders_manquants, 'placeholder manquant nommé').toContain('date_validite')
})

// ── ACVI71 — le PATCH d'une visite applique les gardes de planification ────────────────────────
etape('PA1.05.patch_visite_gardes', ['ACVI71'], async ({ page }) => {
  const m = marque()
  const l = await nouveauLead(page.request, `ACVI71 ${m}`)
  const ids = await py(`a = U.objects.get(username='demo_tech')
b = compte('acvi_inactif', role=6); b.is_active = False; b.save()
sortie(dict(a=a.id, b=b.id))`)
  const d1 = isoDansJours(5)
  const v = await lireJson(await page.request.post(`${V}/`, { ...T, data: { lead: l.id, date_prevue: d1, commercial: ids.a } }), 'visite')
  const refusPost = await page.request.post(`${V}/`, { ...T, data: { lead: (await nouveauLead(page.request, `ACVI71 ${m} P`)).id, date_prevue: d1, commercial: ids.b } })
  expect(refusPost.status(), 'POST : compte inactif').toBe(400)
  const msgPost = await refusPost.json()
  const refus = await page.request.patch(`${V}/${v.id}/`, { ...T, data: { commercial: ids.b } })
  expect(refus.status(), 'PATCH commercial inactif').toBe(400)
  expect((await refus.json()).commercial, 'même message que le POST').toEqual(msgPost.commercial)
  const d2 = isoDansJours(8)
  await lireJson(await page.request.patch(`${V}/${v.id}/`, { ...T, data: { date_prevue: d2 } }), 'déplacer')
  const relue = await visiteRelue(page.request, v.id)
  expect(relue.commercial.id, 'persistance : commercial').toBe(ids.a)
  expect(relue.date_prevue, 'persistance : date').toBe(d2)
  expect(relue.notes, 'ligne « déplacé au »').toMatch(/Rendez-vous du .* déplacé au /)
})

// ── ACVI23 — first_contacted_at : jamais sur un geste interne ──────────────────────────────────
etape('PA1.02.premier_contact_reel', ['ACVI23'], async ({ page }) => {
  const m = marque()
  const fca = (id) => py(`from apps.crm.models import Lead; sortie(str(Lead.objects.get(pk=${id}).first_contacted_at))`)
  const l = await nouveauLead(page.request, `ACVI23 ${m}`)
  const tpl = await lireJson(await page.request.post(`${API}/crm/message-templates/`, { ...T, data: { nom: `ACVI23 ${m}`, langue: 'fr', corps: 'Bonjour {prenom}.' } }), 'modèle')
  await lireJson(await page.request.post(`${API}/crm/leads/bulk/`, { ...T, data: { action: 'prepare_whatsapp', ids: [l.id], template_id: tpl.id } }), 'lot')
  expect(await fca(l.id), 'après le lot').toBe('None')
  await lireJson(await page.request.post(`${V}/`, { ...T, data: { lead: l.id } }), 'visite créée')
  expect(await fca(l.id), 'après « Visite technique créée »').toBe('None')
  const { a, b } = await doublonsMemeNumero(`ACVI23 ${m} A`, `ACVI23 ${m} B`)
  await lireJson(await page.request.post(`${API}/crm/leads/${b}/merge/`, { ...T, data: { others: [a] } }), 'fusion')
  expect(await fca(b), 'après fusion').toBe('None')
  const arch = await nouveauLead(page.request, `ACVI23 ${m} Arch`)
  await lireJson(await page.request.post(`${API}/crm/leads/${arch.id}/archiver/`, { ...T, data: {} }), 'archiver')
  expect(await fca(arch.id), 'après archivage').toBe('None')
  await lireJson(await page.request.post(`${API}/crm/leads/${l.id}/noter/`, { ...T, data: { body: 'Appelé, pas de réponse' } }), 'note d\'appel')
  expect(await fca(l.id), 'note d\'un vrai contact : horodatée').not.toBe('None')
})

// ── ACVI69 — chaque écriture automatique de visite_prevue_le est tracée ────────────────────────
etape('PA1.05.visite_prevue_tracee', ['ACVI69'], async ({ page }) => {
  const m = marque()
  const l = await nouveauLead(page.request, `ACVI69 ${m}`)
  const main = isoDansJours(30)
  const planif = isoDansJours(5)
  await lireJson(await page.request.patch(`${API}/crm/leads/${l.id}/`, { ...T, data: { visite_prevue_le: main } }), 'date à la main')
  await lireJson(await page.request.post(`${V}/`, { ...T, data: { lead: l.id, date_prevue: planif } }), 'planifier')
  await lireJson(await page.request.patch(`${API}/crm/leads/${l.id}/`, { ...T, data: { perdu: true, motif_perte: 'Budget' } }), 'perdu')
  const h = (await historique(page.request, l.id)).filter((x) => x.field === 'visite_prevue_le')
  const dernieres = h.slice().sort((x, y) => x.id - y.id).slice(-2)
  expect(dernieres.length, `2 lignes ${JSON.stringify(h)}`).toBe(2)
  const txt = JSON.stringify(dernieres)
  expect(txt, 'ligne 1 : ancienne date').toContain(main)
  expect(txt, 'ligne 2 : date planifiée').toContain(planif)
  const rel = await py(`from apps.crm.models import Lead; x = Lead.objects.get(pk=${l.id}); sortie(dict(s=x.saisies_humaines, v=str(x.visite_prevue_le)))`)
  expect(rel.v, 'persistance : vide').toBe('None')
  expect(Array.isArray(rel.s) ? rel.s : Object.keys(rel.s), 'sort de saisies_humaines').not.toContain('visite_prevue_le')
})

// ── ACVI14 — un compte désactivé n'est jamais attribué ─────────────────────────────────────────
etape('PA1.01.compte_inactif_owner', ['ACVI14'], async ({ page }) => {
  const m = marque()
  const inactif = await py(`b = compte('acvi_inactif', role=6); b.is_active = False; b.save(); sortie(b.id)`)
  const l = await nouveauLead(page.request, `ACVI14 ${m}`)
  const avant = l.owner
  const refus = await page.request.patch(`${API}/crm/leads/${l.id}/`, { ...T, data: { owner: inactif } })
  expect(refus.status(), 'PATCH owner inactif').toBe(400)
  expect((await refus.json()).owner, 'nomme owner').toEqual(['Utilisateur inactif.'])
  const lot = await lireJson(await page.request.post(`${API}/crm/leads/bulk/`, { ...T, data: { action: 'reassign', ids: [l.id], owner: inactif } }), 'lot reassign')
  expect(JSON.stringify(lot), 'lot : sauté').toContain('Responsable inactif')
  expect((await relu(page.request, l.id)).owner, 'persistance : owner inchangé').toBe(avant)
  const r = await py(`from apps.crm.leads_attribution import default_responsable_for
from apps.parametres.models import CompanyProfile
from authentication.models import Company
from django.db import transaction
co = Company.objects.get(pk=1)
res = {}
try:
    with transaction.atomic():
        CompanyProfile.objects.filter(company=co).update(responsable_defaut_leads_id=${inactif}, round_robin_leads_actif=False)
        d = default_responsable_for(co)
        res = dict(id=getattr(d, 'id', None), actif=getattr(d, 'is_active', None))
        raise KeyError('rollback')
except KeyError:
    pass
sortie(res)`)
  expect(r.id, 'le compte inactif ne reçoit rien').not.toBe(inactif)
  expect(r.actif, 'repli sur un commercial actif').toBe(true)
})

// ── ACVI68 — acceptation refusée : le dialogue « Signé » revient pré-rempli ────────────────────
etape('PA3.signe_refus_prerempli', ['ACVI68'], async ({ page, suivi }) => {
  const m = marque()
  const nom = `ACVI68 ${m}`
  const l = await nouveauLead(page.request, nom)
  const prod = await lireJson(await page.request.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur ${nom}`, prix_vente: '10000.00', prix_achat: '4321.09' } }), 'produit')
  const d = await lireJson(await page.request.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: l.id, lignes: [{ produit: prod.id, designation: 'Onduleur', quantite: '1', prix_unitaire: '10000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  await lireJson(await page.request.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  // Refus injecté (seul moyen d'obtenir un 400 hors conflit sur une saisie valide à l'écran).
  const url = new RegExp(`/ventes/devis/${d.id}/accepter/`)
  suivi.attendre(url, 400)
  await page.route(url, (route) => route.fulfill({ status: 400, contentType: 'application/json', body: JSON.stringify({ nom: ['Obligatoire.'] }) }))
  await page.goto(`/crm/leads?view=kanban&q=${encodeURIComponent(nom)}`)
  const carte = page.locator(`[data-lead-id="${l.id}"]`)
  await expect(carte).toBeVisible({ timeout: 60_000 })
  const colonne = page.locator('[aria-label^="Étape Signé"]').first()
  const a = await carte.boundingBox()
  await page.mouse.move(a.x + a.width / 2, a.y + a.height / 2)
  await page.mouse.down()
  await page.mouse.move(a.x + a.width / 2 + 15, a.y + a.height / 2 + 5, { steps: 4 })
  await colonne.evaluate((el) => el.scrollIntoView({ inline: 'center', block: 'nearest' }))
  const b = await colonne.boundingBox()
  await page.mouse.move(b.x + b.width / 2, b.y + 60, { steps: 12 })
  await page.mouse.up()
  const champNom = page.locator('#sd-nom')
  await expect(champNom).toBeVisible({ timeout: 30_000 })
  await champNom.fill('Signataire Essai')
  const dateSaisie = await page.locator('#sd-date').inputValue()
  const [rep] = await Promise.all([
    page.waitForResponse((r) => url.test(r.url()), T),
    page.getByRole('button', { name: 'Confirmer l’acceptation' }).click(),
  ])
  expect(rep.status()).toBe(400)
  await expect(champNom, 'le dialogue revient, signataire pré-rempli').toHaveValue('Signataire Essai', { timeout: 30_000 })
  await expect(page.locator('#sd-date'), 'date pré-remplie').toHaveValue(dateSaisie)
  await expect(page.locator('.form-error').filter({ hasText: 'Obligatoire.' }), 'erreur sous le signataire').toBeVisible()
  expect((await lireJson(await page.request.get(`${API}/ventes/devis/${d.id}/`, T), 'devis relu')).statut, 'statut intact').toBe('envoye')
})
