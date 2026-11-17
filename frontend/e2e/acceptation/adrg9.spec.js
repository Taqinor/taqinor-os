// Preuves en direct du groupe ADRG, lot 9 (vague d'acceptation 6, runner GitHub, 16/11/2026) : rejeu sur `main`
// des tâches « code livré, preuve en direct due » ADRG4, 5, 20, 21, 22, 37, 40, 47, 63 (parcours PF4 « droits de la
// grille », dossier docs/audits/2026-11-10-parcours-PF4.md). Les étapes reprennent celles des lots 1-3 (13/11) SANS
// leurs anciens écarts (lectures refusées retirées depuis, ADRG113-115, 124-137) ; seul ADRG63 déclare un écart
// (garde d'écran antérieure, hors de ses Files — relecture adverse du 16/11). Comptes
// d'essai aux rôles SYSTÈME du registre (`init_roles`, relus par leur nom dans la société de demo_admin — jamais un
// rôle fabriqué), connectés par la vraie route `/token/` ; chaque écran est rendu dans un navigateur à part (aucun
// cookie de demo_admin). Données propres créées par l'API ou le shell Django ; persistance = relecture en base
// après le refus, écrans relus après rechargement.
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { connexionApi, assurerSessionPage, lireJson, telephoneMobileUnique } from '../helpers.js'

