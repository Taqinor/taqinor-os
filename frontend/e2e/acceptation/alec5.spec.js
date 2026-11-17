// Preuve en direct d'ALEC5 (groupe ALEC, vague 6) jouée À PART d'alec4.spec.js : relecture du 16/11 — le 403
// `installations/bin-locations/` de l'écran Expéditions en Commercial (ExpeditionsPage.jsx, dans les Files d'ALEC5) est
// un défaut de la tâche, pas un écart : l'étape reste un FAIL franc (trace, ne couvre rien), enregistrée sur son
// propre sha pour ne pas faire tomber l'enregistrement d'alec4. Témoin : même écran en Technicien.
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { delimiter, join } from 'node:path'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, connexionApi, uiLoginJusquAuxApps } from '../helpers.js'

const etape = groupe('ALEC', ['ALEC5'])
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
/** Écran Expéditions sous `s` : bouton « Tarifs » de l'expédition → « libellé — — », sans devise (puis rechargé). */
async function ecranTarifsSansCout(context, suivi, testInfo, s, fx) {
  const p = await ecranSous(context, suivi, testInfo, s)
  for (const passe of ['', 'rechargé : ']) {
    if (passe) await p.reload(); else await p.goto('/stock/entrepot/expeditions')
    const bouton = p.getByRole('button', { name: `Tarifs de l'expédition ${fx.ex}` })
    await expect(bouton, `${s.role} ${passe}écran Expéditions : l'expédition est listée`).toBeVisible({ timeout: 60_000 })
    await bouton.click()
    for (const lib of [fx.RAPIDE, fx.LENT]) {
      const li = p.getByRole('listitem').filter({ hasText: lib })
      await expect(li, `${s.role} ${passe}écran : ${lib} — —`).toHaveText(new RegExp(`^\\s*${lib} — —\\s*$`), { timeout: 30_000 })
      await expect(li, `${s.role} ${passe}écran : ${lib} sans devise`).not.toContainText('MAD')
    }
  }
}
etape('PF6.1-ALEC5-tarifs-expedition', ['ALEC5'], async ({ context, suivi, testInfo }) => {
  sondeApres(testInfo, 'C-ALEC-004')
  const com = await session(testInfo, 'alec5c', 'Commercial')
  const dir = await session(testInfo, 'alec5d', 'Directeur')
  const fx = await fixtureAlec5(marque())
  const { RAPIDE, LENT } = fx
  try {
    const url = fx.url
    const nos = (offres) => offres.filter((o) => o.source === 'interne' && [String(fx.t1), String(fx.t2)].includes(String(o.code)))
    const c = await json200(com.ctx, url, 'Commercial')
    const d = await json200(dir.ctx, url, 'Directeur')
    const oc = nos(c.offres)
    const od = nos(d.offres)
    expect(oc.map((o) => o.libelle).sort(), 'Commercial : mêmes offres (libellés)').toEqual([LENT, RAPIDE].sort())
    expect(oc.map((o) => o.cout), 'Commercial : cout null sur nos deux offres').toEqual([null, null])
    expect(c.offres.every((o) => o.cout === null), `Commercial : TOUTES les offres à cout null ${J(c.offres.map((o) => o.cout))}`).toBe(true)
    const parCode = (xs) => Object.fromEntries(xs.map((o) => [String(o.code), o]))
    const pc = parCode(oc)
    const pd = parCode(od)
    for (const k of [String(fx.t1), String(fx.t2)]) {
      expect([pc[k].libelle, pc[k].delai_jours, pc[k].source], `Commercial = Directeur (libellé, délai, source) ${k}`)
        .toEqual([pd[k].libelle, pd[k].delai_jours, pd[k].source])
    }
    expect(Number(pd[String(fx.t1)].cout), 'Directeur : 350').toBe(350)
    expect(Number(pd[String(fx.t2)].cout), 'Directeur : 500').toBe(500)

    // Écran Expéditions en Commercial (rôle de la clause) : « libellé — — », sans devise.
    await ecranTarifsSansCout(context, suivi, testInfo, com, fx)
  } finally {
    await nettoyerAlec5(fx)
  }
})

// Témoin : même écran sous un rôle livré sans prix_achat_voir qui lit aussi les casiers (Technicien) — aucun 403.
etape('PF6.1-ALEC5-ecran-technicien', ['ALEC5'], async ({ context, suivi, testInfo }) => {
  const tech = await session(testInfo, 'alec5t', 'Technicien')
  const fx = await fixtureAlec5(marque())
  try {
    const t = await json200(tech.ctx, fx.url, 'Technicien')
    expect(t.offres.every((o) => o.cout === null), 'Technicien (sans prix_achat_voir) : toutes les offres à cout null').toBe(true)
    await ecranTarifsSansCout(context, suivi, testInfo, tech, fx)
  } finally {
    await nettoyerAlec5(fx)
  }
})
