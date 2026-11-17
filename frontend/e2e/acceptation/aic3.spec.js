// AIC — vague d'acceptation 8 (lane aic8, 17/11/2026) : preuves en direct AIC90 (plafond de dépense du jour par
// commercial ⇒ repli Groq, jamais d'arrêt), AIC91 + AIC101 (trois étapes du tour affichées avant la réponse, sur un
// téléphone à connexion bridée, rejouée TROIS fois pour la stabilité) et AIC102 (table `ia_ocr_document` absente ⇒
// jamais proposée au modèle, le Directeur reçoit une réponse). VRAI service IA FastAPI dans le job (vraie clé Claude,
// Groq en repli ; secrets du dépôt, jamais affichés), moteur et interrupteurs à leur défaut du merge ; le workflow pose
// `ASSISTANT_PLAFOND_JOUR_USD=0.01` (clause AIC90), `AGENT_HMAC_SECRET` (journal des tours : le coût du jour en dépend)
// et NE pose PAS `RUN_DB_DDL` (clause AIC102 : base sans `ia_ocr_document`). L'écran atteint le service sous
// `/api/fastapi/` comme derrière nginx (route Playwright → E2E_IA_URL, jeton de la session relayé en Bearer).
// Comptes d'essai NEUFS aux rôles SYSTÈME relus dans le registre livré, connectés PAR L'ÉCRAN : chaque compte part
// d'un coût du jour nul, donc sa première question est servie par Claude.
// Le modèle n'est pas déterministe : chaque étape affirme les invariants de la clause (étapes, événement journalisé,
// coût du jour, bandeau de budget, absence de l'erreur générique), jamais un texte libre du modèle.
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { join } from 'node:path'
import { groupe } from './_oracles.js'
import { RACINE } from './_enregistrement.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, telephoneMobileUnique, connexionApi, uiLoginJusquAuxApps } from '../helpers.js'

