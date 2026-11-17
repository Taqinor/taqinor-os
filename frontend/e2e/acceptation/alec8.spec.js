// ALEC — preuves en direct ALEC48, ALEC49 (correctifs de la vague 7) et ALEC5 (débloquée par ALEC48), vague d'acceptation 8
// (lane alec8, 17/11/2026), SANS modèle. Comptes d'essai aux rôles SYSTÈME de la société démo relus dans le registre livré
// (`CANONICAL_SYSTEM_ROLES`), écrans ouverts par la connexion de l'ÉCRAN et observés par les oracles 1-4 et 8 (un 403
// `installations/*` avalé par l'écran reste visible : réponse 4xx + « Failed to load resource » en console). « Aucun appel »
// se lit dans la liste des requêtes de la page, bornée par une requête SŒUR émise par le même `useEffect` de montage APRÈS
// l'appel gardé (Expéditions : `crm/clients/` ; Qualité : `stock/categories/`) ; le témoin Directeur prouve, sur la même
// borne, que l'appel gardé part bien quand le droit est là.
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { delimiter, join } from 'node:path'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, connexionApi, listeDe, uiLoginJusquAuxApps } from '../helpers.js'

const etape = groupe('ALEC', ['ALEC48', 'ALEC49', 'ALEC5'])
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
  console.log(`[ALEC8] ${type} : ${description}`)
}

// ── Sonde hôte du dossier (docs/audits/sondes/ALEC/<constat>.py), rejouée STRICTEMENT : elle doit s'exécuter ET repro=false ──
function sondeStricte(testInfo, constat) {
  const r = spawnSync(process.env.E2E_PYTHON || 'python', [`docs/audits/sondes/ALEC/${constat}.py`], {
    cwd: RACINE, encoding: 'utf8', maxBuffer: 50_000_000,
    env: { ...process.env, PYTHONPATH: [join(RACINE, 'backend/django_core'), process.env.PYTHONPATH].filter(Boolean).join(delimiter) },
  })
  let d = null
  try { d = JSON.parse(r.stdout) } catch { d = null }
  note(testInfo, `sonde ${constat}`, d ? `repro=${d.repro}` : `NON EXÉCUTÉE : ${((r.stderr || r.stdout || '').trim().split('\n').pop() || `code ${r.status}`).slice(0, 300)}`)
  expect(d, `sonde ${constat} exécutée (sortie JSON)`).not.toBeNull()
  expect(d.repro, `sonde ${constat} rejouée après correctif : repro`).toBe(false)
}

// Codes qui ouvrent la lecture du module chantiers à l'écran (`useHasPermission.js::CODES_MODULE_INSTALLATIONS`).
const CODES_CHANTIERS = ['installation_voir', 'installation_gerer', 'installation_export', 'intervention_gerer', 'technicien_assign', 'approuver_demande_achat']
// ── Comptes aux rôles LIVRÉS ───────────────────────────────────────────────────────────────────────────────────────
async function roleReel(nom) {
  const r = await py(`from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
r = Role.objects.get(company_id=${SOC}, nom=${J(nom)})
reg = set(dict(CANONICAL_SYSTEM_ROLES)[${J(nom)}])
sortie(dict(pk=r.pk, manque=sorted(reg - set(r.permissions)), plus=sorted(set(r.permissions) - reg),
    installations=sorted(c for c in r.permissions if c.startswith('installation') or c in ${J(CODES_CHANTIERS)})))`)
  expect([r.manque, r.plus], `rôle « ${nom} » en base = registre livré`).toEqual([[], []])
  return r
}
const sessions = []
/** Compte d'essai au rôle livré `nomRole`, connecté par `/token/` ; {ctx, id, username, role, codesInstallations}. */
async function session(testInfo, prefixe, nomRole) {
  const username = `${prefixe}_${marque()}`
  const role = await roleReel(nomRole)
  const id = await py(`u = compte(${J(username)}, role=${role.pk}, societe=${SOC})
sortie(u.id)`)
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(ctx, { username, password: MDP_ESSAI })
  const s = { ctx, id, username, role: nomRole, codesInstallations: role.installations }
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

async function json200(ctx, url, quoi) {
  const r = await ctx.get(url, T)
  expect(r.status(), `${quoi} : ${url} → ${(await r.text()).slice(0, 300)}`).toBe(200)
  return r.json()
}

/** Écran sous un compte d'essai (connexion par l'ÉCRAN, accueil déjà vu), observé par les oracles ; `requetes` = URLs
 *  de TOUTES les requêtes de la page (journal réseau de l'onglet). */
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
  const requetes = []
  p.on('request', (r) => requetes.push({ methode: r.method(), url: r.url() }))
  await uiLoginJusquAuxApps(p, { username: s.username, password: MDP_ESSAI })
  const visites = await ctx.request.get(`${API}/onboarding/tours/`, T)
  if (visites.ok()) {
    for (const v of await visites.json()) {
      if (!v.vu) await ctx.request.post(`${API}/onboarding/tours/${v.tour_key}/vu/`, T)
    }
  }
  return { p, requetes }
}
const appelsA = (requetes, motif) => requetes.filter((r) => motif.test(new URL(r.url).pathname))
const BIN = /\/api\/django\/installations\/bin-locations\/?$/

