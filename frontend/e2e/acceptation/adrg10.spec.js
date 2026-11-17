// Preuves en direct du groupe ADRG, lot 10 (vague d'acceptation 6, runner GitHub, 16/11/2026) : ADRG11, 12, 13, 15,
// 38, 41, 43, 46, 69, 70 (parcours PF4 « droits de la grille », dossier docs/audits/2026-11-10-parcours-PF4.md).
// Rôles LIVRÉS du registre (`init_roles`, relus par leur nom dans la société de demo_admin) ; quand la clause exige
// « un rôle personnalisé portant `parametres_modifier` », le rôle d'essai est le Commercial responsable du registre
// + ce seul code (non système, nommé « Essai ADRGxx … »). Comptes connectés par la vraie route `/token/` ; écrans
// rendus dans un navigateur à part. Réglages société relus avant, comparés après chaque refus, rétablis à la fin.
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { connexionApi, assurerSessionPage, lireJson, telephoneMobileUnique } from '../helpers.js'

const etape = groupe('ADRG', ['ADRG11', 'ADRG12', 'ADRG13', 'ADRG15', 'ADRG38', 'ADRG41', 'ADRG43', 'ADRG46', 'ADRG69', 'ADRG70'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const V = { timeout: 60_000 }
test.describe.configure({ timeout: 480_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const OUVERTS = []
test.afterEach(async () => { for (const fermer of OUVERTS.splice(0)) await fermer().catch(() => undefined) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const J = JSON.stringify
const SOC = `U.objects.get(username='demo_admin').company_id`
const comptes = []
const rolesPerso = []
test.afterAll(async () => {
  if (comptes.length) {
    await py(`U.objects.filter(username__in=${J(comptes)}).update(is_active=False)
sortie(1)`).catch(() => null)
  }
  if (rolesPerso.length) {
    await py(`from apps.roles.models import Role
U.objects.filter(role_id__in=${J(rolesPerso)}).update(role_id=None)
Role.objects.filter(pk__in=${J(rolesPerso)}, est_systeme=False).delete()
sortie(1)`).catch(() => null)
  }
})

/** Compte d'essai du rôle SYSTÈME `nomRole` ; {username, id, codes, nomRole}. */
async function compteDe(nomRole, prefixe) {
  const username = `${prefixe}_${marque()}`
  const r = await py(`from apps.roles.models import Role
r = Role.objects.get(company_id=${SOC}, nom=${J(nomRole)}, est_systeme=True)
u = compte(${J(username)}, role=r.pk, societe=${SOC})
sortie(dict(id=u.id, codes=sorted(r.permissions or [])))`)
  comptes.push(username)
  return { username, id: r.id, codes: r.codes, nomRole }
}
/** Rôle PERSONNALISÉ (non système) = codes du rôle système `base` + `ajout`, et son compte d'essai. */
async function comptePerso(prefixe, base, ajout) {
  const username = `${prefixe}_${marque()}`
  const nom = `Essai ${prefixe} ${marque()}`
  const r = await py(`from apps.roles.models import Role
b = Role.objects.get(company_id=${SOC}, nom=${J(base)}, est_systeme=True)
r = Role.objects.create(company_id=${SOC}, nom=${J(nom)}, est_systeme=False, permissions=sorted(set(b.permissions or []) | set(${J(ajout)})))
u = compte(${J(username)}, role=r.pk, societe=${SOC})
sortie(dict(id=u.id, role=r.pk, codes=r.permissions))`)
  comptes.push(username)
  rolesPerso.push(r.role)
  return { username, id: r.id, codes: r.codes, nomRole: `rôle personnalisé (${base} + ${ajout.join(', ')})` }
}
async function apiDe(testInfo, c) {
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  OUVERTS.push(() => ctx.dispose())
  await connexionApi(ctx, { username: c.username, password: MDP_ESSAI })
  return ctx
}
async function ecranDe(page, suivi, testInfo, c) {
  if (!page.isClosed()) await page.close()
  const ctx = await page.context().browser().newContext({
    baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
    viewport: { width: 1600, height: 1000 },
  })
  OUVERTS.push(() => ctx.close())
  await ctx.addInitScript(() => {
    try {
      localStorage.setItem('taqinor-pwa-install-dismissed', '1')
      localStorage.setItem('taqinor:welcome:seen:v1', '1')
    } catch { /* mode privé */ }
  })
  await connexionApi(ctx.request, { username: c.username, password: MDP_ESSAI })
  const visites = await ctx.request.get(`${API}/onboarding/tours/`, T)
  if (visites.ok()) {
    for (const v of await visites.json().catch(() => [])) {
      if (!v.vu) await ctx.request.post(`${API}/onboarding/tours/${v.tour_key}/vu/`, T).catch(() => undefined)
    }
  }
  return suivi.surveiller(await ctx.newPage())
}
const calme = (p) => p.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => undefined)
async function statut(rep, attendu, quoi) {
  const t = rep.status() === 204 ? '' : await rep.text()
  expect(rep.status(), `${quoi} : ${t.slice(0, 240)}`).toBe(attendu)
  return t
}
const jsonDe = async (r, url, quoi) => lireJson(await r.get(`${API}/${url}`, T), quoi)

// ── ADRG11 — % de variante et réglages de gammes sous `parametres_modifier` ; ordre des lignes au palier ventes ────
etape('PF4.4-ADRG11-variante-gammes', ['ADRG11'], async ({ page, suivi, testInfo }) => {
  const admin = page.context().request
  const m = marque()
  const pct0 = (await jsonDe(admin, 'ventes/devis/variante-config/', 'variante relue')).variante_pct
  const gammes0 = await jsonDe(admin, 'ventes/parametres-gammes/', 'gammes relues')
  const cr = await compteDe('Commercial responsable', 'adrg11cr')
  const co = await compteDe('Commercial', 'adrg11co')
  const perso = await comptePerso('adrg11pm', 'Commercial responsable', ['parametres_modifier'])
  expect([cr.codes.includes('parametres_modifier'), perso.codes.includes('parametres_modifier')], 'Given : Commercial responsable sans parametres_modifier, rôle personnalisé avec').toEqual([false, true])
  const [xcr, xco, xpm] = [await apiDe(testInfo, cr), await apiDe(testInfo, co), await apiDe(testInfo, perso)]
  try {
    await statut(await xcr.put(`${API}/ventes/devis/variante-config/`, { ...T, data: { variante_pct: '31.5' } }), 403, 'Commercial responsable PUT variante-config')
    expect((await jsonDe(admin, 'ventes/devis/variante-config/', 'variante relue')).variante_pct, 'persistance : % de variante inchangé après le 403').toBe(pct0)
    const marques = JSON.parse(J(gammes0.marques || {}))
    marques.Essentielle = { ...(marques.Essentielle || {}), panneau: `ADRG11 ${m}` }
    await statut(await xcr.patch(`${API}/ventes/parametres-gammes/`, { ...T, data: { marques } }), 403, 'Commercial responsable PATCH épinglage de marque')
    const gammes1 = await jsonDe(admin, 'ventes/parametres-gammes/', 'gammes relues')
    expect(J([gammes1.marques, gammes1.deux_gammes, gammes1.updated_at]), 'persistance : réglages de gammes inchangés après le 403').toBe(J([gammes0.marques, gammes0.deux_gammes, gammes0.updated_at]))
    const ordre = await statut(await xco.patch(`${API}/ventes/parametres-gammes/`, { ...T, data: { ordre_lignes: gammes0.ordre_lignes ?? [] } }), 200, 'Commercial PATCH {ordre_lignes}')
    expect(JSON.parse(ordre).ordre_lignes, 'Commercial : ordre des lignes écrit').toEqual(gammes0.ordre_lignes ?? [])
    await statut(await xpm.put(`${API}/ventes/devis/variante-config/`, { ...T, data: { variante_pct: '31.5' } }), 200, 'rôle personnalisé PUT variante-config')
    expect(parseFloat((await jsonDe(admin, 'ventes/devis/variante-config/', 'variante relue')).variante_pct), 'relu : % écrit par le rôle personnalisé').toBe(31.5)
    await statut(await xpm.put(`${API}/ventes/devis/variante-config/`, { ...T, data: { variante_pct: pct0 } }), 200, 'rétablir le %')
    // Écran Ventes → Devis : modale « Variante » — % en lecture seule au Commercial responsable, éditable au porteur.
    const prod = await lireJson(await admin.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur réseau ADRG11 ${m}`, prix_vente: '1000.00', prix_achat: '600.00' } }), 'produit')
    const devisDe = async (c) => {
      const lead = await lireJson(await admin.post(`${API}/crm/leads/`, { ...T, data: { nom: `ADRG11 ${c.username}`, ville: 'Casablanca', telephone: telephoneMobileUnique() } }), 'lead')
      const d = await lireJson(await admin.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, lignes: [{ produit: prod.id, designation: prod.nom, quantite: '1', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
      await py(`from apps.ventes.models import Devis
from apps.crm.models import Lead
Devis.objects.filter(pk=${d.id}).update(created_by_id=${c.id}); Lead.objects.filter(pk=${lead.id}).update(owner_id=${c.id})
sortie(1)`)
      return d
    }
    const pctAffiche = String(parseFloat(pct0))
    async function modale(p, d) {
      await p.goto(`/ventes/devis?q=${encodeURIComponent(d.reference)}`)
      const ligne = p.locator(`#devis-row-${d.id}`)
      await expect(ligne, `ligne ${d.reference} affichée`).toBeVisible(V)
      await ligne.getByRole('button', { name: `Plus d'actions — ${d.reference}` }).click()
      await p.getByRole('menu').getByRole('menuitem', { name: 'Variante', exact: true }).click()
      const dlg = p.getByRole('dialog').filter({ hasText: `Créer des variantes — ${d.reference}` })
      await expect(dlg, 'modale Variantes ouverte').toBeVisible(V)
      const champ = dlg.locator('#variante-pct')
      await expect(champ, 'config de la société chargée').toBeEnabled(V)
      await expect(champ, 'valeur = % de la société').toHaveValue(pctAffiche)
      return { dlg, champ }
    }
    const dcr = await devisDe(cr)
    const pc = await ecranDe(page, suivi, testInfo, cr)
    for (const passeRe of ['', 'relu après rechargement : ']) {
      if (passeRe) await pc.reload()
      const { dlg, champ } = await modale(pc, dcr)
      await expect(champ, `${passeRe}Commercial responsable : % en lecture seule`).toHaveAttribute('readonly', '')
      await expect(champ, `${passeRe}Commercial responsable : aria-readonly`).toHaveAttribute('aria-readonly', 'true')
      await expect(dlg.getByText('modification réservée au droit « Modifier les paramètres »', { exact: false }), `${passeRe}Commercial responsable : raison affichée`).toBeVisible()
      await dlg.getByRole('button', { name: 'Annuler', exact: true }).click()
      await expect(dlg).toBeHidden()
    }
    const pp = await ecranDe(page, suivi, testInfo, perso)
    const { dlg: dlgP, champ: champP } = await modale(pp, await devisDe(perso))
    await expect(champP, 'rôle personnalisé : % éditable').not.toHaveAttribute('readonly', '')
    await expect(dlgP.getByText('Modifiez-la pour cette génération uniquement', { exact: false }), 'rôle personnalisé : aide d\'édition').toBeVisible()
    await dlgP.getByRole('button', { name: 'Annuler', exact: true }).click()
    // Générateur au Commercial responsable : « Enregistrer cet ordre comme ordre par défaut » fonctionne toujours.
    await pc.goto(`/ventes/devis/nouveau?edit=${dcr.id}`)
    const enreg = pc.getByRole('button', { name: 'Enregistrer cet ordre comme ordre par défaut' })
    await expect(enreg, 'générateur : bouton de l\'ordre des lignes').toBeVisible(V)
    const [rep] = await Promise.all([
      pc.waitForResponse((x) => /\/ventes\/parametres-gammes\/$/.test(new URL(x.url()).pathname) && x.request().method() === 'PATCH', V),
      enreg.click(),
    ])
    expect(rep.status(), 'générateur : PATCH {ordre_lignes} du Commercial responsable').toBe(200)
    expect(Object.keys(rep.request().postDataJSON() || {}), 'générateur : corps = {ordre_lignes} seul').toEqual(['ordre_lignes'])
    await expect(pc.getByText('Ordre des lignes enregistré comme ordre par défaut', { exact: false }).first(), 'générateur : confirmation affichée').toBeVisible(V)
  } finally {
    await admin.put(`${API}/ventes/devis/variante-config/`, { ...T, data: { variante_pct: pct0 } }).catch(() => null)
    await admin.patch(`${API}/ventes/parametres-gammes/`, { ...T, data: { ordre_lignes: gammes0.ordre_lignes ?? [] } }).catch(() => null)
  }
})

// ── ADRG12 — Paramètres → Devis : % de variante en lecture seule sans `parametres_modifier`, modifiable avec ──────
etape('PF4.4-ADRG12-parametres-devis', ['ADRG12'], async ({ page, suivi, testInfo }) => {
  const admin = page.context().request
  const pct0 = (await jsonDe(admin, 'ventes/devis/variante-config/', 'variante relue')).variante_pct
  const cr = await compteDe('Commercial responsable', 'adrg12cr')
  const perso = await comptePerso('adrg12pm', 'Commercial responsable', ['parametres_modifier'])
  expect([cr.codes.includes('parametres_modifier'), perso.codes.includes('parametres_modifier')], 'Given : codes').toEqual([false, true])
  const champDe = (p) => p.locator('#pe-variante-pct')
  try {
    const pc = await ecranDe(page, suivi, testInfo, cr)
    for (const passeRe of ['', 'relu après rechargement : ']) {
      if (passeRe) await pc.reload(); else await pc.goto('/parametres?onglet=devis')
      const champ = champDe(pc)
      await expect(champ, `${passeRe}Commercial responsable : champ % de variation affiché`).toHaveValue(String(parseFloat(pct0)), V)
      await expect(champ, `${passeRe}Commercial responsable : lecture seule`).toHaveAttribute('readonly', '')
      await expect(champ, `${passeRe}Commercial responsable : aria-readonly`).toHaveAttribute('aria-readonly', 'true')
      await expect(champ.locator('xpath=..').getByRole('button', { name: 'Enregistrer' }), `${passeRe}Commercial responsable : aucun « Enregistrer » du %`).toHaveCount(0)
      await expect(pc.getByText('Réservé au droit « Modifier les paramètres ».', { exact: false }), `${passeRe}Commercial responsable : raison affichée`).toBeVisible()
    }
    const pp = await ecranDe(page, suivi, testInfo, perso)
    await pp.goto('/parametres?onglet=devis')
    const champ = champDe(pp)
    await expect(champ, 'rôle personnalisé : valeur chargée').toHaveValue(String(parseFloat(pct0)), V)
    await expect(champ, 'rôle personnalisé : champ éditable').not.toHaveAttribute('readonly', '')
    await champ.fill('27.5')
    const [rep] = await Promise.all([
      pp.waitForResponse((x) => /\/ventes\/devis\/variante-config\/$/.test(new URL(x.url()).pathname) && x.request().method() === 'PUT', V),
      champ.locator('xpath=..').getByRole('button', { name: 'Enregistrer' }).click(),
    ])
    expect(rep.status(), 'rôle personnalisé : PUT variante-config').toBe(200)
    await expect(pp.getByText('Pourcentage de variation enregistré.').first(), 'rôle personnalisé : confirmation').toBeVisible(V)
    await pp.reload()
    await expect(champDe(pp), 'relu après rechargement : 27.5 %').toHaveValue('27.5', V)
    expect(parseFloat((await jsonDe(admin, 'ventes/devis/variante-config/', 'variante relue')).variante_pct), 'relu en base : 27.5').toBe(27.5)
  } finally {
    await admin.put(`${API}/ventes/devis/variante-config/`, { ...T, data: { variante_pct: pct0 } }).catch(() => null)
  }
})

// ── ADRG13 — Paramètres → Gammes et marques : lecture seule sans `parametres_modifier`, enregistrement avec ───────
etape('PF4.4-ADRG13-gammes-marques', ['ADRG13'], async ({ page, suivi, testInfo }) => {
  const admin = page.context().request
  const m = marque()
  const g0 = await jsonDe(admin, 'ventes/parametres-gammes/', 'gammes relues')
  const cr = await compteDe('Commercial responsable', 'adrg13cr')
  const perso = await comptePerso('adrg13pm', 'Commercial responsable', ['parametres_modifier'])
  try {
    const pc = await ecranDe(page, suivi, testInfo, cr)
    for (const passeRe of ['', 'relu après rechargement : ']) {
      if (passeRe) await pc.reload(); else await pc.goto('/parametres/gammes')
      await expect(pc.getByRole('heading', { name: 'Gammes & marques' }), `${passeRe}Commercial responsable : écran Gammes & marques`).toBeVisible(V)
      await expect(pc.locator('#gm-nom-essentielle'), `${passeRe}Commercial responsable : libellé chargé`).toHaveValue(g0.nom_essentielle || 'Essentielle', V)
      await expect(pc.locator('#gm-nom-essentielle'), `${passeRe}Commercial responsable : libellé en lecture seule`).toBeDisabled()
      await expect(pc.getByRole('switch', { name: "Activer l'offre à deux gammes" }), `${passeRe}Commercial responsable : interrupteur en lecture seule`).toBeDisabled()
      await expect(pc.getByRole('button', { name: /^Enregistrer/ }), `${passeRe}Commercial responsable : aucun « Enregistrer »`).toHaveCount(0)
    }
    const pp = await ecranDe(page, suivi, testInfo, perso)
    await pp.goto('/parametres/gammes')
    const champ = pp.locator('#gm-nom-essentielle')
    await expect(champ, 'rôle personnalisé : libellé éditable').toBeEnabled(V)
    const nouveau = `Essentielle ${m}`
    await champ.fill(nouveau)
    const [rep] = await Promise.all([
      pp.waitForResponse((x) => /\/ventes\/parametres-gammes\/$/.test(new URL(x.url()).pathname) && x.request().method() === 'PATCH', V),
      pp.getByRole('button', { name: 'Enregistrer', exact: true }).click(),
    ])
    expect(rep.status(), 'rôle personnalisé : PATCH parametres-gammes').toBe(200)
    await expect(pp.getByText('Réglages « Gammes & marques » enregistrés.').first(), 'rôle personnalisé : confirmation').toBeVisible(V)
    await pp.reload()
    await expect(pp.locator('#gm-nom-essentielle'), 'relu après rechargement : libellé enregistré').toHaveValue(nouveau, V)
  } finally {
    await admin.patch(`${API}/ventes/parametres-gammes/`, { ...T, data: { nom_essentielle: g0.nom_essentielle, nom_premium: g0.nom_premium, deux_gammes: g0.deux_gammes, marques: g0.marques } }).catch(() => null)
  }
})

// ── ADRG15 — écritures de la règle d'équipe : + `crm_modifier` ; le cockpit reste lisible ──────────────────────────
etape('PF4.4-ADRG15-regle-equipe', ['ADRG15'], async ({ testInfo }) => {
  const m = marque()
  const vi = await compteDe('Viewer', 'adrg15vi')
  const mem = await compteDe('Commercial', 'adrg15me')
  const cr = await compteDe('Commercial responsable', 'adrg15cr')
  expect([vi.codes.includes('crm_modifier'), cr.codes.includes('crm_modifier')], 'Given : Viewer sans crm_modifier, Commercial responsable avec').toEqual([false, true])
  const eq = await py(`from apps.crm.models_clients import EquipeCommerciale
e = EquipeCommerciale.objects.create(company_id=${SOC}, nom=${J(`Équipe ADRG15 ${m}`)}, responsable_id=${vi.id})
e.membres.add(${mem.id})
sortie(e.pk)`)
  const etat = () => py(`from apps.crm.models_clients import EquipeCommerciale, ObjectifCommercial
e = EquipeCommerciale.objects.get(pk=${eq})
sortie([e.confirmation_responsable, e.delai_attribution_minutes, ObjectifCommercial.objects.filter(owner_id=${mem.id}).count()])`)
  const now = new Date()
  const objectif = { owner: mem.id, metric: 'nb_leads', period_type: 'month', period_year: now.getFullYear(), period_month: now.getMonth() + 1, cible: '5' }
  try {
    const avant = await etat()
    const xvi = await apiDe(testInfo, vi)
    const t1 = await statut(await xvi.patch(`${API}/crm/dispatch/reglages/${eq}/`, { ...T, data: { confirmation_responsable: !avant[0], delai_minutes: 77 } }), 403, 'Viewer responsable d\'équipe PATCH dispatch/reglages')
    expect(t1, 'le refus nomme crm_modifier').toContain('crm_modifier')
    const t2 = await statut(await xvi.post(`${API}/crm/objectifs/`, { ...T, data: objectif }), 403, 'Viewer responsable d\'équipe POST objectif d\'un membre')
    expect(t2, 'le refus nomme crm_modifier').toContain('crm_modifier')
    expect(await etat(), 'persistance : réglages de l\'équipe inchangés, aucun objectif créé').toEqual(avant)
    const ck = await lireJson(await xvi.get(`${API}/crm/cockpit-equipe/?equipe=${eq}`, T), 'Viewer : cockpit d\'équipe')
    expect(J(ck.equipe), 'Viewer : cockpit de SON équipe servi').toContain(`Équipe ADRG15 ${m}`)
    expect(J(ck.membres), 'Viewer : membre de l\'équipe au cockpit').toContain(String(mem.id))
    // Témoin : le même geste par un responsable d'équipe portant crm_modifier passe et écrit.
    await py(`from apps.crm.models_clients import EquipeCommerciale
EquipeCommerciale.objects.filter(pk=${eq}).update(responsable_id=${cr.id})
sortie(1)`)
    const xcr = await apiDe(testInfo, cr)
    await statut(await xcr.patch(`${API}/crm/dispatch/reglages/${eq}/`, { ...T, data: { confirmation_responsable: !avant[0], delai_minutes: 77 } }), 200, 'Commercial responsable PATCH dispatch/reglages')
    await statut(await xcr.post(`${API}/crm/objectifs/`, { ...T, data: objectif }), 201, 'Commercial responsable POST objectif')
    expect(await etat(), 'témoin relu : réglages écrits, un objectif').toEqual([!avant[0], 77, 1])
  } finally {
    await py(`from apps.crm.models_clients import EquipeCommerciale, ObjectifCommercial
ObjectifCommercial.objects.filter(owner_id=${mem.id}).delete(); EquipeCommerciale.objects.filter(pk=${eq}).delete()
sortie(1)`).catch(() => null)
  }
})

// ── ADRG38 — réglage négoce sous `parametres_modifier` : cinq rôles livrés 403, écran Consignations en lecture ─────
const CINQ_38 = ['Responsable', 'Commercial responsable', 'Technicien responsable', 'Technicien', 'Admin Ventes']
etape('PF4.4-ADRG38-negoce', ['ADRG38'], async ({ page, suivi, testInfo }) => {
  const admin = page.context().request
  const p0 = await jsonDe(admin, 'stock/parametres-negoce/', 'réglage négoce relu')
  try {
    for (const nom of CINQ_38) {
      const c = await compteDe(nom, 'adrg38')
      expect(c.codes.includes('parametres_modifier'), `Given : ${nom} sans parametres_modifier`).toBe(false)
      const x = await apiDe(testInfo, c)
      await statut(await x.patch(`${API}/stock/parametres-negoce/`, { ...T, data: { consignation_activee: !p0.consignation_activee, atp_horizon_jours: (p0.atp_horizon_jours || 0) + 7 } }), 403, `${nom} PATCH parametres-negoce`)
    }
    const p1 = await jsonDe(admin, 'stock/parametres-negoce/', 'réglage négoce relu')
    expect([p1.consignation_activee, p1.atp_horizon_jours], 'persistance : réglage inchangé après les cinq refus').toEqual([p0.consignation_activee, p0.atp_horizon_jours])
    const di = await compteDe('Directeur', 'adrg38di')
    await statut(await (await apiDe(testInfo, di)).patch(`${API}/stock/parametres-negoce/`, { ...T, data: { atp_horizon_jours: (p0.atp_horizon_jours || 0) + 7 } }), 200, 'Directeur PATCH parametres-negoce')
    expect((await jsonDe(admin, 'stock/parametres-negoce/', 'relu')).atp_horizon_jours, 'Directeur : réglage écrit').toBe((p0.atp_horizon_jours || 0) + 7)
    // Écran /stock/negoce/consignations, onglet Réglages : lecture seule au Commercial responsable, éditable au Directeur.
    async function reglages(p) {
      await p.getByRole('tab', { name: 'Réglages', exact: true }).click()
      await expect(p.getByLabel('Horizon ATP (jours)'), 'onglet Réglages rendu').toBeVisible(V)
    }
    const pc = await ecranDe(page, suivi, testInfo, await compteDe('Commercial responsable', 'adrg38cr'))
    for (const passeRe of ['', 'relu après rechargement : ']) {
      if (passeRe) await pc.reload(); else await pc.goto('/stock/negoce/consignations')
      await reglages(pc)
      await expect(pc.getByLabel('Horizon ATP (jours)'), `${passeRe}Commercial responsable : horizon en lecture seule`).toBeDisabled()
      await expect(pc.getByLabel('Consignation activée'), `${passeRe}Commercial responsable : consignation en lecture seule`).toBeDisabled()
      await expect(pc.getByRole('button', { name: 'Enregistrer', exact: true }), `${passeRe}Commercial responsable : aucun « Enregistrer »`).toHaveCount(0)
    }
    const pd = await ecranDe(page, suivi, testInfo, di)
    await pd.goto('/stock/negoce/consignations')
    await reglages(pd)
    await expect(pd.getByLabel('Horizon ATP (jours)'), 'Directeur : horizon éditable').toBeEnabled()
    await expect(pd.getByRole('button', { name: 'Enregistrer', exact: true }), 'Directeur : « Enregistrer »').toBeVisible()
  } finally {
    await admin.patch(`${API}/stock/parametres-negoce/`, { ...T, data: { consignation_activee: p0.consignation_activee, atp_horizon_jours: p0.atp_horizon_jours } }).catch(() => null)
  }
})

// ── ADRG41 — référentiels d'entrepôt du module chantiers sous `stock_modifier` ; Paramétrage des kits ─────────────
const ROUTES_41 = ['bin-locations', 'bin-affectations', 'categories-stockage', 'regles-rangement', 'kits', 'kit-composants',
  'controle-qualite-modeles', 'etapes-assemblage', 'regles-reappro', 'transporteurs', 'sous-traitants']
etape('PF4.2-ADRG41-referentiels', ['ADRG41'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const te = await compteDe('Technicien', 'adrg41te')
  const tr = await compteDe('Technicien responsable', 'adrg41tr')
  expect([te.codes.includes('stock_modifier'), tr.codes.includes('stock_modifier')], 'Given : Technicien sans stock_modifier, Technicien responsable avec').toEqual([false, true])
  const [xte, xtr] = [await apiDe(testInfo, te), await apiDe(testInfo, tr)]
  const bilan = []
  for (const route of ROUTES_41) {
    const rt = await xte.post(`${API}/installations/${route}/`, { ...T, data: {} })
    const corps = await rt.text()
    const rr = await xtr.post(`${API}/installations/${route}/`, { ...T, data: {} })
    bilan.push({ route, te: rt.status(), nomme: corps.includes('stock_modifier'), tr: rr.status() })
  }
  console.log(`[ADRG41] ${J(bilan)}`)
  for (const b of bilan) {
    expect([b.te, b.nomme], `Technicien POST ${b.route} : 403 qui nomme stock_modifier`).toEqual([403, true])
    expect(b.tr, `Technicien responsable POST ${b.route} {} : garde passée (validation, pas 403)`).not.toBe(403)
  }
  const nomKit = `Kit ADRG41 ${m}`
  const kits = () => py(`from apps.installations.models_kitting import Kit
sortie(Kit.objects.filter(company_id=${SOC}, nom=${J(nomKit)}).count())`)
  await statut(await xte.post(`${API}/installations/kits/`, { ...T, data: { nom: nomKit } }), 403, 'Technicien POST kit complet')
  expect(await kits(), 'persistance : aucun kit créé par le Technicien').toBe(0)
  const kit = JSON.parse(await statut(await xtr.post(`${API}/installations/kits/`, { ...T, data: { nom: nomKit } }), 201, 'Technicien responsable POST kit'))
  expect(await kits(), 'témoin : kit créé par le Technicien responsable').toBe(1)
  // Écran Paramétrage des kits : route fermée au Technicien (palier normal → /403, aucun bouton) ; le Technicien
  // responsable y voit « Nouveau kit ».
  const pt = await ecranDe(page, suivi, testInfo, te)
  for (const passeRe of ['', 'relu après rechargement : ']) {
    if (passeRe) await pt.reload(); else await pt.goto('/atelier/kits')
    await expect(pt, `${passeRe}Technicien : Paramétrage des kits refusé`).toHaveURL(/\/403/, V)
    await calme(pt)
    await expect(pt.getByRole('button', { name: 'Nouveau kit' }), `${passeRe}Technicien : aucun « Nouveau kit »`).toHaveCount(0)
    await expect(pt.getByRole('button', { name: /Nouveau composant|Nouvelle étape|Activer|Supprimer/ }), `${passeRe}Technicien : aucun bouton d'écriture`).toHaveCount(0)
  }
  const pr = await ecranDe(page, suivi, testInfo, tr)
  await pr.goto('/atelier/kits')
  await expect(pr.getByRole('heading', { name: "Paramétrage des kits d'assemblage" }), 'Technicien responsable : écran rendu').toBeVisible(V)
  await expect(pr.getByRole('button', { name: 'Nouveau kit' }), 'Technicien responsable : « Nouveau kit »').toBeVisible(V)
  await xtr.delete(`${API}/installations/kits/${kit.id}/`, T).catch(() => null)
}, { ecart: {
  base: 'FAIL',
  raison: "/atelier/kits est réservé au palier responsable/admin (frontend/src/features/installations/module.config.jsx:107, depuis 2db39a7c2 du 08/08/2026, PACT61) : le Technicien (palier normal) est renvoyé sur /403, l'écran « Paramétrage des kits sans boutons d'écriture » de la clause n'est donc pas rendu pour lui. Garde de route antérieure à ADRG41 et hors de ses Files ; l'étape affirme la redirection sans aucun bouton, les 11 routes (Technicien 403 qui nomme stock_modifier) et le témoin Technicien responsable.",
} })

// ── ADRG43 — clôture d'une session de comptage chantier (ajustements de stock) : administrateur seul ──────────────
etape('PF4.2-ADRG43-comptage', ['ADRG43'], async ({ testInfo }) => {
  const m = marque()
  const ids = await py(`from apps.stock.models import Produit
from apps.installations.models_comptage import SessionComptage, ComptageLigne
p = Produit.objects.create(company_id=${SOC}, nom=${J(`Câble ADRG43 ${m}`)}, sku=${J(`ADRG43-${m}`)}, prix_vente=100, prix_achat=60, quantite_stock=10)
s = SessionComptage.objects.create(company_id=${SOC}, reference=${J(`CYC-ADRG43-${m}`)}, statut='en_cours')
ComptageLigne.objects.create(session=s, produit=p, designation=p.nom, quantite_theorique=10, quantite_comptee=7, compte=True)
sortie(dict(p=p.pk, s=s.pk, ref=s.reference))`)
  const etat = () => py(`from apps.stock.models import Produit, MouvementStock
from apps.installations.models_comptage import SessionComptage
sortie([SessionComptage.objects.get(pk=${ids.s}).statut, Produit.objects.get(pk=${ids.p}).quantite_stock, MouvementStock.objects.filter(company_id=${SOC}, reference=${J(ids.ref)}).count()])`)
  expect(await etat(), 'Given : session en cours, stock 10, aucun ajustement').toEqual(['en_cours', 10, 0])
  for (const nom of ['Technicien', 'Technicien responsable', 'Responsable']) {
    const x = await apiDe(testInfo, await compteDe(nom, 'adrg43'))
    await statut(await x.post(`${API}/installations/sessions-comptage/${ids.s}/terminer/`, { ...T, data: {} }), 403, `${nom} POST terminer`)
    expect(await etat(), `${nom} : session toujours en cours, stock inchangé, aucun ajustement posté`).toEqual(['en_cours', 10, 0])
  }
  // Témoin : le Directeur (palier administrateur) clôture — l'ajustement est posté.
  const di = await apiDe(testInfo, await compteDe('Directeur', 'adrg43di'))
  await statut(await di.post(`${API}/installations/sessions-comptage/${ids.s}/terminer/`, { ...T, data: {} }), 200, 'Directeur POST terminer')
  expect(await etat(), 'Directeur : session terminée, stock aligné sur le compté, un ajustement').toEqual(['termine', 7, 1])
})

// ── ADRG46 — SLA SAV et réglage de supervision sous `parametres_modifier` ; écrans en lecture seule sans le droit ──
etape('PF4.4-ADRG46-sla-supervision', ['ADRG46'], async ({ page, suivi, testInfo }) => {
  const admin = page.context().request
  const sla0 = await jsonDe(admin, 'sav/sla-settings/', 'SLA relus')
  const mon0 = await jsonDe(admin, 'monitoring/settings/', 'supervision relue')
  const lire = async () => {
    const [s, n] = [await jsonDe(admin, 'sav/sla-settings/', 'SLA relus'), await jsonDe(admin, 'monitoring/settings/', 'supervision relue')]
    return [s.sla_resolution_days, s.sla_response_days, String(n.underperf_threshold_pct), n.auto_create_ticket]
  }
  const avant = await lire()
  try {
    for (const nom of ['Commercial responsable', 'Technicien', 'Technicien responsable', 'Responsable']) {
      const c = await compteDe(nom, 'adrg46')
      expect(c.codes.includes('parametres_modifier'), `Given : ${nom} sans parametres_modifier`).toBe(false)
      const x = await apiDe(testInfo, c)
      await statut(await x.post(`${API}/sav/sla-settings/`, { ...T, data: { sla_resolution_days: (sla0.sla_resolution_days || 0) + 3 } }), 403, `${nom} POST sla-settings`)
      await statut(await x.post(`${API}/monitoring/settings/`, { ...T, data: { underperf_threshold_pct: '23.5', auto_create_ticket: !mon0.auto_create_ticket } }), 403, `${nom} POST monitoring/settings`)
    }
    expect(await lire(), 'persistance : SLA et supervision inchangés après les refus').toEqual(avant)
    const di = await compteDe('Directeur', 'adrg46di')
    await statut(await (await apiDe(testInfo, di)).post(`${API}/sav/sla-settings/`, { ...T, data: { sla_resolution_days: (sla0.sla_resolution_days || 0) + 3 } }), 200, 'Directeur POST sla-settings')
    expect((await lire())[0], 'Directeur : délai écrit').toBe((sla0.sla_resolution_days || 0) + 3)
    await admin.post(`${API}/sav/sla-settings/`, { ...T, data: { sla_resolution_days: sla0.sla_resolution_days } })
    // Écrans au Commercial responsable : /sav/parametres (SLA / Automatisation) et Paramètres → Supervision.
    const LIBELLE = 'Délai de résolution cible (jours)'
    async function ongletSla(p) {
      await p.goto('/sav/parametres')
      await p.getByRole('tab', { name: 'SLA / Automatisation' }).click()
      const panneau = p.getByRole('tabpanel')
      await expect(panneau.getByLabel(LIBELLE), 'onglet SLA rendu').toHaveValue(String(sla0.sla_resolution_days), V)
      return panneau
    }
    const pc = await ecranDe(page, suivi, testInfo, await compteDe('Commercial responsable', 'adrg46cr'))
    for (const passeRe of ['', 'relu après rechargement : ']) {
      if (passeRe) await pc.reload()
      const panneau = await ongletSla(pc)
      await expect(panneau.getByLabel(LIBELLE), `${passeRe}Commercial responsable : délai SLA en lecture seule`).toBeDisabled()
      await expect(panneau.getByTestId('sla-lecture-seule'), `${passeRe}Commercial responsable : lecture seule annoncée`).toBeVisible()
      await expect(panneau.getByRole('button', { name: 'Enregistrer', exact: true }), `${passeRe}Commercial responsable : aucun « Enregistrer » SLA`).toHaveCount(0)
      await pc.goto('/parametres?onglet=monitoring')
      await expect(pc.locator('#underperf-threshold'), `${passeRe}Commercial responsable : seuil de supervision affiché`).toBeVisible(V)
      await expect(pc.locator('#underperf-threshold'), `${passeRe}Commercial responsable : seuil en lecture seule`).toBeDisabled()
      await expect(pc.getByTestId('supervision-lecture-seule'), `${passeRe}Commercial responsable : supervision en lecture seule`).toBeVisible()
    }
    const pd = await ecranDe(page, suivi, testInfo, di)
    const panneauD = await ongletSla(pd)
    await expect(panneauD.getByLabel(LIBELLE), 'Directeur : délai éditable').toBeEnabled()
    await expect(panneauD.getByRole('button', { name: 'Enregistrer', exact: true }), 'Directeur : « Enregistrer »').toBeVisible()
  } finally {
    await admin.post(`${API}/sav/sla-settings/`, { ...T, data: { sla_resolution_days: sla0.sla_resolution_days } }).catch(() => null)
    await admin.post(`${API}/monitoring/settings/`, { ...T, data: { underperf_threshold_pct: mon0.underperf_threshold_pct, auto_create_ticket: mon0.auto_create_ticket } }).catch(() => null)
  }
})

// ── ADRG69 — « Journal d'activité » des rapports sous `journal_activite_voir` : Commercial 403 + carte absente ─────
etape('PF4.3-ADRG69-journal', ['ADRG69'], async ({ page, suivi, testInfo }) => {
  const co = await compteDe('Commercial', 'adrg69co')
  const di = await compteDe('Directeur', 'adrg69di')
  expect([co.codes.includes('journal_activite_voir'), di.codes.includes('journal_activite_voir')], 'Given : Commercial sans journal_activite_voir, Directeur avec').toEqual([false, true])
  const [xco, xdi] = [await apiDe(testInfo, co), await apiDe(testInfo, di)]
  for (const q of ['', '?export=xlsx']) {
    await statut(await xco.get(`${API}/reporting/insights/audit-log/${q}`, T), 403, `Commercial audit-log${q}`)
    expect((await xdi.get(`${API}/reporting/insights/audit-log/${q}`, T)).status(), `Directeur audit-log${q}`).toBe(200)
  }
  const TITRE = "Journal d'activité (qui a fait quoi)"
  const pc = await ecranDe(page, suivi, testInfo, co)
  const appels = []
  pc.on('request', (r) => { if (/\/reporting\/insights\/audit-log\//.test(r.url())) appels.push(r.url()) })
  for (const passeRe of ['', 'relu après rechargement : ']) {
    if (passeRe) await pc.reload(); else await pc.goto('/rapports')
    const onglet = pc.getByRole('tab', { name: 'Insights', exact: true })
    await expect(onglet, `${passeRe}Commercial : rapports rendus`).toBeVisible(V)
    await onglet.click()
    await expect(onglet, `${passeRe}Commercial : onglet Insights ouvert`).toHaveAttribute('aria-selected', 'true')
    await expect(pc.getByRole('tabpanel'), `${passeRe}Commercial : panneau Insights rendu`).toBeVisible(V)
    await calme(pc)
    await expect(pc.getByText(TITRE), `${passeRe}Commercial : carte Journal absente`).toHaveCount(0)
    expect(appels, `${passeRe}Commercial : aucun appel audit-log (donc aucune 403 en console)`).toEqual([])
  }
  const pd = await ecranDe(page, suivi, testInfo, di)
  for (const passeRe of ['', 'relu après rechargement : ']) {
    if (passeRe) await pd.reload(); else await pd.goto('/rapports')
    await pd.getByRole('tab', { name: 'Insights', exact: true }).click()
    await expect(pd.getByText(TITRE).first(), `${passeRe}Directeur : carte Journal rendue`).toBeVisible(V)
  }
})

// ── ADRG70 — rapports ventes/CRM (11 routes) sous la lecture du module source : Technicien 403, Commercial 200 ─────
const ROUTES_70 = (client) => [
  'reporting/dashboard/', 'reporting/reports/sales/', 'reporting/insights/analytics/',
  'reporting/insights/sales-leaderboard/', 'reporting/insights/cohorts/', `reporting/archive/client/${client}/`,
  'reporting/balance-agee/export/', 'reporting/commercial/dashboard/', 'reporting/commercial/win-loss-by-source/',
  'reporting/pipeline/', 'reporting/pipeline/velocity/',
]
etape('PF4.3-ADRG70-rapports', ['ADRG70'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const cl = await py(`from apps.crm.models import Client
c = Client.objects.create(company_id=${SOC}, nom='Client ADRG70 ${m}', email='adrg70_${m}@example.invalid')
sortie(c.pk)`)
  try {
    const te = await compteDe('Technicien', 'adrg70te')
    const co = await compteDe('Commercial', 'adrg70co')
    const cr = await compteDe('Commercial responsable', 'adrg70cr')
    // Le Client n'a pas de propriétaire : il entre dans la portée d'un compte par un lead dont il est le responsable
    // (`core/scoping.py::scope_client_queryset`) — un lead par compte lecteur.
    await py(`from apps.crm.models import Lead
for o in (${co.id}, ${cr.id}, ${te.id}):
    Lead.objects.create(company_id=${SOC}, nom='Lead ADRG70 ${m} ' + str(o), client_id=${cl}, owner_id=o)
sortie(1)`)
    const [xte, xco, xcr] = [await apiDe(testInfo, te), await apiDe(testInfo, co), await apiDe(testInfo, cr)]
    const bilan = []
    for (const route of ROUTES_70(cl)) {
      bilan.push({ route, te: (await xte.get(`${API}/${route}`, T)).status(), co: (await xco.get(`${API}/${route}`, T)).status(), cr: (await xcr.get(`${API}/${route}`, T)).status() })
    }
    console.log(`[ADRG70] ${J(bilan)}`)
    for (const b of bilan) {
      expect(b.te, `Technicien 403 : ${b.route}`).toBe(403)
      expect(b.cr, `Commercial responsable 200 : ${b.route}`).toBe(200)
      // Le Commercial ne porte pas `reporting_export` : l'export de la balance âgée reste refusé (inchangé).
      expect(b.co, `Commercial : ${b.route}`).toBe(b.route.startsWith('reporting/balance-agee/export/') ? 403 : 200)
    }
    // Écrans au Technicien : accueil puis /reporting — aucune erreur visible, aucune donnée de vente servie.
    const p = await ecranDe(page, suivi, testInfo, te)
    const servis = []
    const lus = []
    p.on('response', (x) => {
      const chemin = new URL(x.url()).pathname.replace(`${API}/`, '')
      if (ROUTES_70(cl).some((r) => chemin === r)) lus.push(`${chemin} → ${x.status()}`)
      if (x.status() === 200 && ROUTES_70(cl).some((r) => chemin === r)) servis.push(chemin)
    })
    for (const passeRe of ['', 'relu après rechargement : ']) {
      if (passeRe) await p.reload(); else await p.goto('/dashboard')
      await expect(p.locator('main').first(), `${passeRe}Technicien : accueil rendu`).toBeVisible(V)
      await calme(p)
      expect(lus, `${passeRe}Technicien : l'accueil ne tente aucune lecture ventes/CRM`).toEqual([])
    }
    await p.goto('/reporting')
    await calme(p)
    console.log(`[ADRG70] /reporting du Technicien → ${p.url()} ; lectures ventes/CRM : ${J(lus)}`)
    await expect(p, 'Technicien : /reporting refusé (écran 403, aucune donnée)').toHaveURL(/\/403/)
    expect(servis, 'Technicien : aucune route ventes/CRM servie à l\'écran').toEqual([])
    expect(lus, 'Technicien : aucune lecture ventes/CRM tentée (donc aucune 403 en console)').toEqual([])
  } finally {
    await py(`from apps.crm.models import Client
Client.objects.filter(pk=${cl}).delete()
sortie(1)`).catch(() => null)
  }
}, { ecart: {
  base: 'FAIL',
  raison: "/reporting est réservé au palier responsable/admin (frontend/src/features/reporting/module.config.jsx:142, roles RESPONSABLE_ADMIN, depuis ee7df19b4 du 10/07/2026) : le Technicien y est renvoyé sur /403, l'écran « /reporting sans donnée de vente » de la clause n'est donc pas rendu pour lui. Garde de route antérieure à ADRG70 et hors de ses Files (backend reporting seul) ; l'étape affirme la redirection, l'accueil sans aucune lecture ventes/CRM et les 11 routes (Technicien 403, Commercial 200).",
} })
