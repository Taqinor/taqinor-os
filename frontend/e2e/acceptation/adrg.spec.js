// Preuves en direct du groupe ADRG (audit PF4 « droits de la grille des rôles », dossier
// docs/audits/2026-11-10-parcours-PF4.md), lot 1 : ADRG5, 19, 21, 31, 61, 62, 63, 64, 69, 70, 71, 73, 86, 99, 104.
// Chaque étape joue le geste par la VRAIE route sous des comptes d'essai portant les rôles SYSTÈME du registre
// (`apps/roles/permissions_registre.py`, semés par `init_roles` dans la société de demo_admin, relus par leur nom),
// connectés par /token/ ; l'écran est rejoué dans un contexte navigateur propre à chaque compte. Données propres
// créées puis retirées ; clause de persistance = relecture en base après le refus. Les sondes du dossier sont
// rejouées (transaction annulée) par le programme de `scripts/sonde.py --dry-run` envoyé au shell Django.
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { connexionApi, assurerSessionPage, lireJson, telephoneMobileUnique } from '../helpers.js'

const etape = groupe('ADRG', [
  'ADRG5', 'ADRG19', 'ADRG62', 'ADRG21', 'ADRG31', 'ADRG86', 'ADRG99', 'ADRG104',
  'ADRG61', 'ADRG63', 'ADRG64', 'ADRG69', 'ADRG70', 'ADRG71', 'ADRG73',
])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 420_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const J = (x) => JSON.stringify(x)
const SOC = `U.objects.get(username='demo_admin').company_id`

// Contextes ouverts par une étape : fermés APRÈS l'écriture de l'étape (oracles + capture d'écran faits).
const ouverts = []
test.afterEach(async () => {
  for (const fermer of ouverts.splice(0)) await fermer().catch(() => undefined)
})

/** Compte d'essai du rôle SYSTÈME `nomRole` de la société démo, connecté par /token/ (contexte API) ; {ctx, id}. */
async function session(testInfo, nom, nomRole, apres = '') {
  const id = await py(`from apps.roles.models import Role
u = compte(${J(nom)}, role=Role.objects.get(company_id=${SOC}, nom=${J(nomRole)}, est_systeme=True).pk, societe=${SOC})
${apres}
sortie(u.id)`)
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  ouverts.push(() => ctx.dispose())
  await connexionApi(ctx, { username: nom, password: MDP_ESSAI })
  return { ctx, id, nom }
}

/** Écran sous le compte `nom` : contexte navigateur vierge, connexion par /token/, visites guidées fermées
 *  comme un habitué (même geste que auth.setup.js), page observée par les oracles. */
async function ecran(page, suivi, testInfo, nom, stockage = {}) {
  const ctx = await page.context().browser().newContext({
    baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
  })
  ouverts.push(() => ctx.close())
  await ctx.addInitScript((extra) => {
    try {
      localStorage.setItem('taqinor-pwa-install-dismissed', '1')
      localStorage.setItem('taqinor:welcome:seen:v1', '1')
      for (const [k, v] of Object.entries(extra)) localStorage.setItem(k, v)
    } catch { /* mode privé */ }
  }, stockage)
  await connexionApi(ctx.request, { username: nom, password: MDP_ESSAI })
  const visites = await ctx.request.get(`${API}/onboarding/tours/`, T)
  if (visites.ok()) {
    for (const v of await visites.json()) {
      if (!v.vu) await ctx.request.post(`${API}/onboarding/tours/${v.tour_key}/vu/`, T)
    }
  }
  return suivi.surveiller(await ctx.newPage())
}

/** 403 qui NOMME le code manquant (et, par défaut, `droit_manquant`). */
async function refus(res, code, quoi, { droitManquant = true } = {}) {
  const corps = await res.text()
  expect(res.status(), `${quoi} : ${corps.slice(0, 240)}`).toBe(403)
  expect(corps, `${quoi} : le refus nomme ${code}`).toContain(code)
  if (droitManquant) expect(corps, `${quoi} : code droit_manquant`).toContain('droit_manquant')
}

/** Rejoue une sonde du dossier (programme de `scripts/sonde.py --dry-run`, transaction annulée) dans le shell
 *  Django de la pile ; {ok, verdict, repro, base, observe} ou {ok: false, err}. */
function sonde(constat) {
  const prog = spawnSync(process.env.E2E_PYTHON || 'python', ['scripts/sonde.py', `ADRG/${constat}`, '--dry-run'],
    { cwd: RACINE, encoding: 'utf8', maxBuffer: 50_000_000 })
  if (prog.status !== 0 || !prog.stdout) return { ok: false, err: `programme : ${(prog.stderr || '').slice(-300)}` }
  const [cmd, ...args] = (process.env.E2E_DJANGO_EXEC || 'docker compose exec -T django_core').split(' ')
  const r = spawnSync(cmd, [...args, 'python', '-u', 'manage.py', 'shell'],
    { cwd: RACINE, input: prog.stdout, encoding: 'utf8', maxBuffer: 50_000_000, timeout: 300_000 })
  const ligne = (r.stdout || '').split('\n').find((l) => l.startsWith('@@RESULT '))
  if (!ligne) return { ok: false, err: `aucun résultat : ${(r.stderr || r.stdout || '').slice(-400)}` }
  const res = JSON.parse(ligne.slice('@@RESULT '.length))
  const m = /"repro":\s*(true|false)/.exec(res.observe || '')
  const sortieSonde = { ok: true, verdict: res.verdict, repro: m ? m[1] === 'true' : null, base: res.base_inchangee, observe: res.observe }
  console.log(`[sonde ${constat}] verdict=${sortieSonde.verdict} repro=${sortieSonde.repro} base=${sortieSonde.base} :: ${String(res.observe).slice(0, 600)}`)
  return sortieSonde
}

/** Sonde décisive (la preuve de la tâche la nomme) : exécutée, non reproduite, base inchangée. */
function sondeNonReproduite(constat) {
  const s = sonde(constat)
  expect(s.ok, `sonde ${constat} exécutée : ${s.err || ''}`).toBe(true)
  expect(s.repro, `sonde ${constat} : non reproduit après correctif`).toBe(false)
  expect(s.base, `sonde ${constat} : base inchangée`).toBe(true)
}

/** Sonde d'appoint (la preuve de la tâche est l'écran) : rejouée et journalisée ; un `repro: true` serait une
 *  régression et fait tomber l'étape ; une sonde périmée (n'aboutit pas) est seulement nommée au journal. */