// ══ ALEC48 — casiers des écrans Expéditions et Qualité selon la lecture du module chantiers ═════════════════════════════
const ECRANS_CASIERS = [
  { route: '/stock/entrepot/expeditions', titre: 'Expéditions', section: 'Expéditions transporteur', soeur: /\/api\/django\/crm\/clients\/?$/,
    selecteurs: ['Casier de destination'] },
  { route: '/stock/entrepot/qualite', titre: 'Qualité et rappels', section: 'Blocages qualité', soeur: /\/api\/django\/stock\/categories\/?$/,
    selecteurs: ['Casier en quarantaine', 'Casier compatible'] },
]
/** Ouvre `e.route` (puis le recharge) ; rend, par passe, les appels `bin-locations` vus avant la requête sœur + la réponse. */
async function ouvrirEcranCasiers(p, requetes, e, passe) {
  const avant = requetes.length
  const soeur = p.waitForRequest((r) => e.soeur.test(new URL(r.url()).pathname), { timeout: 60_000 })
  const reponseBin = p.waitForResponse((r) => BIN.test(new URL(r.url()).pathname), { timeout: 60_000 }).catch(() => null)
  if (passe) await p.reload(); else await p.goto(e.route)
  await soeur
  await expect(p.getByRole('heading', { name: e.titre, exact: true }).first(), `${passe}écran ${e.titre} rendu`).toBeVisible({ timeout: 60_000 })
  await expect(p.getByText(e.section, { exact: true }).first(), `${passe}écran ${e.titre} : section « ${e.section} »`).toBeVisible({ timeout: 30_000 })
  return { bin: appelsA(requetes.slice(avant), BIN), reponseBin }
}
/** Options (hors « — ») du sélecteur libellé `libelle`, ou null s'il est absent de l'écran. */
async function optionsDe(p, libelle) {
  const lab = p.locator('label').filter({ has: p.locator('span', { hasText: new RegExp(`^${libelle}$`) }) })
  if (await lab.count() === 0) return null
  const textes = await lab.first().locator('select option').allTextContents()
  return textes.map((t) => t.trim()).filter((t) => t && t !== '—')
}

