// Preuves en direct du groupe ALEC, lot 4 (vague d'acceptation 6, runner GitHub) : ALEC6, ALEC16, ALEC18,
// ALEC22, ALEC23, ALEC24, ALEC28, ALEC29, ALEC42, ALEC43 (ALEC5 : alec5.spec.js) (décisions D-ALEC du 11/11 : portée du rôle,
// montants d'achat masqués). Chaque étape joue ce que LIT chaque rôle LIVRÉ (rôle système de la société démo relu par
// son nom et comparé au registre `CANONICAL_SYSTEM_ROLES` — jamais un rôle fabriqué) par la VRAIE route, sous un vrai
// compte connecté par /token/ (clé absente / à null, ligne absente, 403/404), puis, quand la clause nomme un écran,
// l'AFFIRME sous un compte connecté par l'écran de connexion. Données propres à l'étape (marque unique) posées par le
// shell Django, retirées à la fin. La sonde hôte du constat est rejouée : si elle s'exécute, `repro` doit être faux ;
// une sonde dont les bouchons ne suivent plus le code corrigé est NOMMÉE (annotation), jamais comptée comme preuve.
// ALEC16 (agent SQL FastAPI) : l'outil sécurisé RÉEL (`_make_secure_query_tool`) dans le venv FastAPI
// (`E2E_IA_PYTHON`), droits lus par le vrai `resolve_caller_permissions` (→ `/auth/me/` du Django du rejeu), requêtes
// exécutées sur la base du rejeu ; aucune clé de LLM en jeu (la garde est en amont du modèle).
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { delimiter, join } from 'node:path'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, connexionApi, uiLoginJusquAuxApps } from '../helpers.js'

