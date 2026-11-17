// (17/11/2026) Ce fichier remplace l'ancien rejeu FAIL d'ALEC41 (vague 6, trace de l'enregistrement ALEC 2026-11-17-b9e2a9ebd,
// git le garde) : ALEC41 est prouvée par alec9.spec.js (vague 8). Il porte désormais la preuve en direct d'ALEC52
// (rejouée sous le nom alec10.spec.js, enregistrement ALEC 2026-11-17-852f728c9, run 44051270319).
// ALEC — preuve en direct ALEC52 avec le VRAI assistant SQL (vague d'acceptation 9, lane alec52, 17/11/2026).
// Montage d'alec9 (vague 8) : service IA FastAPI RÉEL dans le job (vraie clé de modèle, agent sous le rôle Postgres
// lecture seule `sql_agent_ro` de `backend/db/rls_roles.sql`), atteint par l'écran sous `/api/fastapi/` comme derrière
// nginx ; base migrée, donc RLS AUD422 FORCE posée sur ventes_devis/facture/paiement ; `POSTGRES_RLS_ENABLED` ABSENT
// du service IA (comme en prod). Le défaut confirmé en prod : sans GUC `app.current_company`, `sql_agent_ro`
// (NOBYPASSRLS) voyait 0 facture. Preuves : (1) préconditions du défaut relues en base et dans l'environnement du
// processus uvicorn ; (2) le Directeur crée une facture (désignation unique) puis demande « liste mes factures » dans
// le tiroir : la RÉPONSE cite la référence de CETTE facture, et le journal Postgres (`log_statement = 'all'` sur le
// SEUL rôle `sql_agent_ro`) montre chaque lecture de ventes_facture de l'agent précédée, dans SA transaction, du
// `set_config('app.current_company', '<A>', true)` ; (3) témoin d'isolement : le Directeur d'une AUTRE société pose
// la même question : sa facture est citée, celle de A jamais, et son GUC porte SA société.
import { test, expect, request as pwRequest } from '@playwright/test'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, uiLoginJusquAuxApps, connexionApi } from '../helpers.js'