etape('PF6.1-ALEC48-casiers-expeditions-qualite', ['ALEC48'], async ({ context, suivi, testInfo }) => {
  const m = marque()
  const com = await session(testInfo, 'alec48c', 'Commercial')
  const dir = await session(testInfo, 'alec48d', 'Directeur')
  expect(com.codesInstallations, 'Given : le Commercial livré ne porte aucun code installation_*').toEqual([])
  expect(dir.codesInstallations.length, 'Given : le Directeur livré lit le module chantiers').toBeGreaterThan(0)
  // Un casier de la société (le Directeur doit en voir au moins un).
  const casier = await py(`from apps.installations.models import BinLocation
from apps.stock.models import EmplacementStock
co = U.objects.get(username='demo_admin').company
emp = EmplacementStock.objects.create(company=co, nom='ALEC48 Dépôt ${m}')
b = BinLocation.objects.create(company=co, emplacement=emp, code='ALEC48-${m}', zone='A', allee='01', casier='01', ordre=1)
sortie(dict(emp=emp.pk, bin=b.pk, code=b.code))`)
  try {
    // Garde serveur inchangée (hors périmètre) : le Commercial est bien refusé sur la route — ce que l'écran ne doit plus demander.
    const r403 = await com.ctx.get(`${API}/installations/bin-locations/`, T)
    expect(r403.status(), 'Commercial : la route des casiers reste gardée (403) — l\'écran ne doit donc pas l\'appeler').toBe(403)
    const vueDir = await json200(dir.ctx, `${API}/installations/bin-locations/`, 'Directeur casiers')
    expect(listeDe(vueDir).length, 'Directeur : la route des casiers sert au moins un casier').toBeGreaterThan(0)

    // Commercial : Expéditions puis Qualité (et rechargées) — aucun appel bin-locations, sélecteur absent ou vide.
    const ec = await ecranSous(context, suivi, testInfo, com)
    for (const e of ECRANS_CASIERS) {
      for (const passe of ['', 'rechargé : ']) {
        const vu = await ouvrirEcranCasiers(ec.p, ec.requetes, e, passe)
        expect(vu.bin.map((x) => `${x.methode} ${x.url}`), `Commercial ${passe}${e.titre} : aucun appel installations/bin-locations/`).toEqual([])
        for (const sel of e.selecteurs) {
          const opts = await optionsDe(ec.p, sel)
          note(testInfo, `Commercial ${passe}${e.titre} « ${sel} »`, opts === null ? 'sélecteur absent' : `options ${J(opts)}`)
          if (opts !== null) expect(opts, `Commercial ${passe}${e.titre} : sélecteur « ${sel} » vide`).toEqual([])
        }
      }
    }

    // Directeur : mêmes écrans — l'appel part (200) et les casiers servis sont listés dans les sélecteurs.
    const ed = await ecranSous(context, suivi, testInfo, dir)
    for (const e of ECRANS_CASIERS) {
      const vu = await ouvrirEcranCasiers(ed.p, ed.requetes, e, '')
      expect(vu.bin.length, `Directeur ${e.titre} : l'appel installations/bin-locations/ part au montage`).toBeGreaterThan(0)
      const rep = await vu.reponseBin
      expect(rep?.status(), `Directeur ${e.titre} : bin-locations 200`).toBe(200)
      const codes = listeDe(await rep.json()).map((c) => c.code)
      expect(codes.length, `Directeur ${e.titre} : casiers servis`).toBeGreaterThan(0)
      let affiches = 0
      for (const sel of e.selecteurs) {
        const opts = await optionsDe(ed.p, sel)
        if (opts === null) continue
        affiches += 1
        await expect.poll(() => optionsDe(ed.p, sel), { message: `Directeur ${e.titre} : « ${sel} » liste les casiers servis`, timeout: 30_000 })
          .toEqual(codes)
      }
      expect(affiches, `Directeur ${e.titre} : au moins un sélecteur de casier à l'écran`).toBeGreaterThan(0)
      note(testInfo, `Directeur ${e.titre}`, `${codes.length} casier(s) listé(s) (dont ALEC48 : ${codes.includes(casier.code)})`)
    }
  } finally {
    await py(`from apps.installations.models import BinLocation
from apps.stock.models import EmplacementStock
BinLocation.objects.filter(pk=${casier.bin}).delete(); EmplacementStock.objects.filter(pk=${casier.emp}).delete()
sortie(1)`).catch(() => null)
  }
})

