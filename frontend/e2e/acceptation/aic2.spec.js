// AIC — preuve en direct AIC91 (progression du tour), jouée À PART d'aic.spec.js (AIC94) sur son propre sha : rejouée
// trois fois, elle échoue deux fois sur un défaut de l'écran (étape sautée), et un enregistrement FAIL ne couvre rien.
// Même harnais qu'aic.spec.js : VRAI copilote (vague d'acceptation 6, lane « llm », 16/11/2026). Le service IA FastAPI RÉEL tourne dans le job (vraie clé
// de modèle ; moteur `ASSISTANT_MOTEUR` et interrupteur `ASSISTANT_COPILOTE` à leur défaut du merge : copilote allumé
// pour un administrateur) ; l'écran l'atteint sous `/api/fastapi/` comme derrière nginx (route Playwright →
// E2E_IA_URL, jeton de la session relayé en Bearer). Compte d'essai NEUF au rôle système « Administrateur » relu dans
// le registre livré (file et agenda propres : aucune donnée du seed ne pousse nos lignes hors des 10 du digest).
// Le modèle n'est pas déterministe : chaque étape affirme les invariants de la clause (étapes affichées avant la
// réponse, bandeau servi par le serveur, rangée de visite + « Ouvrir la fiche »), jamais un texte libre du modèle.
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, telephoneMobileUnique, connexionApi, uiLoginJusquAuxApps } from '../helpers.js'

