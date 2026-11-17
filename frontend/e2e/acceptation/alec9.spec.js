// ALEC — preuves en direct ALEC41, ALEC51 et ALEC46 avec le VRAI assistant SQL (vague d'acceptation 8, lane alec8,
// 17/11/2026). Même montage que alec6/alec7 (vague 6, lane « llm ») : service IA FastAPI RÉEL dans le job (vraie clé de
// modèle, moteur et interrupteurs à leur défaut du merge, agent sous le rôle Postgres lecture seule `sql_agent_ro` de
// `backend/db/rls_roles.sql`), atteint par l'écran sous `/api/fastapi/` comme derrière nginx (route Playwright →
// E2E_IA_URL, jeton relayé en Bearer) ; comptes d'essai aux rôles SYSTÈME relus dans le registre livré, connectés PAR
// L'ÉCRAN. « Aucune requête exécutée » = journal Postgres du job (E2E_PG_LOG, `log_statement = 'all'` sur le SEUL rôle
// `sql_agent_ro`), borné par l'offset avant/après chaque tour, avec un TÉMOIN positif par étape. La réponse de l'OUTIL
// au modèle se lit dans le journal du service IA : depuis ALEC51 un refus de droit y est écrit
// « SECURITE: refus de droit (<motif>). » et ce motif est EXACTEMENT ce que l'outil rend au modèle
// (`_REFUS_DE_DROIT_PREFIXE + str(exc)`, sql_agent_service.py::_make_secure_query_tool). Le modèle n'est pas
// déterministe : les invariants des clauses sont affirmés ; le texte n'est affirmé que là où la clause le cite.
import { test, expect } from '@playwright/test'
import { readFileSync, statSync } from 'node:fs'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, uiLoginJusquAuxApps } from '../helpers.js'

const etape = groupe('ALEC', ['ALEC41', 'ALEC51', 'ALEC46'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
test.describe.configure({ timeout: 600_000 })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const SOC = `U.objects.get(username='demo_admin').company_id`

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
async function ouvrirAssistant(page) {
  const panneau = page.getByTestId('copilot-panel')
  if (await panneau.isVisible().catch(() => false)) return panneau
  await page.getByTestId('copilot-toggle').click()
  await expect(panneau, 'tiroir Copilote ouvert').toBeVisible({ timeout: 30_000 })
  return panneau
}

// ── journaux du job : requêtes de l'agent (rôle sql_agent_ro, Postgres) et service IA pendant UN tour ─────────
const PG = process.env.E2E_PG_LOG || '/tmp/pg.log'
const IA_LOG = process.env.E2E_IA_LOG || '/tmp/uvicorn.log'
const tailleDe = (f) => { try { return statSync(f).size } catch { return 0 } }
function instructionsAgent(debut) {
  let txt = ''
  try { txt = readFileSync(PG).subarray(debut).toString('utf8') } catch { return [] }
  return txt.split(/\n(?=\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})/)
    .filter((e) => /\] sql_agent_ro LOG: {2}(statement|execute [^:]*): /.test(e))
    .map((e) => e.replace(/^[\s\S]*? sql_agent_ro LOG: {2}(statement|execute [^:]*): /, '').replace(/\s+/g, ' ').trim())
}
/** Les journaux sont écrits par d'AUTRES processus : relus jusqu'à y voir au moins une requête de l'agent et deux
 *  journaux qui ne bougent plus entre deux relectures (au plus 15 s ; les assertions jugent ce qui est écrit). */
async function journauxDuTourEcrits(debut) {
  let avant = null
  await expect.poll(() => {
    const n = instructionsAgent(debut).length
    const etat = `${n}:${tailleDe(PG)}:${tailleDe(IA_LOG)}`
    const stable = n > 0 && etat === avant
    avant = etat
    return stable
  }, { timeout: 15_000, intervals: [500] }).toBe(true).catch(() => undefined)
}
/** Requêtes de l'agent qui LISENT la table `table` (FROM/JOIN, réécrite ou non ; jamais le catalogue). */
const lectures = (instr, table) => instr.filter((s) => new RegExp(`\\b(from|join)\\s+(\\(\\s*select\\s+\\*\\s+from\\s+)?("?public"?\\.)?"?${table}"?\\b`, 'i').test(s)
  && !/pg_catalog|information_schema/i.test(s))