// ══ ALEC49 — Paramètres › Avancé : sections chantiers selon la lecture du module ══════════════════════════════════════
const EQUIPES = /\/api\/django\/installations\/equipes\/?$/
const FICHES = /\/api\/django\/installations\/fiche-intervention-templates\/?$/
const SECTIONS_CHANTIERS = ['Équipes terrain', "Modèles de fiche d'intervention"]
async function ouvrirAvance(p, passe) {
  if (passe) await p.reload(); else await p.goto('/parametres?onglet=avance')
  await expect(p.getByText('Hypothèses ROI').first(), `${passe}onglet Avancé rendu`).toBeVisible({ timeout: 60_000 })
  // Section rendue dans le MÊME rendu, après les deux montages gardés (AvanceSection.jsx).
  await expect(p.getByText("Chantiers — Checklist d'exécution").first(), `${passe}onglet Avancé : section suivante rendue`).toBeVisible({ timeout: 30_000 })
}
etape('PF6.4-ALEC49-avance-sections-chantiers', ['ALEC49'], async ({ context, suivi, testInfo }) => {
  const cr = await session(testInfo, 'alec49cr', 'Commercial responsable')
  const dir = await session(testInfo, 'alec49d', 'Directeur')
  expect(cr.codesInstallations, 'Given : le Commercial responsable livré ne porte aucun code installation_*').toEqual([])
  for (const r of [`${API}/installations/equipes/`, `${API}/installations/fiche-intervention-templates/`]) {
    expect((await cr.ctx.get(r, T)).status(), `Commercial responsable : ${r} reste gardée (403) — l'écran ne doit pas l'appeler`).toBe(403)
  }
  // Commercial responsable : ni l'une ni l'autre section, aucun appel des deux routes, aucun 403 (oracles).
  const ec = await ecranSous(context, suivi, testInfo, cr)
  for (const passe of ['', 'rechargé : ']) {
    const avant = ec.requetes.length
    await ouvrirAvance(ec.p, passe)
    for (const t of SECTIONS_CHANTIERS) {
      await expect(ec.p.getByText(t, { exact: true }), `Commercial responsable ${passe}: section « ${t} » absente`).toHaveCount(0)
    }
    const appels = [...appelsA(ec.requetes.slice(avant), EQUIPES), ...appelsA(ec.requetes.slice(avant), FICHES)]
    expect(appels.map((x) => x.url), `Commercial responsable ${passe}: aucun GET equipes/ ni fiche-intervention-templates/`).toEqual([])
  }
  // Directeur : les deux sections chargées (200 + titres à l'écran).
  const ed = await ecranSous(context, suivi, testInfo, dir)
  const repEq = ed.p.waitForResponse((r) => EQUIPES.test(new URL(r.url()).pathname), { timeout: 60_000 })
  const repFi = ed.p.waitForResponse((r) => FICHES.test(new URL(r.url()).pathname), { timeout: 60_000 })
  await ouvrirAvance(ed.p, '')
  expect((await repEq).status(), 'Directeur : installations/equipes/ 200').toBe(200)
  expect((await repFi).status(), 'Directeur : installations/fiche-intervention-templates/ 200').toBe(200)
  for (const t of SECTIONS_CHANTIERS) {
    await expect(ed.p.getByText(t, { exact: true }).first(), `Directeur : section « ${t} » à l'écran`).toBeVisible({ timeout: 30_000 })
  }
})

// ══ ALEC5 — comparatif des tarifs de transport (stock) : `cout` à null sans prix_achat_voir ═══════════════════════════
/** 2 transporteurs internes (350, 500), une unité logistique et son expédition. */
async function fixtureAlec5(m) {
  const RAPIDE = `ALEC5 Rapide ${m}`
  const LENT = `ALEC5 Lent ${m}`
  const fx = await py(`from decimal import Decimal
from apps.installations.models import Transporteur
from apps.stock.models_wms import UniteLogistique, ExpeditionTransporteur
from apps.stock.services_wms import _prochain_sscc
co = U.objects.get(username='demo_admin').company
t1 = Transporteur.objects.create(company=co, nom=${J(RAPIDE)}, tarif_base=Decimal('350'), active=True)
t2 = Transporteur.objects.create(company=co, nom=${J(LENT)}, tarif_base=Decimal('500'), active=True)
ul = UniteLogistique.objects.create(company=co, type_unite='colis', sscc=_prochain_sscc(co), poids_kg=Decimal('12'))
ex = ExpeditionTransporteur.objects.create(company=co, unite_logistique=ul, destination=${J(`Rabat ALEC5 ${m}`)})
sortie(dict(t1=t1.pk, t2=t2.pk, ul=ul.pk, ex=ex.pk))`)
  return { ...fx, RAPIDE, LENT, url: `${API}/stock/expeditions/tarifs/?unite_logistique=${fx.ul}` }
}
const nettoyerAlec5 = (fx) => py(`from apps.installations.models import Transporteur
from apps.stock.models_wms import UniteLogistique, ExpeditionTransporteur
ExpeditionTransporteur.objects.filter(pk=${fx.ex}).delete(); UniteLogistique.objects.filter(pk=${fx.ul}).delete()
Transporteur.objects.filter(pk__in=[${fx.t1}, ${fx.t2}]).delete()
sortie(1)`).catch(() => null)