const etape = groupe('AIC', ['AIC91'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
test.describe.configure({ timeout: 480_000 })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const SOC = `U.objects.get(username='demo_admin').company_id`
const TELEPHONE = { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true }

// ── service IA réel (FastAPI du workflow), branché sous /api/fastapi comme nginx en prod ─────────────────────
const IA = process.env.E2E_IA_URL
const attendre = (ms) => new Promise((r) => setTimeout(r, ms))
const jetonDe = async (context) => (await context.cookies()).find((c) => c.name === 'access_token')?.value || ''
/** `latenceMs` : connexion bridée — délai à l'aller ET au retour de chaque appel au service IA. */
async function brancherIA(page, { latenceMs = 0 } = {}) {
  expect(IA, 'service IA lancé par le workflow (E2E_IA_URL)').toBeTruthy()
  await page.route(/\/api\/fastapi\//, async (route) => {
    const req = route.request()
    const u = new URL(req.url())
    const headers = { ...req.headers() }
    delete headers.host; delete headers.cookie; delete headers['content-length']
    const jeton = await jetonDe(page.context())
    if (jeton) headers.authorization = `Bearer ${jeton}`
    try {
      if (latenceMs) await attendre(latenceMs)
      const rep = await route.fetch({ url: `${IA}${u.pathname.replace(/^\/api\/fastapi/, '')}${u.search}`, headers, timeout: 300_000, maxRedirects: 0 })
      if (latenceMs) await attendre(latenceMs)
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
  console.log(`[AIC] « ${question} » → moteur=${corps.moteur} cartes=${J((corps.cartes || []).map((c) => c.carte))} réponse=${J((corps.answer || '').slice(0, 300))}`)
  return { panneau, corps, requete: r.request().postDataJSON() || {} }
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
/** Administrateur d'essai neuf, connecté PAR L'ÉCRAN dans un navigateur de téléphone ; {p, ctx, id, username}. */
async function administrateur(context, suivi, testInfo, prefixe) {
  const username = `${prefixe}_${marque()}`
  const id = await py(`u = compte(${J(username)}, role=${await roleReel('Administrateur')}, societe=${SOC})
u.first_name = 'Salma'; u.save(update_fields=['first_name'])
from apps.agent.registry import copilote_allume_pour
sortie(dict(id=u.id, copilote=copilote_allume_pour(u)))`)
  expect(id.copilote, 'copilote allumé pour un administrateur (réglage du merge ASSISTANT_COPILOTE=admins)').toBe(true)
  const ctx = await context.browser().newContext({ baseURL: testInfo.project.use.baseURL, serviceWorkers: 'block', storageState: { cookies: [], origins: [] }, ...TELEPHONE })
  ouverts.push({ ctx, username })
  const p = suivi.surveiller(await ctx.newPage())
  await p.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await uiLoginJusquAuxApps(p, { username, password: MDP_ESSAI })
  return { p, ctx, id: id.id, username }
}
test.afterEach(async () => {
  for (const o of ouverts.splice(0)) {
    await o.ctx.close().catch(() => undefined)
    await py(`U.objects.filter(username=${J(o.username)}).update(is_active=False)
sortie(1)`).catch(() => null)
  }
})

/** Lead propre à l'étape, responsable = `ownerId`, avec téléphone WhatsApp ; + une touche WhatsApp à faire aujourd'hui. */
async function leadAvecTouche(ctx, ownerId, nom) {
  const lead = await lireJson(await ctx.post(`${API}/crm/leads/`, {
    ...T, data: { nom, prenom: 'Amal', ville: 'Casablanca', telephone: telephoneMobileUnique(), whatsapp: telephoneMobileUnique(), email: `aic-${marque()}@example.invalid` },
  }), 'lead')
  const touche = await py(`from apps.crm.models import Lead
from apps.crm.models_cadence import RelanceEtape
Lead.objects.filter(pk=${lead.id}).update(owner_id=${ownerId})
sortie(RelanceEtape.objects.create(company_id=${SOC}, lead_id=${lead.id}, cadence='contact', ordre=9, due_date=timezone.localdate(),
       due_at=timezone.now(), canal='whatsapp', template_cle='identite', libelle='Identité').id)`)
  return { lead, touche }
}
const nettoyerLead = (id) => py(`from apps.crm.models import Lead
M = getattr(Lead, 'all_objects', Lead.objects)
try: M.filter(pk=${Number(id)}).delete()
except Exception as exc: print('nettoyage', exc)
sortie(1)`).catch(() => null)

// ═══ P7.1 — AIC91 : question à trois outils, téléphone à connexion bridée ⇒ trois étapes affichées avant la réponse ═══
etape('P7.1-AIC91-progression', ['AIC91'], async ({ page, context, suivi, testInfo }) => {
  await page.close() // la capture d'étape prend le navigateur du téléphone, pas l'onglet vide du projet
  const m = marque()
  const a = await administrateur(context, suivi, testInfo, 'aic91')
  const api = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(api, { username: a.username, password: MDP_ESSAI })
  const nom = `Zerhouni${m}`
  const { lead } = await leadAvecTouche(api, a.id, nom)
  try {
    // Connexion bridée : réseau du navigateur ralenti (CDP) + 700 ms à l'aller et au retour de chaque appel IA.
    const cdp = await a.ctx.newCDPSession(a.p)
    await cdp.send('Network.enable')
    await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 400, downloadThroughput: 60 * 1024, uploadThroughput: 30 * 1024 })
    await brancherIA(a.p, { latenceMs: 700 })
    const sondages = []
    a.p.on('response', async (r) => {
      if (!/\/api\/fastapi\/sql-agent\/progression\//.test(new URL(r.url()).pathname)) return
      const c = await r.json().catch(() => null)
      if (c) sondages.push({ n: (c.etapes || []).length, fini: c.fini })
    })
    await a.p.goto('/apps')
    // Collecteur DANS la page : chaque libellé affiché sous la bulle d'attente, dans l'ordre, horodaté.
    const { corps, requete } = await demander(a.p,
      `Trois choses dans l'ordre, une à la fois : 1) retrouve le lead ${nom} ; 2) résume-moi sa fiche ; 3) prépare sa prochaine touche du suivi.`,
      {
        avantEnvoi: () => a.p.evaluate(() => {
          window.__etapesVues = []
          window.__collecte = setInterval(() => {
            const el = document.querySelector('[data-testid="etape-en-cours"]')
            const t = el?.textContent?.trim()
            const l = window.__etapesVues
            if (t && l[l.length - 1]?.libelle !== t) l.push({ libelle: t, at: Date.now() })
          }, 50)
        }),
      })
    const vues = await a.p.evaluate(() => { clearInterval(window.__collecte); return window.__etapesVues })
    console.log(`[AIC91] étapes affichées : ${J(vues)} ; sondages : ${J(sondages)}`)
    // Persistance : la clé Redis `assistant:progression:<utilisateur>:<id>` relue ⇒ les étapes dans l'ordre, fini.
    expect(requete.progression_id, 'identifiant de progression envoyé avec la question').toMatch(/^[A-Za-z0-9_-]{8,64}$/)
    const cle = `assistant:progression:${a.id}:${requete.progression_id}`
    const redis = await py(`import os, redis
r = redis.Redis(host=os.environ.get('REDIS_HOST', 'redis'), port=int(os.environ.get('REDIS_PORT', '6379')), db=2, decode_responses=True)
v = r.get(${J(cle)})
sortie(dict(etat=json.loads(v) if v else None, ttl=r.ttl(${J(cle)})))`)
    console.log(`[AIC91] Redis ${cle} : ${J(redis)}`)
    await expect(a.p.getByTestId('etape-en-cours'), 'la bulle d\'attente (et son étape) s\'arrête à la réponse').toHaveCount(0)
    const distinctes = [...new Set(vues.map((v) => v.libelle))]
    // Libellés du REGISTRE (jamais un argument d'outil ni une donnée personnelle) : jamais le nom du lead.
    for (const l of distinctes) expect(l, 'libellé sans donnée du lead').not.toContain(nom)
    expect(sondages.length, 'l\'écran a sondé la progression').toBeGreaterThan(0)
    expect(distinctes.length, `trois étapes distinctes affichées avant la réponse (vues : ${J(distinctes)} ; publiées : ${J(redis.etat?.etapes || [])})`).toBeGreaterThanOrEqual(3)
    expect(redis.etat, 'clé de progression en Redis').toBeTruthy()
    const enBase = redis.etat.etapes.map((e) => e.libelle)
    expect(enBase.length, 'au moins trois étapes publiées').toBeGreaterThanOrEqual(3)
    expect(redis.etat.fini, 'tour marqué fini').toBe(true)
    expect(redis.ttl, 'clé effacée sous 10 minutes').toBeLessThanOrEqual(600)
    const ts = redis.etat.etapes.map((e) => e.t)
    expect(ts, 'étapes dans l\'ordre').toEqual([...ts].sort((x, y) => x - y))
    // Chaque libellé affiché est l'un des libellés publiés, dans le même ordre.
    expect(distinctes.filter((l) => !enBase.includes(l)), 'affiché = publié').toEqual([])
    const publieesVues = [...new Set(enBase)].filter((l) => distinctes.includes(l))
    expect(distinctes, 'ordre affiché = ordre publié').toEqual(publieesVues)
    // La réponse arrive ensuite (carte(s) du tour rendue(s) dans le tiroir).
    expect((corps.cartes || []).length, 'cartes du tour').toBeGreaterThan(0)
    await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 }).catch(() => undefined)
  } finally {
    await api.dispose().catch(() => undefined)
    await nettoyerLead(lead.id)
  }
})