const etape = groupe('AIC', ['AIC90', 'AIC91', 'AIC101', 'AIC102'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
test.describe.configure({ timeout: 480_000 })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const SOC = `U.objects.get(username='demo_admin').company_id`
const TELEPHONE = { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true }
const ERREUR_GENERIQUE = 'Je n\'ai pas pu traiter votre demande'
const MESSAGE_BUDGET = 'Budget du jour de l\'assistant atteint : réponses par le modèle de secours jusqu\'à demain.'

// ── service IA réel (FastAPI du workflow), branché sous /api/fastapi comme nginx en prod ─────────────────────
const IA = process.env.E2E_IA_URL
const jetonDe = async (context) => (await context.cookies()).find((c) => c.name === 'access_token')?.value || ''
/** `bridee` : connexion bridée — chaque appel au service IA attend, à l'aller ET au retour, un aller-retour RÉEL du
 *  navigateur sur le réseau émulé par l'étape (CDP `Network.emulateNetworkConditions`) : `route.fetch` part du client
 *  HTTP de Playwright (Node), hors de ce réseau ; la latence vient donc de la connexion bridée elle-même. */
async function brancherIA(page, { bridee = false } = {}) {
  expect(IA, 'service IA lancé par le workflow (E2E_IA_URL)').toBeTruthy()
  const allerRetourBride = () => page.evaluate(() => fetch('/api/django/auth/me/', { cache: 'no-store', credentials: 'same-origin' })
    .then((x) => x.status)).catch(() => undefined)
  await page.route(/\/api\/fastapi\//, async (route) => {
    const req = route.request()
    const u = new URL(req.url())
    const headers = { ...req.headers() }
    delete headers.host; delete headers.cookie; delete headers['content-length']
    const jeton = await jetonDe(page.context())
    if (jeton) headers.authorization = `Bearer ${jeton}`
    try {
      if (bridee) await allerRetourBride()
      const rep = await route.fetch({ url: `${IA}${u.pathname.replace(/^\/api\/fastapi/, '')}${u.search}`, headers, timeout: 300_000, maxRedirects: 0 })
      if (bridee) await allerRetourBride()
      await route.fulfill({ response: rep })
    } catch {
      await route.abort().catch(() => undefined)
    }
  })
}
async function ouvrirAssistant(page) {
  const panneau = page.getByTestId('copilot-panel')
  if (await panneau.isVisible().catch(() => false)) return panneau
  const bouton = page.getByTestId('copilot-toggle')
  await expect(bouton, 'bouton Copilote de l\'en-tête').toBeAttached({ timeout: 60_000 })
  if (await bouton.isVisible().catch(() => false)) {
    await bouton.click()
  } else {
    // En-tête replié sur téléphone : l'événement d'ouverture que les écrans émettent (« Demander à l'assistant »).
    console.log('[AIC] bouton Copilote masqué : ouverture par l\'événement taqinor:assistant:ouvrir')
    await page.evaluate(() => window.dispatchEvent(new CustomEvent('taqinor:assistant:ouvrir', { detail: {} })))
  }
  await expect(panneau, 'tiroir Copilote ouvert').toBeVisible({ timeout: 30_000 })
  return panneau
}
/** Pose `question` dans le tiroir ; rend {panneau, corps, requete} (corps = JSON de `/sql-agent/query`). */
async function demander(page, question, { avantEnvoi } = {}) {
  const panneau = await ouvrirAssistant(page)
  const zone = panneau.getByPlaceholder('Posez votre question en français…')
  await expect(zone).toBeEnabled({ timeout: 60_000 })
  await zone.fill(question)
  if (avantEnvoi) await avantEnvoi()
  const rep = page.waitForResponse((r) => r.request().method() === 'POST' && /\/api\/fastapi\/sql-agent\/query$/.test(new URL(r.url()).pathname), { timeout: 300_000 })
  await panneau.getByRole('button', { name: 'Envoyer' }).click()
  const r = await rep
  const corps = await r.json().catch(() => ({}))
  expect(r.status(), `réponse de l'assistant : ${J(corps).slice(0, 400)}`).toBe(200)
  await expect(zone, 'tour terminé').toBeEnabled({ timeout: 60_000 })
  console.log(`[AIC] « ${question} » → moteur=${corps.moteur} evenement=${corps.evenement_id} cartes=${J((corps.cartes || []).map((c) => c.carte))} réponse=${J((corps.answer || '').slice(0, 400))}`)
  return { panneau, corps, requete: r.request().postDataJSON() || {} }
}
/** Première ligne non vide de la réponse servie, affichée dans le tiroir (l'écran est AFFIRMÉ, pas seulement ouvert). */
async function reponseAffichee(panneau, corps, qui) {
  // Premier segment de texte brut (hors syntaxe Markdown, rendue autrement à l'écran) d'au moins 12 caractères.
  const segment = (corps.answer || '').split(/[*_#`|>[\]()\n]/).map((x) => x.replace(/\s+/g, ' ').trim()).find((x) => x.length >= 12) || ''
  expect(segment, `${qui} : réponse non vide`).not.toBe('')
  await expect(panneau, `${qui} : réponse affichée dans le tiroir`).toContainText(segment.slice(0, 30))
}

/** Rôle SYSTÈME relu par son nom ; ses codes en base = ceux du registre livré. */
async function roleReel(nom) {
  const r = await py(`from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
r = Role.objects.get(company_id=${SOC}, nom=${J(nom)})
reg = set(dict(CANONICAL_SYSTEM_ROLES)[${J(nom)}])
sortie(dict(pk=r.pk, manque=sorted(reg - set(r.permissions)), plus=sorted(set(r.permissions) - reg)))`)
  expect([r.manque, r.plus], `rôle « ${nom} » en base = registre livré`).toEqual([[], []])
  return r.pk
}
const ouverts = []
/** Compte d'essai NEUF au rôle `nomRole`, connecté PAR L'ÉCRAN ; {p, ctx, id, username, copilote}. */
async function sous(context, suivi, testInfo, prefixe, nomRole, { telephone = false, ia = true } = {}) {
  const username = `${prefixe}_${marque()}`
  const id = await py(`u = compte(${J(username)}, role=${await roleReel(nomRole)}, societe=${SOC})
u.first_name = 'Salma'; u.save(update_fields=['first_name'])
from apps.agent.registry import copilote_allume_pour
sortie(dict(id=u.id, copilote=copilote_allume_pour(u)))`)
  const ctx = await context.browser().newContext({
    baseURL: testInfo.project.use.baseURL, serviceWorkers: 'block', storageState: { cookies: [], origins: [] }, ...(telephone ? TELEPHONE : {}),
  })
  ouverts.push({ ctx, username })
  const p = suivi.surveiller(await ctx.newPage())
  await p.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await uiLoginJusquAuxApps(p, { username, password: MDP_ESSAI })
  if (ia) await brancherIA(p)
  return { p, ctx, id: id.id, username, copilote: id.copilote, role: nomRole }
}
test.afterEach(async () => {
  for (const o of ouverts.splice(0)) {
    await o.ctx.close().catch(() => undefined)
    await py(`U.objects.filter(username=${J(o.username)}).update(is_active=False)
sortie(1)`).catch(() => null)
  }
})
/** Événements AssistantEvent de l'utilisateur, dans l'ordre (écrits par le relais, preuve HMAC). */
const evenementsDe = (userId) => py(`from apps.agent.models import AssistantEvent
sortie([dict(id=e.id, modele=e.modele, repli=e.repli, tokens=e.tokens, intention=e.intention, erreur=e.erreur)
        for e in AssistantEvent.objects.filter(user_id=${Number(userId)}).order_by('created_at', 'id')])`)
async function attendreEvenements(userId, n) {
  let evs = []
  await expect.poll(async () => { evs = await evenementsDe(userId); return evs.length }, { timeout: 30_000, message: `${n} événement(s) journalisé(s)` }).toBeGreaterThanOrEqual(n)
  return evs
}

/** Lead propre à l'étape, responsable = `ownerId`, avec téléphone WhatsApp ; + une touche WhatsApp à faire aujourd'hui. */
async function leadAvecTouche(ctx, ownerId, nom) {
  const lead = await lireJson(await ctx.post(`${API}/crm/leads/`, {
    ...T, data: { nom, prenom: 'Amal', ville: 'Casablanca', telephone: telephoneMobileUnique(), whatsapp: telephoneMobileUnique(), email: `aic-${marque()}@example.invalid` },
  }), 'lead')
  await py(`from apps.crm.models import Lead
from apps.crm.models_cadence import RelanceEtape
Lead.objects.filter(pk=${lead.id}).update(owner_id=${ownerId})
sortie(RelanceEtape.objects.create(company_id=${SOC}, lead_id=${lead.id}, cadence='contact', ordre=9, due_date=timezone.localdate(),
       due_at=timezone.now(), canal='whatsapp', template_cle='identite', libelle='Identité').id)`)
  return lead
}
const nettoyerLead = (id) => py(`from apps.crm.models import Lead
M = getattr(Lead, 'all_objects', Lead.objects)
try: M.filter(pk=${Number(id)}).delete()
except Exception as exc: print('nettoyage', exc)
sortie(1)`).catch(() => null)

// ═══ P7.1 — AIC91 + AIC101 : question à trois outils, téléphone à connexion bridée ⇒ trois étapes affichées avant la
//      réponse, toutes, dans l'ordre publié, sans qu'une étape disparaisse (rejouée trois fois : stabilité) ═══
async function progression({ page, context, suivi, testInfo }) {
  await page.close() // la capture d'étape prend le navigateur du téléphone, pas l'onglet vide du projet
  const m = marque()
  const a = await sous(context, suivi, testInfo, 'aic91', 'Administrateur', { telephone: true, ia: false })
  expect(a.copilote, 'copilote allumé pour un administrateur (réglage du merge ASSISTANT_COPILOTE=admins)').toBe(true)
  const api = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(api, { username: a.username, password: MDP_ESSAI })
  const nom = `Zerhouni${m}`
  const lead = await leadAvecTouche(api, a.id, nom)
  try {
    // Connexion bridée : réseau du navigateur ralenti (CDP) ; chaque appel IA routé paie un aller-retour sur ce réseau à l'aller et au retour.
    const cdp = await a.ctx.newCDPSession(a.p)
    await cdp.send('Network.enable')
    await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 400, downloadThroughput: 60 * 1024, uploadThroughput: 30 * 1024 })
    await brancherIA(a.p, { bridee: true })
    const sondages = []
    a.p.on('response', async (r) => {
      if (!/\/api\/fastapi\/sql-agent\/progression\//.test(new URL(r.url()).pathname)) return
      const c = await r.json().catch(() => null)
      if (c) sondages.push({ libelles: (c.etapes || []).map((e) => e.libelle), fini: c.fini })
    })
    await a.p.goto('/apps')
    // Collecteur DANS la page (MutationObserver, aucun minuteur) : à chaque changement du DOM, la LISTE des étapes
    // affichées sous la bulle d'attente est relevée ; une nouvelle liste différente de la précédente est empilée.
    const { corps, requete } = await demander(a.p,
      `Trois choses dans l'ordre, une à la fois : 1) retrouve le lead ${nom} ; 2) résume-moi sa fiche ; 3) prépare sa prochaine touche du suivi.`,
      {
        avantEnvoi: () => a.p.evaluate(() => {
          window.__listes = []
          const relever = () => {
            const l = [...document.querySelectorAll('[data-testid="etape-en-cours"]')].map((el) => (el.textContent || '').trim()).filter(Boolean)
            const der = window.__listes[window.__listes.length - 1]
            if (!der || JSON.stringify(der.l) !== JSON.stringify(l)) window.__listes.push({ l, at: Date.now() })
          }
          window.__obs = new MutationObserver(relever)
          window.__obs.observe(document.body, { childList: true, subtree: true, characterData: true })
          relever()
        }),
      })
    const listes = await a.p.evaluate(() => { window.__obs.disconnect(); return window.__listes })
    console.log(`[AIC91] listes affichées : ${J(listes)} ; sondages : ${J(sondages)}`)
    // Persistance : la clé Redis `assistant:progression:<utilisateur>:<id>` relue ⇒ les étapes dans l'ordre, fini.
    expect(requete.progression_id, 'identifiant de progression envoyé avec la question').toMatch(/^[A-Za-z0-9_-]{8,64}$/)
    const cle = `assistant:progression:${a.id}:${requete.progression_id}`
    const redis = await py(`import os, redis
r = redis.Redis(host=os.environ.get('REDIS_HOST', 'redis'), port=int(os.environ.get('REDIS_PORT', '6379')), db=2, decode_responses=True)
v = r.get(${J(cle)})
sortie(dict(etat=json.loads(v) if v else None, ttl=r.ttl(${J(cle)})))`)
    console.log(`[AIC91] Redis ${cle} : ${J(redis)}`)
    expect(redis.etat, 'clé de progression en Redis').toBeTruthy()
    const enBase = redis.etat.etapes.map((e) => e.libelle)
    expect(enBase.length, 'au moins trois étapes publiées').toBeGreaterThanOrEqual(3)
    expect(redis.etat.fini, 'tour marqué fini').toBe(true)
    expect(redis.ttl, 'clé effacée sous 10 minutes').toBeGreaterThan(0)
    expect(redis.ttl, 'clé effacée sous 10 minutes').toBeLessThanOrEqual(600)
    const ts = redis.etat.etapes.map((e) => e.t)
    expect(ts, 'étapes publiées dans l\'ordre').toEqual([...ts].sort((x, y) => x - y))
    expect(sondages.length, 'l\'écran a sondé la progression').toBeGreaterThan(0)
    // Écran : la bulle d'attente (et ses étapes) s'efface à la réponse.
    await expect(a.p.getByTestId('etape-en-cours'), 'les étapes s\'effacent à la réponse').toHaveCount(0)
    // Pendant l'attente (listes non vides, avant le vidage de la réponse) : AIC101 — une étape affichée ne disparaît
    // jamais (chaque liste prolonge la précédente) ; la dernière liste montre TOUTES les étapes, sans doublon,
    // chacune publiée, dans l'ordre publié ; au moins trois (AIC91).
    const finAttente = listes.findIndex((x, i) => i > 0 && x.l.length === 0 && listes[i - 1].l.length > 0)
    const attente = (finAttente < 0 ? listes : listes.slice(0, finAttente)).filter((x) => x.l.length > 0)
    expect(attente.length, 'des étapes affichées sous la bulle d\'attente').toBeGreaterThan(0)
    for (let i = 1; i < attente.length; i += 1) {
      expect(attente[i].l.slice(0, attente[i - 1].l.length), `aucune étape ne disparaît (${J(attente[i - 1].l)} → ${J(attente[i].l)})`).toEqual(attente[i - 1].l)
    }
    const derniere = attente[attente.length - 1].l
    expect(derniere.length, `trois étapes affichées avant la réponse (affichées : ${J(derniere)} ; publiées : ${J(enBase)})`).toBeGreaterThanOrEqual(3)
    expect(new Set(derniere).size, 'sans doublon').toBe(derniere.length)
    expect(derniere.filter((l) => !enBase.includes(l)), 'affiché = publié').toEqual([])
    expect(derniere, 'ordre affiché = ordre publié').toEqual(enBase.slice(0, derniere.length))
    // Libellés du REGISTRE (jamais un argument d'outil ni une donnée personnelle) : jamais le nom du lead.
    for (const l of derniere) expect(l, 'libellé sans donnée du lead').not.toContain(nom)
    // Cas AIC101 observé ou non sur ce rejeu (deux étapes nouvelles ou plus servies par un même sondage).
    let vu = 0
    const sautes = sondages.filter((s) => { const n = s.libelles.length - vu; vu = Math.max(vu, s.libelles.length); return n >= 2 })
    console.log(`[AIC101] sondages apportant ≥ 2 étapes d'un coup : ${J(sautes)}`)
    // La réponse arrive ensuite (carte(s) du tour rendue(s) dans le tiroir).
    expect((corps.cartes || []).length, 'cartes du tour').toBeGreaterThan(0)
    await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 }).catch(() => undefined)
  } finally {
    await api.dispose().catch(() => undefined)
    await nettoyerLead(lead.id)
  }
}
for (const n of [1, 2, 3]) etape(`P7.1-AIC91-progression-r${n}`, ['AIC91', 'AIC101'], progression)