function sondeAppoint(constat) {
  const s = sonde(constat)
  if (!s.ok) { console.log(`[sonde ${constat}] périmée ou en échec, non comptée : ${s.err}`); return }
  expect(s.repro, `sonde ${constat} rejouée : le constat ne se reproduit plus`).not.toBe(true)
}

const csv = (nom, texte) => ({ name: nom, mimeType: 'text/csv', buffer: Buffer.from(texte) })

// ───────────────────────── PF4.3 — imports, exports, rapports ─────────────────────────

etape('PF4.3-ADRG61', ['ADRG61'], async ({ testInfo }) => {
  const m = marque()
  const email = `adrg61_${m}@example.invalid`
  const cl = await py(`from apps.crm.models import Client
c = Client.objects.create(company_id=${SOC}, nom='Alaoui ADRG61 ${m}', email=${J(email)})
sortie(c.pk)`)
  const factures = () => py(`from apps.ventes.models import Facture
sortie(dict(client=Facture.objects.filter(client_id=${cl}).count(), societe=Facture.objects.filter(company_id=${SOC}).count()))`)
  try {
    const te = await session(testInfo, `adrg61te_${m}`, 'Technicien')
    const co = await session(testInfo, `adrg61co_${m}`, 'Commercial')
    const fichier = csv('factures.csv', `client_email,statut\n${email},emise\n`)
    const avant = await factures()
    for (const route of ['dry-run', 'commit']) {
      await refus(await te.ctx.post(`${API}/imports/${route}/`, { ...T, multipart: { file: fichier, target: 'factures' } }),
        'ventes_creer', `Technicien imports/${route} factures`)
    }
    expect(await factures(), 'persistance : aucune facture après les deux refus').toEqual(avant)
    const ok = await co.ctx.post(`${API}/imports/commit/`, { ...T, multipart: { file: fichier, target: 'factures' } })
    const corps = await ok.text()
    expect(ok.status(), `Commercial imports/commit : ${corps.slice(0, 240)}`).toBe(200)
    expect(JSON.parse(corps).created, 'Commercial : created 1').toBe(1)
    expect((await factures()).client, 'relu : une facture pour le Commercial').toBe(1)
    sondeNonReproduite('C-ADRG-001')
  } finally {
    await py(`from apps.ventes.models import Facture
from apps.crm.models import Client
for f in Facture.objects.filter(client_id=${cl}):
    try:
        f.delete()
    except Exception:
        pass
try:
    Client.objects.filter(pk=${cl}).delete()
except Exception:
    pass
sortie(1)`).catch(() => null)
  }
})

etape('PF4.3-ADRG63', ['ADRG63'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const sku = `ADRG63-${m}`
  // Prix d'achat actuel volontairement singulier (9017.31) : sa chaîne ne peut venir que de la fiche.
  const prod = await py(`from decimal import Decimal
from apps.stock.models import Produit
p = Produit.objects.create(company_id=${SOC}, nom='Panneau ADRG63 ${m}', sku=${J(sku)}, prix_achat=Decimal('9017.31'), prix_vente=Decimal('12000'))
sortie(p.pk)`)
  try {
    const cr = await session(testInfo, `adrg63cr_${m}`, 'Commercial responsable')
    const di = await session(testInfo, `adrg63di_${m}`, 'Directeur')
    const fichier = csv('produits.csv', `Nom,SKU,prix_achat\nPanneau,${sku},9502.77\n`)
    const rc = await cr.ctx.post(`${API}/imports/dry-run/`, { ...T, multipart: { file: fichier, target: 'products' } })
    const tc = await rc.text()
    expect(rc.status(), `Commercial responsable dry-run : ${tc.slice(0, 240)}`).toBe(200)
    const dc = JSON.parse(tc)
    const champs = (dc.conflits || []).flatMap((c) => [...(c.ecrasements || []).map((e) => e.champ), ...(c.remplissages || [])])
    expect(champs, 'Commercial responsable : aucun prix_achat dans écrasements ni remplissages').not.toContain('prix_achat')
    expect(tc, 'Commercial responsable : la valeur actuelle n\'est nulle part dans la réponse').not.toContain('9017')
    const rd = await di.ctx.post(`${API}/imports/dry-run/`, { ...T, multipart: { file: fichier, target: 'products' } })
    const dd = await lireJson(rd, 'Directeur dry-run')
    const entree = (dd.conflits || []).flatMap((c) => c.ecrasements || []).find((e) => e.champ === 'prix_achat')
    expect(entree, `Directeur : l'entrée prix_achat est servie (${JSON.stringify(dd.conflits)})`).toBeTruthy()
    expect(String(entree.ancienne), 'Directeur : ancienne valeur = 9017.31').toContain('9017.31')
    // Écran Stock → Importer (aperçu) au Commercial responsable.
    const p = await ecran(page, suivi, testInfo, cr.nom)
    await p.goto('/stock')
    await p.getByRole('button', { name: 'Importer', exact: true }).first().click()
    const [apercu] = await Promise.all([
      p.waitForResponse((x) => /\/imports\/dry-run\/$/.test(new URL(x.url()).pathname), { timeout: 60_000 }),
      p.locator('input[type="file"][accept=".csv,.xlsx"]').setInputFiles(fichier),
    ])
    expect(apercu.status(), 'aperçu écran : 200').toBe(200)
    await expect(p.getByText(/colonnes reconnues/), 'aperçu affiché').toBeVisible({ timeout: 60_000 })
    expect(await p.locator('body').innerText(), 'écran : aucun prix d\'achat actuel affiché').not.toContain('9017')
    sondeAppoint('C-ADRG-004')
    await page.close()
  } finally {
    await py(`from apps.stock.models import Produit
try:
    Produit.objects.filter(pk=${prod}).delete()
except Exception:
    Produit.objects.filter(pk=${prod}).update(archived=True) if hasattr(Produit, 'archived') else None
sortie(1)`).catch(() => null)
  }
})

