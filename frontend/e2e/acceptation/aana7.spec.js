// AANA — preuve en direct AANA81 avec le VRAI agent SQL (vague d'acceptation 6, lane « llm », 16/11/2026) :
// « pile locale, agent sous `sql_agent_ro`, « montant du devis X » ⇒ aucune somme des lignes ». Le service IA
// FastAPI RÉEL tourne dans le job (vraie clé de modèle ; `SQL_AGENT_DB_USER=sql_agent_ro`, rôle provisionné par
// `backend/db/rls_roles.sql`) ; l'écran l'atteint sous `/api/fastapi/` comme derrière nginx (route Playwright →
// E2E_IA_URL, jeton relayé en Bearer). Les requêtes que l'agent EXÉCUTE se lisent dans le journal Postgres du job
// (E2E_PG_LOG : `log_statement = 'all'` sur le seul rôle `sql_agent_ro`, `%u` dans le préfixe), bornées au tour.
// Le modèle n'est pas déterministe : l'étape affirme l'invariant de la clause (agent connecté sous `sql_agent_ro`,
// aucune requête `quantite * prix_unitaire` sur `ventes_lignedevis`), pas un texte.
import { test, expect, request as pwRequest } from '@playwright/test'
import { readFileSync, statSync } from 'node:fs'
import { groupe } from './_oracles.js'
import { fermerDjangoApresTout } from './_django.js'
import { lireJson, telephoneMobileUnique, assurerSessionPage } from '../helpers.js'