const etape = groupe('ALEC', ['ALEC52'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
test.describe.configure({ timeout: 600_000 })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const SOC = `U.objects.get(username='demo_admin').company_id`
const QUESTION = 'Liste mes factures avec leur référence et leur montant TTC.'

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

// ── journal Postgres du job : instructions du SEUL rôle sql_agent_ro, avec le pid (= la connexion) ────────────
const PG = process.env.E2E_PG_LOG || '/tmp/pg.log'
const IA_LOG = process.env.E2E_IA_LOG || '/tmp/uvicorn.log'
const tailleDe = (f) => { try { return statSync(f).size } catch { return 0 } }
const LIGNE_AGENT = /^\S+ \S+(?: \S+)? \[(\d+)\] sql_agent_ro LOG: {2}(?:statement|execute [^:]*): ([\s\S]*)$/
function entreesAgent(debut) {
  let txt = ''
  try { txt = readFileSync(PG).subarray(debut).toString('utf8') } catch { return [] }
  return txt.split(/\n(?=\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})/)
    .map((e) => LIGNE_AGENT.exec(e.trim()))
    .filter(Boolean)
    .map((m) => ({ pid: m[1], sql: m[2].replace(/\s+/g, ' ').trim() }))
}
async function journauxDuTourEcrits(debut) {
  let avant = null
  await expect.poll(() => {
    const n = entreesAgent(debut).length
    const etat = `${n}:${tailleDe(PG)}:${tailleDe(IA_LOG)}`
    const stable = n > 0 && etat === avant
    avant = etat
    return stable
  }, { timeout: 15_000, intervals: [500] }).toBe(true).catch(() => undefined)
}
const litTable = (sql, table) => new RegExp(`\\b(from|join)\\s+(\\(\\s*select\\s+\\*\\s+from\\s+)?("?public"?\\.)?"?${table}"?\\b`, 'i').test(sql)
  && !/pg_catalog|information_schema/i.test(sql)
const GUC = /set_config\(\s*'app\.current_company'\s*,\s*'(\d+)'\s*,\s*(true|false)\s*\)/i
const FIN_TX = /^(BEGIN|COMMIT|ROLLBACK|END)\b/i
/** Pour chaque lecture de `table` par l'agent : le GUC posé dans SA transaction (même pid, remontée jusqu'au
 *  set_config sans franchir BEGIN/COMMIT/ROLLBACK). Rend {lectures, gucs, fautes}. */
function gucDesLectures(entrees, table, societe) {
  const lectures = []
  const fautes = []
  entrees.forEach((e, i) => {
    if (!litTable(e.sql, table)) return
    let pose = null
    for (let j = i - 1; j >= 0; j--) {
      const x = entrees[j]
      if (x.pid !== e.pid) continue
      const m = GUC.exec(x.sql)
      if (m) { pose = { societe: m[1], local: m[2].toLowerCase() === 'true' }; break }
      if (FIN_TX.test(x.sql)) break
    }
    lectures.push({ sql: e.sql.slice(0, 300), pose })
    if (!pose || pose.societe !== String(societe) || !pose.local) fautes.push({ sql: e.sql.slice(0, 300), pose })
  })
  const gucs = [...new Set(entrees.map((e) => GUC.exec(e.sql)?.[1]).filter(Boolean))]
  return { lectures, gucs, fautes }
}
/** Affiche dans `page` (capturée en fin d'étape) les faits que l'étape vient d'affirmer : [[titre, valeur], …]. */
async function tracer(page, titre, blocs) {
  const echapper = (x) => String(x).replace(/&/g, '&amp;').replace(/</g, '&lt;')
  const texte = (v) => (typeof v === 'string' ? v : J(v, null, 1))
  await page.setContent(`<html><body style="font:13px monospace;padding:16px"><h3>${echapper(titre)}</h3>`
    + blocs.map(([t, v]) => `<h4>${echapper(t)}</h4><pre style="white-space:pre-wrap">${echapper(texte(v)).slice(0, 3000)}</pre>`).join('')
    + '</body></html>')
}
const sansEspace = (t) => String(t || '').replace(/[\s\u00a0\u202f]/g, '')
const AUCUNE = /aucune facture|pas de facture|0 facture|n['’]avez (encore )?(aucune|pas)/i

/** Pose QUESTION dans le tiroir du Directeur ; rend {corps, entrees, ia, panneau}. */
async function demanderEcran(page, qui) {
  const panneau = await ouvrirAssistant(page)
  const zone = panneau.getByPlaceholder('Posez votre question en français…')
  await expect(zone).toBeEnabled({ timeout: 60_000 })
  await zone.fill(QUESTION)
  const debut = tailleDe(PG)
  const debutIa = tailleDe(IA_LOG)
  const rep = page.waitForResponse((r) => r.request().method() === 'POST' && /\/api\/fastapi\/sql-agent\/query$/.test(new URL(r.url()).pathname), { timeout: 300_000 })
  await panneau.getByRole('button', { name: 'Envoyer' }).click()
  const r = await rep
  const corps = await r.json().catch(() => ({}))
  expect(r.status(), `${qui} : réponse de l'assistant ${J(corps).slice(0, 400)}`).toBe(200)
  await expect(zone, 'tour terminé').toBeEnabled({ timeout: 60_000 })
  return { corps, panneau, ...(await apresTour(qui, debut, debutIa, corps)) }
}
/** Même question par la route du service IA, jeton du compte en Bearer (témoin d'une autre société, sans écran). */
async function demanderApi(ctx, qui) {
  const jeton = (await ctx.storageState()).cookies.find((c) => c.name === 'access_token')?.value
  expect(jeton, `${qui} : jeton d'accès`).toBeTruthy()
  const debut = tailleDe(PG)
  const debutIa = tailleDe(IA_LOG)
  const r = await ctx.post(`${IA}/sql-agent/query`, { headers: { authorization: `Bearer ${jeton}` }, data: { question: QUESTION }, timeout: 300_000 })
  const corps = await r.json().catch(() => ({}))
  expect(r.status(), `${qui} : réponse de l'assistant ${J(corps).slice(0, 400)}`).toBe(200)
  return { corps, ...(await apresTour(qui, debut, debutIa, corps)) }
}
async function apresTour(qui, debut, debutIa, corps) {
  await journauxDuTourEcrits(debut)
  const entrees = entreesAgent(debut)
  let ia = []
  try { ia = readFileSync(IA_LOG).subarray(debutIa).toString('utf8').split('\n').filter((l) => /SECURITE|Traceback|Error|repli sur/.test(l)).map((l) => l.slice(0, 400)) } catch { /* journal absent */ }
  const metier = entrees.filter((e) => !/pg_catalog|^BEGIN|^ROLLBACK|^COMMIT|^show |^select (pg_catalog\.version|current_schema)/i.test(e.sql))
  console.log(`[ALEC52] ${qui} « ${QUESTION} » → réponse=${J(corps.answer || '')} ; data=${J(corps.data || null).slice(0, 300)} ; requêtes agent (${entrees.length}, utiles : ${J(metier.slice(0, 14))}) ; journal IA : ${J(ia.slice(0, 10))}`)
  expect(entrees.length, `${qui} : le journal Postgres voit l'agent sous sql_agent_ro pendant le tour`).toBeGreaterThan(0)
  return { entrees, ia }
}

// ── comptes d'essai : rôle SYSTÈME du registre livré, connectés par l'écran ──────────────────────────────────
async function roleReel(nom) {
  const r = await py(`from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
r = Role.objects.get(company_id=${SOC}, nom=${J(nom)})
reg = set(dict(CANONICAL_SYSTEM_ROLES)[${J(nom)}])
sortie(dict(pk=r.pk, manque=sorted(reg - set(r.permissions)), plus=sorted(set(r.permissions) - reg)))`)
  expect([r.manque, r.plus], `rôle « ${nom} » en base = registre livré`).toEqual([[], []])
  return r
}
const ouverts = []
const comptes = []
async function directeurA(context, suivi, testInfo) {
  const username = `alec52d_${marque()}`
  const role = await roleReel('Directeur')
  await py(`u = compte(${J(username)}, role=${role.pk}, societe=${SOC})
u.first_name = 'Essai'; u.save(update_fields=['first_name'])
sortie(u.id)`)
  comptes.push(username)
  const ctx = await context.browser().newContext({ baseURL: testInfo.project.use.baseURL, serviceWorkers: 'block', storageState: { cookies: [], origins: [] } })
  ouverts.push(ctx)
  const p = suivi.surveiller(await ctx.newPage())
  await p.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await uiLoginJusquAuxApps(p, { username, password: MDP_ESSAI })
  await brancherIA(p)
  await p.goto('/apps')
  return { p, ctx, username }
}
test.afterEach(async () => {
  // Contexte navigateur (close) ou contexte de requêtes API (dispose).
  for (const c of ouverts.splice(0)) await (typeof c.dispose === 'function' ? c.dispose() : c.close()).catch(() => undefined)
  for (const u of comptes.splice(0)) {
    await py(`U.objects.filter(username=${J(u)}).update(is_active=False)
sortie(1)`).catch(() => null)
  }
})

/** Facture émise par la VRAIE chaîne (devis atomique → envoi → acceptation → facture complète), sous la session
 *  `r` ; désignation unique, prix unique. Rend {reference, ttc, id, designation, societe}. */
async function factureCreee(r, m) {
  const designation = `Article ALEC52 ${m}`
  const produit = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: designation, prix_vente: '4873.19', prix_achat: '3000.00' } }), 'produit')
  const client = await py(`from apps.crm.models import Client
sortie(Client.objects.create(company_id=${SOC}, nom='ALEC52 ${m}', prenom='Essai', email='alec52-${m}@example.invalid').pk)`)
  const devis = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { client, taux_tva: '20.00', lignes: [{ produit: produit.id, designation, quantite: '1.00', prix_unitaire: '4873.19', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  await lireJson(await r.post(`${API}/ventes/devis/${devis.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await r.post(`${API}/ventes/devis/${devis.id}/accepter/`, { ...T, data: { nom: 'Client ALEC52' } }), 'acceptation')
  await lireJson(await r.post(`${API}/ventes/devis/${devis.id}/facturer-complet/`, { ...T, data: { remplacer_brouillons: true } }), 'facture complète')
  const f = await py(`from apps.facturation.models import Facture
f = Facture.objects.filter(company_id=${SOC}, devis_id=${Number(devis.id)}).order_by('-id').first()
sortie(dict(id=f.pk, reference=f.reference, ttc=str(f.total_ttc_stocke if f.total_ttc_stocke is not None else f.montant_ttc), statut=f.statut,
  lignes=list(f.lignes.values_list('designation', flat=True)), societe=f.company_id))`)
  console.log(`[ALEC52] facture créée : ${J(f)}`)
  expect(f.reference, 'facture créée avec une référence').toBeTruthy()
  expect(f.lignes, 'la facture porte la désignation unique').toContain(designation)
  return { ...f, designation }
}
const formesMontant = (ttc) => {
  const n = Number(ttc)
  if (!Number.isFinite(n) || n <= 0) return []
  const deux = n.toFixed(2)
  const [e, d] = deux.split('.')
  const milliers = (s, sep) => s.replace(/\B(?=(\d{3})+(?!\d))/g, sep)
  return [...new Set([deux, `${e},${d}`, `${milliers(e, ',')}.${d}`, `${milliers(e, '.')},${d}`])]
}

// ═══ PF6 — ALEC52 : préconditions du défaut (RLS FORCE, rôle sans BYPASSRLS, POSTGRES_RLS_ENABLED absent) ═══
etape('PF6-ALEC52-preconditions-rls', ['ALEC52'], async ({ page }) => {
  const base = await py(`import os
from django.db import connection
with connection.cursor() as c:
    c.execute("SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relkind = 'r' AND relname IN ('ventes_devis', 'ventes_facture', 'ventes_paiement')")
    rls = {r[0]: [bool(r[1]), bool(r[2])] for r in c.fetchall()}
    c.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'sql_agent_ro'")
    role = [bool(x) for x in (c.fetchone() or [])]
    c.execute("SELECT pg_get_expr(polqual, polrelid) FROM pg_policy WHERE polrelid = 'ventes_facture'::regclass")
    pol = [r[0] for r in c.fetchall()]
sortie(dict(rls=rls, role=role, politique=pol, django_rls=os.environ.get('POSTGRES_RLS_ENABLED')))`)
  console.log(`[ALEC52] préconditions en base : ${J(base)}`)
  expect(base.rls, 'RLS active ET forcée (AUD422) sur ventes_devis / ventes_facture / ventes_paiement').toEqual({
    ventes_devis: [true, true], ventes_facture: [true, true], ventes_paiement: [true, true],
  })
  expect(base.role, 'sql_agent_ro : ni superutilisateur, ni BYPASSRLS').toEqual([false, false])
  expect(base.politique.some((q) => /current_setting\('app\.current_company'/.test(q)), 'politique de ventes_facture sur app.current_company').toBe(true)
  // Environnement du PROCESSUS uvicorn (service IA) : POSTGRES_RLS_ENABLED absent ou vide, agent sous sql_agent_ro.
  let svc = null
  for (const pid of readdirSync('/proc').filter((x) => /^\d+$/.test(x))) {
    let cmd = ''
    try { cmd = readFileSync(`/proc/${pid}/cmdline`).toString().replace(/\0/g, ' ') } catch { continue }
    if (!/uvicorn/.test(cmd) || !/app\.main:app/.test(cmd)) continue
    const env = readFileSync(`/proc/${pid}/environ`).toString().split('\0')
    svc = { pid, cmd: cmd.trim(), rls: env.filter((x) => x.startsWith('POSTGRES_RLS_ENABLED=')), user: env.filter((x) => x.startsWith('SQL_AGENT_DB_USER=')) }
    break
  }
  console.log(`[ALEC52] service IA : ${J(svc)}`)
  expect(svc, 'processus uvicorn du service IA trouvé').toBeTruthy()
  expect(svc.rls.filter((x) => x !== 'POSTGRES_RLS_ENABLED='), 'service IA : POSTGRES_RLS_ENABLED absent ou vide (comme en prod)').toEqual([])
  expect(svc.user, 'service IA : agent sous sql_agent_ro').toEqual(['SQL_AGENT_DB_USER=sql_agent_ro'])
  expect(base.django_rls || '', 'Django : POSTGRES_RLS_ENABLED absent ou vide').not.toBe('1')
  // Trace lisible : ce que l'étape vient d'affirmer est affiché dans la page capturée (plus de page blanche).
  await tracer(page, 'ALEC52 — préconditions du défaut (base relue sous erp_user, environnement du service IA)', [
    ['pg_class (relrowsecurity, relforcerowsecurity) — ventes_devis / ventes_facture / ventes_paiement', base.rls],
    ['pg_roles sql_agent_ro (rolsuper, rolbypassrls)', base.role],
    ['pg_policy de ventes_facture', base.politique],
    [`processus uvicorn ${svc.pid} : ${svc.cmd}`, { POSTGRES_RLS_ENABLED: svc.rls.length ? svc.rls : 'absent', SQL_AGENT_DB_USER: svc.user }],
    ['Django : POSTGRES_RLS_ENABLED', base.django_rls ?? 'absent'],
  ])
})

// ═══ PF6 — ALEC52 : le Directeur crée une facture puis « liste mes factures » ⇒ elle est citée ; GUC de SA société
//      posé dans la transaction de chaque lecture de l'agent ═══
etape('PF6-ALEC52-facture-vue-par-l-assistant', ['ALEC52'], async ({ page, context, suivi, testInfo }) => {
  await page.close() // la capture d'étape prend le navigateur du Directeur, pas l'onglet vide du projet
  const m = marque()
  const societe = await py(`sortie(${SOC})`)
  const dir = await directeurA(context, suivi, testInfo)
  // Le DIRECTEUR crée la facture (sa session, la vraie chaîne devis → facture).
  const f = await factureCreee(dir.ctx.request, m)
  expect(f.societe, 'facture de la société du Directeur').toBe(societe)
  // Mécanisme, relu en base sous sql_agent_ro : sans GUC la facture est invisible (le défaut), avec le GUC de A elle
  // est vue, et le GUC local ne survit pas à la fin de la transaction.
  const meca = await py(`import os
from django.conf import settings
try:
    import psycopg2 as drv
except ImportError:
    import psycopg as drv
d = settings.DATABASES['default']
cn = drv.connect(host=d['HOST'] or 'localhost', port=d['PORT'] or 5432, dbname=d['NAME'], user=os.environ['SQL_AGENT_DB_USER'], password=os.environ['SQL_AGENT_DB_PASSWORD'])
cur = cn.cursor()
cur.execute("SELECT count(*) FROM ventes_facture WHERE id = %s", [${Number(f.id)}]); sans = cur.fetchone()[0]
cn.rollback()
cur.execute("SELECT set_config('app.current_company', %s, true)", [str(${Number(societe)})])
cur.execute("SELECT count(*) FROM ventes_facture WHERE id = %s", [${Number(f.id)}]); avec = cur.fetchone()[0]
cn.rollback()
cur.execute("SELECT current_setting('app.current_company', true)"); apres = cur.fetchone()[0]
cn.rollback(); cn.close()
sortie(dict(sans=sans, avec=avec, apres=apres))`)
  console.log(`[ALEC52] mécanisme sous sql_agent_ro : ${J(meca)}`)
  expect(meca.sans, 'sql_agent_ro sans GUC : facture invisible (RLS FORCE — le défaut de prod)').toBe(0)
  expect(meca.avec, 'sql_agent_ro avec le GUC de la société : facture vue').toBe(1)
  expect(meca.apres || '', 'GUC local à la transaction : rien ne survit').toBe('')

  const t = await demanderEcran(dir.p, 'Directeur A')
  const reponse = t.corps.answer || ''
  const montants = formesMontant(f.ttc)
  const citee = sansEspace(reponse).includes(sansEspace(f.reference)) ? f.reference : montants.find((x) => sansEspace(reponse).includes(x))
  expect(citee, `Directeur A : la réponse cite la facture qu'il vient de créer (${f.reference} / ${montants.join(' | ')})`).toBeTruthy()
  expect(reponse, 'Directeur A : pas « aucune facture »').not.toMatch(AUCUNE)
  // L'ÉCRAN (tiroir Copilote) affiche cette référence/ce montant.
  await expect.poll(async () => sansEspace(await t.panneau.innerText()).includes(sansEspace(citee)), { timeout: 30_000, message: `tiroir : « ${citee} » affiché` }).toBe(true)
  // Journal Postgres : lecture(s) de ventes_facture exécutées sous sql_agent_ro, chacune dans une transaction où
  // `set_config('app.current_company', '<A>', true)` a été posé ; aucun GUC d'une autre société pendant le tour.
  const g = gucDesLectures(t.entrees, 'ventes_facture', societe)
  console.log(`[ALEC52] Directeur A : lectures ventes_facture ${J(g.lectures)} ; GUC vus ${J(g.gucs)}`)
  expect(g.lectures.length, 'Directeur A : la lecture de ventes_facture par l\'agent est exécutée').toBeGreaterThan(0)
  expect(g.fautes, `Directeur A : chaque lecture précédée, dans sa transaction, de set_config('app.current_company', '${societe}', true)`).toEqual([])
  expect(g.gucs, 'Directeur A : seul le GUC de SA société est posé').toEqual([String(societe)])
  expect(t.ia.filter((l) => /Traceback/.test(l)), 'service IA : aucune exception').toEqual([])
})

// ═══ PF6 — ALEC52 : témoin d'isolement — le Directeur d'une AUTRE société ne voit pas la facture de A ═══
etape('PF6-ALEC52-isolement-autre-societe', ['ALEC52'], async ({ page, context, suivi, testInfo }) => {
  suivi.verifie(9)
  const m = marque()
  const societeA = await py(`sortie(${SOC})`)
  const fa = await factureCreee(context.request, m) // facture de A (session demo_admin), désignation unique
  const b = await py(`from decimal import Decimal
from authentication.models import Company
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from apps.crm.models import Client
from apps.facturation.models import Facture
co = Company.objects.create(slug='alec52-b-${m}', nom='ALEC52 B ${m}')
rd = Role.objects.create(company=co, nom='Directeur', permissions=list(DIRECTEUR_PERMISSIONS), est_systeme=True)
u = compte('alec52b_${m}', role=rd.pk, societe=co.pk)
cl = Client.objects.create(company=co, nom='Cli ALEC52 B', prenom='X', email='alec52b-${m}@example.invalid')
f = Facture.objects.create(company=co, reference='FAC-ALEC52B-${m}', client=cl, statut='emise', taux_tva=Decimal('20.00'))
sortie(dict(societe=co.pk, username=u.username, reference=f.reference, facture=f.pk))`)
  comptes.push(b.username)
  console.log(`[ALEC52] société B : ${J(b)}`)
  expect(b.societe, 'B ≠ A').not.toBe(societeA)
  const ctxB = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  ouverts.push(ctxB)
  await connexionApi(ctxB, { username: b.username, password: MDP_ESSAI })
  const t = await demanderApi(ctxB, 'Directeur B')
  const reponse = t.corps.answer || ''
  const donnees = J(t.corps.data || null)
  expect(sansEspace(reponse), 'Directeur B : la référence de la facture de A n\'est jamais citée').not.toContain(sansEspace(fa.reference))
  expect(donnees, 'Directeur B : la facture de A n\'est dans aucune donnée servie').not.toContain(fa.reference)
  for (const x of formesMontant(fa.ttc)) expect(sansEspace(reponse), `Directeur B : le montant de A (${x}) n'est pas servi`).not.toContain(x)
  expect(sansEspace(reponse), 'Directeur B : aucune facture de démo de A').not.toMatch(/FAC-DEMO-000\d/)
  // Témoin positif : B voit SA facture (le GUC porte SA société, pas un résultat vide par construction).
  expect(sansEspace(reponse), `Directeur B : sa propre facture ${b.reference} citée`).toContain(sansEspace(b.reference))
  const g = gucDesLectures(t.entrees, 'ventes_facture', b.societe)
  console.log(`[ALEC52] Directeur B : lectures ventes_facture ${J(g.lectures)} ; GUC vus ${J(g.gucs)}`)
  expect(g.lectures.length, 'Directeur B : la lecture de ventes_facture par l\'agent est exécutée').toBeGreaterThan(0)
  expect(g.fautes, `Directeur B : chaque lecture sous set_config('app.current_company', '${b.societe}', true)`).toEqual([])
  expect(g.gucs, 'Directeur B : seul le GUC de SA société, jamais celui de A').toEqual([String(b.societe)])
  // Trace lisible : réponse servie à B et lignes GUC / lectures de ventes_facture du journal Postgres du tour.
  await tracer(page, `ALEC52 — témoin d'isolement : Directeur de la société B (${b.societe}) ; facture de A = ${fa.reference}`, [
    [`Question de B : « ${QUESTION} » — réponse de l'assistant`, reponse],
    ['Journal Postgres du tour (sql_agent_ro) : set_config app.current_company', t.entrees.filter((e) => GUC.test(e.sql)).map((e) => `[${e.pid}] ${e.sql}`)],
    ['Lectures de ventes_facture par l\'agent et GUC posé dans leur transaction', g.lectures],
  ])
})