etape('PF4.3-ADRG64', ['ADRG64'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const budget = await py(`from decimal import Decimal
from apps.stock.models import BudgetDepartement
b, cree = BudgetDepartement.objects.get_or_create(company_id=${SOC}, periodicite='annuelle', annee=timezone.localdate().year, mois=0,
    defaults=dict(montant_alloue=Decimal('480000'), actif=True))
if not b.actif:
    b.actif = True; b.save(update_fields=['actif'])
sortie(dict(id=b.pk, cree=cree))`)
  try {
    const cr = await session(testInfo, `adrg64cr_${m}`, 'Commercial responsable')
    const di = await session(testInfo, `adrg64di_${m}`, 'Directeur')
    const kc = await lireJson(await cr.ctx.get(`${API}/reporting/p2p/kpi/`, T), 'Commercial responsable p2p/kpi')
    const kd = await lireJson(await di.ctx.get(`${API}/reporting/p2p/kpi/`, T), 'Directeur p2p/kpi')
    expect(kc.budgets_departement, 'Commercial responsable : budgets_departement []').toEqual([])
    expect(Object.keys(kc).sort(), 'Commercial responsable : les autres clés inchangées').toEqual(Object.keys(kd).sort())
    expect(kd.budgets_departement.length, `Directeur : l'enveloppe servie (${JSON.stringify(kd.budgets_departement)})`).toBeGreaterThan(0)
    expect(kd.budgets_departement[0], 'Directeur : montant_alloue').toHaveProperty('montant_alloue')
    // Écran /reporting, carte « Achats → paiement ».
    for (const [qui, nom, attendu] of [['Commercial responsable', cr.nom, 0], ['Directeur', di.nom, 1]]) {
      const p = await ecran(page, suivi, testInfo, nom)
      const [rep] = await Promise.all([
        p.waitForResponse((x) => /\/reporting\/p2p\/kpi\/$/.test(new URL(x.url()).pathname), { timeout: 60_000 }),
        p.goto('/reporting'),
      ])
      expect(rep.status(), `${qui} : p2p/kpi 200`).toBe(200)
      await expect(p.getByTestId('kpi-p2p-card'), `${qui} : carte Achats affichée`).toBeVisible({ timeout: 60_000 })
      const lignes = p.locator('[data-testid^="kpi-p2p-budget-"]')
      if (attendu === 0) {
        await expect(p.getByTestId('kpi-p2p-chargement')).toHaveCount(0, { timeout: 60_000 })
        await expect(lignes, `${qui} : aucune ligne de budget`).toHaveCount(0)
      } else {
        await expect(lignes.first(), `${qui} : ligne de budget affichée`).toBeVisible({ timeout: 60_000 })
      }
    }
    sondeAppoint('C-ADRG-005')
    await page.close()
  } finally {
    if (budget?.cree) {
      await py(`from apps.stock.models import BudgetDepartement
BudgetDepartement.objects.filter(pk=${budget.id}).delete()
sortie(1)`).catch(() => null)
    }
  }
})