etape('PF6.1-ALEC5-tarifs-expedition', ['ALEC5'], async ({ context, suivi, testInfo }) => {
  sondeStricte(testInfo, 'C-ALEC-004')
  const com = await session(testInfo, 'alec5c', 'Commercial')
  const cr = await session(testInfo, 'alec5cr', 'Commercial responsable')
  const dir = await session(testInfo, 'alec5d', 'Directeur')
  const fx = await fixtureAlec5(marque())
  const { RAPIDE, LENT } = fx
  try {
    const nos = (offres) => offres.filter((o) => o.source === 'interne' && [String(fx.t1), String(fx.t2)].includes(String(o.code)))
    const parCode = (xs) => Object.fromEntries(xs.map((o) => [String(o.code), o]))
    const d = await json200(dir.ctx, fx.url, 'Directeur')
    const pd = parCode(nos(d.offres))
    expect(Number(pd[String(fx.t1)].cout), 'Directeur : 350').toBe(350)
    expect(Number(pd[String(fx.t2)].cout), 'Directeur : 500').toBe(500)
    for (const s of [com, cr]) {
      const c = await json200(s.ctx, fx.url, s.role)
      const oc = nos(c.offres)
      expect(oc.map((o) => o.libelle).sort(), `${s.role} : mêmes offres (libellés)`).toEqual([LENT, RAPIDE].sort())
      expect(c.offres.length, `${s.role} : autant d'offres que le Directeur`).toBe(d.offres.length)
      expect(c.offres.every((o) => o.cout === null), `${s.role} : TOUTES les offres à cout null ${J(c.offres.map((o) => o.cout))}`).toBe(true)
      const pc = parCode(oc)
      for (const k of [String(fx.t1), String(fx.t2)]) {
        expect([pc[k].libelle, pc[k].delai_jours, pc[k].source], `${s.role} = Directeur (libellé, délai, source) ${k}`)
          .toEqual([pd[k].libelle, pd[k].delai_jours, pd[k].source])
      }
    }

    // Écran Expéditions en Commercial (rôle de la clause) : « libellé — — », sans devise ; aucun 403 (oracles, ALEC48).
    const { p } = await ecranSous(context, suivi, testInfo, com)
    for (const passe of ['', 'rechargé : ']) {
      if (passe) await p.reload(); else await p.goto('/stock/entrepot/expeditions')
      const bouton = p.getByRole('button', { name: `Tarifs de l'expédition ${fx.ex}` })
      await expect(bouton, `Commercial ${passe}écran Expéditions : l'expédition est listée`).toBeVisible({ timeout: 60_000 })
      await bouton.click()
      for (const lib of [RAPIDE, LENT]) {
        const li = p.getByRole('listitem').filter({ hasText: lib })
        await expect(li, `Commercial ${passe}écran : ${lib} — —`).toHaveText(new RegExp(`^\\s*${lib} — —\\s*$`), { timeout: 30_000 })
        await expect(li, `Commercial ${passe}écran : ${lib} sans devise`).not.toContainText('MAD')
      }
    }
  } finally {
    await nettoyerAlec5(fx)
  }
})