const etape = groupe('AANA', ['AANA81'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
test.describe.configure({ timeout: 480_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`

// ── service IA réel (FastAPI du workflow), branché sous /api/fastapi comme nginx en prod ─────────────────────
const IA = process.env.E2E_IA_URL
const jetonDe = async (context) => (await context.cookies()).find((c) => c.name === 'access_token')?.value || ''
async function brancherIA(page) {
  expect(IA, 'service IA lancé par le workflow (E2E_IA_URL)').toBeTruthy()
  await page.route(/\/api\/fastapi\//, async (route) => {
    const req = route.request()
    const u = new URL(req.url())
    const headers = { ...req.headers() }
    delete headers.host; delete headers.cookie; delete headers['content-length']
    const jeton = await jetonDe(page.context())
    if (jeton) headers.authorization = `Bearer ${jeton}`
    try {
      const rep = await route.fetch({ url: `${IA}${u.pathname.replace(/^\/api\/fastapi/, '')}${u.search}`, headers, timeout: 300_000, maxRedirects: 0 })
      await route.fulfill({ response: rep })
    } catch {
      await route.abort().catch(() => undefined)
    }
  })
}
async function viderHistorique(context) {
  const ia = await pwRequest.newContext({ baseURL: IA, extraHTTPHeaders: { Authorization: `Bearer ${await jetonDe(context)}` } })
  try { await ia.delete('/sql-agent/history', T) } finally { await ia.dispose() }
}

// ── journal Postgres du job : TOUTES les requêtes du tour (préfixe `%m [%p] %u `) ─────────────────────────────
const PG = process.env.E2E_PG_LOG || '/tmp/pg.log'
const tailleDe = (f) => { try { return statSync(f).size } catch { return 0 } }
function instructions(debut) {
  let txt = ''
  try { txt = readFileSync(PG).subarray(debut).toString('utf8') } catch { return [] }
  return txt.split(/\n(?=\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})/)
    .map((e) => /\] (\S+) LOG: {2}(?:statement|execute [^:]*): ([\s\S]*)$/.exec(e))
    .filter(Boolean)
    .map((x) => ({ role: x[1], sql: x[2].replace(/\s+/g, ' ').trim() }))
}
/** Le journal Postgres est écrit par un AUTRE processus : relit le journal jusqu'à y voir les requêtes de l'agent du
 *  tour (au moins une) et un journal qui ne bouge plus entre deux relectures. Au-delà de 15 s, rien n'est affirmé ici :
 *  les assertions de l'étape jugent ce qui a été écrit. */
async function journalDuTourEcrit(debut) {
  let avant = null
  await expect.poll(() => {
    const n = instructions(debut).filter((x) => x.role === 'sql_agent_ro').length
    const etat = `${n}:${tailleDe(PG)}`
    const stable = n > 0 && etat === avant
    avant = etat
    return stable
  }, { timeout: 15_000, intervals: [500] }).toBe(true).catch(() => undefined)
}

// ═══ AANA81 : « montant du devis X » à l'agent sous sql_agent_ro ⇒ aucune somme des lignes ═══
etape('PA4-AANA81-montant-devis', ['AANA81'], async ({ page }) => {
  const r = page.request
  const m = marque()
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `AANA81 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `aana81-${m}@example.invalid` } }), 'lead')
  const p = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Panneau AANA81 ${m}`, prix_vente: '1000.00', prix_achat: '400.00' } }), 'produit')
  // Deux lignes : la somme quantite × prix_unitaire (2 × 1 000 + 1 × 500 = 2 500 HT) n'est PAS le montant du devis.
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, {
    ...T, data: {
      taux_tva: '20.00', remise_globale: '0', lead: lead.id,
      lignes: [
        { produit: p.id, designation: p.nom, quantite: '2', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 },
        { produit: p.id, designation: `Pose AANA81 ${m}`, quantite: '1', prix_unitaire: '500.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 1 },
      ],
    },
  }), 'devis')
  try {
    await brancherIA(page)
    await viderHistorique(page.context())
    await page.goto('/apps')
    const panneau = page.getByTestId('copilot-panel')
    await page.getByTestId('copilot-toggle').click()
    await expect(panneau, 'tiroir Copilote ouvert').toBeVisible({ timeout: 30_000 })
    const zone = panneau.getByPlaceholder('Posez votre question en français…')
    await expect(zone).toBeEnabled({ timeout: 60_000 })
    const question = `Quel est le montant du devis ${d.reference} ?`
    await zone.fill(question)
    const debut = tailleDe(PG)
    const rep = page.waitForResponse((x) => x.request().method() === 'POST' && /\/api\/fastapi\/sql-agent\/query$/.test(new URL(x.url()).pathname), { timeout: 300_000 })
    await panneau.getByRole('button', { name: 'Envoyer' }).click()
    const reponse = await rep
    const corps = await reponse.json().catch(() => ({}))
    expect(reponse.status(), `réponse de l'agent : ${J(corps).slice(0, 400)}`).toBe(200)
    await expect(zone, 'tour terminé').toBeEnabled({ timeout: 60_000 })
    const premiere = (corps.answer || '').split('\n').map((l) => l.trim()).find((l) => l.length > 0) || ''
    expect(premiere, 'réponse non vide').toBeTruthy()
    await expect(panneau, 'réponse affichée à l\'écran').toContainText(premiere.slice(0, 40))
    await journalDuTourEcrit(debut)
    const tour = instructions(debut)
    const agent = tour.filter((x) => x.role === 'sql_agent_ro').map((x) => x.sql)
    console.log(`[AANA81] « ${question} » → réponse=${J(corps.answer || '')} ; requêtes sql_agent_ro (${agent.length}) : ${J(agent.slice(0, 15))}`)
    // L'agent tourne sous le rôle lecture seule `sql_agent_ro` (jamais le propriétaire) : il apparaît dans le journal.
    expect(agent.length, 'agent connecté sous sql_agent_ro pendant le tour').toBeGreaterThan(0)
    // Invariant de la clause : AUCUNE somme des lignes (quantite × prix_unitaire) de ventes_lignedevis.
    const somme = agent.filter((s) => /ventes_lignedevis/i.test(s) && /quantite\s*\)?\s*\*\s*\(?\s*("?\w+"?\.)?"?prix_unitaire|prix_unitaire\s*\)?\s*\*\s*\(?\s*("?\w+"?\.)?"?quantite/i.test(s))
    expect(somme, 'aucune somme quantite × prix_unitaire des lignes de devis exécutée').toEqual([])
    expect(agent.filter((s) => /sum\s*\(/i.test(s) && /ventes_lignedevis/i.test(s)), 'aucune SUM sur ventes_lignedevis').toEqual([])
    const plat = String(corps.answer || '').replace(/[\s\u00a0\u202f]/g, '')
    expect(plat, 'la réponse ne donne pas la somme HT des lignes (2 500)').not.toContain('2500')
    expect(plat, 'la réponse ne donne pas la somme TTC des lignes (3 000)').not.toContain('3000')
    expect(corps.answer || '', 'la réponse renvoie à la fiche du devis').toMatch(/fiche|\/ventes\/devis/i)
  } finally {
    await r.delete(`${API}/ventes/devis/${d.id}/`, T).catch(() => null)
    await r.delete(`${API}/crm/leads/${lead.id}/`, T).catch(() => null)
  }
})