etape('PF4.3-ADRG69', ['ADRG69'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const co = await session(testInfo, `adrg69co_${m}`, 'Commercial')
  const di = await session(testInfo, `adrg69di_${m}`, 'Directeur')
  for (const q of ['', '?export=xlsx']) {
    const r = await co.ctx.get(`${API}/reporting/insights/audit-log/${q}`, T)
    expect(r.status(), `Commercial audit-log${q} : ${(await r.text()).slice(0, 200)}`).toBe(403)
    const d = await di.ctx.get(`${API}/reporting/insights/audit-log/${q}`, T)
    expect(d.status(), `Directeur audit-log${q}`).toBe(200)
  }
  // Écran /rapports : Commercial sans carte ni appel ; Directeur avec la carte.
  const TITRE = "Journal d'activité (qui a fait quoi)"
  const pc = await ecran(page, suivi, testInfo, co.nom)
  const appels = []
  pc.on('request', (r) => { if (/\/reporting\/insights\/audit-log\//.test(r.url())) appels.push(r.url()) })
  await Promise.all([
    pc.waitForResponse((x) => /\/reporting\/reports\/sales\/$/.test(new URL(x.url()).pathname), { timeout: 60_000 }),
    pc.goto('/rapports'),
  ])
  await pc.waitForLoadState('networkidle')
  await expect(pc.getByText(TITRE), 'Commercial : carte Journal absente').toHaveCount(0)
  expect(appels, 'Commercial : aucun appel auditLog').toEqual([])
  const pd = await ecran(page, suivi, testInfo, di.nom)
  await pd.goto('/rapports')
  await expect(pd.getByText(TITRE).first(), 'Directeur : carte Journal rendue').toBeVisible({ timeout: 60_000 })
  sondeAppoint('C-ADRG-018')
  await page.close()
})

// ADRG70 — les 11 routes ventes/CRM (fabrique `lecture_source`).
const ROUTES_70 = (client) => [
  'reporting/dashboard/', 'reporting/reports/sales/', 'reporting/insights/analytics/',
  'reporting/insights/sales-leaderboard/', 'reporting/insights/cohorts/', `reporting/archive/client/${client}/`,
  'reporting/balance-agee/export/', 'reporting/commercial/dashboard/', 'reporting/commercial/win-loss-by-source/',
  'reporting/pipeline/', 'reporting/pipeline/velocity/',
]

etape('PF4.3-ADRG70', ['ADRG70'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const cl = await py(`from apps.crm.models import Client
c = Client.objects.create(company_id=${SOC}, nom='Client ADRG70 ${m}', email='adrg70_${m}@example.invalid')
sortie(c.pk)`)
  try {
    const te = await session(testInfo, `adrg70te_${m}`, 'Technicien')
    const co = await session(testInfo, `adrg70co_${m}`, 'Commercial')
    const cr = await session(testInfo, `adrg70cr_${m}`, 'Commercial responsable')
    const bilan = []
    for (const route of ROUTES_70(cl)) {
      const [st, sc, sr] = [
        (await te.ctx.get(`${API}/${route}`, T)).status(),
        (await co.ctx.get(`${API}/${route}`, T)).status(),
        (await cr.ctx.get(`${API}/${route}`, T)).status(),
      ]
      bilan.push(`${route} te=${st} co=${sc} cr=${sr}`)
    }
    console.log(`[ADRG70] ${bilan.join(' | ')}`)
    for (const l of bilan) {
      const [, st, sc, sr] = /te=(\d+) co=(\d+) cr=(\d+)/.exec(l)
      expect(st, `Technicien 403 : ${l}`).toBe('403')
      expect(sr, `Commercial responsable 200 : ${l}`).toBe('200')
      expect(sc, `Commercial : ${l}`).toBe(l.startsWith('reporting/balance-agee/export/') ? '403' : '200')
    }
    // Écran : accueil puis /reporting au Technicien — aucune donnée de vente servie.
    const p = await ecran(page, suivi, testInfo, te.nom)
    const servis = []
    p.on('response', (x) => {
      const chemin = new URL(x.url()).pathname.replace(`${API}/`, '')
      if (x.status() === 200 && ROUTES_70(cl).some((r) => chemin === r)) servis.push(chemin)
    })
    await p.goto('/dashboard')
    await p.waitForLoadState('networkidle')
    await p.goto('/reporting')
    await p.waitForLoadState('networkidle')
    expect(servis, 'Technicien : aucune route ventes/CRM servie à l\'écran').toEqual([])
    sondeAppoint('C-ADRG-019')
    await page.close()
  } finally {
    await py(`from apps.crm.models import Client
Client.objects.filter(pk=${cl}).delete()
sortie(1)`).catch(() => null)
  }
})

etape('PF4.3-ADRG71', ['ADRG71'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const chantier = await py(`from apps.installations.models import Installation
i = Installation.objects.create(company_id=${SOC}, reference='CHT-ADRG71-${m}')
sortie(i.pk)`)
  const CHANTIERS = ['reporting/reports/service/', 'reporting/reports/field/', 'reporting/insights/technicien-scorecard/',
    'reporting/reports/chantier/', `reporting/archive/chantier/${chantier}/`]
  const AUTRES = ['reporting/insights/sav-sla/', 'reporting/insights/recurring-revenue/', 'reporting/reports/stock/']
  try {
    const co = await session(testInfo, `adrg71co_${m}`, 'Commercial')
    const rh = await session(testInfo, `adrg71rh_${m}`, 'Admin RH')
    const tr = await session(testInfo, `adrg71tr_${m}`, 'Technicien responsable')
    const bilan = []
    for (const route of [...CHANTIERS, ...AUTRES]) {
      bilan.push([route, (await co.ctx.get(`${API}/${route}`, T)).status(), (await rh.ctx.get(`${API}/${route}`, T)).status(),
        (await tr.ctx.get(`${API}/${route}`, T)).status()])
    }
    console.log(`[ADRG71] ${bilan.map((b) => `${b[0]} co=${b[1]} rh=${b[2]} tr=${b[3]}`).join(' | ')}`)
    for (const [route, sc, sh, st] of bilan) {
      expect(sc, `Commercial ${route}`).toBe(CHANTIERS.includes(route) ? 403 : 200)
      expect(sh, `Admin RH ${route}`).toBe(403)
      expect(st, `Technicien responsable ${route}`).toBe(200)
    }
    // Écran /rapports au Commercial : cartes chantiers absentes ou vides, sans erreur.
    const p = await ecran(page, suivi, testInfo, co.nom)
    await Promise.all([
      p.waitForResponse((x) => /\/reporting\/reports\/sales\/$/.test(new URL(x.url()).pathname), { timeout: 60_000 }),
      p.goto('/rapports'),
    ])
    await p.waitForLoadState('networkidle')
    const carte = p.locator('div').filter({ has: p.getByText('Service (chantiers + SAV)', { exact: true }) })
      .filter({ hasText: 'Rapport indisponible' })
    await expect(carte, 'Commercial : la carte chantiers n\'est pas en erreur').toHaveCount(0)
    sondeAppoint('C-ADRG-019')
    await page.close()
  } finally {
    await py(`from apps.installations.models import Installation
Installation.objects.filter(pk=${chantier}).delete()
sortie(1)`).catch(() => null)
  }
})

etape('PF4.3-ADRG73', ['ADRG73'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const co = await session(testInfo, `adrg73co_${m}`, 'Commercial')
  const cr = await session(testInfo, `adrg73cr_${m}`, 'Commercial responsable')
  await refus(await co.ctx.get(`${API}/reporting/dashboard/?export=xlsx`, T), 'reporting_export', 'Commercial export xlsx')
  expect((await co.ctx.get(`${API}/reporting/dashboard/`, T)).status(), 'Commercial : JSON 200').toBe(200)
  const x = await cr.ctx.get(`${API}/reporting/dashboard/?export=xlsx`, T)
  expect(x.status(), 'Commercial responsable : export 200').toBe(200)
  expect((await x.body()).subarray(0, 2).toString(), 'classeur PK…').toBe('PK')
  for (const [qui, nom, visible] of [['Commercial', co.nom, false], ['Commercial responsable', cr.nom, true]]) {
    const p = await ecran(page, suivi, testInfo, nom)
    const [rep] = await Promise.all([
      p.waitForResponse((r) => /\/reporting\/dashboard\/$/.test(new URL(r.url()).pathname), { timeout: 60_000 }),
      p.goto('/reporting'),
    ])
    expect(rep.status(), `${qui} : tableau de bord 200`).toBe(200)
    const bouton = p.getByRole('button', { name: /Exporter Excel/ })
    if (visible) await expect(bouton.first(), `${qui} : bouton présent`).toBeVisible({ timeout: 60_000 })
    else {
      await p.waitForLoadState('networkidle')
      await expect(bouton, `${qui} : aucun bouton « Exporter Excel »`).toHaveCount(0)
    }
  }
  sondeAppoint('C-ADRG-020')
  await page.close()
})

// ───────────────────────── PF4.1 — écritures ventes ─────────────────────────

etape('PF4.1-ADRG5', ['ADRG5'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const ids = await py(`from apps.ventes.models import ListePrix, DevisPreset
l = ListePrix.objects.create(company_id=${SOC}, nom='Liste ADRG5 ${m}')
d = DevisPreset.objects.create(company_id=${SOC}, nom='Modèle ADRG5 ${m}', lignes_snapshot=[])
sortie(dict(liste=l.pk, preset=d.pk, nom=l.nom))`)
  const existent = () => py(`from apps.ventes.models import ListePrix, DevisPreset
sortie([ListePrix.objects.filter(pk=${ids.liste}).exists(), DevisPreset.objects.filter(pk=${ids.preset}).exists()])`)
  try {
    const co = await session(testInfo, `adrg5co_${m}`, 'Commercial')
    const cr = await session(testInfo, `adrg5cr_${m}`, 'Commercial responsable')
    await refus(await co.ctx.delete(`${API}/ventes/listes-prix/${ids.liste}/`, T), 'ventes_supprimer', 'Commercial DELETE liste de prix')
    await refus(await co.ctx.delete(`${API}/ventes/presets/${ids.preset}/`, T), 'ventes_supprimer', 'Commercial DELETE modèle')
    expect(await existent(), 'persistance : les deux objets existent après les refus').toEqual([true, true])
    // Écran Ventes → Listes de prix : « Supprimer » absent au Commercial, présent au Commercial responsable.
    for (const [qui, nom, visible] of [['Commercial', co.nom, false], ['Commercial responsable', cr.nom, true]]) {
      const p = await ecran(page, suivi, testInfo, nom)
      await p.goto('/ventes/listes-prix')
      await p.getByRole('button', { name: ids.nom, exact: true }).click({ timeout: 60_000 })
      const dlg = p.getByRole('dialog')
      await expect(dlg.getByRole('button', { name: 'Archiver' }), `${qui} : fiche ouverte`).toBeVisible({ timeout: 60_000 })
      const suppr = dlg.getByRole('button', { name: 'Supprimer', exact: true })
      if (visible) await expect(suppr, `${qui} : « Supprimer » présent`).toBeVisible()
      else await expect(suppr, `${qui} : aucun « Supprimer »`).toHaveCount(0)
    }
    expect((await cr.ctx.delete(`${API}/ventes/listes-prix/${ids.liste}/`, T)).status(), 'Commercial responsable : liste 204').toBe(204)
    expect((await cr.ctx.delete(`${API}/ventes/presets/${ids.preset}/`, T)).status(), 'Commercial responsable : modèle 204').toBe(204)
    expect(await existent(), 'relu : supprimés par le Commercial responsable').toEqual([false, false])
    sondeAppoint('C-ADRG-013')
    await page.close()
  } finally {
    await py(`from apps.ventes.models import ListePrix, DevisPreset
ListePrix.objects.filter(pk=${ids.liste}).delete(); DevisPreset.objects.filter(pk=${ids.preset}).delete()
sortie(1)`).catch(() => null)
  }
})

etape('PF4.1-ADRG19', ['ADRG19'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const r = page.request
  const vi = await session(testInfo, `adrg19vi_${m}`, 'Viewer')
  const co = await session(testInfo, `adrg19co_${m}`, 'Commercial')
  // Trois devis (brouillon, envoyé, accepté) posés par demo_admin puis attribués au Commercial.
  const prod = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur réseau ADRG19 ${m}`, prix_vente: '1000.00', prix_achat: '321.00' } }), 'produit')
  const devis = {}
  for (const etat of ['brouillon', 'envoye', 'accepte']) {
    const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `ADRG19 ${etat} ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `adrg19${etat}${m}@example.invalid` } }), 'lead')
    const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, lignes: [{ produit: prod.id, designation: prod.nom, quantite: '1', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
    if (etat !== 'brouillon') await lireJson(await r.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
    if (etat === 'accepte') await lireJson(await r.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client ADRG19' } }), 'accepter')
    devis[etat] = d
  }
  await py(`from apps.ventes.models import Devis
Devis.objects.filter(pk__in=${J(Object.values(devis).map((d) => d.id))}).update(created_by_id=${co.id})
sortie(1)`)
  const GESTES = {
    brouillon: { boutons: ['PDF', 'Envoyer'], menu: ['Éditer', 'Aperçu du PDF', 'Variante', 'Créer une variante de gamme', 'Proforma (PDF)'] },
    envoye: { boutons: ['PDF', 'Relancer'], menu: ['Éditer', 'Aperçu du PDF', 'Proforma (PDF)'] },
    accepte: { boutons: ['PDF'], menu: ['Aperçu du PDF', 'Convertir en bon de commande', 'Révoquer le lien client', 'Proforma (PDF)'] },
  }
  for (const [qui, nom, present] of [['Viewer', vi.nom, false], ['Commercial', co.nom, true]]) {
    const p = await ecran(page, suivi, testInfo, nom)
    for (const [etat, d] of Object.entries(devis)) {
      await p.goto(`/ventes/devis?q=${encodeURIComponent(d.reference)}`)
      const ligne = p.locator(`#devis-row-${d.id}`)
      await expect(ligne, `${qui} : ligne ${etat} affichée`).toBeVisible({ timeout: 60_000 })
      const entete = [p.getByRole('button', { name: /Exporter Excel/ }), p.getByRole('button', { name: /Nouveau devis/ })]
      for (const b of entete) {
        if (present) await expect(b.first(), `${qui} : en-tête`).toBeVisible()
        else await expect(b, `${qui} : aucun geste d'en-tête`).toHaveCount(0)
      }
      for (const nomBouton of GESTES[etat].boutons) {
        const b = ligne.getByRole('button', { name: nomBouton, exact: true })
        if (present) await expect(b, `${qui} ${etat} : « ${nomBouton} »`).toBeVisible()
        else await expect(b, `${qui} ${etat} : pas de « ${nomBouton} »`).toHaveCount(0)
      }
      await ligne.getByRole('button', { name: `Plus d'actions — ${d.reference}` }).click()
      const menu = p.getByRole('menu')
      await expect(menu.getByRole('menuitem', { name: 'Lien interne' }), `${qui} ${etat} : menu ouvert`).toBeVisible()
      for (const item of GESTES[etat].menu) {
        const it = menu.getByRole('menuitem', { name: item, exact: true })
        if (present) await expect(it, `${qui} ${etat} : menu « ${item} »`).toBeVisible()
        else await expect(it, `${qui} ${etat} : menu sans « ${item} »`).toHaveCount(0)
      }
      await p.keyboard.press('Escape')
    }
  }
  await page.close()
})

etape('PF4.1-ADRG62', ['ADRG62'], async ({ testInfo }) => {
  const m = marque()
  // Given/When/Then de la tâche par le VRAI code (`creer_facture_import`), comptes aux rôles livrés ; transaction
  // annulée : la série légale ne garde rien du rejeu (persistance relue DANS la transaction).
  const res = await py(`from django.db import transaction
from apps.roles.models import Role
from apps.crm.models import Client
from apps.ventes.models import Facture
from apps.ventes.domain.imports import creer_facture_import
from authentication.models import Company
from core.numbering import est_reference_provisoire
CO = ${SOC}
def r(n): return Role.objects.get(company_id=CO, nom=n, est_systeme=True).pk
out = {}
with transaction.atomic():
    av = compte('adrg62av_${m}', role=r('Admin Ventes'), societe=CO)
    cm = compte('adrg62co_${m}', role=r('Commercial'), societe=CO)
    di = compte('adrg62di_${m}', role=r('Directeur'), societe=CO)
    cl = Client.objects.create(company_id=CO, nom='ADRG62 ${m}', email='adrg62_${m}@example.invalid')
    soc = Company.objects.get(pk=CO)
    lignes = []
    for u, s in [(av, 'emise'), (cm, 'paid'), (cm, 'emise'), (di, 'paid'), (av, 'draft')]:
        statut, motif, f = creer_facture_import(soc, {'client_email': cl.email, 'statut': s}, user=U.objects.get(pk=u.pk))
        lignes.append([statut, motif, None if f is None else est_reference_provisoire(f.reference), None if f is None else f.statut])
    out['lignes'] = lignes
    out['factures_client'] = Facture.objects.filter(client=cl).count()
    transaction.set_rollback(True)
out['rien_laisse'] = not Client.objects.filter(nom='ADRG62 ${m}').exists()
sortie(out)`)
  const [l1, l2, l3, l4, l5] = res.lignes
  expect([l1[0], l2[0]], `refus (Admin Ventes émise, Commercial payée) : ${J(res.lignes)}`).toEqual(['erreur', 'erreur'])
  expect(l1[1], 'motif Admin Ventes').toContain('Encaisser')
  expect(l2[1], 'motif Commercial payée').toContain('administrateur')
  expect([l3[0], l4[0], l5[0]], 'créées : Commercial émise, Directeur payée, Admin Ventes brouillon').toEqual(['cree', 'cree', 'cree'])
  expect([l3[2], l4[2], l5[2]], 'série légale, série légale, BROUILLON-').toEqual([false, false, true])
  expect(res.factures_client, 'persistance : 3 factures, aucune pour les lignes refusées').toBe(3)
  expect(res.rien_laisse, 'transaction annulée').toBe(true)
  // Par la vraie route : la ligne refusée sort dans `skipped` avec son motif, aucune facture.
  const email = `adrg62api_${m}@example.invalid`
  const cl = await py(`from apps.crm.models import Client
sortie(Client.objects.create(company_id=${SOC}, nom='ADRG62 API ${m}', email=${J(email)}).pk)`)
  try {
    const av = await session(testInfo, `adrg62avapi_${m}`, 'Admin Ventes')
    const rc = await av.ctx.post(`${API}/imports/commit/`, { ...T, multipart: { file: csv('f.csv', `client_email,statut\n${email},emise\n`), target: 'factures' } })
    const corps = await rc.text()
    expect(rc.status(), `Admin Ventes commit : ${corps.slice(0, 240)}`).toBe(200)
    const c = JSON.parse(corps)
    expect(c.created, 'aucune création').toBe(0)
    expect(J(c.skipped), 'ligne refusée avec son motif').toContain('Encaisser')
    expect(await py(`from apps.ventes.models import Facture
sortie(Facture.objects.filter(client_id=${cl}).count())`), 'relu : aucune facture').toBe(0)
  } finally {
    await py(`from apps.crm.models import Client
Client.objects.filter(pk=${cl}).delete()
sortie(1)`).catch(() => null)
  }
})

// ───────────────────────── PF4.2 — chantiers, achats, monitoring ─────────────────────────

etape('PF4.2-ADRG21', ['ADRG21'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const tr = await session(testInfo, `adrg21tr_${m}`, 'Technicien responsable')
  const te = await session(testInfo, `adrg21te_${m}`, 'Technicien')
  // Le Technicien encadré par le Technicien responsable : son intervention entre dans la portée du second.
  await py(`U.objects.filter(pk=${te.id}).update(supervisor_id=${tr.id})
sortie(1)`)
  const co = await session(testInfo, `adrg21co_${m}`, 'Commercial')
  const ids = await py(`from apps.installations.models import Installation, Intervention
i = Installation.objects.create(company_id=${SOC}, reference='CHT-ADRG21-${m}', statut='installe', created_by_id=${co.id}, technicien_responsable_id=${te.id})
iv = Intervention.objects.create(company_id=${SOC}, installation=i, type_intervention='pose', technicien_id=${te.id}, created_by_id=${te.id}, date_prevue=timezone.localdate())
sortie(dict(chantier=i.pk, ref=i.reference, iv=iv.pk))`)
  try {
    // Fiche et liste au Commercial : lecture seule, aucun « Exporter Excel ».
    const pc = await ecran(page, suivi, testInfo, co.nom)
    await pc.goto(`/chantiers?id=${ids.chantier}`)
    const fiche = pc.getByRole('dialog')
    await expect(fiche.getByText(ids.ref).first(), 'Commercial : fiche ouverte').toBeVisible({ timeout: 60_000 })
    await expect(fiche.getByRole('button', { name: 'Fermer', exact: true }), 'Commercial : fiche rendue').toBeVisible()
    for (const geste of ['Mettre à jour', 'Annuler le chantier', 'Marquer réceptionné']) {
      await expect(fiche.getByRole('button', { name: geste }), `Commercial : pas de « ${geste} »`).toHaveCount(0)
    }
    await expect(pc.getByRole('button', { name: /Exporter Excel/ }), 'Commercial : aucun « Exporter Excel »').toHaveCount(0)
    // Témoin : le Technicien garde les gestes de la fiche.
    const pt = await ecran(page, suivi, testInfo, te.nom)
    await pt.goto(`/chantiers?id=${ids.chantier}`)
    await expect(pt.getByRole('dialog').getByRole('button', { name: 'Mettre à jour' }), 'Technicien : gestes présents').toBeVisible({ timeout: 60_000 })
    // Planning : carte non glissable au Technicien, glissable au Technicien responsable.
    await pt.goto('/planification')
    const carte = pt.getByTestId(`iv-${ids.iv}`)
    await expect(carte, 'Technicien : intervention au planning').toBeVisible({ timeout: 60_000 })
    await expect(carte.getByRole('button', { name: /Déplacer l'intervention/ }), 'Technicien : carte non glissable').toHaveCount(0)
    await expect(pt.getByText(/Lecture seule : déplacer une intervention demande le droit/), 'Technicien : lecture seule annoncée').toBeVisible()
    const pr = await ecran(page, suivi, testInfo, tr.nom)
    await pr.goto('/planification')
    await expect(pr.getByTestId(`iv-${ids.iv}`).getByRole('button', { name: /Déplacer l'intervention/ }), 'Technicien responsable : carte glissable').toBeVisible({ timeout: 60_000 })
    await page.close()
  } finally {
    await py(`from apps.installations.models import Installation, Intervention
Intervention.objects.filter(pk=${ids.iv}).delete()
try:
    Installation.objects.filter(pk=${ids.chantier}).delete()
except Exception:
    Installation.objects.filter(pk=${ids.chantier}).update(annule=True)
sortie(1)`).catch(() => null)
  }
})

etape('PF4.2-ADRG99', ['ADRG99'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const tr = await session(testInfo, `adrg99tr_${m}`, 'Technicien responsable')
  const te = await session(testInfo, `adrg99te_${m}`, 'Technicien')
  const te2 = await session(testInfo, `adrg99te2_${m}`, 'Technicien')
  await py(`U.objects.filter(pk__in=[${te.id}, ${te2.id}]).update(supervisor_id=${tr.id})
sortie(1)`)
  const ids = await py(`from apps.installations.models import Installation
i = Installation.objects.create(company_id=${SOC}, reference='CHT-ADRG99-${m}', statut='planifie', technicien_responsable_id=${te.id})
sortie(dict(chantier=i.pk, ref=i.reference))`)
  const relu = () => py(`from apps.installations.models import Installation
i = Installation.objects.get(pk=${ids.chantier})
sortie([i.technicien_responsable_id, i.acces_instructions])`)
  const URL_CH = `${API}/installations/chantiers/${ids.chantier}/`
  try {
    await refus(await te.ctx.patch(URL_CH, { ...T, data: { technicien_responsable: te2.id } }), 'technicien_assign', 'Technicien réaffecte')
    expect((await relu())[0], 'persistance : titulaire inchangé').toBe(te.id)
    const acces = `Portail bleu ${m}`
    const ok = await te.ctx.patch(URL_CH, { ...T, data: { acces_instructions: acces } })
    expect(ok.status(), `Technicien modifie l'accès : ${(await ok.text()).slice(0, 200)}`).toBe(200)
    expect(await relu(), 'relu : accès modifié, titulaire inchangé').toEqual([te.id, acces])
    // Écran Chantiers (Kanban) : aucun sélecteur « Installateur » au Technicien ; présent au Technicien responsable.
    const pt = await ecran(page, suivi, testInfo, te.nom, { 'taqinor.chantiers.view': 'kanban' })
    await pt.goto('/chantiers')
    await expect(pt.getByText(ids.ref).first(), 'Technicien : carte du chantier').toBeVisible({ timeout: 60_000 })
    await expect(pt.getByRole('combobox', { name: 'Installateur' }), 'Technicien : aucun sélecteur « Installateur »').toHaveCount(0)
    const pr = await ecran(page, suivi, testInfo, tr.nom, { 'taqinor.chantiers.view': 'kanban' })
    await pr.goto('/chantiers')
    await expect(pr.getByText(ids.ref).first(), 'Technicien responsable : carte du chantier').toBeVisible({ timeout: 60_000 })
    await expect(pr.getByRole('combobox', { name: 'Installateur' }).first(), 'Technicien responsable : sélecteur présent').toBeVisible()
    // Le Technicien responsable réaffecte : 200, relu.
    const re = await tr.ctx.patch(URL_CH, { ...T, data: { technicien_responsable: te2.id } })
    expect(re.status(), `Technicien responsable réaffecte : ${(await re.text()).slice(0, 200)}`).toBe(200)
    expect((await relu())[0], 'relu : réaffecté').toBe(te2.id)
    sondeAppoint('C-ADRG-055')
    await page.close()
  } finally {
    await py(`from apps.installations.models import Installation
try:
    Installation.objects.filter(pk=${ids.chantier}).delete()
except Exception:
    Installation.objects.filter(pk=${ids.chantier}).update(annule=True)
sortie(1)`).catch(() => null)
  }
})

etape('PF4.2-ADRG31', ['ADRG31'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const ids = await py(`from decimal import Decimal
from apps.installations.models_dossier_import import DossierImport
from apps.installations.models_landed_cost import FraisImport, LandedCostLigne
from apps.achats.models import BonCommandeFournisseur, LigneBonCommandeFournisseur
bcf = BonCommandeFournisseur.objects.filter(company_id=${SOC}, lignes__isnull=False).order_by('-pk').first()
d = DossierImport.objects.create(company_id=${SOC}, reference='DI-ADRG31-${m}', designation='Dossier ADRG31 ${m}', bon_commande=bcf)
f = FraisImport.objects.create(company_id=${SOC}, dossier=d, categorie='fret', montant=Decimal('1500'))
l = LandedCostLigne.objects.create(company_id=${SOC}, dossier=d, designation='Panneaux', quantite=Decimal('10'), valeur_fob=Decimal('20000'))
sortie(dict(dossier=d.pk, frais=f.pk, ligne=l.pk, bcf=bcf.pk if bcf else None))`)
  console.log(`[ADRG31] BCF rattaché : ${ids.bcf}`)
  const etat = () => py(`from apps.installations.models_dossier_import import DossierImport
from apps.installations.models_landed_cost import FraisImport, LandedCostLigne
from apps.achats.models import LigneBonCommandeFournisseur
d = DossierImport.objects.get(pk=${ids.dossier})
sortie(dict(statut=d.statut_douane, note=d.note, frais=list(FraisImport.objects.filter(dossier=d).values_list('pk', 'montant')),
    lignes=list(LandedCostLigne.objects.filter(dossier=d).values_list('pk', 'valeur_fob')),
    dossiers=DossierImport.objects.filter(company_id=${SOC}).count(),
    annexes=list(LigneBonCommandeFournisseur.objects.filter(bon_commande_id=${ids.bcf || 'None'}).order_by('pk').values_list('pk', 'frais_annexes'))))`)
  try {
    const tr = await session(testInfo, `adrg31tr_${m}`, 'Technicien responsable')
    const ad = await session(testInfo, `adrg31ad_${m}`, 'Administrateur')
    const avant = await etat()
    const B = `${API}/installations`
    const gestes = [
      ['POST dossiers-import', () => tr.ctx.post(`${B}/dossiers-import/`, { ...T, data: { reference: `DI-X-${m}`, designation: 'X' } })],
      ['PATCH dossier', () => tr.ctx.patch(`${B}/dossiers-import/${ids.dossier}/`, { ...T, data: { note: `pirate ${m}` } })],
      ['POST avancer', () => tr.ctx.post(`${B}/dossiers-import/${ids.dossier}/avancer/`, { ...T, data: {} })],
      ['POST appliquer-cout-stock', () => tr.ctx.post(`${B}/dossiers-import/${ids.dossier}/appliquer-cout-stock/`, { ...T, data: {} })],
      ['POST frais-import', () => tr.ctx.post(`${B}/frais-import/`, { ...T, data: { dossier: ids.dossier, categorie: 'douane', montant: '999' } })],
      ['POST landed-cost-lignes', () => tr.ctx.post(`${B}/landed-cost-lignes/`, { ...T, data: { dossier: ids.dossier, designation: 'Y', quantite: '1', valeur_fob: '1' } })],
    ]
    for (const [quoi, geste] of gestes) {
      await refus(await geste(), 'achats_commander', `Technicien responsable ${quoi}`, { droitManquant: false })
    }
    expect(await etat(), 'persistance : dossier, frais, lignes et frais_annexes du BCF inchangés').toEqual(avant)
    // Lectures inchangées pour le Technicien responsable.
    expect((await tr.ctx.get(`${B}/dossiers-import/${ids.dossier}/`, T)).status(), 'lecture du dossier').toBe(200)
    // L'Administrateur du registre écrit (201), objet retiré ensuite.
    const cree = await ad.ctx.post(`${B}/dossiers-import/`, { ...T, data: { reference: `DI-AD-${m}`, designation: 'Admin ADRG31' } })
    const corps = await cree.text()
    expect(cree.status(), `Administrateur POST dossiers-import : ${corps.slice(0, 200)}`).toBe(201)
    await py(`from apps.installations.models_dossier_import import DossierImport
DossierImport.objects.filter(pk=${JSON.parse(corps).id}).delete()
sortie(1)`)
    // Écran Suivi import : aucun bouton d'écriture au Technicien responsable ; présents à l'Administrateur.
    for (const [qui, nom, present] of [['Technicien responsable', tr.nom, false], ['Administrateur', ad.nom, true]]) {
      const p = await ecran(page, suivi, testInfo, nom)
      await p.goto('/chantiers/import')
      await p.getByTestId(`dossier-import-${ids.dossier}`).click({ timeout: 60_000 })
      await expect(p.getByText(`DI-ADRG31-${m}`).first(), `${qui} : fiche du dossier`).toBeVisible({ timeout: 60_000 })
      const boutons = [p.getByRole('button', { name: 'Nouveau dossier' }), p.getByRole('button', { name: 'Faire avancer' }),
        p.getByRole('button', { name: /Nouveau frais/ })]
      for (const b of boutons) {
        if (present) await expect(b.first(), `${qui} : bouton présent`).toBeVisible({ timeout: 30_000 })
        else await expect(b, `${qui} : bouton absent`).toHaveCount(0)
      }
      await p.getByRole('tab', { name: 'Coût débarqué' }).click()
      await expect(p.getByRole('button', { name: 'Calculer le coût débarqué' }), `${qui} : onglet ouvert`).toBeVisible({ timeout: 30_000 })
      const ligne = p.getByRole('button', { name: /Nouvelle ligne SKU/ })
      if (present) await expect(ligne, `${qui} : « Nouvelle ligne SKU »`).toBeVisible()
      else await expect(ligne, `${qui} : pas de « Nouvelle ligne SKU »`).toHaveCount(0)
    }
    sondeAppoint('C-ADRG-006')
    await page.close()
  } finally {
    await py(`from apps.installations.models_dossier_import import DossierImport
DossierImport.objects.filter(pk=${ids.dossier}).delete()
sortie(1)`).catch(() => null)
  }
})

etape('PF4.2-ADRG86', ['ADRG86'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const r = page.request
  const da = await lireJson(await r.post(`${API}/installations/demandes-achat/`, { ...T, data: { objet: `Demande ADRG86 ${m}` } }), 'demande d\'achat')
  try {
    const soumise = await lireJson(await r.post(`${API}/installations/demandes-achat/${da.id}/soumettre/`, { ...T, data: {} }), 'soumettre')
    expect(soumise.statut, 'demande soumise').toBe('soumise')
    const tr = await session(testInfo, `adrg86tr_${m}`, 'Technicien responsable')
    const di = await session(testInfo, `adrg86di_${m}`, 'Directeur')
    for (const [qui, nom, present] of [['Technicien responsable', tr.nom, false], ['Directeur', di.nom, true]]) {
      const p = await ecran(page, suivi, testInfo, nom)
      await p.goto(`/chantiers/demandes-achat?da=${da.id}`)
      await expect(p.getByText(`Demande ADRG86 ${m}`).first(), `${qui} : détail ouvert`).toBeVisible({ timeout: 60_000 })
      const boutons = [p.getByRole('button', { name: 'Approuver', exact: true }), p.getByRole('button', { name: 'Refuser', exact: true })]
      if (present) {
        for (const b of boutons) await expect(b, `${qui} : bouton présent`).toBeVisible({ timeout: 30_000 })
      } else {
        await expect(p.getByRole('button', { name: 'Fermer', exact: true }).first(), `${qui} : détail rendu`).toBeVisible({ timeout: 30_000 })
        for (const b of boutons) await expect(b, `${qui} : aucun bouton d'approbation`).toHaveCount(0)
      }
    }
    expect(await py(`from apps.installations.models_demande_achat import DemandeAchat
sortie(DemandeAchat.objects.get(pk=${da.id}).statut)`), 'relu : demande toujours soumise').toBe('soumise')
    await page.close()
  } finally {
    await py(`from apps.installations.models_demande_achat import DemandeAchat
DemandeAchat.objects.filter(pk=${da.id}).delete()
sortie(1)`).catch(() => null)
  }
})

etape('PF4.2-ADRG104', ['ADRG104'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const av = await session(testInfo, `adrg104av_${m}`, 'Admin Ventes')
  const co = await session(testInfo, `adrg104co_${m}`, 'Commercial')
  const di = await session(testInfo, `adrg104di_${m}`, 'Directeur')
  const CO2 = /\/monitoring\/configs\/co2-fleet\//
  for (const [qui, nom, charge] of [['Admin Ventes', av.nom, false], ['Commercial', co.nom, true], ['Directeur', di.nom, true]]) {
    const p = await ecran(page, suivi, testInfo, nom)
    const appels = []
    p.on('response', (x) => { if (CO2.test(x.url())) appels.push(x.status()) })
    if (charge) {
      const [rep] = await Promise.all([
        p.waitForResponse((x) => CO2.test(x.url()), { timeout: 60_000 }),
        p.goto('/ventes/devis'),
      ])
      expect(rep.status(), `${qui} : pastille chargée (200)`).toBe(200)
    } else {
      await p.goto('/ventes/devis')
      await p.waitForLoadState('networkidle')
      await expect(p.getByRole('navigation').first(), `${qui} : barre latérale rendue`).toBeVisible({ timeout: 60_000 })
      expect(appels, `${qui} : aucune requête co2-fleet`).toEqual([])
    }
  }
  await page.close()
})