const etape = groupe('ADRG', ['ADRG4', 'ADRG5', 'ADRG20', 'ADRG21', 'ADRG22', 'ADRG37', 'ADRG40', 'ADRG47', 'ADRG63'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const V = { timeout: 60_000 }
test.describe.configure({ timeout: 480_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
// Contextes des rôles : fermés APRÈS l'étape (ses oracles, dont le 8, relisent chaque page encore ouverte).
const OUVERTS = []
test.afterEach(async () => { for (const fermer of OUVERTS.splice(0)) await fermer().catch(() => undefined) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const J = JSON.stringify
const SOC = `U.objects.get(username='demo_admin').company_id`
const echapper = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const aujourdhui = () => new Date().toISOString().slice(0, 10)
const comptes = []
test.afterAll(async () => {
  if (!comptes.length) return
  await py(`U.objects.filter(username__in=${J(comptes)}).update(is_active=False)
sortie(1)`).catch(() => null)
})

/** Compte d'essai du rôle SYSTÈME `nomRole` (null = compte hérité « responsable » sans rôle fin) ; {username, id, codes}. */
async function compteDe(nomRole, prefixe) {
  const username = `${prefixe}_${marque()}`
  const r = await py(`from apps.roles.models import Role
r = ${nomRole === null ? 'None' : `Role.objects.get(company_id=${SOC}, nom=${J(nomRole)}, est_systeme=True)`}
u = compte(${J(username)}, role=(r.pk if r else None), societe=${SOC})
${nomRole === null ? "u.role_id = None; u.role_legacy = 'responsable'; u.save()" : ''}
sortie(dict(id=u.id, codes=sorted((r.permissions if r else None) or [])))`)
  comptes.push(username)
  return { username, id: r.id, codes: r.codes, nomRole }
}
/** Contexte API connecté par la vraie route `/token/`. */
async function apiDe(testInfo, c) {
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  OUVERTS.push(() => ctx.dispose())
  await connexionApi(ctx, { username: c.username, password: MDP_ESSAI })
  return ctx
}
/** Onglet navigateur neuf connecté sous `c`, visites guidées fermées, observé par les oracles. La page demo_admin
 *  de l'étape est refermée : la capture de l'étape montre l'écran du rôle joué. */
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
/** Ouvre `url` et attend la réponse de liste `re` (la donnée est chargée : une absence vaut alors preuve). */
async function ouvrir(p, url, re) {
  const charge = re ? p.waitForResponse((r) => re.test(new URL(r.url()).pathname) && r.request().method() === 'GET', V) : null
  await p.goto(url)
  if (charge) expect((await charge).status(), `chargement ${url}`).toBeLessThan(400)
  await p.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => undefined)
}
/** 403 ; `code` : le refus nomme ce code (et `droit_manquant`). */
async function refus(rep, quoi, code = null) {
  const t = await rep.text()
  expect(rep.status(), `${quoi} : ${t.slice(0, 240)}`).toBe(403)
  if (code) {
    expect(t, `${quoi} : le refus nomme ${code}`).toContain(code)
    expect(t, `${quoi} : code droit_manquant`).toContain('droit_manquant')
  }
}
async function passe(rep, quoi, attendus = [200, 201, 204]) {
  const t = rep.status() === 204 ? '' : await rep.text()
  expect(attendus, `${quoi} → ${rep.status()} ${t.slice(0, 240)}`).toContain(rep.status())
  if (!t) return null
  try { return JSON.parse(t) } catch { return t }
}
const bouton = (p, nom) => p.getByRole('button', { name: nom })
const clientCrm = async (r, m) => lireJson(await r.post(`${API}/crm/clients/`, { ...T, data: { nom: `ADRG9 ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), email: `adrg9_${m}@example.invalid` } }), 'client')
const produitApi = async (r, nom) => lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom, prix_vente: '1000.00', prix_achat: '600.00' } }), 'produit')
/** Devis posé par demo_admin (lead + ligne produit) ; `etat` : brouillon, envoye ou accepte. */
async function devisDemo(r, m, etat, prod) {
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `ADRG9 ${etat} ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `adrg9${etat}${m}@example.invalid` } }), 'lead')
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, lignes: [{ produit: prod.id, designation: prod.nom, quantite: '1', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  if (etat !== 'brouillon') await lireJson(await r.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  if (etat === 'accepte') await lireJson(await r.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client ADRG9' } }), 'accepter')
  return d
}
/** Libellés des entrées d'un menu ouvert (Radix), menu refermé ensuite. */
async function entreesMenu(p) {
  const menu = p.getByRole('menu')
  await expect(menu, 'menu ouvert').toBeVisible({ timeout: 30_000 })
  const textes = (await menu.getByRole('menuitem').allInnerTexts()).map((x) => x.replace(/\s+/g, ' ').trim())
  await p.keyboard.press('Escape')
  await expect(menu).toBeHidden()
  return textes
}

// ── ADRG4 — supprimer un objet autonome du CRM (15 routes) exige `crm_supprimer` ; « Retirer » des appareils ──────
const ROUTES_4 = ['salles-vente', 'partenaires', 'apporteurs', 'deals-enregistres', 'defis', 'appareils-equipe',
  'parrainages', 'plans-activite', 'concurrents-perte', 'forecast-entries', 'plans-compte', 'revues-compte',
  'playbooks', 'playbook-etapes', 'playbook-taches']
etape('PF4.1-ADRG4-suppressions', ['ADRG4'], async ({ page, suivi, testInfo }) => {
  const admin = page.context().request
  const m = marque()
  const co = await compteDe('Commercial', 'adrg4co')
  const re = await compteDe('Responsable', 'adrg4re')
  const cr = await compteDe('Commercial responsable', 'adrg4cr')
  expect([co.codes.includes('crm_supprimer'), re.codes.includes('crm_supprimer'), cr.codes.includes('crm_supprimer')],
    'Given : Commercial et Responsable sans crm_supprimer, Commercial responsable avec').toEqual([false, false, true])
  const [xco, xre, xcr] = [await apiDe(testInfo, co), await apiDe(testInfo, re), await apiDe(testInfo, cr)]
  // Défi réel : refusé aux deux rôles sans le code (toujours en base), supprimé (204) par le Commercial responsable.
  const defi = await py(`from apps.crm.models_clients import Defi, ObjectifCommercial
d = Defi.objects.create(company_id=${SOC}, nom=${J(`Défi ADRG4 ${m}`)}, periode_debut=datetime.date.today(), periode_fin=datetime.date.today() + datetime.timedelta(days=30), metrique=ObjectifCommercial.Metric.choices[0][0])
sortie(d.id)`)
  const existe = () => py(`from apps.crm.models_clients import Defi
sortie(Defi.objects.filter(pk=${defi}).exists())`)
  await refus(await xco.delete(`${API}/crm/defis/${defi}/`, T), 'Commercial DELETE défi')
  await refus(await xre.delete(`${API}/crm/defis/${defi}/`, T), 'Responsable DELETE défi', 'crm_supprimer')
  expect(await existe(), 'persistance : le défi existe après les deux refus').toBe(true)
  expect((await xcr.delete(`${API}/crm/defis/${defi}/`, T)).status(), 'Commercial responsable DELETE défi').toBe(204)
  expect(await existe(), 'relu : défi supprimé par le Commercial responsable').toBe(false)
  // Les 14 autres routes : la garde précède la recherche de l'objet (DRF `initial`) — id absent : sans le code 403,
  // avec le code la garde passe et la route répond 404 (objet introuvable ou viewset parqué).
  const bilan = []
  for (const route of ROUTES_4.filter((x) => x !== 'defis')) {
    const url = `${API}/crm/${route}/2147480000/`
    const [rc, rr, rk] = [await xco.delete(url, T), await xre.delete(url, T), await xcr.delete(url, T)]
    const corpsRe = await rr.text()
    bilan.push({ route, co: rc.status(), re: rr.status(), cr: rk.status(), nomme: corpsRe.includes('crm_supprimer') })
  }
  console.log(`[ADRG4] ${J(bilan)}`)
  for (const b of bilan) {
    expect(b.co, `Commercial DELETE ${b.route}`).toBe(403)
    expect([b.re, b.nomme], `Responsable DELETE ${b.route} : 403 qui nomme crm_supprimer`).toEqual([403, true])
    expect(b.cr, `Commercial responsable DELETE ${b.route} : garde passée (404)`).toBe(404)
  }
  // Écran CRM → Visiteurs, carte « Appareils équipe » : « Retirer » au Commercial responsable, absent au Responsable.
  const libelle = `Poste ADRG4 ${m}`
  const app = await lireJson(await admin.post(`${API}/crm/appareils-equipe/`, { ...T, data: { appareil_id: `adrg4-${m}-appareil`, libelle } }), 'appareil équipe')
  try {
    for (const [c, retirer] of [[cr, true], [re, false]]) {
      const p = await ecranDe(page, suivi, testInfo, c)
      await p.goto('/crm/visiteurs')
      for (const passeRe of ['', 'relu après rechargement : ']) {
        if (passeRe) await p.reload()
        const ligne = p.getByRole('row').filter({ hasText: libelle })
        await expect(ligne, `${passeRe}${c.nomRole} : appareil équipe listé`).toBeVisible(V)
        await expect(ligne.getByRole('button', { name: 'Retirer', exact: true }), `${passeRe}${c.nomRole} : « Retirer » ${retirer ? 'présent' : 'absent'}`).toHaveCount(retirer ? 1 : 0)
      }
    }
  } finally {
    await admin.delete(`${API}/crm/appareils-equipe/${app.id}/`, T).catch(() => null)
  }
})

// ── ADRG5 — supprimer une liste de prix / un modèle partagé exige `ventes_supprimer` ; « Supprimer » à qui le porte ─
etape('PF4.1-ADRG5-listes-prix', ['ADRG5'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const ids = await py(`from apps.ventes.models import ListePrix, DevisPreset
l = ListePrix.objects.create(company_id=${SOC}, nom='Liste ADRG5 ${m}')
d = DevisPreset.objects.create(company_id=${SOC}, nom='Modèle ADRG5 ${m}', lignes_snapshot=[])
sortie(dict(liste=l.pk, preset=d.pk, nom=l.nom))`)
  const existent = () => py(`from apps.ventes.models import ListePrix, DevisPreset
sortie([ListePrix.objects.filter(pk=${ids.liste}).exists(), DevisPreset.objects.filter(pk=${ids.preset}).exists()])`)
  try {
    const co = await compteDe('Commercial', 'adrg5co')
    const cr = await compteDe('Commercial responsable', 'adrg5cr')
    expect([co.codes.includes('ventes_supprimer'), cr.codes.includes('ventes_supprimer')], 'Given : Commercial sans ventes_supprimer, Commercial responsable avec').toEqual([false, true])
    const [xco, xcr] = [await apiDe(testInfo, co), await apiDe(testInfo, cr)]
    await refus(await xco.delete(`${API}/ventes/listes-prix/${ids.liste}/`, T), 'Commercial DELETE liste de prix', 'ventes_supprimer')
    await refus(await xco.delete(`${API}/ventes/presets/${ids.preset}/`, T), 'Commercial DELETE modèle', 'ventes_supprimer')
    expect(await existent(), 'persistance : les deux objets existent après les refus').toEqual([true, true])
    // Écran Ventes → Listes de prix : fiche ouverte, « Supprimer » absent au Commercial, présent au Commercial responsable.
    for (const [c, visible] of [[co, false], [cr, true]]) {
      const p = await ecranDe(page, suivi, testInfo, c)
      await p.goto('/ventes/listes-prix')
      for (const passeRe of ['', 'relu après rechargement : ']) {
        if (passeRe) await p.reload()
        await p.getByRole('button', { name: ids.nom, exact: true }).click({ timeout: 60_000 })
        const dlg = p.getByRole('dialog')
        await expect(dlg.getByRole('button', { name: 'Archiver' }), `${passeRe}${c.nomRole} : fiche de la liste ouverte`).toBeVisible(V)
        const suppr = dlg.getByRole('button', { name: 'Supprimer', exact: true })
        if (visible) await expect(suppr, `${passeRe}${c.nomRole} : « Supprimer » présent`).toBeVisible()
        else await expect(suppr, `${passeRe}${c.nomRole} : aucun « Supprimer »`).toHaveCount(0)
        await p.keyboard.press('Escape')
      }
    }
    expect((await xcr.delete(`${API}/ventes/listes-prix/${ids.liste}/`, T)).status(), 'Commercial responsable : liste 204').toBe(204)
    expect((await xcr.delete(`${API}/ventes/presets/${ids.preset}/`, T)).status(), 'Commercial responsable : modèle 204').toBe(204)
    expect(await existent(), 'relu : supprimés par le Commercial responsable').toEqual([false, false])
  } finally {
    await py(`from apps.ventes.models import ListePrix, DevisPreset
ListePrix.objects.filter(pk=${ids.liste}).delete(); DevisPreset.objects.filter(pk=${ids.preset}).delete()
sortie(1)`).catch(() => null)
  }
})

// ── ADRG20 — fiche et liste des leads : Commercial sans réaffectation ; Viewer sans écriture ni export ─────────────
etape('PF4.4-ADRG20-leads', ['ADRG20'], async ({ page, suivi, testInfo }) => {
  const admin = page.context().request
  for (const [nomRole, prefixe] of [['Commercial', 'adrg20co'], ['Viewer', 'adrg20vi']]) {
    const c = await compteDe(nomRole, prefixe)
    const ecrit = nomRole === 'Commercial'
    expect([c.codes.includes('crm_reassign'), c.codes.includes('crm_modifier'), c.codes.includes('crm_export')],
      `Given : codes crm du ${nomRole}`).toEqual([false, ecrit, ecrit])
    const m = marque()
    const leads = []
    for (const k of ['a', 'b']) {
      const l = await lireJson(await admin.post(`${API}/crm/leads/`, { ...T, data: { nom: `ADRG20 ${m}${k}`, ville: 'Casablanca', telephone: telephoneMobileUnique() } }), 'lead')
      await py(`from apps.crm.models import Lead
Lead.objects.filter(pk=${l.id}).update(owner_id=${c.id})
sortie(1)`)
      leads.push(l)
    }
    const p = await ecranDe(page, suivi, testInfo, c)
    for (const passeRe of ['', 'relu après rechargement : ']) {
      // Fiche : sélecteur « Responsable » inerte (crm_reassign absent) ; menu ⋯ : écriture selon crm_modifier.
      await p.goto(`/crm/leads/${leads[0].id}`)
      if (passeRe) await p.reload()
      const picker = p.locator('.lw-rail-triade .ap-trigger')
      await expect(picker, `${passeRe}${nomRole} : rail de la fiche rendu`).toBeVisible(V)
      await expect(picker, `${passeRe}${nomRole} : sélecteur « Responsable » du rail inerte`).toBeDisabled()
      // Section « Suivi commercial » (SectionPipeline, #lf-owner) : même sélecteur, rendu désactivé (crm_reassign absent).
      const owner = p.locator('#lf-owner .ap-trigger')
      if (!(await owner.isVisible().catch(() => false))) {
        await p.getByRole('button', { name: /Suivi commercial/ }).first().click().catch(() => undefined)
      }
      await owner.scrollIntoViewIfNeeded()
      await expect(owner, `${passeRe}${nomRole} : sélecteur « Responsable » de la section Suivi commercial rendu`).toBeVisible(V)
      await expect(owner, `${passeRe}${nomRole} : sélecteur « Responsable » de la section Suivi commercial inerte`).toBeDisabled()
      await p.getByRole('button', { name: /Plus d'actions/ }).first().click()
      const menu = p.getByRole('menu')
      await expect(menu).toBeVisible({ timeout: 30_000 })
      for (const nom of [/Convertir en client/, /^Archiver$/]) {
        const item = menu.getByRole('menuitem', { name: nom })
        await expect(item, `${passeRe}${nomRole} : ${nom}`).toHaveCount(1)
        if (ecrit) await expect(item, `${passeRe}${nomRole} : ${nom} actif`).not.toHaveAttribute('aria-disabled', 'true')
        else await expect(item, `${passeRe}${nomRole} : ${nom} inerte`).toHaveAttribute('aria-disabled', 'true')
      }
      await p.keyboard.press('Escape')
      // Liste : barre de masse sur deux leads ; « Responsable » (réaffecter en masse) jamais offert.
      await p.goto('/crm/leads')
      await p.getByRole('radio', { name: 'Vue liste' }).click()
      for (const l of leads) {
        await p.getByRole('checkbox', { name: new RegExp(`Sélectionner .*${echapper(l.nom)}`) }).check({ timeout: 60_000 })
      }
      const barre = p.getByRole('region', { name: 'Actions en masse' }).first()
      await expect(barre, `${passeRe}${nomRole} : barre de masse`).toContainText(/2\s*sélectionnés/, { timeout: 30_000 })
      await expect(barre.getByRole('button', { name: 'Responsable', exact: true }), `${passeRe}${nomRole} : aucun « Réaffecter »`).toHaveCount(0)
      await expect(barre.getByRole('button', { name: 'Étape', exact: true }), `${passeRe}${nomRole} : Étape`).toHaveCount(ecrit ? 1 : 0)
      await expect(barre.getByRole('button', { name: 'Archiver', exact: true }), `${passeRe}${nomRole} : Archiver`).toHaveCount(ecrit ? 1 : 0)
      await expect(barre.getByRole('button', { name: /Exporter Excel/ }), `${passeRe}${nomRole} : Exporter Excel (masse)`).toHaveCount(ecrit ? 1 : 0)
      await p.getByRole('button', { name: "Plus d'actions", exact: true }).click()
      const entete = await entreesMenu(p)
      expect(entete.some((x) => /Exporter Excel/.test(x)), `${passeRe}${nomRole} : Exporter Excel (en-tête) ${J(entete)}`).toBe(ecrit)
    }
    const owners = await py(`from apps.crm.models import Lead
sortie(sorted(set(Lead.objects.filter(pk__in=${J(leads.map((l) => l.id))}).values_list('owner_id', flat=True))))`)
    expect(owners, `${nomRole} : rendu seul, owner relu inchangé`).toEqual([c.id])
  }
})

// ── ADRG21 — fiche/liste chantier au Commercial (lecture), planning du Technicien non glissable ────────────────────
etape('PF4.2-ADRG21-chantier', ['ADRG21'], async ({ page, suivi, testInfo }) => {
  const admin = page.context().request
  const m = marque()
  const tr = await compteDe('Technicien responsable', 'adrg21tr')
  const te = await compteDe('Technicien', 'adrg21te')
  const co = await compteDe('Commercial', 'adrg21co')
  expect([co.codes.includes('installation_gerer'), co.codes.includes('installation_export'), te.codes.includes('technicien_assign'), tr.codes.includes('technicien_assign')],
    'Given : Commercial sans installation_gerer/export ; Technicien sans technicien_assign ; Technicien responsable avec').toEqual([false, false, false, true])
  await py(`U.objects.filter(pk=${te.id}).update(supervisor_id=${tr.id})
sortie(1)`)
  const dv = await devisDemo(admin, m, 'brouillon', await produitApi(admin, `Onduleur réseau ADRG21 ${m}`))
  const ids = await py(`from apps.installations.models import Installation, Intervention
from apps.ventes.models import Devis
Devis.objects.filter(pk=${dv.id}).update(created_by_id=${co.id})
i = Installation.objects.create(company_id=${SOC}, reference='CHT-ADRG21-${m}', statut='installe', created_by_id=${co.id}, technicien_responsable_id=${te.id}, devis_id=${dv.id})
iv = Intervention.objects.create(company_id=${SOC}, installation=i, type_intervention='pose', technicien_id=${te.id}, created_by_id=${te.id}, date_prevue=timezone.localdate())
sortie(dict(chantier=i.pk, ref=i.reference, iv=iv.pk))`)
  try {
    const pc = await ecranDe(page, suivi, testInfo, co)
    await pc.goto(`/chantiers?id=${ids.chantier}`)
    for (const passeRe of ['', 'relu après rechargement : ']) {
      if (passeRe) await pc.reload()
      const fiche = pc.getByRole('dialog')
      await expect(fiche.getByText(`Chantier — ${ids.ref}`).first(), `${passeRe}Commercial : fiche chantier ouverte`).toBeVisible(V)
      await expect(fiche.getByRole('button', { name: 'Fermer', exact: true }).first(), `${passeRe}Commercial : fiche rendue`).toBeVisible()
      for (const geste of ['Mettre à jour', 'Annuler le chantier', 'Marquer réceptionné']) {
        await expect(fiche.getByRole('button', { name: geste }), `${passeRe}Commercial : pas de « ${geste} »`).toHaveCount(0)
      }
    }
    // Liste /chantiers SANS fiche ouverte (sinon la feuille modale masque la page aux rôles ARIA) : le chantier est
    // listé, aucun « Exporter Excel » au Commercial ; témoin : le Technicien responsable (installation_export) l'a.
    async function liste(p) {
      await p.goto('/chantiers')
      await expect(p.getByText(ids.ref).first(), 'liste des chantiers : le chantier est listé').toBeVisible(V)
      await expect(p.getByRole('dialog'), 'liste sans fiche ouverte').toHaveCount(0)
    }
    for (const passeRe of ['', 'relu après rechargement : ']) {
      if (passeRe) await pc.reload()
      await liste(pc)
      await expect(pc.getByRole('button', { name: /Exporter Excel/ }), `${passeRe}Commercial : aucun « Exporter Excel » sur la liste`).toHaveCount(0)
    }
    const pt = await ecranDe(page, suivi, testInfo, te)
    await pt.goto(`/chantiers?id=${ids.chantier}`)
    // Témoin (installation_gerer, chantier « installé ») : les trois gestes de la fiche sont offerts.
    for (const geste of ['Mettre à jour', 'Annuler le chantier', 'Marquer réceptionné']) {
      await expect(pt.getByRole('dialog').getByRole('button', { name: geste }).first(), `Technicien : « ${geste} » présent`).toBeVisible(V)
    }
    await pt.goto('/planification')
    for (const passeRe of ['', 'relu après rechargement : ']) {
      if (passeRe) await pt.reload()
      const carte = pt.getByTestId(`iv-${ids.iv}`)
      await expect(carte, `${passeRe}Technicien : intervention au planning`).toBeVisible(V)
      await expect(carte.getByRole('button', { name: /Déplacer l'intervention/ }), `${passeRe}Technicien : carte non glissable`).toHaveCount(0)
      await expect(pt.getByText(/Lecture seule : déplacer une intervention demande le droit/), `${passeRe}Technicien : lecture seule annoncée`).toBeVisible()
    }
    const pr = await ecranDe(page, suivi, testInfo, tr)
    await pr.goto('/planification')
    await expect(pr.getByTestId(`iv-${ids.iv}`).getByRole('button', { name: /Déplacer l'intervention/ }), 'Technicien responsable : carte glissable').toBeVisible(V)
    await liste(pr)
    await expect(pr.getByRole('button', { name: /Exporter Excel/ }), 'Technicien responsable (installation_export) : « Exporter Excel » présent').toBeVisible(V)
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

// ── ADRG22 — tickets SAV : Technicien sans « Assigner à » ni technicien éditable ; Commercial sans aucun geste ──────
etape('PF4.4-ADRG22-tickets', ['ADRG22'], async ({ page, suivi, testInfo }) => {
  const admin = page.context().request
  const m = marque()
  const te = await compteDe('Technicien', 'adrg22te')
  const co = await compteDe('Commercial', 'adrg22co')
  const re = await compteDe('Responsable', 'adrg22re')
  expect([te.codes.includes('sav_gerer'), te.codes.includes('sav_reassign'), co.codes.includes('sav_voir'), co.codes.includes('sav_gerer')],
    'Given : Technicien sav_gerer sans sav_reassign ; Commercial sav_voir sans sav_gerer').toEqual([true, false, true, false])
  const cl = await clientCrm(admin, m)
  const tickets = []
  for (const s of ['a', 'b']) tickets.push(await lireJson(await admin.post(`${API}/sav/tickets/`, { ...T, data: { client: cl.id, type: 'correctif', description: `ADRG22 ${m} ${s}` } }), 'ticket'))
  await py(`from apps.sav.models import Ticket
Ticket.objects.filter(pk__in=${J(tickets.map((t) => t.id))}).update(technicien_responsable_id=${te.id}, created_by_id=${co.id})
sortie(1)`)
  const refs = tickets.map((t) => t.reference || t.numero || `ADRG22 ${m}`)
  async function actionsGroupees(p) {
    await ouvrir(p, '/sav', /\/sav\/tickets\/?$/)
    await p.getByPlaceholder('Rechercher (référence, client, chantier, description)…').fill(refs[0] === refs[1] ? `ADRG22 ${m}` : String(m))
    for (const ref of refs) {
      const ligne = p.getByRole('row').filter({ hasText: ref }).first()
      await expect(ligne, `ligne ${ref}`).toBeVisible(V)
      await ligne.getByRole('checkbox').first().check()
    }
    const barre = p.locator('[aria-label="2 ligne(s) sélectionnée(s)"]')
    await expect(barre, 'barre d’actions groupées').toBeVisible(V)
    const libelles = (await barre.getByRole('button').allInnerTexts()).map((x) => x.trim())
    const plus = barre.getByRole('button', { name: /^Plus$/ })
    if (await plus.count()) {
      await plus.click()
      libelles.push(...(await p.getByRole('menuitem').allInnerTexts()).map((x) => x.trim()))
      await p.keyboard.press('Escape')
    }
    return libelles
  }
  async function fiche(p) {
    await ouvrir(p, `/sav?id=${tickets[0].id}`, /\/sav\/tickets\/?$/)
    const d = p.locator('aside[aria-label^="Détail du ticket"], [role="dialog"]').filter({ has: p.locator('label', { hasText: /^Technicien responsable/ }) }).first()
    await expect(d, 'fiche ticket').toBeVisible(V)
    return d
  }
  const champ = (d, libelle) => d.locator('label', { hasText: new RegExp(`^${libelle}`) }).first().locator('xpath=..').getByRole('combobox').first()
  const t1 = await ecranDe(page, suivi, testInfo, te)
  const c1 = await ecranDe(page, suivi, testInfo, co)
  for (const passeRe of ['', 'relu après rechargement : ']) {
    const libT = await actionsGroupees(t1)
    expect(libT.filter((x) => /Assigner à/.test(x)), `${passeRe}Technicien : actions groupées ${J(libT)}`).toEqual([])
    const dT = await fiche(t1)
    await expect(champ(dT, 'Technicien responsable'), `${passeRe}Technicien : « Technicien responsable » en lecture`).toBeDisabled()
    await expect(champ(dT, 'Statut'), `${passeRe}Technicien : transitions présentes (sav_gerer)`).toBeEnabled()
    await expect(bouton(dT, /Mettre à jour/), `${passeRe}Technicien : enregistrer présent`).toBeVisible()
    const libC = await actionsGroupees(c1)
    expect(libC.filter((x) => /Assigner à|^Annuler$|^Priorité/.test(x)), `${passeRe}Commercial : actions groupées ${J(libC)}`).toEqual([])
    const dC = await fiche(c1)
    await expect(champ(dC, 'Statut'), `${passeRe}Commercial : statut en lecture`).toBeDisabled()
    await expect(champ(dC, 'Technicien responsable'), `${passeRe}Commercial : technicien en lecture`).toBeDisabled()
    for (const n of [/Mettre à jour/, /Annuler le ticket/, /^Noter$/, /Planifier une intervention/, /Ajouter une intervention/]) {
      await expect(bouton(dC, n), `${passeRe}Commercial : pas de « ${n} »`).toHaveCount(0)
    }
  }
  // Témoin : le Responsable (sav_reassign) garde « Assigner à … » et le sélecteur éditable.
  const r1 = await ecranDe(page, suivi, testInfo, re)
  const libR = await actionsGroupees(r1)
  expect(libR.some((x) => /Assigner à/.test(x)), `Responsable : actions groupées ${J(libR)}`).toBeTruthy()
  await expect(champ(await fiche(r1), 'Technicien responsable'), 'Responsable : sélecteur éditable').toBeEnabled()
  const relus = await py(`from apps.sav.models import Ticket
sortie(sorted(Ticket.objects.filter(pk__in=${J(tickets.map((t) => t.id))}).values_list('technicien_responsable_id', flat=True)))`)
  expect(relus, 'rendu seul : tickets relus inchangés').toEqual([te.id, te.id])
})

// ── ADRG37 — supprimer un conditionnement / un prix fournisseur : administrateur seul ; « Supprimer » retiré ───────
etape('PF4.2-ADRG37-conditionnements', ['ADRG37'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  let i = 0
  const objets = () => {
    i += 1
    return py(`from decimal import Decimal
from apps.stock.models import Produit, ConditionnementProduit, PrixFournisseur, Fournisseur
p, _ = Produit.objects.get_or_create(company_id=${SOC}, sku=${J(`SKU-ADRG37-${m}`)}, defaults=dict(nom=${J(`Câble ADRG37 ${m}`)}, prix_vente=Decimal('100.00'), prix_achat=Decimal('60.00')))
c = ConditionnementProduit.objects.create(company_id=${SOC}, produit=p, nom=${J(`Carton ADRG37 ${m} `)} + str(${i}), facteur=Decimal('10'))
f = Fournisseur.objects.create(company_id=${SOC}, nom=${J(`F-ADRG37 ${m} `)} + str(${i}))
x = PrixFournisseur.objects.create(company_id=${SOC}, produit=p, fournisseur=f, prix_achat=Decimal('800.00'))
sortie(dict(c=c.pk, x=x.pk, nom=c.nom))`)
  }
  const presents = (o) => py(`from apps.stock.models import ConditionnementProduit, PrixFournisseur
sortie([ConditionnementProduit.objects.filter(pk=${o.c}).exists(), PrixFournisseur.objects.filter(pk=${o.x}).exists()])`)
  for (const [nom, attendu] of [['Technicien responsable', 403], ['Responsable', 403], ['Directeur', 204]]) {
    const o = await objets()
    const x = await apiDe(testInfo, await compteDe(nom, 'adrg37'))
    for (const url of [`${API}/stock/conditionnements/${o.c}/`, `${API}/stock/prix-fournisseurs/${o.x}/`]) {
      const rep = await x.delete(url, T)
      expect(rep.status(), `${nom} DELETE ${url} : ${rep.status() === 204 ? '' : (await rep.text()).slice(0, 200)}`).toBe(attendu)
    }
    expect(await presents(o), `${nom} : objets relus`).toEqual(attendu === 403 ? [true, true] : [false, false])
  }
  // Écran Stock → Conditionnements : « Supprimer » absent au Responsable (« Modifier » reste), présent au Directeur.
  const o = await objets()
  async function ligne(p) {
    await ouvrir(p, '/stock/conditionnements', /\/stock\/conditionnements\/?$/)
    await p.getByPlaceholder('Rechercher (conditionnement, produit)…').fill(o.nom)
    const l = p.getByRole('row').filter({ hasText: o.nom }).first()
    await expect(l, 'conditionnement listé').toBeVisible(V)
    return { sup: await l.getByRole('button', { name: 'Supprimer' }).count(), mod: await l.getByRole('button', { name: 'Modifier' }).count() }
  }
  const pre = await ecranDe(page, suivi, testInfo, await compteDe('Responsable', 'adrg37re'))
  const re1 = await ligne(pre)
  expect([re1.sup, re1.mod > 0], 'Responsable : pas de « Supprimer », « Modifier » présent').toEqual([0, true])
  await pre.reload()
  const re2 = await ligne(pre)
  expect([re2.sup, re2.mod > 0], 'Responsable relu après rechargement').toEqual([0, true])
  const di = await ligne(await ecranDe(page, suivi, testInfo, await compteDe('Directeur', 'adrg37di')))
  expect(di.sup, 'Directeur : « Supprimer » présent').toBeGreaterThan(0)
})

// ── ADRG40 — affecter un technicien (tournée, ticket déjà affecté) exige `sav_reassign` ; onglet Tournée ───────────
etape('PF4.2-ADRG40-tournee', ['ADRG40'], async ({ page, suivi, testInfo }) => {
  const admin = page.context().request
  const m = marque()
  const cl = await clientCrm(admin, m)
  const autre = await py(`sortie(U.objects.get(username='demo_tech').id)`)
  const equipe = await py(`from apps.sav.models import EquipeMaintenance
sortie(EquipeMaintenance.objects.create(company_id=${SOC}, nom=${J(`Équipe ADRG40 ${m}`)}).pk)`)
  const prev = []
  for (const s of ['a', 'b']) prev.push((await lireJson(await admin.post(`${API}/sav/tickets/`, { ...T, data: { client: cl.id, type: 'preventif', description: `ADRG40 ${m} ${s}` } }), 'ticket préventif')).id)
  const etat = () => py(`from apps.sav.models import Ticket
sortie([list(Ticket.objects.filter(pk__in=${J(prev)}).order_by('pk').values_list('technicien_responsable_id', 'date_tournee')), Ticket.objects.filter(company_id=${SOC}, description__startswith=${J(`ADRG40 ${m}`)}).count()])`)
  const te = await compteDe('Technicien', 'adrg40te')
  expect(te.codes.includes('sav_reassign'), 'Given : Technicien sans sav_reassign').toBe(false)
  const x = await apiDe(testInfo, te)
  const avant = await etat()
  await refus(await x.post(`${API}/sav/contrats-maintenance/planifier-tournee/`, { ...T, data: { ticket_ids: prev, date_tournee: aujourdhui(), technicien_id: autre } }), 'Technicien tournée avec technicien', 'sav_reassign')
  await refus(await x.post(`${API}/sav/tickets/`, { ...T, data: { client: cl.id, type: 'correctif', description: `ADRG40 ${m} tech`, technicien_responsable: autre } }), 'Technicien ticket affecté', 'sav_reassign')
  await refus(await x.post(`${API}/sav/tickets/`, { ...T, data: { client: cl.id, type: 'correctif', description: `ADRG40 ${m} equipe`, equipe } }), 'Technicien ticket à une équipe', 'sav_reassign')
  expect(await etat(), 'après les 403 : tickets relus inchangés, aucun ticket créé').toEqual(avant)
  const sans = await passe(await x.post(`${API}/sav/contrats-maintenance/planifier-tournee/`, { ...T, data: { ticket_ids: prev, date_tournee: aujourdhui() } }), 'Technicien tournée sans technicien')
  expect(sans.tickets_planifies, 'tournée sans technicien : 2 tickets').toBe(2)
  await passe(await x.post(`${API}/sav/tickets/`, { ...T, data: { client: cl.id, type: 'correctif', description: `ADRG40 ${m} libre` } }), 'Technicien ticket non affecté')
  const re = await compteDe('Responsable', 'adrg40re')
  const y = await apiDe(testInfo, re)
  await passe(await y.post(`${API}/sav/contrats-maintenance/planifier-tournee/`, { ...T, data: { ticket_ids: prev, date_tournee: aujourdhui(), technicien_id: autre } }), 'Responsable tournée avec technicien')
  await passe(await y.post(`${API}/sav/tickets/`, { ...T, data: { client: cl.id, type: 'correctif', description: `ADRG40 ${m} resp`, technicien_responsable: autre } }), 'Responsable ticket affecté')
  // Écran SAV → Contrats, onglet Tournée : pas de choix du technicien au Technicien ; le Responsable l'a.
  const ongletTournee = (p) => p.getByRole('radio', { name: 'Tournée' }).or(p.getByRole('button', { name: 'Tournée', exact: true })).or(p.getByRole('tab', { name: 'Tournée' })).first()
  const pt = await ecranDe(page, suivi, testInfo, te)
  for (const passeRe of ['', 'relu après rechargement : ']) {
    if (passeRe) await pt.reload()
    await ouvrir(pt, '/sav/contrats', /\/sav\/contrats-maintenance\/?$/)
    await ongletTournee(pt).click()
    await expect(pt.getByLabel('Date de tournée'), `${passeRe}Technicien : onglet Tournée rendu`).toBeVisible(V)
    await expect(pt.getByText('Technicien (optionnel)'), `${passeRe}Technicien : pas de choix du technicien`).toHaveCount(0)
  }
  const pr = await ecranDe(page, suivi, testInfo, re)
  await ouvrir(pr, '/sav/contrats', /\/sav\/contrats-maintenance\/?$/)
  await ongletTournee(pr).click()
  await expect(pr.getByLabel('Technicien (optionnel)'), 'Responsable : choix du technicien').toBeVisible(V)
})

// ── ADRG47 — supervision : aucun geste d'écriture au Commercial, présents au porteur de `sav_gerer` (Directeur) ─────
etape('PF4.4-ADRG47-supervision', ['ADRG47'], async ({ page, suivi, testInfo }) => {
  const admin = page.context().request
  const m = marque()
  const co = await compteDe('Commercial', 'adrg47co')
  const di = await compteDe('Directeur', 'adrg47di')
  expect([co.codes.includes('sav_gerer'), di.codes.includes('sav_gerer')], 'Given : Commercial sans sav_gerer, Directeur avec').toEqual([false, true])
  const xc = await apiDe(testInfo, co)
  const lead = await lireJson(await xc.post(`${API}/crm/leads/`, { ...T, data: { nom: `ADRG47 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `adrg47_${m}@example.invalid` } }), 'lead')
  const prod = await produitApi(admin, `Onduleur réseau ADRG47 ${m}`)
  const d = await lireJson(await xc.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, lignes: [{ produit: prod.id, designation: prod.nom, quantite: '1', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  await lireJson(await xc.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await admin.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client ADRG47' } }), 'accepter')
  const inst = await py(`from apps.installations.models import Installation
from apps.ventes.models import Devis
from apps.monitoring.models import MonitoringConfig
d = Devis.objects.get(pk=${d.id})
inst = Installation.objects.filter(devis=d).first()
if inst is None:
    from apps.installations.services import create_installation_from_devis
    res = create_installation_from_devis(d, U.objects.get(username='demo_admin'), d.company)
    inst = res[0] if isinstance(res, tuple) else res
Installation.objects.filter(pk=inst.pk).update(statut=Installation.Statut.RECEPTIONNE, parc_actif=True, annule=False)
MonitoringConfig.objects.get_or_create(company_id=inst.company_id, installation=inst, defaults=dict(provider='noop'))
sortie(dict(id=inst.pk, ref=inst.reference))`)
  // Given complet : relevé, nettoyage, garantie, abonnement, certificat carbone et alerte de sous-performance ouverte
  // sur ce système (API demo_admin, service et ORM pour le certificat et l'alerte).
  const hier = new Date(Date.now() - 86_400_000).toISOString().slice(0, 10)
  await lireJson(await admin.post(`${API}/monitoring/readings/`, { ...T, data: { installation: inst.id, date: hier, energy_kwh: '12.50', period_days: 1 } }), 'relevé')
  await lireJson(await admin.post(`${API}/monitoring/cleanings/`, { ...T, data: { installation: inst.id, date: hier } }), 'nettoyage')
  await lireJson(await admin.post(`${API}/monitoring/warranties/`, { ...T, data: { installation: inst.id, guaranteed_year1_kwh: '5000', degradation_pct_per_year: '0.5', start_year: new Date().getFullYear(), tolerance_pct: '5', compensation_mad_per_kwh: '1' } }), 'garantie')
  await lireJson(await admin.post(`${API}/monitoring/abonnements/`, { ...T, data: { installation_id: inst.id, periodicite: 'mensuel', montant: '150' } }), 'abonnement')
  await py(`from decimal import Decimal
from apps.monitoring.models import UnderperformanceFlag
from apps.monitoring.services import emettre_certificat_carbone
from authentication.models import Company
UnderperformanceFlag.objects.filter(installation_id=${inst.id}, is_open=True).delete()
UnderperformanceFlag.objects.create(company_id=${SOC}, installation_id=${inst.id}, ratio_pct=Decimal('55.00'))
emettre_certificat_carbone(Company.objects.get(pk=${SOC}), installation_id=${inst.id}, periode_debut=datetime.date(2025, 1, 1), periode_fin=datetime.date(2025, 12, 31), tco2_evitees=Decimal('1.234'))
sortie(1)`)
  const choix = new RegExp(`${echapper(inst.ref)}|#${inst.id}\\b`)
  async function systeme(p) {
    const s = p.getByRole('combobox', { name: /Choisir un système (supervisé|installé)/ }).first()
    await expect(s, 'sélecteur de système').toBeVisible(V)
    await s.click()
    await p.getByRole('option', { name: choix }).first().click()
  }
  const calmeP = (p) => p.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => undefined)
  /** Les 8 écrans du Then ; renvoie [écran, geste, nombre de boutons offerts]. `ferme` : /sav/monitoring refusé. */
  async function supervision(p, c, passeRe) {
    const vus = []
    const compte = async (ecranNom, geste, loc) => vus.push([ecranNom, geste, await loc.count()])
    // Production : synchroniser, saisir un relevé, supprimer un relevé, fournisseur / activation (enregistrer).
    await ouvrir(p, '/production', /\/installations\/chantiers\/?$/)
    await systeme(p)
    await expect(p.getByText('Supervision automatique').first(), `${passeRe}${c.nomRole} : Production lisible`).toBeVisible(V)
    await calmeP(p)
    await compte('Production', 'Synchroniser maintenant', bouton(p, /Synchroniser maintenant/))
    await compte('Production', 'Saisir un relevé', p.getByText('Saisir un relevé', { exact: true }))
    await compte('Production', 'Supprimer (relevé)', bouton(p, 'Supprimer'))
    await compte('Production', 'Fournisseur modifiable', p.getByRole('combobox', { name: 'Fournisseur de supervision' }).and(p.locator(':enabled')))
    // Nettoyages : enregistrer, supprimer.
    await ouvrir(p, '/production/nettoyages', /\/monitoring\/configs\/?$/)
    await systeme(p)
    await calmeP(p)
    await compte('Nettoyages', 'Enregistrer un nettoyage', p.getByText('Enregistrer un nettoyage', { exact: true }))
    await compte('Nettoyages', 'Supprimer (nettoyage)', bouton(p, 'Supprimer'))
    // Garanties : ajouter, modifier, supprimer.
    await ouvrir(p, '/production/garanties', /\/monitoring\/warranties\/?$/)
    await calmeP(p)
    await compte('Garanties', 'Nouvelle garantie', bouton(p, /Nouvelle garantie/))
    await compte('Garanties', 'Modifier (garantie)', bouton(p, 'Modifier'))
    await compte('Garanties', 'Supprimer (garantie)', bouton(p, 'Supprimer'))
    // Flotte : l'alerte du système est listée ; classer.
    await p.goto('/production/parc')
    const alertes = p.getByRole('region', { name: 'Alertes de sous-performance' })
    await expect(alertes.getByRole('listitem').filter({ hasText: choix }).first(), `${passeRe}${c.nomRole} : Flotte, alerte du système listée`).toBeVisible(V)
    await compte('Flotte', 'Classer', alertes.getByRole('button', { name: 'Classer', exact: true }))
    // Rapport O&M : rapport du système rendu ; envoyer.
    await ouvrir(p, '/production/rapports', /\/monitoring\/configs\/?$/)
    await systeme(p)
    await expect(p.getByTestId('om-report'), `${passeRe}${c.nomRole} : Rapport O&M rendu`).toBeVisible(V)
    await compte('Rapport O&M', 'Envoyer par e-mail', bouton(p, /Envoyer par e-mail/))
    // Abonnements, SLA de disponibilité, Certificats carbone (écran SAV → Monitoring).
    await p.goto('/sav/monitoring')
    await calmeP(p)
    let ferme = false
    if (/\/403/.test(p.url())) {
      ferme = true
    } else {
      await expect(p.getByRole('heading', { name: 'Monitoring', exact: true }), `${passeRe}${c.nomRole} : SAV → Monitoring rendu`).toBeVisible(V)
      await compte('Abonnements', "Créer l'abonnement", bouton(p, "Créer l'abonnement"))
      await compte('Abonnements', 'Résilier', bouton(p, 'Résilier'))
      await compte('SLA de disponibilité', 'Enregistrer le SLA', bouton(p, 'Enregistrer le SLA'))
      await compte('Certificats carbone', 'Émettre le certificat', bouton(p, 'Émettre le certificat'))
      await compte('Certificats carbone', 'Annuler', p.getByRole('button', { name: 'Annuler', exact: true }))
    }
    console.log(`[ADRG47] ${passeRe}${c.nomRole} : ${J(vus)} ; /sav/monitoring ${ferme ? 'refusé (/403)' : 'rendu'}`)
    return { vus, ferme }
  }
  const pc = await ecranDe(page, suivi, testInfo, co)
  for (const passeRe of ['', 'relu après rechargement : ']) {
    if (passeRe) await pc.reload()
    const { vus, ferme } = await supervision(pc, co, passeRe)
    for (const [e, g, k] of vus) expect(k, `${passeRe}Commercial : ${e} — « ${g} » absent`).toBe(0)
    // Route `/sav/monitoring` réservée au palier responsable/admin : le Commercial n'y entre pas (aucun bouton).
    expect(ferme, `${passeRe}Commercial : SAV → Monitoring (Abonnements, SLA, Certificats) refusé`).toBe(true)
    await expect(pc.getByRole('button', { name: /Créer l'abonnement|Résilier|Enregistrer le SLA|Émettre le certificat/ }), `${passeRe}Commercial : aucun geste SAV → Monitoring`).toHaveCount(0)
  }
  const { vus: vusD, ferme: fermeD } = await supervision(await ecranDe(page, suivi, testInfo, di), di, '')
  expect(fermeD, 'Directeur : SAV → Monitoring rendu').toBe(false)
  expect(vusD.length, 'Directeur : les gestes des 8 écrans relevés').toBe(16)
  for (const [e, g, k] of vusD) expect(k, `Directeur : ${e} — « ${g} » présent`).toBeGreaterThan(0)
  await py(`from apps.monitoring.models import MonitoringConfig, UnderperformanceFlag
from apps.installations.models import Installation
UnderperformanceFlag.objects.filter(installation_id=${inst.id}).delete()
MonitoringConfig.objects.filter(installation_id=${inst.id}).delete(); Installation.objects.filter(pk=${inst.id}).update(parc_actif=False)
sortie(1)`).catch(() => null)
})

// ── ADRG63 — aperçu d'import de produits sans `prix_achat_voir` : ni le champ `prix_achat` ni sa valeur ────────────
etape('PF4.3-ADRG63-apercu-import', ['ADRG63'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const sku = `ADRG63-${m}`
  // Prix d'achat actuel volontairement singulier (9017.31) : sa chaîne ne peut venir que de la fiche.
  const prod = await py(`from decimal import Decimal
from apps.stock.models import Produit
p = Produit.objects.create(company_id=${SOC}, nom='Panneau ADRG63 ${m}', sku=${J(sku)}, prix_achat=Decimal('9017.31'), prix_vente=Decimal('12000'))
sortie(p.pk)`)
  // Nom distinctif dans le fichier : témoin que la ligne du fichier est rendue dans l'aperçu.
  const fichier = { name: 'produits.csv', mimeType: 'text/csv', buffer: Buffer.from(`Nom,SKU,prix_achat\nPanneau renommé ADRG63 ${m},${sku},9502.77\n`) }
  const champsDe = (d) => (d.conflits || []).flatMap((c) => [...(c.ecrasements || []).map((e) => e.champ), ...(c.remplissages || [])])
  try {
    const cr = await compteDe('Commercial responsable', 'adrg63cr')
    const re = await compteDe('Responsable', 'adrg63re')
    const di = await compteDe('Directeur', 'adrg63di')
    expect([cr.codes.includes('prix_achat_voir'), re.codes.includes('prix_achat_voir'), di.codes.includes('prix_achat_voir')],
      'Given : Commercial responsable et Responsable sans prix_achat_voir, Directeur avec').toEqual([false, false, true])
    for (const c of [cr, re]) {
      const rc = await (await apiDe(testInfo, c)).post(`${API}/imports/dry-run/`, { ...T, multipart: { file: fichier, target: 'products' } })
      const tc = await rc.text()
      expect(rc.status(), `${c.nomRole} dry-run : ${tc.slice(0, 240)}`).toBe(200)
      expect(champsDe(JSON.parse(tc)), `${c.nomRole} : aucun prix_achat dans écrasements ni remplissages`).not.toContain('prix_achat')
      expect(tc, `${c.nomRole} : la valeur actuelle n'est nulle part dans la réponse`).not.toContain('9017')
    }
    const dd = await lireJson(await (await apiDe(testInfo, di)).post(`${API}/imports/dry-run/`, { ...T, multipart: { file: fichier, target: 'products' } }), 'Directeur dry-run')
    const entree = (dd.conflits || []).flatMap((c) => c.ecrasements || []).find((e) => e.champ === 'prix_achat')
    expect(String(entree?.ancienne), `Directeur : l'entrée prix_achat est servie (${J(dd.conflits)})`).toContain('9017.31')
    // Écran Stock au Commercial responsable : « Importer » suit `stock_modifier` (absent de ce rôle) — aucun accès à
    // l'aperçu, et aucun prix d'achat actuel nulle part à l'écran.
    const pc = await ecranDe(page, suivi, testInfo, cr)
    for (const passeRe of ['', 'relu après rechargement : ']) {
      if (passeRe) await pc.reload(); else await ouvrir(pc, '/stock', /\/stock\/produits\/?$/)
      await pc.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => undefined)
      await expect(pc.getByRole('button', { name: 'Importer', exact: true }), `${passeRe}Commercial responsable : pas de « Importer »`).toHaveCount(0)
      expect(await pc.locator('body').innerText(), `${passeRe}Commercial responsable : aucun prix d'achat actuel affiché`).not.toContain('9017')
    }
    // Écran Stock → Importer (aperçu) au Responsable (stock_modifier, sans prix_achat_voir) puis au Directeur (témoin).
    // Pour la cible « products », l'écran n'offre que « Créer seulement » : la fiche existante est un doublon, la table
    // des écrasements n'est pas dessinée — l'aperçu = la réponse dry-run que l'écran reçoit + le tableau des lignes du
    // fichier. Les deux sont relus.
    async function apercu(p, c) {
      await ouvrir(p, '/stock', /\/stock\/produits\/?$/)
      await p.getByRole('button', { name: 'Importer', exact: true }).first().click()
      const [rep] = await Promise.all([
        p.waitForResponse((x) => /\/imports\/dry-run\/$/.test(new URL(x.url()).pathname), V),
        p.locator('input[type="file"][accept=".csv,.xlsx"]').setInputFiles(fichier),
      ])
      expect(rep.status(), `${c.nomRole} : aperçu servi à l'écran`).toBe(200)
      await expect(p.getByText(/colonnes reconnues/), `${c.nomRole} : aperçu affiché`).toBeVisible(V)
      await expect(p.getByRole('cell', { name: `Panneau renommé ADRG63 ${m}`, exact: true }).first(), `${c.nomRole} : la ligne du fichier est affichée`).toBeVisible()
      return rep.text()
    }
    const pr = await ecranDe(page, suivi, testInfo, re)
    for (const passeRe of ['', 'relu après rechargement : ']) {
      if (passeRe) await pr.reload()
      const corps = await apercu(pr, re)
      expect(champsDe(JSON.parse(corps)), `${passeRe}Responsable : l'aperçu reçu ne contient aucun champ prix_achat`).not.toContain('prix_achat')
      expect(corps, `${passeRe}Responsable : l'aperçu reçu ne contient pas la valeur actuelle`).not.toContain('9017')
      expect(await pr.locator('body').innerText(), `${passeRe}Responsable : aucun prix d'achat actuel affiché`).not.toContain('9017')
    }
    const pd = await ecranDe(page, suivi, testInfo, di)
    const corpsD = await apercu(pd, di)
    expect(champsDe(JSON.parse(corpsD)), 'Directeur (témoin) : l\'aperçu reçu porte prix_achat').toContain('prix_achat')
    expect(corpsD, 'Directeur (témoin) : l\'aperçu reçu porte la valeur actuelle').toContain('9017.31')
  } finally {
    await py(`from apps.stock.models import Produit
try:
    Produit.objects.filter(pk=${prod}).delete()
except Exception:
    pass
sortie(1)`).catch(() => null)
  }
}, { ecart: {
  base: 'FAIL',
  raison: "« Importer » de /stock est gardé par stock_modifier (frontend/src/pages/stock/StockList.jsx, canWrite = useHasPermission('stock_modifier'), depuis 41c6ab405 du 10/07/2026, ARC47) : le Commercial responsable de la clause (stock_creer, sans stock_modifier) n'atteint pas l'aperçu à l'écran. Garde antérieure à ADRG63 et hors de ses Files (backend dataimport seul) ; l'étape affirme le dry-run de ce compte (ni champ ni valeur prix_achat), l'absence d'« Importer », et l'aperçu à l'écran joué par le Responsable (stock_modifier, sans prix_achat_voir).",
} })