const BRUIT = /pg_catalog|pg_type|^BEGIN|^ROLLBACK|^COMMIT|^show |^select (pg_catalog\.version|current_schema)|^SELECT 1$/i
const sansEspace = (t) => String(t || '').replace(/[\s\u00a0\u202f]/g, '')
/** Refus de la garde SQL au journal du service IA : refus de DROIT (ALEC51, motif rendu au modèle) ou refus générique. */
const REFUS_DROIT = /SECURITE: refus de droit \(/
const REFUS_GARDE = /SECURITE: (requete refusee|refus de droit) \(/

/** Pose `question` dans le tiroir ; rend {corps, instr, ia} : JSON de `/sql-agent/query`, requêtes de l'agent du tour,
 *  lignes du journal IA du tour (refus de la garde, erreurs). */
async function demander(page, qui, question) {
  const panneau = await ouvrirAssistant(page)
  const zone = panneau.getByPlaceholder('Posez votre question en français…')
  await expect(zone).toBeEnabled({ timeout: 60_000 })
  await zone.fill(question)
  const debut = tailleDe(PG)
  const debutIa = tailleDe(IA_LOG)
  const rep = page.waitForResponse((r) => r.request().method() === 'POST' && /\/api\/fastapi\/sql-agent\/query$/.test(new URL(r.url()).pathname), { timeout: 300_000 })
  await panneau.getByRole('button', { name: 'Envoyer' }).click()
  const r = await rep
  const corps = await r.json().catch(() => ({}))
  expect(r.status(), `${qui} : réponse de l'assistant ${J(corps).slice(0, 400)}`).toBe(200)
  await expect(zone, 'tour terminé').toBeEnabled({ timeout: 60_000 })
  // Réponse UTILISATEUR affichée dans le tiroir (première ligne de la réponse servie).
  const premiere = (corps.answer || '').split('\n').map((l) => l.trim()).find((l) => l.length > 0) || ''
  if (premiere) await expect(panneau, `${qui} : réponse affichée à l'écran`).toContainText(premiere.slice(0, 40))
  await journauxDuTourEcrits(debut)
  const instr = instructionsAgent(debut)
  const metier = instr.filter((x) => !BRUIT.test(x))
  let ia = []
  try { ia = readFileSync(IA_LOG).subarray(debutIa).toString('utf8').split('\n').filter((l) => /SECURITE|Traceback|Error|repli sur/.test(l)).map((l) => l.slice(0, 400)) } catch { /* journal absent */ }
  console.log(`[ALEC] ${qui} « ${question} » → réponse=${J(corps.answer || '')} ; data=${J(corps.data || null).slice(0, 200)} ; requêtes agent (${instr.length}, métier : ${J(metier.slice(0, 12))}) ; journal IA : ${J(ia.slice(0, 12))}`)
  expect(instr.length, `${qui} : le journal Postgres voit l'agent sous sql_agent_ro pendant le tour`).toBeGreaterThan(0)
  return { corps, instr, ia }
}

// ── comptes d'essai aux rôles du registre, connectés par l'écran ─────────────────────────────────────────────
async function roleReel(nom) {
  const r = await py(`from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
r = Role.objects.get(company_id=${SOC}, nom=${J(nom)})
reg = set(dict(CANONICAL_SYSTEM_ROLES)[${J(nom)}])
sortie(dict(pk=r.pk, manque=sorted(reg - set(r.permissions)), plus=sorted(set(r.permissions) - reg), codes=sorted(r.permissions)))`)
  expect([r.manque, r.plus], `rôle « ${nom} » en base = registre livré`).toEqual([[], []])
  return r
}
const ouverts = []
async function sous(context, suivi, testInfo, prefixe, nomRole) {
  const username = `${prefixe}_${marque()}`
  const role = await roleReel(nomRole)
  const id = await py(`u = compte(${J(username)}, role=${role.pk}, societe=${SOC})
u.first_name = 'Essai'; u.save(update_fields=['first_name'])
sortie(u.id)`)
  const ctx = await context.browser().newContext({ baseURL: testInfo.project.use.baseURL, serviceWorkers: 'block', storageState: { cookies: [], origins: [] } })
  ouverts.push({ ctx, username })
  const p = suivi.surveiller(await ctx.newPage())
  await p.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await uiLoginJusquAuxApps(p, { username, password: MDP_ESSAI })
  await brancherIA(p)
  await p.goto('/apps')
  return { p, ctx, id, username, role: nomRole, codes: role.codes }
}
test.afterEach(async () => {
  for (const o of ouverts.splice(0)) {
    await o.ctx.close().catch(() => undefined)
    await py(`U.objects.filter(username=${J(o.username)}).update(is_active=False)
sortie(1)`).catch(() => null)
  }
})
const REFUS = /refus|pas autoris|non autoris|ne (peux|pouvez|suis) pas|impossible|n['’]ai pas (acc[eè]s|le droit)|restreint|interdit|pas (le droit|accès|accessible|disponible)|confidenti|s[ée]curit[ée]|prot[ée]g|droit du module|permission/i
// Texte cité par la clause d'ALEC41 (« utilisez l'écran »), sur la réponse UTILISATEUR.
const UTILISEZ_ECRAN = /utilise[zr]?\s+(plut[ôo]t\s+|directement\s+|donc\s+)?l['’]\s?[ée]cran/i
const QUESTION_LIGNES = 'Liste les lignes de mes factures.'
const motifPortee = (ia) => ia.filter((l) => REFUS_DROIT.test(l) && /Portee restreinte/.test(l))

/** Une facture émise de la société (devis accepté → facture complète) : le Directeur a des lignes à lire. */
async function factureEmise(r, m) {
  const produit = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Article ALEC41 ${m}`, prix_vente: '5000.00', prix_achat: '3000.00' } }), 'produit')
  const client = await py(`from apps.crm.models import Client
sortie(Client.objects.create(company_id=${SOC}, nom='ALEC41 ${m}', prenom='Essai', email='alec41-${m}@example.invalid').pk)`)
  const devis = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { client, taux_tva: '20.00', lignes: [{ produit: produit.id, designation: produit.nom, quantite: '1.00', prix_unitaire: '5000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  await lireJson(await r.post(`${API}/ventes/devis/${devis.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await r.post(`${API}/ventes/devis/${devis.id}/accepter/`, { ...T, data: { nom: 'Client ALEC41' } }), 'acceptation')
  await lireJson(await r.post(`${API}/ventes/devis/${devis.id}/facturer-complet/`, { ...T, data: { remplacer_brouillons: true } }), 'facture complète')
  return produit
}
/** Témoin Directeur (clauses ALEC41 et ALEC51) : la lecture de ventes_lignefacture est EXÉCUTÉE, réécrite sur la société. */
async function temoinDirecteur(context, suivi, testInfo, prefixe, societe) {
  const dir = await sous(context, suivi, testInfo, prefixe, 'Directeur')
  const d = await demander(dir.p, 'Directeur', QUESTION_LIGNES)
  const lu = lectures(d.instr, 'ventes_lignefacture')
  expect(lu.length, 'Directeur (témoin) : la lecture de ventes_lignefacture est exécutée').toBeGreaterThan(0)
  expect(lu.every((s) => new RegExp(`company_id\\s*=\\s*${societe}\\b`).test(s)), `Directeur : SQL exécuté réécrit sur company_id = ${societe}`).toBe(true)
  expect(d.ia.filter((l) => REFUS_GARDE.test(l) && /ventes_lignefacture|Portee restreinte/i.test(l)), 'Directeur : aucun refus de la garde sur les lignes').toEqual([])
  expect(d.corps.answer || '', 'Directeur : une réponse, pas un renvoi à l\'écran').not.toMatch(UTILISEZ_ECRAN)
  expect((d.corps.answer || '').length, 'Directeur : réponse non vide').toBeGreaterThan(0)
  return d
}

// ═══ PF6 — ALEC41 : Commercial (portée « soi ») « liste les lignes de mes factures » ⇒ refus « utilisez l'écran »,
//      aucune requête exécutée ; Directeur ⇒ réponse ═══
etape('PF6-ALEC41-lignes-factures', ['ALEC41'], async ({ page, context, suivi, testInfo }) => {
  await page.close() // la capture d'étape prend le navigateur du rôle, pas l'onglet vide du projet
  const m = marque()
  const societe = await py(`sortie(${SOC})`)
  const produit = await factureEmise(context.request, m)
  const com = await sous(context, suivi, testInfo, 'alec41c', 'Commercial')
  expect(com.codes.filter((c) => c.startsWith('records_scope')), 'Given : Commercial du registre, portée « soi »').toContain('records_scope_soi')
  const c = await demander(com.p, 'Commercial', QUESTION_LIGNES)
  expect(lectures(c.instr, 'ventes_lignefacture'), 'Commercial : aucune requête exécutée sur ventes_lignefacture').toEqual([])
  expect(sansEspace(c.corps.answer), 'Commercial : aucune ligne de facture servie').not.toContain(sansEspace(produit.nom))
  expect(J(c.corps.data || null), 'Commercial : aucune donnée servie').not.toContain(produit.nom)
  expect(motifPortee(c.ia).length, 'Commercial : la garde a refusé la lecture « Portee restreinte »').toBeGreaterThan(0)
  expect(c.corps.answer || '', 'Commercial : refus').toMatch(REFUS)
  expect(c.corps.answer || '', 'Commercial : refus « utilisez l\'écran » (texte cité par la clause)').toMatch(UTILISEZ_ECRAN)
  await temoinDirecteur(context, suivi, testInfo, 'alec41d', societe)
})

// ═══ PF6 — ALEC51 : la raison d'un refus de droit part au modèle ; le Commercial est renvoyé à l'écran, jamais
//      « je ne sais pas pourquoi » ; module manquant ⇒ le nom du module ; Directeur ⇒ exécution ═══
etape('PF6-ALEC51-raison-du-refus', ['ALEC51'], async ({ page, context, suivi, testInfo }) => {
  await page.close()
  const m = marque()
  const societe = await py(`sortie(${SOC})`)
  await factureEmise(context.request, m)
  const com = await sous(context, suivi, testInfo, 'alec51c', 'Commercial')
  const c = await demander(com.p, 'Commercial', QUESTION_LIGNES)
  // Réponse de l'OUTIL : le motif de droit (« Portee restreinte » + « utilisez l'ecran ») et non le refus générique.
  const motifs = motifPortee(c.ia)
  console.log(`[ALEC51] Commercial : motifs rendus au modèle : ${J(motifs)}`)
  expect(motifs.length, 'Commercial : l\'outil rend « Portee restreinte » au modèle').toBeGreaterThan(0)
  expect(motifs.every((l) => /utilisez l'ecran/.test(l)), 'Commercial : le motif rendu contient « utilisez l\'ecran »').toBe(true)
  expect(c.ia.filter((l) => /SECURITE: requete refusee \(Portee/.test(l)), 'Commercial : plus aucun refus de portée rendu en générique').toEqual([])
  expect(lectures(c.instr, 'ventes_lignefacture'), 'Commercial : requête non exécutée').toEqual([])
  // Réponse UTILISATEUR : l'envoie vers l'écran, jamais « je ne sais pas pourquoi ».
  expect(c.corps.answer || '', 'Commercial : la réponse renvoie à l\'écran').toMatch(/[ée]cran/i)
  expect(c.corps.answer || '', 'Commercial : pas « je ne sais pas pourquoi »').not.toMatch(/je ne sais pas pourquoi|sans savoir pourquoi|raison inconnue/i)

  // Module manquant ⇒ le nom du module dans le motif rendu (Admin Ventes livré, sans code adsengine_).
  const av = await sous(context, suivi, testInfo, 'alec51v', 'Admin Ventes')
  expect(av.codes.filter((x) => x.startsWith('adsengine_')), 'Given : Admin Ventes sans code adsengine_').toEqual([])
  const a = await demander(av.p, 'Admin Ventes', 'Combien ai-je dépensé en publicité ce mois ?')
  const module = a.ia.filter((l) => REFUS_DROIT.test(l) && /adsengine_/.test(l))
  console.log(`[ALEC51] Admin Ventes : motifs rendus au modèle : ${J(module)}`)
  expect(module.length, 'Admin Ventes : un refus de droit sur un miroir adsengine_').toBeGreaterThan(0)
  expect(module.every((l) => /droit du module adsengine manquant/.test(l)), 'Admin Ventes : le motif nomme le module (adsengine)').toBe(true)
  expect(lectures(a.instr, 'adsengine_insightsnapshot'), 'Admin Ventes : requête non exécutée').toEqual([])

  await temoinDirecteur(context, suivi, testInfo, 'alec51d', societe)
})

// ═══ PF6 — ALEC46 : Admin Ventes « combien ai-je dépensé en publicité ce mois ? » ⇒ refus ; Directeur ⇒ le montant ═══
etape('PF6-ALEC46-miroirs-publicitaires', ['ALEC46'], async ({ page, context, suivi, testInfo }) => {
  await page.close()
  const m = marque()
  const pose = await py(`from decimal import Decimal
from django.contrib.contenttypes.models import ContentType
from django.db.models import Sum
from apps.adsengine.models import AdCampaignMirror, InsightSnapshot
from core.dates import aujourd_hui_local
j = aujourd_hui_local()
c = AdCampaignMirror.objects.create(company_id=${SOC}, meta_id='alec46-${m}', name='Campagne ALEC46 ${m}', status='PAUSED')
InsightSnapshot.objects.create(company_id=${SOC}, content_type=ContentType.objects.get_for_model(AdCampaignMirror), object_id=c.pk, date=j, spend=Decimal('4321.77'))
tot = InsightSnapshot.objects.filter(company_id=${SOC}, date__year=j.year, date__month=j.month).aggregate(s=Sum('spend'))['s']
sortie(dict(campagne=c.pk, total=str(tot), societe=${SOC}))`)
  console.log(`[ALEC46] dépense du mois en base : ${J(pose)}`)
  const total = Number(pose.total)
  const formes = [...new Set([total.toFixed(2), total.toFixed(2).replace('.', ','), String(Math.trunc(total)), String(Math.round(total))])]
  try {
    const av = await sous(context, suivi, testInfo, 'alec46v', 'Admin Ventes')
    expect(av.codes.filter((x) => x.startsWith('adsengine_')), 'Given : Admin Ventes du registre sans code adsengine_').toEqual([])
    const a = await demander(av.p, 'Admin Ventes', 'Combien ai-je dépensé en publicité ce mois ?')
    expect(lectures(a.instr, 'adsengine_insightsnapshot'), 'Admin Ventes : aucune requête exécutée sur adsengine_insightsnapshot').toEqual([])
    for (const f of formes) expect(sansEspace(a.corps.answer), 'Admin Ventes : le montant n\'est pas servi').not.toContain(f)
    expect(a.corps.answer || '', 'Admin Ventes : refus').toMatch(REFUS)
    const refusModule = a.ia.filter((l) => REFUS_GARDE.test(l) && /adsengine_/i.test(l))
    console.log(`[ALEC46] Admin Ventes : refus de la garde : ${J(refusModule)}`)
    expect(refusModule.length, 'Admin Ventes : la garde a refusé au moins une lecture d\'un miroir adsengine_').toBeGreaterThan(0)
    expect(refusModule.every((l) => /droit du module/i.test(l)), 'tout refus sur un miroir adsengine_ est « droit du module »').toBe(true)

    const dir = await sous(context, suivi, testInfo, 'alec46d', 'Directeur')
    expect(dir.codes.some((x) => x.startsWith('adsengine_')), 'Given : Directeur du registre porte le droit du module publicitaire').toBe(true)
    // Témoin sur le chemin CORRIGÉ (le SQL de l'agent) : question reformulée vers les statistiques publicitaires
    // enregistrées (la description de adsengine_insightsnapshot), pour que l'agent la lise PAR LE SQL.
    const b = await demander(dir.p, 'Directeur', 'Additionne la dépense des statistiques publicitaires enregistrées ce mois (performance publicitaire datée : somme de spend dans adsengine_insightsnapshot).')
    const lu = lectures(b.instr, 'adsengine_insightsnapshot')
    expect(lu.length, 'Directeur (témoin) : la lecture SQL de adsengine_insightsnapshot est exécutée').toBeGreaterThan(0)
    expect(lu.every((s) => new RegExp(`company_id\\s*=\\s*${pose.societe}\\b`).test(s)), `Directeur : SQL exécuté réécrit sur company_id = ${pose.societe}`).toBe(true)
    const refusDir = b.ia.filter((l) => REFUS_GARDE.test(l) && /adsengine_/i.test(l))
    expect(refusDir, 'Directeur : aucun refus de la garde sur les miroirs publicitaires').toEqual([])
    expect(formes.some((f) => sansEspace(b.corps.answer).includes(f)), `Directeur : le montant ${total} dans la réponse`).toBe(true)
  } finally {
    await py(`from apps.adsengine.models import AdCampaignMirror, InsightSnapshot
InsightSnapshot.objects.filter(company_id=${SOC}, object_id=${Number(pose.campagne)}).delete()
AdCampaignMirror.objects.filter(pk=${Number(pose.campagne)}).delete()
sortie(1)`).catch(() => null)
  }
})