const etape = groupe('ALEC', ['ALEC6', 'ALEC16', 'ALEC18', 'ALEC42', 'ALEC43', 'ALEC22', 'ALEC23', 'ALEC24', 'ALEC28',
  'ALEC29'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 420_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const SOC = `U.objects.get(username='demo_admin').company_id`
const J = (x) => JSON.stringify(x)
const note = (testInfo, type, description) => {
  testInfo.annotations.push({ type, description })
  console.log(`[ALEC4] ${type} : ${description}`)
}

// ── Sondes hôte du dossier (docs/audits/sondes/ALEC/<constat>.py) ──────────────────────────────────────────────────
function sonde(constat) {
  const r = spawnSync(process.env.E2E_PYTHON || 'python', [`docs/audits/sondes/ALEC/${constat}.py`], {
    cwd: RACINE, encoding: 'utf8', maxBuffer: 50_000_000,
    env: { ...process.env, PYTHONPATH: [join(RACINE, 'backend/django_core'), process.env.PYTHONPATH].filter(Boolean).join(delimiter) },
  })
  try {
    const d = JSON.parse(r.stdout)
    return { ok: true, repro: d.repro }
  } catch {
    return { ok: false, erreur: ((r.stderr || r.stdout || '').trim().split('\n').pop() || `code ${r.status}`).slice(0, 300) }
  }
}
/** Sonde rejouée : si elle s'exécute, `repro` doit être faux ; sinon (bouchon périmé) elle est nommée, non comptée. */
function sondeApres(testInfo, constat) {
  const s = sonde(constat)
  note(testInfo, s.ok ? `sonde ${constat}` : `sonde ${constat} périmée (non comptée)`, s.ok ? `repro=${s.repro}` : s.erreur)
  if (s.ok) expect(s.repro, `sonde ${constat} après correctif`).toBe(false)
  return s
}

// ── Comptes aux rôles LIVRÉS ───────────────────────────────────────────────────────────────────────────────────────
async function roleReel(nom) {
  const r = await py(`from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
r = Role.objects.get(company_id=${SOC}, nom=${J(nom)})
reg = set(dict(CANONICAL_SYSTEM_ROLES)[${J(nom)}])
sortie(dict(pk=r.pk, manque=sorted(reg - set(r.permissions)), plus=sorted(set(r.permissions) - reg)))`)
  expect([r.manque, r.plus], `rôle « ${nom} » en base = registre livré`).toEqual([[], []])
  return r.pk
}
const sessions = []
/** Compte d'essai au rôle livré `nomRole`, connecté par `/token/` ; {ctx, id, username, role}. */
async function session(testInfo, prefixe, nomRole) {
  const username = `${prefixe}_${marque()}`
  const id = await py(`u = compte(${J(username)}, role=${await roleReel(nomRole)}, societe=${SOC})
sortie(u.id)`)
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(ctx, { username, password: MDP_ESSAI })
  const s = { ctx, id, username, role: nomRole }
  sessions.push(s)
  return s
}
const ouverts = []
test.afterEach(async () => {
  for (const c of ouverts.splice(0)) await c.close().catch(() => undefined)
  const noms = sessions.splice(0).map((s) => { s.ctx.dispose().catch(() => undefined); return s.username })
  if (noms.length) await py(`U.objects.filter(username__in=${J(noms)}).update(is_active=False)
sortie(1)`).catch(() => null)
})

/** Toutes les lignes d'une liste DRF (paginée ou non) ; `next` ramené au chemin relatif. */
async function lignes(ctx, url) {
  const out = []
  let suivant = url
  while (suivant) {
    const r = await ctx.get(suivant, T)
    expect(r.status(), `${url} → ${(await r.text()).slice(0, 200)}`).toBe(200)
    const d = await r.json()
    if (Array.isArray(d)) return out.concat(d)
    out.push(...(d.results || []))
    suivant = d.next ? (() => { const u = new URL(d.next, 'http://x'); return `${u.pathname}${u.search}` })() : null
  }
  return out
}
const statut = async (ctx, url) => (await ctx.get(url, T)).status()
async function json200(ctx, url, quoi) {
  const r = await ctx.get(url, T)
  expect(r.status(), `${quoi} : ${url} → ${(await r.text()).slice(0, 300)}`).toBe(200)
  return r.json()
}

/** Écran sous un compte d'essai (connexion par l'ÉCRAN de connexion, accueil déjà vu), observé par les oracles. */
async function ecranSous(context, suivi, testInfo, s) {
  const ctx = await context.browser().newContext({
    baseURL: testInfo.project.use.baseURL, serviceWorkers: 'block', storageState: { cookies: [], origins: [] },
  })
  ouverts.push(ctx)
  await ctx.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  const p = suivi.surveiller(await ctx.newPage())
  await uiLoginJusquAuxApps(p, { username: s.username, password: MDP_ESSAI })
  const visites = await ctx.request.get(`${API}/onboarding/tours/`, T)
  if (visites.ok()) {
    for (const v of await visites.json()) {
      if (!v.vu) await ctx.request.post(`${API}/onboarding/tours/${v.tour_key}/vu/`, T)
    }
  }
  return p
}

const ECART_SONDE = { base: 'FAIL', raison: 'sonde périmée depuis ATST13 d611254e2 : registre des permissions enregistré sur une copie runpy ; 016/020/025 extraient le corps corrigé sans ses imports — rejeu Given/When/Then réel' }

// ══ ALEC6 — référentiel des transporteurs (chantiers) : clé `tarif_base` absente sans prix_achat_voir ═════════════════
etape('PF6.1-ALEC6-transporteurs', ['ALEC6'], async ({ testInfo }) => {
  sondeApres(testInfo, 'C-ALEC-004')
  const m = marque()
  const tech = await session(testInfo, 'alec6t', 'Technicien')
  const dir = await session(testInfo, 'alec6d', 'Directeur')
  const tid = await py(`from decimal import Decimal
from apps.installations.models import Transporteur
sortie(Transporteur.objects.create(company_id=${SOC}, nom=${J(`ALEC6 Transport ${m}`)}, tarif_base=Decimal('350'), active=True).pk)`)
  try {
    const base = `${API}/installations/transporteurs/`
    const listeT = await lignes(tech.ctx, base)
    const ligneT = listeT.find((t) => t.id === tid)
    expect(ligneT, 'Technicien : le transporteur listé (200)').toBeTruthy()
    expect('tarif_base' in ligneT, 'Technicien : liste sans la clé tarif_base').toBe(false)
    expect(listeT.some((t) => 'tarif_base' in t), 'Technicien : aucune ligne ne porte tarif_base').toBe(false)
    const detT = await json200(tech.ctx, `${base}${tid}/`, 'Technicien détail')
    expect([detT.nom, 'tarif_base' in detT], 'Technicien : détail 200 sans tarif_base').toEqual([`ALEC6 Transport ${m}`, false])
    const listeD = await lignes(dir.ctx, base)
    expect(Number(listeD.find((t) => t.id === tid).tarif_base), 'Directeur : liste tarif_base 350').toBe(350)
    expect(Number((await json200(dir.ctx, `${base}${tid}/`, 'Directeur détail')).tarif_base), 'Directeur : détail 350').toBe(350)
    // PATCH du tarif par un rôle d'écriture : accepté, la donnée n'est jamais perdue (persistance relue).
    const pa = await dir.ctx.patch(`${base}${tid}/`, { ...T, data: { tarif_base: '420.00' } })
    expect(pa.status(), `PATCH Directeur : ${(await pa.text()).slice(0, 200)}`).toBe(200)
    expect(Number((await json200(dir.ctx, `${base}${tid}/`, 'Directeur relu')).tarif_base), 'Directeur relu : 420').toBe(420)
    expect(await py(`from apps.installations.models import Transporteur
sortie(str(Transporteur.objects.get(pk=${tid}).tarif_base))`), 'base : 420 gardé').toBe('420.00')
    const detT2 = await json200(tech.ctx, `${base}${tid}/`, 'Technicien relu')
    expect('tarif_base' in detT2, 'Technicien relu : toujours sans tarif_base').toBe(false)
  } finally {
    await py(`from apps.installations.models import Transporteur
Transporteur.objects.filter(pk=${tid}).delete()
sortie(1)`).catch(() => null)
  }
})

// ══ ALEC16 — agent SQL FastAPI : droit du module + portée du rôle (outil sécurisé réel) ═════════════════════
const IA = `
import json, os, sys
sys.path.insert(0, os.getcwd())
os.environ['DJANGO_INTERNAL_URL'] = 'http://127.0.0.1:8000'
os.environ['DJANGO_INTERNAL_HOST'] = 'localhost'
from app.services.action_tools import ActionContext, resolve_caller_permissions
from app.services import sql_agent_service as s
from langchain_community.utilities import SQLDatabase
a = json.loads(sys.argv[1])
ctx = resolve_caller_permissions(ActionContext(a['company_id'], '', None, a['token']))
perms = list(ctx.permissions)
# Même dérivation que SQLAgentService (allow_price L17, allow_pii ALEC15, permissions ALEC16).
allow_price = 'prix_achat_voir' in perms
allow_pii = 'client_pii_voir' in perms
permissions = perms or None
db = SQLDatabase.from_uri(a['db'], include_tables=['sav_ticket', 'crm_client'], sample_rows_in_table_info=0)
outil = s._make_secure_query_tool(db, a['company_id'], allow_price, allow_pii, permissions)
refus = (s._UNSAFE_QUERY_REPLY, s._FORBIDDEN_TOOL_REPLY)
res = dict(n_permissions=len(perms), allow_price=allow_price, allow_pii=allow_pii,
           scope=sorted(p for p in perms if p.startswith('records_scope_')), cas={})
for sql in a['sql']:
    c = {}
    try:
        c['securise'] = s._validate_and_secure(sql, a['company_id'], allow_price=allow_price, allow_pii=allow_pii, permissions=permissions)
    except s.SQLSecurityError as e:
        c['refus'] = str(e)
    # Appel direct SANS permissions (tests, outils système) : inchangé.
    try:
        c['sans_permissions'] = s._validate_and_secure(sql, a['company_id'], allow_price=True, allow_pii=True, permissions=None)
    except s.SQLSecurityError as e:
        c['sans_permissions_refus'] = str(e)
    out = outil._run(sql)
    c['outil_refuse'] = out in refus or str(out).startswith(s._REFUS_DE_DROIT_PREFIXE)  # ALEC51 : refus de droit motivé
    c['outil'] = str(out)[:300]
    res['cas'][sql] = c
print('@@' + json.dumps(res, default=str))
`
async function agentSql(s, companyId, sqls) {
  const py3 = process.env.E2E_IA_PYTHON
  expect(py3, 'E2E_IA_PYTHON (venv des dépendances FastAPI) posé par le workflow').toBeTruthy()
  const jeton = (await s.ctx.storageState()).cookies.find((c) => c.name === 'access_token')?.value
  expect(jeton, `${s.role} : jeton d'accès`).toBeTruthy()
  const arg = J({ token: jeton, company_id: companyId, sql: sqls, db: process.env.E2E_IA_DB || 'postgresql://erp_user:ci_password@localhost:5432/erp_db' })
  const r = spawnSync(py3, ['-c', IA, arg], { cwd: join(RACINE, 'backend/fastapi_ia'), encoding: 'utf8', maxBuffer: 50_000_000 })
  const l = (r.stdout || '').split('\n').filter((x) => x.startsWith('@@')).pop()
  expect(l, `outil SQL (${s.role}) : ${(r.stderr || '').slice(-800)}`).toBeTruthy()
  const res = JSON.parse(l.slice(2))
  console.log(`[ALEC4] agent SQL ${s.role} : ${J(res).slice(0, 1800)}`)
  return res
}
const societe = () => py(`sortie(${SOC})`)

etape('PF6.4-ALEC16-agent-sql-module-portee', ['ALEC16'], async ({ testInfo }) => {
  sondeApres(testInfo, 'C-ALEC-014')
  const cid = await societe()
  const FAC = 'SELECT reference FROM ventes_facture'
  const DEV = 'SELECT reference FROM ventes_devis'
  const CH = 'SELECT reference FROM installations_installation'
  const tech = await session(testInfo, 'alec16t', 'Technicien')
  const t = await agentSql(tech, cid, [FAC, CH])
  expect(t.cas[FAC].refus, 'Technicien : ventes_facture refusée (module)').toMatch(/droit du module manquant/)
  expect(t.cas[CH].refus, 'Technicien : installations_installation refusée (portée équipe)').toMatch(/Portee restreinte/)
  expect([t.cas[FAC].outil_refuse, t.cas[CH].outil_refuse], 'Technicien : refusées par l\'outil, sans exécution').toEqual([true, true])
  const com = await session(testInfo, 'alec16c', 'Commercial')
  const c = await agentSql(com, cid, [DEV])
  expect(c.scope, 'Commercial : portée « soi » lue par /auth/me/').toEqual(['records_scope_soi'])
  expect(c.cas[DEV].refus, 'Commercial (soi) : ventes_devis refusée (portée)').toMatch(/Portee restreinte/)
  expect(c.cas[DEV].outil_refuse, 'Commercial : sans exécution').toBe(true)
  const dir = await session(testInfo, 'alec16d', 'Directeur')
  const d = await agentSql(dir, cid, [FAC, DEV])
  for (const q of [FAC, DEV]) {
    expect(d.cas[q].refus, `Directeur : ${q} accepté`).toBeUndefined()
    expect(d.cas[q].securise, `Directeur : ${q} réécrit filtré par société`).toContain(`company_id = ${cid}`)
    expect(d.cas[q].outil_refuse, `Directeur : ${q} passe l'outil`).toBe(false)
    expect(/"contenu": "Error/.test(d.cas[q].outil), `Directeur : ${q} exécuté : ${d.cas[q].outil}`).toBe(false)
  }
  for (const [qui, r] of [['Technicien', t], ['Commercial', c]]) {
    for (const q of Object.keys(r.cas)) {
      expect(r.cas[q].sans_permissions_refus, `${qui} : appel sans permissions inchangé (${q})`).toBeUndefined()
      expect(r.cas[q].sans_permissions, `${qui} : sans permissions, filtre société seul (${q})`).toContain(`company_id = ${cid}`)
    }
  }
})

// ══ ALEC18 / ALEC42 / ALEC43 — GED : documents, demandes de signature et coordonnées des signataires ══════════════════
const nettoyerGed = (m) => py(`from apps.ged.models import Cabinet
for c in Cabinet.objects.filter(company_id=${SOC}, nom__startswith='ALEC4 ${m}'):
    try: c.delete()
    except Exception: pass
sortie(1)`).catch(() => null)

etape('PF6.3-ALEC18-ged-documents', ['ALEC18'], async ({ context, suivi, testInfo }) => {
  sondeApres(testInfo, 'C-ALEC-016')
  const m = marque()
  const c1 = await session(testInfo, 'alec18c1', 'Commercial')
  const c2 = await session(testInfo, 'alec18c2', 'Commercial')
  const terrain = await session(testInfo, 'alec18t', 'Commercial terrain')
  const rh = await session(testInfo, 'alec18rh', 'Admin RH')
  const dir = await session(testInfo, 'alec18d', 'Directeur')
  try {
    const ids = await py(`from apps.ged.models import Cabinet, Folder, Document
cab = Cabinet.objects.create(company_id=${SOC}, nom='ALEC4 ${m} 18')
fol = Folder.objects.create(company_id=${SOC}, cabinet=cab, nom='Dossier ALEC18 ${m}')
interne = Document.objects.create(company_id=${SOC}, folder=fol, nom='ALEC18-${m}-interne')
fac = Document.objects.create(company_id=${SOC}, folder=fol, nom='ALEC18-${m}-FAC.pdf', created_by_id=${c1.id}, custom_data={'routage_reference': 'FAC-${m}'})
up = Document.objects.create(company_id=${SOC}, folder=fol, nom='ALEC18-${m}-CIN.pdf', custom_data={'source_type': 'portail.piece', 'source_id': 1})
sortie(dict(interne=interne.pk, fac=fac.pk, up=up.pk))`)
    const vus = async (s) => new Set((await lignes(s.ctx, `${API}/ged/documents/?search=ALEC18-${m}`)).map((d) => d.id))
    for (const chemin of ['documents/', `documents/${ids.interne}/`, 'versions/']) {
      expect(await statut(terrain.ctx, `${API}/ged/${chemin}`), `Commercial terrain : ${chemin} 403`).toBe(403)
    }
    expect([...await vus(rh)], 'Admin RH : document interne seul').toEqual([ids.interne])
    expect([...await vus(c2)], 'C2 : ni la facture de C1 ni l\'upload portail').toEqual([ids.interne])
    expect([...await vus(c1)].sort(), 'C1 : document interne + sa facture').toEqual([ids.interne, ids.fac].sort())
    expect([...await vus(dir)].sort(), 'Directeur : tout').toEqual([ids.interne, ids.fac, ids.up].sort())
    for (const id of [ids.fac, ids.up]) expect(await statut(c2.ctx, `${API}/ged/documents/${id}/`), `C2 détail ${id} 404`).toBe(404)
    // Écran GED en C2 : le dossier montre le document interne, jamais la facture de C1 (ni l'upload portail).
    const p = await ecranSous(context, suivi, testInfo, c2)
    await p.goto('/ged')
    const choix = p.getByRole('combobox', { name: 'Choisir le cabinet' })
    if (await choix.count()) {
      await choix.click()
      await p.getByRole('option', { name: `ALEC4 ${m} 18`, exact: true }).click()
    }
    await p.getByRole('treeitem').getByRole('button', { name: `Dossier ALEC18 ${m}` }).click()
    await expect(p.getByLabel(`Sélectionner ALEC18-${m}-interne`), 'écran GED C2 : document interne affiché').toBeVisible({ timeout: 30_000 })
    await expect(p.getByLabel(`Sélectionner ALEC18-${m}-FAC.pdf`), 'écran GED C2 : facture de C1 absente').toHaveCount(0)
    await expect(p.getByLabel(`Sélectionner ALEC18-${m}-CIN.pdf`), 'écran GED C2 : upload portail absent').toHaveCount(0)
    await p.reload()
    await expect(p.getByText(`ALEC18-${m}-FAC.pdf`), 'écran GED C2 rechargé : facture de C1 absente').toHaveCount(0)
  } finally {
    await nettoyerGed(m)
  }
}, { ecart: ECART_SONDE })

/** Document interne D (dossier commun, non produit) + demande de signature à deux destinataires créée par `dir`. */
async function demandeSignature(m, dir) {
  return py(`from apps.ged.models import Cabinet, Folder, Document, DemandeSignatureDocument, SignataireDemande
cab = Cabinet.objects.create(company_id=${SOC}, nom='ALEC4 ${m} sig')
fol = Folder.objects.create(company_id=${SOC}, cabinet=cab, nom='Dossier commun ALEC42 ${m}')
doc = Document.objects.create(company_id=${SOC}, folder=fol, nom='ALEC42-${m}-D')
dem = DemandeSignatureDocument.objects.create(company_id=${SOC}, document=doc, signataire_nom='Nadia ALEC42 ${m}',
    signataire_email='nadia-${m}@example.invalid', created_by_id=${dir.id}, adresse_ip='10.4.2.7', user_agent='Navigateur ALEC43 ${m}')
s1 = SignataireDemande.objects.create(company_id=${SOC}, demande=dem, nom='Amal ALEC42 ${m}', email='amal-${m}@example.invalid',
    telephone='+212600004201', ordre=1, statut='signe', adresse_ip='10.4.2.8', user_agent='Navigateur signe ${m}', date_action=timezone.now())
s2 = SignataireDemande.objects.create(company_id=${SOC}, demande=dem, nom='Badr ALEC42 ${m}', email='badr-${m}@example.invalid',
    telephone='+212600004202', ordre=2)
sortie(dict(doc=doc.pk, dem=dem.pk, s1=s1.pk, s2=s2.pk, nom_doc=doc.nom))`)
}

etape('PF6.3-ALEC42-ged-demandes-signature', ['ALEC42'], async ({ context, suivi, testInfo }) => {
  sondeApres(testInfo, 'C-ALEC-VER1-102')
  const m = marque()
  const terrain = await session(testInfo, 'alec42t', 'Commercial terrain')
  const com = await session(testInfo, 'alec42c', 'Commercial')
  const dir = await session(testInfo, 'alec42d', 'Directeur')
  try {
    const x = await demandeSignature(m, dir)
    const routes = [`${API}/ged/demandes-signature/`, `${API}/ged/demandes-signature/${x.dem}/`,
      `${API}/ged/demandes-signature/${x.dem}/pdf-signe/`, `${API}/ged/signataires-demande/?demande=${x.dem}`]
    for (const r of routes) expect(await statut(terrain.ctx, r), `Commercial terrain : ${r} 403`).toBe(403)
    for (const s of [com, dir]) {
      for (const r of routes) expect(await statut(s.ctx, r), `${s.role} : ${r} jamais 403`).not.toBe(403)
      expect((await lignes(s.ctx, routes[0])).map((d) => d.id), `${s.role} : liste 200 avec la demande`).toContain(x.dem)
      expect((await json200(s.ctx, routes[1], `${s.role} détail`)).id, `${s.role} : détail 200`).toBe(x.dem)
      expect((await lignes(s.ctx, routes[3])).map((d) => d.id).sort(), `${s.role} : destinataires 200`).toEqual([x.s1, x.s2].sort())
    }
    // Écran ApprobationPage du Directeur : onglet Signatures, la demande listée.
    const p = await ecranSous(context, suivi, testInfo, dir)
    for (const passe of ['', 'rechargé : ']) {
      if (passe) await p.reload(); else await p.goto('/ged/approbation')
      await p.getByRole('tab', { name: 'Signatures' }).click()
      await expect(p.getByRole('row').filter({ hasText: x.nom_doc }), `${passe}Directeur : la demande listée à l'écran`).toBeVisible({ timeout: 60_000 })
    }
  } finally {
    await nettoyerGed(m)
  }
})

etape('PF6.3-ALEC43-ged-coordonnees-signataires', ['ALEC43'], async ({ context, suivi, testInfo }) => {
  const m = marque()
  const rh = await session(testInfo, 'alec43rh', 'Admin RH')
  const com = await session(testInfo, 'alec43c', 'Commercial')
  const dir = await session(testInfo, 'alec43d', 'Directeur')
  try {
    const x = await demandeSignature(m, dir)
    const COORD = ['email', 'telephone', 'adresse_ip', 'user_agent']
    const lire = async (s) => ({
      dem: await json200(s.ctx, `${API}/ged/demandes-signature/${x.dem}/`, `${s.role} détail`),
      dest: await lignes(s.ctx, `${API}/ged/signataires-demande/?demande=${x.dem}`),
    })
    const r = await lire(rh)
    expect([r.dem.signataire_email, r.dem.adresse_ip, r.dem.user_agent], 'Admin RH : demande, coordonnées à null').toEqual([null, null, null])
    for (const [ou, liste] of [['listés', r.dest], ['imbriqués', r.dem.signataires || []]]) {
      expect(liste.length, `Admin RH : destinataires ${ou}`).toBe(2)
      for (const d of liste) {
        expect([d.nom, d.statut].every(Boolean), `Admin RH : nom et statut présents (${ou})`).toBe(true)
        for (const k of COORD) {
          expect(k in d, `Admin RH : clé ${k} gardée (${ou})`).toBe(true)
          expect(d[k], `Admin RH : ${k} à null (${ou} ${d.nom})`).toBeNull()
        }
      }
    }
    for (const s of [com, dir]) {
      const v = await lire(s)
      expect(v.dem.signataire_email, `${s.role} : e-mail de la demande présent`).toBe(`nadia-${m}@example.invalid`)
      expect(v.dem.adresse_ip, `${s.role} : IP de la demande`).toBe('10.4.2.7')
      const s1 = v.dest.find((d) => d.id === x.s1)
      expect([s1.email, s1.telephone, s1.adresse_ip, s1.user_agent], `${s.role} : coordonnées du signataire`)
        .toEqual([`amal-${m}@example.invalid`, '+212600004201', '10.4.2.8', `Navigateur signe ${m}`])
    }
    // Persistance : rendu seulement — la base garde les valeurs.
    expect(await py(`from apps.ged.models import DemandeSignatureDocument, SignataireDemande
d = DemandeSignatureDocument.objects.get(pk=${x.dem}); s = SignataireDemande.objects.get(pk=${x.s1})
sortie([d.signataire_email, d.adresse_ip, s.email, s.telephone, s.adresse_ip, s.user_agent])`), 'base inchangée')
      .toEqual([`nadia-${m}@example.invalid`, '10.4.2.7', `amal-${m}@example.invalid`, '+212600004201', '10.4.2.8', `Navigateur signe ${m}`])
    // Écran ApprobationPage : colonne « Email » à « — » en Admin RH, e-mail visible en Directeur.
    const ligneEcran = async (s) => {
      const p = await ecranSous(context, suivi, testInfo, s)
      await p.goto('/ged/approbation')
      await p.getByRole('tab', { name: 'Signatures' }).click()
      const row = p.getByRole('row').filter({ hasText: x.nom_doc })
      await expect(row, `${s.role} : la demande listée`).toBeVisible({ timeout: 60_000 })
      return row
    }
    const rowRh = await ligneEcran(rh)
    await expect(rowRh, 'écran Admin RH : signataire nommé').toContainText(`Nadia ALEC42 ${m}`)
    await expect(rowRh, 'écran Admin RH : e-mail absent').not.toContainText(`nadia-${m}@example.invalid`)
    await expect(rowRh.getByRole('gridcell', { name: '—', exact: true }).first(), 'écran Admin RH : colonne Email à « — »').toBeVisible()
    const rowDir = await ligneEcran(dir)
    await expect(rowDir, 'écran Directeur : e-mail visible').toContainText(`nadia-${m}@example.invalid`)
  } finally {
    await nettoyerGed(m)
  }
})

// ══ ALEC22 — reporting : tableau de bord, tableau commercial, classement, archive client bornés à la portée ═══════════
/** Client + devis signé + facture émise impayée créés par `uid` (montant HT `ht`). */
const affaire = (m, qui, uid, ht) => `from decimal import Decimal
from django.utils import timezone
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, Facture, LigneFacture
u = U.objects.get(pk=${uid})
cl = Client.objects.create(company_id=${SOC}, nom='Client ALEC ${qui} ${m}', created_by=u)
p = Produit.objects.create(company_id=${SOC}, nom='Kit ALEC ${qui} ${m}', sku='ALEC-${qui}-${m}', prix_vente=Decimal('${ht}'), quantite_stock=0)
dv = Devis.objects.create(company_id=${SOC}, reference='DEV-ALEC-${qui}-${m}', client=cl, statut=Devis.Statut.ACCEPTE,
    date_acceptation=timezone.localdate(), created_by=u)
LigneDevis.objects.create(devis=dv, produit=p, designation='Kit ${qui}', quantite=Decimal('1'), prix_unitaire=Decimal('${ht}'))
f = Facture.objects.create(company_id=${SOC}, reference='FAC-ALEC-${qui}-${m}', client=cl, statut=Facture.Statut.EMISE,
    taux_tva=Decimal('20'), montant_ht=Decimal('${ht}'), montant_tva=Decimal('${ht}') / 5, montant_ttc=Decimal('${ht}') * Decimal('1.2'), created_by=u)
LigneFacture.objects.create(facture=f, produit=p, designation='Kit ${qui}', quantite=Decimal('1'), prix_unitaire=Decimal('${ht}'))
sortie(dict(cl=cl.pk, nom_client=str(cl), p=p.pk, dv=dv.pk, f=f.pk))`
const nettoyerAffaires = (xs) => py(`from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, Facture, LigneFacture
for x in ${J(xs.filter(Boolean))}:
    LigneFacture.objects.filter(facture_id=x['f']).delete(); Facture.objects.filter(pk=x['f']).delete()
    LigneDevis.objects.filter(devis_id=x['dv']).delete(); Devis.objects.filter(pk=x['dv']).delete()
    Produit.objects.filter(pk=x['p']).delete(); Client.objects.filter(pk=x['cl']).delete()
sortie(1)`).catch(() => null)

etape('PF6.2-ALEC22-reporting-portee', ['ALEC22'], async ({ context, suivi, testInfo }) => {
  sondeApres(testInfo, 'C-ALEC-020')
  const m = marque()
  const a = await session(testInfo, 'alec22a', 'Commercial')
  const b = await session(testInfo, 'alec22b', 'Commercial')
  const cr = await session(testInfo, 'alec22cr', 'Commercial responsable')
  const dir = await session(testInfo, 'alec22d', 'Directeur')
  const xs = []
  try {
    xs.push(await py(affaire(m, 'A', a.id, 2000)))
    xs.push(await py(affaire(m, 'B', b.id, 1000)))
    const [xa, xb] = xs
    const lire = async (s) => {
      const dash = await json200(s.ctx, `${API}/reporting/dashboard/`, `${s.role} dashboard`)
      const comm = await json200(s.ctx, `${API}/reporting/commercial/dashboard/`, `${s.role} commercial`)
      const clas = await json200(s.ctx, `${API}/reporting/insights/sales-leaderboard/`, `${s.role} classement`)
      const ligne = (rows, qui) => rows.find((r) => r.commercial === qui.username)
      return {
        creances: (dash.creances || []).map((c) => String(c.client).trim()),
        lignes: (qui) => [ligne(comm.leaderboard, qui), ligne(clas.rows, qui)],
        archive: (cl) => statut(s.ctx, `${API}/reporting/archive/client/${cl}/`),
      }
    }
    const MONTANTS = ['ca_ht', 'nb_devis_signes', 'avg_deal_ht', 'kwc']
    const va = await lire(a)
    for (const lb of va.lignes(b)) {
      expect(lb, 'Commercial A : B nommé au classement').toBeTruthy()
      expect(MONTANTS.map((k) => lb[k]), 'Commercial A : montants de B à null').toEqual([null, null, null, null])
    }
    for (const la of va.lignes(a)) {
      expect(Number(la.ca_ht), 'Commercial A : son CA HT (2000)').toBeCloseTo(2000, 2)
      expect(la.nb_devis_signes, 'Commercial A : son devis signé').toBe(1)
    }
    expect(va.creances, 'Commercial A : sa créance').toContain(xa.nom_client.trim())
    expect(va.creances, 'Commercial A : client de B absent des créances').not.toContain(xb.nom_client.trim())
    expect(await va.archive(xb.cl), 'Commercial A : archive du client de B 404').toBe(404)
    expect(await va.archive(xa.cl), 'Commercial A : archive de son client 200').toBe(200)
    const vd = await lire(dir)
    for (const lb of vd.lignes(b)) {
      expect(Number(lb.ca_ht), 'Directeur : CA de B (1000)').toBeCloseTo(1000, 2)
      expect(lb.nb_devis_signes, 'Directeur : devis signé de B').toBe(1)
    }
    expect(vd.creances, 'Directeur : créance du client de B').toContain(xb.nom_client.trim())
    expect(await vd.archive(xb.cl), 'Directeur : archive du client de B 200').toBe(200)

    // Écran « Tableau commercial » (Classement) : un plain Commercial n'a pas l'écran (palier « normal », route
    // responsable/admin) — joué en Commercial responsable (portée sous-arbre : A et B hors de son sous-arbre) :
    // B nommé, « — » ; témoin Directeur : montants de B affichés.
    const classement = async (s) => {
      const p = await ecranSous(context, suivi, testInfo, s)
      await p.goto('/reporting/commercial')
      await p.getByRole('radio', { name: 'Classement' }).or(p.getByRole('button', { name: 'Classement' })).first().click()
      const row = p.getByRole('table', { name: 'Classement commerciaux' }).getByRole('row').filter({ hasText: b.username })
      await expect(row, `${s.role} : B nommé au classement à l'écran`).toBeVisible({ timeout: 60_000 })
      return row
    }
    const rowCr = await classement(cr)
    await expect(rowCr, 'écran Commercial responsable : aucun montant de B').not.toContainText('MAD')
    await expect(rowCr.getByRole('cell', { name: '—', exact: true }).first(), 'écran Commercial responsable : « — » chez B').toBeVisible()
    const rowDir = await classement(dir)
    await expect(rowDir, 'écran Directeur : CA de B affiché').toContainText('MAD')
  } finally {
    await nettoyerAffaires(xs)
  }
}, { ecart: ECART_SONDE })

// ══ ALEC23 — ventes/dashboard (quote-to-cash) sans ?mine=1 : ses seuls totaux, collègues sans montants ═══════════════
etape('PF6.2-ALEC23-quote-to-cash-portee', ['ALEC23'], async ({ testInfo }) => {
  sondeApres(testInfo, 'C-ALEC-020')
  const m = marque()
  const a = await session(testInfo, 'alec23a', 'Commercial')
  const b = await session(testInfo, 'alec23b', 'Commercial')
  const dir = await session(testInfo, 'alec23d', 'Directeur')
  const fx = await py(`from decimal import Decimal
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, Facture, LigneFacture
cl = Client.objects.create(company_id=${SOC}, nom='Client ALEC23 ${m}', created_by_id=${b.id})
p = Produit.objects.create(company_id=${SOC}, nom='Kit ALEC23 ${m}', sku='ALEC23-${m}', prix_vente=Decimal('10000'), quantite_stock=0)
out = dict(cl=cl.pk, p=p.pk, dv=[], f=[])
for uid, ref, prix in ((${a.id}, 'A', '5000'), (${b.id}, 'B', '10000')):
    dv = Devis.objects.create(company_id=${SOC}, reference='DEV-ALEC23-' + ref + '-${m}', client=cl, statut='envoye', created_by_id=uid)
    LigneDevis.objects.create(devis=dv, produit=p, designation='Kit ' + ref, quantite=Decimal('1'), prix_unitaire=Decimal(prix))
    out['dv'].append(dv.pk)
f = Facture.objects.create(company_id=${SOC}, reference='FAC-ALEC23-B-${m}', client=cl, statut=Facture.Statut.EMISE, taux_tva=Decimal('20'),
    montant_ht=Decimal('8000'), montant_tva=Decimal('1600'), montant_ttc=Decimal('9600'), created_by_id=${b.id})
LigneFacture.objects.create(facture=f, produit=p, designation='Kit B', quantite=Decimal('1'), prix_unitaire=Decimal('8000'))
out['f'].append(f.pk)
sortie(out)`)
  try {
    const url = `${API}/ventes/dashboard/`
    const ligneDe = (v, s) => (v.par_commercial || []).find((l) => l.commercial === s.username)
    const va = await json200(a.ctx, url, 'Commercial A')
    expect([va.devis.total, va.devis.envoyes], 'Commercial A : ses seuls devis (1 envoyé)').toEqual([1, 1])
    expect(Number(va.devis.valeur_pipeline), 'Commercial A : sa valeur pipeline').toBeGreaterThan(0)
    expect([va.factures.total, Number(va.factures.montant_facture), Number(va.factures.montant_encaisse)], 'Commercial A : aucune facture de B')
      .toEqual([0, 0, 0])
    const bVuParA = ligneDe(va, b)
    expect(bVuParA, 'Commercial A : B nommé dans par_commercial').toBeTruthy()
    expect([bVuParA.devis_actifs, bVuParA.valeur_pipeline], 'Commercial A : devis_actifs et valeur_pipeline de B à null').toEqual([null, null])
    expect(ligneDe(va, a)?.devis_actifs, 'Commercial A : sa ligne complète').toBe(1)
    const vd = await json200(dir.ctx, url, 'Directeur')
    const bVuParDir = ligneDe(vd, b)
    expect(bVuParDir?.devis_actifs, 'Directeur : devis_actifs de B').toBe(1)
    expect(Number(bVuParDir.valeur_pipeline), 'Directeur : valeur pipeline de B').toBeGreaterThan(0)
    expect(vd.devis.total, 'Directeur : les devis de A et de B comptés').toBeGreaterThanOrEqual(2)
    expect(vd.factures.total, 'Directeur : la facture de B comptée').toBeGreaterThanOrEqual(1)
  } finally {
    await py(`from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, Facture, LigneFacture
LigneFacture.objects.filter(facture_id__in=${J(fx.f)}).delete(); Facture.objects.filter(pk__in=${J(fx.f)}).delete()
LigneDevis.objects.filter(devis_id__in=${J(fx.dv)}).delete(); Devis.objects.filter(pk__in=${J(fx.dv)}).delete()
Produit.objects.filter(pk=${fx.p}).delete(); Client.objects.filter(pk=${fx.cl}).delete()
sortie(1)`).catch(() => null)
  }
}, { ecart: ECART_SONDE })

// ══ ALEC24 — objectifs commerciaux : cible, réalisé, taux à null hors portée ; owner_nom gardé ══════════════════════
etape('PF6.2-ALEC24-objectifs-portee', ['ALEC24'], async ({ context, suivi, testInfo }) => {
  sondeApres(testInfo, 'C-ALEC-020')
  const a = await session(testInfo, 'alec24a', 'Commercial')
  const b = await session(testInfo, 'alec24b', 'Commercial')
  const dir = await session(testInfo, 'alec24d', 'Directeur')
  const ob = await py(`from decimal import Decimal
from django.utils import timezone
from apps.crm.models import ObjectifCommercial
d = timezone.localdate()
mk = lambda metric, owner, cible: ObjectifCommercial.objects.create(company_id=${SOC}, metric=metric, period_type='month',
    period_year=d.year, period_month=d.month, cible=Decimal(cible), owner_id=owner).pk
sortie(dict(a=mk('nb_leads', ${a.id}, '10'), b=mk('nb_leads', ${b.id}, '12'), soc=mk('nb_contacts', None, '30')))`)
  try {
    const base = `${API}/crm/objectifs/`
    const C = ['cible', 'realise', 'taux']
    const lire = async (s) => ({
      att: Object.fromEntries((await json200(s.ctx, `${base}attainment/`, `${s.role} attainment`)).map((o) => [o.id, o])),
      une: await json200(s.ctx, `${base}${ob.b}/attainment/`, `${s.role} attainment de B`),
      liste: Object.fromEntries((await lignes(s.ctx, base)).map((o) => [o.id, o])),
    })
    const va = await lire(a)
    expect(C.map((k) => va.att[ob.a][k]).includes(null), 'Commercial A : son objectif complet').toBe(false)
    expect(va.liste[ob.a].cible, 'Commercial A : sa cible listée').not.toBeNull()
    for (const oid of [ob.b, ob.soc]) {
      expect(C.map((k) => va.att[oid][k]), `Commercial A : objectif ${oid} hors portée à null`).toEqual([null, null, null])
      expect(va.liste[oid].cible, `Commercial A : cible ${oid} listée à null`).toBeNull()
    }
    expect(va.att[ob.b].owner_nom, 'Commercial A : B reste nommé').toBe(b.username)
    expect(C.map((k) => va.une[k]), 'Commercial A : attainment de B à null').toEqual([null, null, null])
    const vd = await lire(dir)
    for (const oid of [ob.a, ob.b, ob.soc]) {
      expect(C.map((k) => vd.att[oid][k]).includes(null), `Directeur : objectif ${oid} complet`).toBe(false)
      expect(vd.liste[oid].cible, `Directeur : cible ${oid}`).not.toBeNull()
    }
    expect(C.map((k) => vd.une[k]).includes(null), 'Directeur : attainment de B complet').toBe(false)

    // Écran CrmInsightsPanel (cockpit CRM) en Commercial A : « — » sur l'objectif de B, chiffres sur le sien.
    const p = await ecranSous(context, suivi, testInfo, a)
    for (const passe of ['', 'rechargé : ']) {
      if (passe) await p.reload(); else await p.goto('/crm/cockpit')
      const panneau = p.getByTestId('crm-insights')
      const liB = panneau.getByRole('listitem').filter({ hasText: `— ${b.username}` })
      await expect(liB, `${passe}écran : objectif de B listé`).toBeVisible({ timeout: 60_000 })
      await expect(liB.getByText('—', { exact: true }), `${passe}écran : taux de B « — »`).toBeVisible()
      await expect(liB, `${passe}écran : réalisé et cible de B « — »`).toContainText('réalisé — / cible —')
      const liA = panneau.getByRole('listitem').filter({ hasText: `— ${a.username}` })
      await expect(liA, `${passe}écran : son objectif chiffré`).toContainText('%')
      await expect(liA, `${passe}écran : sa cible (10)`).toContainText('cible 10')
    }
  } finally {
    await py(`from apps.crm.models import ObjectifCommercial
ObjectifCommercial.objects.filter(pk__in=${J([ob.a, ob.b, ob.soc])}).delete()
sortie(1)`).catch(() => null)
  }
}, { ecart: ECART_SONDE })

// ══ ALEC28 — journal des réglages : journal_activite_voir exigé ══════════════════════════════════════════════════════
etape('PF6.4-ALEC28-journal-reglages', ['ALEC28'], async ({ context, suivi, testInfo }) => {
  sondeApres(testInfo, 'C-ALEC-024')
  const m = marque()
  const cr = await session(testInfo, 'alec28cr', 'Commercial responsable')
  const adm = await session(testInfo, 'alec28adm', 'Administrateur')
  const dir = await session(testInfo, 'alec28d', 'Directeur')
  const lid = await py(`from apps.parametres.models_audit import SettingsAuditLog
sortie(SettingsAuditLog.objects.create(company_id=${SOC}, user_id=${dir.id}, section='roles', field='alec28_${m}',
    field_label='ALEC28 ${m}', old_value='avant', new_value='apres').pk)`)
  try {
    const routes = [`${API}/parametres/audit/?section=roles`, `${API}/parametres/audit/sections/`]
    for (const s of [cr, adm]) for (const r of routes) expect(await statut(s.ctx, r), `${s.role} : ${r} 403`).toBe(403)
    const j = await json200(dir.ctx, `${routes[0]}&field=alec28_${m}`, 'Directeur journal')
    expect(j.results.map((x) => x.id), 'Directeur : 200 avec la ligne').toEqual([lid])
    expect(j.results[0].section, 'Directeur : section roles').toBe('roles')
    expect((await json200(dir.ctx, routes[1], 'Directeur sections')).sections, 'Directeur : sections 200').toBeTruthy()
    // Écran Paramètres › Avancé : la carte « Journal des modifications » absente en Commercial responsable, présente en Directeur.
    const avance = async (s) => {
      const p = await ecranSous(context, suivi, testInfo, s)
      await p.goto('/parametres?onglet=avance')
      await expect(p.getByText('Hypothèses ROI').first(), `${s.role} : onglet Avancé rendu`).toBeVisible({ timeout: 60_000 })
      return p
    }
    const pCr = await avance(cr)
    await expect(pCr.getByText('Journal des modifications'), 'écran Commercial responsable : carte absente').toHaveCount(0)
    await pCr.reload()
    await expect(pCr.getByText('Hypothèses ROI').first()).toBeVisible({ timeout: 60_000 })
    await expect(pCr.getByText('Journal des modifications'), 'écran Commercial responsable rechargé : carte absente').toHaveCount(0)
    const pDir = await avance(dir)
    await expect(pDir.getByText('Journal des modifications').first(), 'écran Directeur : carte présente').toBeVisible({ timeout: 30_000 })
  } finally {
    await py(`from apps.parametres.models_audit import SettingsAuditLog
SettingsAuditLog.objects.filter(pk=${lid}).delete()
sortie(1)`).catch(() => null)
  }
}, {
  ecart: {
    base: 'FAIL',
    raison: 'défaut ANTÉRIEUR hors du geste de la tâche : l\'onglet Paramètres › Avancé monte les sections '
      + '« Équipe terrain » (WIR112, 5a664f3e8 du 19/07/2026, EquipeTerrainSection.jsx) et « Modèles de fiche '
      + 'd\'intervention » (WIR114) qui lisent `installations/equipes/` et `installations/fiche-intervention-templates/` ; '
      + 'le Commercial responsable (sans code installation_*) reçoit 403 (oracles 2 et 3). ALEC28 (343b58dc3) ne fait que '
      + 'masquer la carte « Journal des modifications » ; témoin sans 403 : étape PF6.4-ALEC28-ecran-administrateur. '
      + 'AvanceSection.jsx figure dans les Files d\'ALEC28 : légitimité de l\'écart à trancher en relecture.',
  },
})

// Témoin : l'Administrateur livré (sans journal_activite_voir, lit les chantiers) : 403 sur le journal, carte absente, aucun 403 d'écran.
etape('PF6.4-ALEC28-ecran-administrateur', ['ALEC28'], async ({ context, suivi, testInfo }) => {
  const adm = await session(testInfo, 'alec28adm2', 'Administrateur')
  for (const r of [`${API}/parametres/audit/?section=roles`, `${API}/parametres/audit/sections/`]) {
    expect(await statut(adm.ctx, r), `Administrateur : ${r} 403`).toBe(403)
  }
  const p = await ecranSous(context, suivi, testInfo, adm)
  for (const passe of ['', 'rechargé : ']) {
    if (passe) await p.reload(); else await p.goto('/parametres?onglet=avance')
    await expect(p.getByText('Hypothèses ROI').first(), `${passe}Administrateur : onglet Avancé rendu`).toBeVisible({ timeout: 60_000 })
    await expect(p.getByText('Journal des modifications'), `${passe}écran Administrateur : carte absente`).toHaveCount(0)
  }
})

// ══ ALEC29 — calepinage : la portée du rôle suit la lecture (réglage « vue restreinte » éteint) ══════════════════════
etape('PF6.2-ALEC29-calepinage-portee', ['ALEC29'], async ({ context, suivi, testInfo }) => {
  sondeApres(testInfo, 'C-ALEC-025')
  const m = marque()
  const a = await session(testInfo, 'alec29a', 'Commercial')
  const b = await session(testInfo, 'alec29b', 'Commercial')
  const dir = await session(testInfo, 'alec29d', 'Directeur')
  const x = await py(`from apps.crm.models import Lead
from apps.calepinage.models import Calepinage
from apps.calepinage.selectors import vue_restreinte_au_responsable
co = U.objects.get(username='demo_admin').company
mk = lambda uid, qui: Calepinage.objects.create(company=co, lead_id=Lead.objects.create(company=co, nom='Lead ALEC29 ' + qui + ' ${m}', owner_id=uid).pk,
    titre='Toit ALEC29 ' + qui + ' ${m}', cree_par_id=uid)
ca, cb = mk(${a.id}, 'A'), mk(${b.id}, 'B')
sortie(dict(a=ca.pk, b=cb.pk, la=ca.lead_id, lb=cb.lead_id, reglage=vue_restreinte_au_responsable(co)))`)
  try {
    expect(x.reglage, 'Given : réglage « vue restreinte » éteint').toBe(false)
    const base = `${API}/calepinage/calepinages/`
    const idsDe = async (s) => (await lignes(s.ctx, base)).map((c) => c.id)
    const vueA = await idsDe(a)
    expect(vueA, 'Commercial A : son calepinage listé').toContain(x.a)
    expect(vueA, 'Commercial A : liste sans le calepinage de B').not.toContain(x.b)
    expect(await statut(a.ctx, `${base}${x.b}/`), 'Commercial A : détail du calepinage de B 404').toBe(404)
    expect(await idsDe(b), 'Commercial B : son calepinage').toContain(x.b)
    const vueD = await idsDe(dir)
    expect([vueD.includes(x.a), vueD.includes(x.b)], 'Directeur : les deux listés').toEqual([true, true])
    expect(await statut(dir.ctx, `${base}${x.b}/`), 'Directeur : détail 200').toBe(200)
    // Écran liste des calepinages en Commercial A : le sien, jamais celui de B ; témoin Directeur.
    const p = await ecranSous(context, suivi, testInfo, a)
    for (const passe of ['', 'rechargé : ']) {
      if (passe) await p.reload(); else await p.goto('/calepinage')
      await expect(p.getByTestId(`cal-vignette-${x.a}`), `${passe}écran A : son calepinage`).toBeVisible({ timeout: 60_000 })
      await expect(p.getByTestId(`cal-vignette-${x.b}`), `${passe}écran A : calepinage de B absent`).toHaveCount(0)
    }
    const pd = await ecranSous(context, suivi, testInfo, dir)
    await pd.goto('/calepinage')
    await expect(pd.getByTestId(`cal-vignette-${x.b}`), 'écran Directeur : calepinage de B').toBeVisible({ timeout: 60_000 })
  } finally {
    await py(`from apps.crm.models import Lead
from apps.calepinage.models import Calepinage
Calepinage.objects.filter(pk__in=${J([x.a, x.b])}).delete()
(Lead.all_objects if hasattr(Lead, 'all_objects') else Lead.objects).filter(pk__in=${J([x.la, x.lb])}).delete()
sortie(1)`).catch(() => null)
  }
}, { ecart: ECART_SONDE })