// ═══ AIC90 — plafond 0,01 $ : 1re question sur Claude, la 2e servie par le repli Groq (repli: true), zéro token
//      Claude ajouté au coût du jour, ligne de budget dans la bulle, jamais d'arrêt ═══
etape('P9.1-AIC90-plafond-du-jour', ['AIC90'], async ({ page, context, suivi, testInfo }) => {
  await page.close()
  const c = await sous(context, suivi, testInfo, 'aic90', 'Commercial')
  console.log(`[AIC90] commercial ${c.id}, copilote=${c.copilote}`)
  const api = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(api, { username: c.username, password: MDP_ESSAI })
  const budget = async (quand) => {
    const b = await lireJson(await api.get(`${API}/agent/evenements/budget/`, T), `budget ${quand}`)
    console.log(`[AIC90] budget ${quand} : ${J(b)}`)
    return b
  }
  try {
    const b0 = await budget('avant')
    expect(b0.plafond_usd, 'plafond du job (ASSISTANT_PLAFOND_JOUR_USD=0.01)').toBe(0.01)
    expect([b0.cout_jour_usd, b0.atteint], 'compte neuf : coût du jour nul, plafond non atteint').toEqual([0, false])
    await c.p.goto('/apps')
    const q1 = await demander(c.p, 'Combien de leads avons-nous en tout, et combien par statut ? Donne aussi le nombre de devis de ce mois.')
    expect(q1.corps.answer || '', 'question 1 : pas d\'erreur générique').not.toContain(ERREUR_GENERIQUE)
    expect(q1.corps.answer || '', 'question 1 : pas encore de budget atteint').not.toContain(MESSAGE_BUDGET)
    await reponseAffichee(q1.panneau, q1.corps, 'question 1')
    const e1 = await attendreEvenements(c.id, 1)
    console.log(`[AIC90] événements après Q1 : ${J(e1)}`)
    expect(e1.length, 'un événement après la question 1').toBe(1)
    expect([e1[0].modele, e1[0].repli], 'question 1 servie par Claude').toEqual(['claude-sonnet-5-5', false])
    const b1 = await budget('après Q1')
    expect(b1.cout_jour_usd, 'coût du jour ≥ plafond après la question 1').toBeGreaterThanOrEqual(0.01)
    expect(b1.atteint, 'plafond atteint').toBe(true)

    const q2 = await demander(c.p, 'Combien de leads avons-nous ?')
    const reponse2 = q2.corps.answer || ''
    expect(reponse2.startsWith(MESSAGE_BUDGET), `question 2 : ligne d'information du budget en tête (${J(reponse2.slice(0, 200))})`).toBe(true)
    expect(reponse2.slice(MESSAGE_BUDGET.length).trim().length, 'jamais d\'arrêt : une réponse suit la ligne de budget').toBeGreaterThan(0)
    expect(reponse2, 'question 2 : pas d\'erreur générique').not.toContain(ERREUR_GENERIQUE)
    await expect(q2.panneau, 'ligne de budget affichée dans la bulle').toContainText('Budget du jour de l\'assistant atteint')
    await reponseAffichee(q2.panneau, { answer: reponse2.slice(MESSAGE_BUDGET.length) }, 'question 2 (repli)')
    const e2 = await attendreEvenements(c.id, 2)
    console.log(`[AIC90] événements après Q2 : ${J(e2)}`)
    expect(e2.length, 'deux événements').toBe(2)
    expect(e2[1].repli, 'question 2 : repli: true à l\'événement').toBe(true)
    expect(e2[1].modele, 'question 2 : modèle du repli (Groq), pas Claude').toBe('openai/gpt-oss-120b')
    expect(e2[1].erreur, 'question 2 : aucun échec journalisé').toBeNull()
    // Persistance : coût du jour relu (même calcul que les stats) ⇒ le tour du repli n'ajoute rien de facturé Claude.
    const b2 = await budget('après Q2')
    expect(b2.cout_jour_usd, 'zéro token Claude au tour du repli : coût du jour inchangé').toBe(b1.cout_jour_usd)
    expect(b2.atteint, 'toujours au plafond').toBe(true)
  } finally {
    await api.dispose().catch(() => undefined)
  }
})

// ═══ AIC102 — base SANS `ia_ocr_document` (RUN_DB_DDL non posé) : la table absente n'est jamais proposée au modèle ;
//      le Directeur reçoit une réponse à une question vague et à une question sur les documents OCR ═══
const SONDE_TABLES = `
import json, os, sys
sys.path.insert(0, os.getcwd())
from app.services.sql_agent_service import sql_agent_service as s
from langchain_community.utilities import SQLDatabase
from app.core import database as d
a = json.loads(sys.argv[1])
res = {}
for q in a['questions']:
    c = {'candidates': s._get_relevant_tables(q)}
    try:
        SQLDatabase(d.create_sql_agent_engine(), include_tables=[t for t in c['candidates'] if t in s._ALLOWED_TABLES] or list(s._ALLOWED_TABLES), sample_rows_in_table_info=0)
        c['sans_filtre'] = 'ok'
    except Exception as e:
        c['sans_filtre'] = str(e)[:300]
    try:
        c['proposees'] = sorted(s._base_sql(q, a['company_id']).get_usable_table_names())
    except Exception as e:
        c['erreur'] = str(e)[:300]
    res[q] = c
print('@@' + json.dumps(res, default=str))
`
etape('P9.2-AIC102-table-ocr-absente', ['AIC102'], async ({ page, context, suivi, testInfo }) => {
  await page.close()
  const base = await py(`from django.db import connection
with connection.cursor() as cur:
    cur.execute("SELECT to_regclass('public.ia_ocr_document') IS NULL")
    absente = cur.fetchone()[0]
sortie(dict(absente=absente, societe=${SOC}))`)
  expect(base.absente, 'base du job SANS ia_ocr_document (RUN_DB_DDL non posé)').toBe(true)
  const vague = 'Quel est le CA du mois ?'
  const ocr = 'Combien de documents OCR (factures et bons de livraison scannés) avons-nous analysés ?'
  // Serveur : tables candidates de la question et tables réellement proposées au modèle (`_base_sql`, code livré).
  const py3 = process.env.E2E_IA_PYTHON
  expect(py3, 'E2E_IA_PYTHON (venv du service IA) posé par le workflow').toBeTruthy()
  const r = spawnSync(py3, ['-c', SONDE_TABLES, J({ questions: [vague, ocr], company_id: base.societe })],
    { cwd: join(RACINE, 'backend/fastapi_ia'), encoding: 'utf8', maxBuffer: 50_000_000, timeout: 300_000 })
  const l = (r.stdout || '').split('\n').filter((x) => x.startsWith('@@')).pop()
  expect(l, `sonde des tables : ${(r.stderr || '').slice(-800)}`).toBeTruthy()
  const tables = JSON.parse(l.slice(2))
  console.log(`[AIC102] tables : ${J(tables)}`)
  for (const q of [vague, ocr]) {
    expect(tables[q].erreur, `« ${q} » : _base_sql construit sans erreur`).toBeUndefined()
    expect(tables[q].proposees, `« ${q} » : ia_ocr_document jamais proposée au modèle`).not.toContain('ia_ocr_document')
    expect(tables[q].proposees.length, `« ${q} » : des tables proposées`).toBeGreaterThan(0)
  }
  // La question OCR cite bien la table absente parmi ses candidates : sans l'intersection, SQLDatabase lèverait.
  expect(tables[ocr].candidates, 'question OCR : ia_ocr_document parmi les tables candidates').toContain('ia_ocr_document')
  expect(tables[ocr].sans_filtre, 'sans l\'intersection : « not found » (le défaut que AIC102 corrige)').toMatch(/not found/i)

  // Écran : deux Directeurs neufs (coût du jour nul ⇒ chaque question servie par Claude malgré le plafond du job).
  for (const [q, absence] of [[vague, false], [ocr, true]]) {
    const dir = await sous(context, suivi, testInfo, 'aic102', 'Directeur')
    console.log(`[AIC102] Directeur ${dir.id}, copilote=${dir.copilote}`)
    await dir.p.goto('/apps')
    const { panneau, corps } = await demander(dir.p, q)
    const rep = corps.answer || ''
    expect(rep, `« ${q} » : jamais l'erreur générique`).not.toContain(ERREUR_GENERIQUE)
    await expect(panneau, `« ${q} » : pas d'erreur générique à l'écran`).not.toContainText(ERREUR_GENERIQUE)
    await reponseAffichee(panneau, corps, `« ${q} »`)
    const evs = await attendreEvenements(dir.id, 1)
    console.log(`[AIC102] événement : ${J(evs)}`)
    expect(evs[0].intention, `« ${q} » : tour journalisé sans échec (intention ≠ bug)`).not.toBe('bug')
    expect(evs[0].erreur, `« ${q} » : aucun échec journalisé`).toBeNull()
    if (absence) {
      expect(rep, 'question OCR : la réponse dit l\'absence de documents OCR')
        .toMatch(/aucun|pas de|n['’](y )?a pas|n['’]existe|absen|indisponible|introuvable|pas (encore )?(disponible|accessible|enregistr)|(^|[^\d])0([^\d]|$)|zéro/i)
    }
  }
})
