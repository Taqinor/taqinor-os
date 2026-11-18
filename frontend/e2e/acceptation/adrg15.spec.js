// Preuves en direct du groupe ADRG, lot 15 (vague d'acceptation, 17/11/2026) : ADRG147 (réorienter l'envoi programmé
// `query` du stock d'un Directeur exige `stock_export`, PATCH partiel compris), ADRG152 (liste et kanban des leads :
// « Responsable » sous `crm_reassign`, écriture sous `crm_modifier`), ADRG153 (panneau document GED : rapport « Qui voit
// ce document » et « CSV » sous `ged_gerer`), ADRG154 (détail d'un ticket SAV et calendrier : gestes d'écriture sous
// `sav_gerer`). Comptes d'essai aux rôles SYSTÈME du registre (`init_roles`, relus par leur nom dans la société démo),
// connexion par la vraie route `/token/` dans un navigateur à part ; chaque réponse de l'API est relevée (« onglet
// réseau ») et chaque `console.error` de la page : les clauses « aucun appel X », « sans 403 », « console propre » sont
// affirmées sur ces relevés, en plus des oracles. Données propres (API de demo_admin / du Directeur, ou shell Django),
// retirées en fin d'étape ; chaque écran est relu après rechargement.
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { connexionApi, assurerSessionPage, lireJson, telephoneMobileUnique } from '../helpers.js'

const etape = groupe('ADRG', ['ADRG147', 'ADRG152', 'ADRG153', 'ADRG154', 'ADRG156', 'ADRG157', 'ADRG158'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const V = { timeout: 60_000 }

test.describe.configure({ timeout: 540_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const OUVERTS = []
test.afterEach(async () => { for (const fermer of OUVERTS.splice(0)) await fermer().catch(() => undefined) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const J = JSON.stringify
const SOC = `U.objects.get(username='demo_admin').company_id`
const comptes = []
test.afterAll(async () => {
  if (comptes.length) {
    await py(`U.objects.filter(username__in=${J(comptes)}).update(is_active=False)
sortie(1)`).catch(() => null)
  }
})

/** Compte d'essai : rôle SYSTÈME `nomRole` ; {username, id, nomRole, codes} (codes du rôle relus en base). */
async function compteDe(nomRole, prefixe) {
  const username = `${prefixe}_${marque()}`
  const x = await py(`from apps.roles.models import Role
r = Role.objects.get(company_id=${SOC}, nom=${J(nomRole)}, est_systeme=True)
u = compte(${J(username)}, role=r.pk, societe=${SOC})
sortie(dict(id=u.id, codes=sorted(r.permissions or [])))`)
  comptes.push(username)
  return { username, id: x.id, codes: x.codes, nomRole }
}

/** Contexte API (vraie route /token/) d'un compte. */
async function apiDe(testInfo, c) {
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  OUVERTS.push(() => ctx.dispose())
  await connexionApi(ctx, { username: c.username, password: MDP_ESSAI })
  return ctx
}

/** Navigateur à part (aucun cookie de demo_admin) connecté par /token/ ; visites guidées marquées vues ; chaque
 *  réponse de l'API relevée dans `reseau` (« MÉTHODE chemin?requête → statut »), chaque console.error dans
 *  `consoles`. La page demo_admin de l'étape est refermée : la capture montre l'écran du rôle joué. */
async function ecranDe(page, suivi, testInfo, c) {
  if (!page.isClosed()) await page.close()
  const ctx = await page.context().browser().newContext({
    baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
    viewport: { width: 1600, height: 1000 },
  })
  OUVERTS.push(() => ctx.close())
  await ctx.addInitScript(() => {
    try {
      localStorage.setItem('taqinor-pwa-install-dismissed', '1'); localStorage.setItem('taqinor:welcome:seen:v1', '1')
    } catch { /* mode privé */ }
  })
  await connexionApi(ctx.request, { username: c.username, password: MDP_ESSAI })
  const visites = await ctx.request.get(`${API}/onboarding/tours/`, T)
  if (visites.ok()) {
    for (const v of await visites.json().catch(() => [])) {
      if (!v.vu) await ctx.request.post(`${API}/onboarding/tours/${v.tour_key}/vu/`, T).catch(() => undefined)
    }
  }
  const p = suivi.surveiller(await ctx.newPage())
  const reseau = []
  const consoles = []
  p.on('response', (r) => {
    const u = new URL(r.url())
    if (u.pathname.startsWith(API)) reseau.push(`${r.request().method()} ${u.pathname.slice(API.length)}${u.search} → ${r.status()}`)
  })
  p.on('console', (msg) => { if (msg.type() === 'error') consoles.push(msg.text()) })
  p.on('pageerror', (e) => consoles.push(`pageerror : ${e.message}`))
  return { ctx, p, reseau, consoles, api: ctx.request, c }
}
const chemin = (l) => l.split(' ')[1].split('?')[0]
/** Lignes de `reseau` dont le chemin (sans requête) correspond à `re`. */
const appels = (reseau, re) => reseau.filter((l) => re.test(chemin(l)))
/** Réponses refusées (4xx/5xx) relevées. */
const refus = (reseau) => reseau.filter((l) => / → [45]\d\d$/.test(l))
const pertinent = (reseau) => reseau.filter((l) => /\/(crm\/leads|ged\/|sav\/|reporting\/saved)/.test(l))
const calme = (p) => p.waitForLoadState('networkidle', { timeout: 20_000 }).catch(() => undefined)
/** Attend une réponse (chemin relatif à l'API = `re`, `filtre(url)` en plus). */
const reponse = (p, re, methode = 'GET', filtre = () => true) => p.waitForResponse((r) => {
  const u = new URL(r.url())
  return re.test(u.pathname.slice(API.length)) && r.request().method() === methode && filtre(u)
}, T)
/** Ouvre `url` (ou recharge) en vidant les relevés ; attend le calme. */
async function charger(s, url, passe) {
  s.reseau.length = 0
  s.consoles.length = 0
  if (passe) await s.p.reload(); else await s.p.goto(url)
  await calme(s.p)
}
const PASSES = ['', 'relu après rechargement : ']
const bouton = (zone, nom) => zone.getByRole('button', { name: nom })

// ───────────────────────── ADRG147 : envoi programmé `query` du stock ─────────────────────────
const RAPPORT = (id) => new RegExp(`^/reporting/saved-reports/${id}/$`)

etape('PF4-ADRG147-envoi-requete-stock', ['ADRG147'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const di = await compteDe('Directeur', 'adrg147di')
  const re = await compteDe('Commercial responsable', 'adrg147re')
  expect(di.codes.includes('stock_export'), 'Given : Directeur avec stock_export').toBe(true)
  expect(re.codes.includes('stock_export'), 'Given : Commercial responsable sans stock_export').toBe(false)
  const apiD = await apiDe(testInfo, di)
  const apiR = await apiDe(testInfo, re)
  const nom = `Stock hebdo ADRG147 ${m}`
  const requete = await lireJson(await apiD.post(`${API}/core/saved-queries/`, { ...T, data: { titre: `Stock ADRG147 ${m}`, dataset: 'stock_produits', spec: { select: ['nom'] }, partage: true } }), 'requête stock')
  let rapport = null
  try {
    rapport = await lireJson(await apiD.post(`${API}/reporting/saved-reports/`, { ...T, data: {
      name: nom, target_kind: 'query', cible_id: requete.id, schedule: 'weekly', canal: 'email', recipients: 'direction@exemple.ma',
    } }), 'envoi programmé stock')
    const url = `${API}/reporting/saved-reports/${rapport.id}/`
    const lire = async (api) => (await lireJson(await api.get(url, T), 'rapport relu')).recipients
    expect(await lire(apiD), 'Given : destinataires = direction@exemple.ma').toBe('direction@exemple.ma')
    suivi.attendre(new RegExp(`/reporting/saved-reports/${rapport.id}/$`), 403) // refus PROVOQUÉ du Commercial responsable (écran puis appel direct)
    const ligneDe = (p) => p.getByTestId(`envoi-programme-${rapport.id}`)
    /** Ouvre « Modifier », remplace les destinataires, enregistre ; renvoie la réponse du PATCH. */
    async function modifier(s, adresse) {
      await ligneDe(s.p).getByRole('button', { name: `Modifier ${nom}` }).click()
      const carte = s.p.getByTestId('envoi-form-carte')
      await expect(carte, `${s.c.nomRole} : formulaire de modification ouvert`).toBeVisible(V)
      await carte.locator('#ep-recipients').fill(adresse)
      const ecrit = reponse(s.p, RAPPORT(rapport.id), 'PATCH')
      await bouton(carte, 'Enregistrer').click()
      return { rep: await ecrit, carte }
    }
    async function ouvrir(s, passe) {
      await charger(s, '/reporting/envois-programmes', passe)
      await expect(s.p.getByRole('heading', { name: 'Envois programmés' }), `${passe}${s.c.nomRole} : écran des envois programmés`).toBeVisible(V)
      await expect(ligneDe(s.p), `${passe}${s.c.nomRole} : l'envoi du stock est listé`).toBeVisible(V)
    }
    // Commercial responsable : l'édition des destinataires est refusée, la liste relue est inchangée.
    const s = await ecranDe(page, suivi, testInfo, re)
    await ouvrir(s, '')
    await expect(ligneDe(s.p), 'Commercial responsable : destinataires actuels').toContainText('direction@exemple.ma')
    const { rep, carte } = await modifier(s, 'x@libre.ma')
    expect(rep.status(), 'Commercial responsable : PATCH des destinataires refusé').toBe(403)
    expect(await rep.text(), 'Commercial responsable : refus du jeu de données').toContain('Accès au jeu de données refusé.')
    await expect(carte.getByText('Accès au jeu de données refusé.').first(), 'Commercial responsable : le refus est affiché à l\'écran').toBeVisible(V)
    expect(await lire(apiD), 'relu (API) : destinataires inchangés après le refus').toBe('direction@exemple.ma')
    for (const passe of PASSES) {
      await ouvrir(s, passe)
      await expect(ligneDe(s.p), `${passe}Commercial responsable : destinataires toujours direction@exemple.ma`).toContainText('direction@exemple.ma')
      await expect(ligneDe(s.p), `${passe}Commercial responsable : x@libre.ma absent`).not.toContainText('x@libre.ma')
    }
    // Même refus par l'appel direct du corps partiel {"recipients": …} (le chemin de la constatation).
    const direct = await apiR.patch(url, { ...T, data: { recipients: 'x@libre.ma' } })
    expect(direct.status(), 'Commercial responsable : PATCH partiel direct refusé').toBe(403)
    expect(await direct.text(), 'Commercial responsable : PATCH partiel — refus du jeu de données').toContain('Accès au jeu de données refusé.')
    expect(await lire(apiD), 'relu : destinataires inchangés après le PATCH partiel').toBe('direction@exemple.ma')
    // Témoin Directeur : la même édition est enregistrée, relue après rechargement ; puis valeur d'origine remise.
    const d = await ecranDe(page, suivi, testInfo, di)
    await ouvrir(d, '')
    const ecr = await modifier(d, 'x@libre.ma')
    expect(ecr.rep.status(), 'Directeur : PATCH des destinataires accepté').toBe(200)
    await expect(ligneDe(d.p), 'Directeur : liste mise à jour').toContainText('x@libre.ma', V)
    for (const passe of PASSES) {
      await ouvrir(d, passe)
      await expect(ligneDe(d.p), `${passe}Directeur : destinataires = x@libre.ma`).toContainText('x@libre.ma')
    }
    expect(refus(d.reseau), 'Directeur : aucune réponse refusée').toEqual([])
    expect(await lire(apiD), 'relu (API) : destinataires = x@libre.ma').toBe('x@libre.ma')
    const retour = await apiD.patch(url, { ...T, data: { recipients: 'direction@exemple.ma' } })
    expect(retour.status(), 'Directeur : valeur d\'origine remise').toBe(200)
    // Le seul refus du Commercial responsable sur l'écran est celui provoqué par l'étape.
    expect(refus(s.reseau).every((l) => l.startsWith('PATCH /reporting/saved-reports/') && l.endsWith('→ 403')), `Commercial responsable : refus relevés ${J(refus(s.reseau))}`).toBe(true)
  } finally {
    await py(`from apps.reporting.models import SavedReport
from core.models import SavedQuery
SavedReport.objects.filter(${rapport ? `pk=${rapport.id}` : 'pk=0'}).delete()
SavedQuery.objects.filter(pk=${requete.id}).delete()
sortie(1)`).catch(() => null)
  }
})

// ───────────────────────── ADRG152 : liste et kanban des leads ─────────────────────────
const LEAD_ECRIT = (ids) => new RegExp(`^/crm/leads/(${ids.join('|')})/$`)

etape('PF4-ADRG152-leads-liste-kanban', ['ADRG152'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const r = page.request
  const co = await compteDe('Commercial', 'adrg152co')
  const vi = await compteDe('Viewer', 'adrg152vi')
  const di = await compteDe('Directeur', 'adrg152di')
  expect(co.codes.includes('crm_modifier') && !co.codes.includes('crm_reassign'), 'Given : Commercial crm_modifier sans crm_reassign').toBe(true)
  expect(vi.codes.includes('crm_modifier') || vi.codes.includes('crm_reassign'), 'Given : Viewer sans crm_modifier ni crm_reassign').toBe(false)
  expect(di.codes.includes('crm_modifier') && di.codes.includes('crm_reassign'), 'Given : Directeur avec crm_modifier et crm_reassign').toBe(true)
  const leads = []
  for (const suffixe of ['un', 'deux']) {
    leads.push(await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `ADRG152 ${suffixe} ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique() } }), `lead ${suffixe}`))
  }
  const ids = leads.map((l) => l.id)
  try {
    /** Pose le responsable des deux leads (le rôle joué les voit quel que soit son filtre « Mes leads »). */
    const attribuer = (c) => py(`from apps.crm.models import Lead
Lead.objects.filter(pk__in=${J(ids)}).update(owner_id=${c.id})
sortie(1)`)
    const PICKER = 'button.ap-trigger'
    const modifiables = (zone) => zone.getByTitle('Cliquer pour modifier')
    const perdu = (zone) => zone.getByRole('button', { name: 'Marquer perdu' })
    /** Ouvre /crm/leads dans la vue `vue` (l'URL porte la recherche : le défaut « Mes leads » ne s'applique pas). */
    async function ouvrir(s, vue, passe) {
      await charger(s, `/crm/leads?view=${vue}&q=${m}`, passe)
      const lus = vue === 'liste' ? s.p.getByRole('row').filter({ hasText: `ADRG152 un ${m}` }) : s.p.locator('article').filter({ hasText: `ADRG152 un ${m}` })
      await expect(lus.first(), `${passe}${s.c.nomRole} ${vue} : premier lead listé`).toBeVisible(V)
      const deux = vue === 'liste' ? s.p.getByRole('row').filter({ hasText: `ADRG152 deux ${m}` }) : s.p.locator('article').filter({ hasText: `ADRG152 deux ${m}` })
      await expect(deux.first(), `${passe}${s.c.nomRole} ${vue} : second lead listé`).toBeVisible(V)
      await calme(s.p)
      return [lus.first(), deux.first()]
    }
    const propres = (s, quoi) => {
      console.log(`[ADRG152] ${quoi} : ${J(pertinent(s.reseau))} ; console ${J(s.consoles)}`)
      expect(refus(s.reseau), `${quoi} : aucune réponse refusée (aucune 403)`).toEqual([])
      expect(appels(s.reseau, LEAD_ECRIT(ids)).filter((l) => !l.startsWith('GET ')), `${quoi} : aucun PATCH/POST crm/leads/<id>/`).toEqual([])
      expect(s.consoles, `${quoi} : console sans erreur`).toEqual([])
    }
    /** Colonne d'étape du kanban (section « Étape <libellé> — n leads »). */
    const colonneDe = (s, libelle) => s.p.getByRole('region', { name: new RegExp(`^Étape ${libelle} `) })
    const carteDans = (s, libelle) => colonneDe(s, libelle).locator('article').filter({ hasText: `ADRG152 un ${m}` })
    /** VRAI glisser de la carte du premier lead : souris enfoncée sur la carte, quelques pixels (seuil MouseSensor), puis
     *  déplacement progressif jusqu'au centre de la colonne cible, relâchement. */
    async function glisser(s, libelleCible) {
      const poignee = s.p.locator(`[data-lead-id="${ids[0]}"]`)
      await poignee.scrollIntoViewIfNeeded()
      const b = await poignee.boundingBox()
      const cible = await colonneDe(s, libelleCible).boundingBox()
      expect(b && cible, `${s.c.nomRole} : carte et colonne cible mesurables`).toBeTruthy()
      const x = b.x + 10
      const y = b.y + 10
      await s.p.mouse.move(x, y)
      await s.p.mouse.down()
      await s.p.mouse.move(x + 8, y + 8, { steps: 3 })
      await s.p.mouse.move(x + 16, y + 16, { steps: 3 })
      await s.p.mouse.move(cible.x + cible.width / 2, cible.y + Math.min(cible.height / 2, 200), { steps: 25 })
      await s.p.waitForTimeout(300)
      await s.p.mouse.up()
    }
    // Commercial : « Responsable » inerte sur chaque ligne et carte ; étape, champs et « Marquer perdu » actifs.
    await attribuer(co)
    const c = await ecranDe(page, suivi, testInfo, co)
    for (const passe of PASSES) {
      const lignes = await ouvrir(c, 'liste', passe)
      for (const l of lignes) {
        await expect(l.locator(PICKER), `${passe}Commercial liste : « Responsable » inerte`).toBeDisabled()
        await expect(modifiables(l).first(), `${passe}Commercial liste : étape et champs actifs`).toBeVisible(V)
        await expect(perdu(l), `${passe}Commercial liste : « Marquer perdu » présent`).toBeVisible(V)
      }
      expect(await modifiables(lignes[0]).count(), `${passe}Commercial liste : étape + champs éditables sur la ligne`).toBeGreaterThanOrEqual(2)
      propres(c, `${passe}Commercial liste`)
    }
    for (const passe of PASSES) {
      const cartes = await ouvrir(c, 'kanban', passe)
      for (const k of cartes) {
        await expect(k.locator(PICKER), `${passe}Commercial kanban : « Responsable » inerte`).toBeDisabled()
        await expect(k.locator(PICKER), `${passe}Commercial kanban : titre du sélecteur`).toHaveAttribute('title', /Responsable|Assigner un responsable/)
      }
      await bouton(cartes[0], /^Actions du lead /).click()
      await expect(c.p.getByRole('menuitem', { name: /Marquer perdu/ }), `${passe}Commercial kanban : « Marquer perdu » du menu actif`).toBeVisible(V)
      await c.p.keyboard.press('Escape')
      propres(c, `${passe}Commercial kanban`)
    }
    // Viewer : aucun geste d'écriture en liste comme en kanban.
    await attribuer(vi)
    const v = await ecranDe(page, suivi, testInfo, vi)
    for (const passe of PASSES) {
      const lignes = await ouvrir(v, 'liste', passe)
      for (const l of lignes) {
        await expect(l.locator(PICKER), `${passe}Viewer liste : « Responsable » inerte`).toBeDisabled()
        await expect(modifiables(l), `${passe}Viewer liste : étape et champs inertes (aucune cellule éditable)`).toHaveCount(0)
        await expect(perdu(l), `${passe}Viewer liste : aucun « Marquer perdu »`).toHaveCount(0)
      }
      await expect(v.p.getByRole('button', { name: 'Marquer perdu' }), `${passe}Viewer liste : aucun « Marquer perdu » sur la page`).toHaveCount(0)
      propres(v, `${passe}Viewer liste`)
    }
    for (const passe of PASSES) {
      const cartes = await ouvrir(v, 'kanban', passe)
      for (const k of cartes) {
        await expect(k.locator(PICKER), `${passe}Viewer kanban : « Responsable » inerte`).toBeDisabled()
        const menu = k.getByRole('button', { name: /^Actions du lead / })
        if (await menu.count()) {
          await menu.click()
          await expect(v.p.getByRole('menuitem', { name: /Marquer perdu/ }), `${passe}Viewer kanban : pas d'entrée « Marquer perdu »`).toHaveCount(0)
          await v.p.keyboard.press('Escape')
        }
      }
      await expect(v.p.getByRole('menuitem', { name: /Marquer perdu/ }), `${passe}Viewer kanban : aucune entrée « Marquer perdu »`).toHaveCount(0)
      propres(v, `${passe}Viewer kanban`)
    }
    // Viewer : un VRAI glisser de carte vers « Contacté » n'envoie aucun PATCH ; la carte reste dans « Nouveau ».
    {
      await ouvrir(v, 'kanban', '')
      await expect(carteDans(v, 'Nouveau'), 'Viewer kanban : le lead est dans « Nouveau » avant le glisser').toBeVisible(V)
      v.reseau.length = 0
      await glisser(v, 'Contacté')
      await calme(v.p)
      await v.p.waitForTimeout(1500)
      expect(appels(v.reseau, LEAD_ECRIT(ids)).filter((l) => !l.startsWith('GET ')), `Viewer glisser : aucun PATCH crm/leads/<id>/ (${J(v.reseau)})`).toEqual([])
      expect(v.reseau.filter((l) => !l.startsWith('GET ')), 'Viewer glisser : aucune requête d\'écriture').toEqual([])
      await expect(carteDans(v, 'Nouveau'), 'Viewer glisser : la carte est toujours dans « Nouveau »').toBeVisible(V)
      await expect(carteDans(v, 'Contacté'), 'Viewer glisser : la carte n\'est pas dans « Contacté »').toHaveCount(0)
      await ouvrir(v, 'kanban', 'relu après rechargement : ')
      await expect(carteDans(v, 'Nouveau'), 'relu après rechargement : Viewer — carte toujours dans « Nouveau »').toBeVisible(V)
      await expect(carteDans(v, 'Contacté'), 'relu après rechargement : Viewer — carte absente de « Contacté »').toHaveCount(0)
      expect((await lireJson(await r.get(`${API}/crm/leads/${ids[0]}/`, T), 'lead relu')).stage, 'relu (API) : étape inchangée = NEW').toBe('NEW')
    }
    // Témoin Directeur : tout est actif.
    await attribuer(di)
    const d = await ecranDe(page, suivi, testInfo, di)
    for (const passe of PASSES) {
      const lignes = await ouvrir(d, 'liste', passe)
      for (const l of lignes) {
        await expect(l.locator(PICKER), `${passe}Directeur liste : « Responsable » actif`).toBeEnabled()
        await expect(modifiables(l).first(), `${passe}Directeur liste : étape et champs actifs`).toBeVisible(V)
        await expect(perdu(l), `${passe}Directeur liste : « Marquer perdu » présent`).toBeVisible(V)
      }
      propres(d, `${passe}Directeur liste`)
    }
    for (const passe of PASSES) {
      const cartes = await ouvrir(d, 'kanban', passe)
      for (const k of cartes) await expect(k.locator(PICKER), `${passe}Directeur kanban : « Responsable » actif`).toBeEnabled()
      await bouton(cartes[0], /^Actions du lead /).click()
      await expect(d.p.getByRole('menuitem', { name: /Marquer perdu/ }), `${passe}Directeur kanban : « Marquer perdu » présent`).toBeVisible(V)
      await d.p.keyboard.press('Escape')
      propres(d, `${passe}Directeur kanban`)
    }
    // Témoin Directeur : le MÊME glisser (en avant, sans confirmation) envoie un PATCH 200 et déplace la carte.
    {
      await ouvrir(d, 'kanban', '')
      await expect(carteDans(d, 'Nouveau'), 'Directeur kanban : le lead est dans « Nouveau » avant le glisser').toBeVisible(V)
      d.reseau.length = 0
      const ecrit = reponse(d.p, LEAD_ECRIT([ids[0]]), 'PATCH')
      await glisser(d, 'Contacté')
      const rep = await ecrit
      expect(rep.status(), 'Directeur glisser : PATCH crm/leads/<id>/ accepté').toBe(200)
      await expect(carteDans(d, 'Contacté'), 'Directeur glisser : la carte est dans « Contacté »').toBeVisible(V)
      await ouvrir(d, 'kanban', 'relu après rechargement : ')
      await expect(carteDans(d, 'Contacté'), 'relu après rechargement : Directeur — carte dans « Contacté »').toBeVisible(V)
      await expect(carteDans(d, 'Nouveau'), 'relu après rechargement : Directeur — carte plus dans « Nouveau »').toHaveCount(0)
      expect((await lireJson(await r.get(`${API}/crm/leads/${ids[0]}/`, T), 'lead relu')).stage, 'relu (API) : étape = CONTACTED').toBe('CONTACTED')
    }
  } finally {
    await py(`from apps.crm.models import Lead
for pk in ${J(ids)}:
    try: Lead.all_objects.filter(pk=pk).delete() if hasattr(Lead, 'all_objects') else Lead.objects.filter(pk=pk).delete()
    except Exception as exc: print('nettoyage', pk, exc)
sortie(1)`).catch(() => null)
  }
})

// ───────────────────────── ADRG153 : panneau document GED, onglet « Accès » ─────────────────────────
const PDF = Buffer.from('%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\ntrailer<</Root 1 0 R>>\nstartxref\n0\n%%EOF\n')
const EFFECTIFS = (id) => new RegExp(`^/ged/documents/${id}/permissions-effectives/$`)
const ACLS = /^\/ged\/acls\/$/

/** Armoire + dossier + document PDF (une version) par demo_admin. */
async function dossierGed(r, m, prefixe) {
  const GED = `${API}/ged`
  const cab = await lireJson(await r.post(`${GED}/cabinets/`, { ...T, data: { nom: `Cab ${prefixe} ${m}` } }), 'armoire')
  const dos = await lireJson(await r.post(`${GED}/dossiers/`, { ...T, data: { nom: `Dos ${prefixe} ${m}`, cabinet: cab.id } }), 'dossier')
  const doc = await lireJson(await r.post(`${GED}/documents/`, { ...T, data: { nom: `Plan ${prefixe} ${m}`, folder: dos.id } }), 'document')
  await lireJson(await r.post(`${GED}/documents/${doc.id}/nouvelle-version/`, { ...T, multipart: { file: { name: 'plan.pdf', mimeType: 'application/pdf', buffer: PDF } } }), 'version PDF')
  return { cab, dos, doc }
}

/** Ouvre /ged, choisit l'armoire (sélecteur présent dès 2 armoires) puis le dossier ; attend la ligne du document. */
async function ouvrirDossierGed(p, { cab, dos, doc }) {
  await p.goto('/ged')
  const choix = p.getByRole('combobox', { name: 'Choisir le cabinet' })
  await expect(p.getByRole('tree', { name: 'Dossiers' }).or(choix).first()).toBeVisible(V)
  if (await choix.count()) {
    await choix.click()
    await p.getByRole('option', { name: cab.nom, exact: true }).click()
  }
  await p.getByRole('treeitem').filter({ hasText: dos.nom }).getByRole('button').first().click()
  await expect(p.getByRole('button', { name: `Aperçu de ${doc.nom}` }), 'document listé').toBeVisible(V)
}

etape('PF4-ADRG153-ged-acces', ['ADRG153'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const m = marque()
  const g = await dossierGed(r, m, 'ADRG153')
  try {
    const vi = await compteDe('Viewer', 'adrg153vi')
    const re = await compteDe('Commercial responsable', 'adrg153re')
    expect([vi.codes.includes('ged_voir'), vi.codes.includes('ged_gerer')], 'Given : Viewer ged_voir sans ged_gerer').toEqual([true, false])
    expect([re.codes.includes('ged_voir'), re.codes.includes('ged_gerer')], 'Given : Commercial responsable ged_voir et ged_gerer').toEqual([true, true])
    // Un droit direct par compte joué : la liste « droits directs » (ged/acls/, lecture ouverte) a de quoi s'afficher.
    for (const c of [vi, re]) {
      await lireJson(await r.post(`${API}/ged/acls/`, { ...T, data: { document: g.doc.id, utilisateur: c.id, niveau: 'lecture', herite: true } }), `droit direct ${c.nomRole}`)
    }
    /** Ouvre le panneau « Détails » du document puis l'onglet « Accès » ; renvoie le panneau. */
    async function ouvrirAcces(s) {
      await ouvrirDossierGed(s.p, g)
      await bouton(s.p, `Détails de ${g.doc.nom}`).click()
      const panneau = s.p.getByRole('dialog').filter({ hasText: g.doc.nom })
      await panneau.getByRole('tab', { name: /Accès/ }).click()
      await expect(panneau.getByText(/Gérer les droits d.accès/), `${s.c.nomRole} : onglet « Accès » rendu`).toBeVisible(V)
      return panneau
    }
    // Viewer : aucun appel permissions-effectives, pas de « CSV », texte neutre, droits directs présents, aucune 403.
    const s = await ecranDe(page, suivi, testInfo, vi)
    for (const passe of PASSES) {
      s.reseau.length = 0
      s.consoles.length = 0
      const acls = reponse(s.p, ACLS)
      const panneau = await ouvrirAcces(s)
      expect((await acls).status(), `${passe}Viewer : droits directs lus (ged/acls/)`).toBe(200)
      await expect(panneau.getByText('Rapport des accès réservé aux gestionnaires.'), `${passe}Viewer : texte neutre à la place du rapport`).toBeVisible(V)
      await expect(panneau.getByTestId('ged-acl-entries'), `${passe}Viewer : liste des droits directs`).toBeVisible(V)
      await expect(panneau.getByRole('button', { name: 'CSV' }), `${passe}Viewer : aucun bouton « CSV »`).toHaveCount(0)
      await expect(panneau.getByTestId('ged-acl'), `${passe}Viewer : aucun rapport des accès effectifs`).toHaveCount(0)
      await expect(panneau.locator('[role="status"], .animate-spin, [aria-busy="true"]'), `${passe}Viewer : pas de spinner sans fin`).toHaveCount(0)
      await calme(s.p)
      console.log(`[ADRG153] ${passe}Viewer panneau document : ${J(pertinent(s.reseau))} ; console ${J(s.consoles)}`)
      expect(appels(s.reseau, EFFECTIFS(g.doc.id)), `${passe}Viewer : aucun GET ged/documents/${g.doc.id}/permissions-effectives/`).toEqual([])
      expect(refus(s.reseau), `${passe}Viewer : aucune réponse refusée (aucune 403)`).toEqual([])
      expect(s.consoles, `${passe}Viewer : console sans erreur`).toEqual([])
    }
    // Témoin Commercial responsable (ged_gerer) : rapport chargé (200) et bouton « CSV ».
    const c = await ecranDe(page, suivi, testInfo, re)
    for (const passe of PASSES) {
      c.reseau.length = 0
      c.consoles.length = 0
      const ef = reponse(c.p, EFFECTIFS(g.doc.id))
      const panneau = await ouvrirAcces(c)
      expect((await ef).status(), `${passe}Commercial responsable : rapport des accès effectifs lu (200)`).toBe(200)
      await expect(panneau.getByTestId('ged-acl').or(panneau.getByText("Aucune règle d'accès")).first(), `${passe}Commercial responsable : rapport affiché`).toBeVisible(V)
      await expect(panneau.getByRole('button', { name: 'CSV' }), `${passe}Commercial responsable : bouton « CSV » présent`).toBeVisible(V)
      await expect(panneau.getByText('Rapport des accès réservé aux gestionnaires.'), `${passe}Commercial responsable : pas de texte de réserve`).toHaveCount(0)
      await calme(c.p)
      expect(refus(c.reseau), `${passe}Commercial responsable : aucune réponse refusée`).toEqual([])
      expect(c.consoles, `${passe}Commercial responsable : console sans erreur`).toEqual([])
    }
  } finally {
    await r.delete(`${API}/ged/documents/${g.doc.id}/`, T).catch(() => null)
    await r.delete(`${API}/ged/dossiers/${g.dos.id}/`, T).catch(() => null)
    await r.delete(`${API}/ged/cabinets/${g.cab.id}/`, T).catch(() => null)
  }
})

// ───────────────────────── ADRG154 : détail d'un ticket SAV et calendrier ─────────────────────────
const REPLANIFIER = /^\/sav\/tickets\/\d+\/replanifier\/$/
const TICKETS_POST = /^\/sav\/tickets\/$/
const ecritures = (reseau, re) => appels(reseau, re).filter((l) => !l.startsWith('GET '))

etape('PF4-ADRG154-sav-detail-calendrier', ['ADRG154'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const m = marque()
  const vi = await compteDe('Viewer', 'adrg154vi')
  const co = await compteDe('Commercial', 'adrg154co')
  const te = await compteDe('Technicien responsable', 'adrg154te')
  expect([vi.codes.includes('sav_voir'), vi.codes.includes('sav_gerer')], 'Given : Viewer sav_voir sans sav_gerer').toEqual([true, false])
  expect([co.codes.includes('sav_voir'), co.codes.includes('sav_gerer')], 'Given : Commercial sav_voir sans sav_gerer').toEqual([true, false])
  expect(te.codes.includes('sav_gerer'), 'Given : Technicien responsable avec sav_gerer').toBe(true)
  const cl = await lireJson(await r.post(`${API}/crm/clients/`, { ...T, data: { nom: `ADRG154 ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), email: `adrg154_${m}@example.invalid` } }), 'client')
  const t = await lireJson(await r.post(`${API}/sav/tickets/`, { ...T, data: { client: cl.id, type: 'correctif', description: `ADRG154 ${m}` } }), 'ticket')
  try {
    const aujourdhui = await py(`import datetime
sortie(timezone.localdate().isoformat())`)
    /** Le ticket est daté d'aujourd'hui (carte du calendrier) et rattaché au compte joué (visible quel que soit son périmètre). */
    const attribuer = (c) => py(`from apps.sav.models import Ticket
Ticket.objects.filter(pk=${t.id}).update(created_by_id=${c.id}, technicien_responsable_id=${c.id}, date_tournee=${J(aujourdhui)})
sortie(1)`)
    const GESTES = ['Fusionner', 'Convertir en opportunité CRM', 'Nouveau prêt']
    async function detail(s, passe) {
      await charger(s, `/sav?id=${t.id}`, passe)
      const fiche = s.p.locator('aside[aria-label^="Détail du ticket"]')
      await expect(fiche, `${passe}${s.c.nomRole} : détail du ticket ouvert`).toBeVisible(V)
      await expect(fiche.getByText("Prêts d'équipement").first(), `${passe}${s.c.nomRole} : panneau avancé rendu`).toBeVisible(V)
      await calme(s.p)
      return fiche
    }
    async function calendrier(s, passe) {
      await charger(s, '/sav', passe)
      await s.p.getByRole('radio', { name: 'Calendrier' }).click()
      await expect(s.p.getByRole('button', { name: "Aujourd'hui" }), `${passe}${s.c.nomRole} : vue calendrier rendue`).toBeVisible(V)
      await expect(s.p.getByRole('button', { name: new RegExp(`ADRG154 ${m}`) }).first(), `${passe}${s.c.nomRole} : le ticket daté est sur le calendrier`).toBeVisible(V)
      await calme(s.p)
    }
    /** Survole une cellule de jour (le contrôle de création rapide n'apparaît qu'au survol). */
    const survol = async (s) => {
      const cellule = s.p.locator('.group').filter({ has: s.p.locator('div.flex.flex-col.gap-1') }).filter({ hasText: /^\d{1,2}/ }).first()
      await cellule.hover()
      return s.p.getByTitle('Créer un ticket ce jour')
    }
    /** Jour cible du glisser : lendemain d'aujourd'hui, ou la veille si le lendemain tombe dans le mois suivant. */
    const [aa, mm, jj] = aujourdhui.split('-').map(Number)
    const lend = new Date(aa, mm - 1, jj + 1)
    const cibleJ = lend.getMonth() === mm - 1 ? lend : new Date(aa, mm - 1, jj - 1)
    const cibleYmd = `${cibleJ.getFullYear()}-${String(cibleJ.getMonth() + 1).padStart(2, '0')}-${String(cibleJ.getDate()).padStart(2, '0')}`
    /** Cellule du mois affiché pour le jour `n` (cellules « dans le mois » = fond bg-card). */
    const celluleDe = (s, n) => s.p.locator('div.group.bg-card').filter({ has: s.p.locator('span', { hasText: new RegExp(`^${n}$`) }) })
    const carteTicket = (zone) => zone.getByRole('button', { name: new RegExp(`ADRG154 ${m}`) })
    /** VRAI glisser de la carte du ticket (aujourd'hui) vers la cellule du jour cible : souris enfoncée, quelques pixels
     *  (seuil du PointerSensor), puis déplacement progressif, relâchement. */
    async function glisserTicket(s) {
      const carte = carteTicket(celluleDe(s, jj)).first()
      await carte.scrollIntoViewIfNeeded()
      const b = await carte.boundingBox()
      const cible = await celluleDe(s, cibleJ.getDate()).first().boundingBox()
      expect(b && cible, `${s.c.nomRole} : carte et cellule cible mesurables`).toBeTruthy()
      const x = b.x + b.width / 2
      const y = b.y + b.height / 2
      await s.p.mouse.move(x, y)
      await s.p.mouse.down()
      await s.p.mouse.move(x + 8, y + 8, { steps: 3 })
      await s.p.mouse.move(x + 16, y + 16, { steps: 3 })
      await s.p.mouse.move(cible.x + cible.width / 2, cible.y + cible.height / 2, { steps: 25 })
      await s.p.waitForTimeout(300)
      await s.p.mouse.up()
    }
    const dateDuTicket = async () => (await lireJson(await r.get(`${API}/sav/tickets/${t.id}/`, T), 'ticket relu')).date_tournee
    const sans403 = (s, quoi) => {
      console.log(`[ADRG154] ${quoi} : ${J(pertinent(s.reseau))} ; console ${J(s.consoles)}`)
      expect(refus(s.reseau), `${quoi} : aucune réponse refusée (aucune 403)`).toEqual([])
      expect(ecritures(s.reseau, REPLANIFIER), `${quoi} : aucun appel replanifier`).toEqual([])
      expect(ecritures(s.reseau, TICKETS_POST), `${quoi} : aucun POST sav/tickets/`).toEqual([])
      expect(s.consoles, `${quoi} : console sans erreur`).toEqual([])
    }
    // Viewer puis Commercial : aucun des trois gestes du détail, aucun contrôle du calendrier.
    for (const [c, quoi] of [[vi, 'Viewer'], [co, 'Commercial']]) {
      await attribuer(c)
      const s = await ecranDe(page, suivi, testInfo, c)
      for (const passe of PASSES) {
        const fiche = await detail(s, passe)
        for (const nom of GESTES) {
          await expect(fiche.getByRole('button', { name: nom }), `${passe}${quoi} détail : aucun « ${nom} »`).toHaveCount(0)
        }
        await expect(fiche.getByText('Fusionner un ticket doublon'), `${passe}${quoi} détail : aucun bloc de fusion`).toHaveCount(0)
        sans403(s, `${passe}${quoi} détail du ticket`)
      }
      for (const passe of PASSES) {
        await calendrier(s, passe)
        const creer = await survol(s)
        await expect(creer, `${passe}${quoi} calendrier : aucun « Créer un ticket ce jour » (même au survol)`).toHaveCount(0)
        await calme(s.p)
        sans403(s, `${passe}${quoi} calendrier`)
      }
      // Un VRAI glisser de la carte vers un autre jour : aucun replanifier, le ticket garde son jour.
      await calendrier(s, '')
      await expect(carteTicket(celluleDe(s, jj)).first(), `${quoi} glisser : le ticket est sur le jour d'origine avant le glisser`).toBeVisible(V)
      s.reseau.length = 0
      await glisserTicket(s)
      await calme(s.p)
      await s.p.waitForTimeout(1500)
      expect(ecritures(s.reseau, REPLANIFIER), `${quoi} glisser : aucun appel replanifier (${J(s.reseau)})`).toEqual([])
      expect(s.reseau.filter((l) => !l.startsWith('GET ')), `${quoi} glisser : aucune requête d'écriture`).toEqual([])
      await expect(carteTicket(celluleDe(s, jj)).first(), `${quoi} glisser : le ticket est toujours sur son jour`).toBeVisible(V)
      await expect(carteTicket(celluleDe(s, cibleJ.getDate())), `${quoi} glisser : rien sur le jour cible`).toHaveCount(0)
      await calendrier(s, 'relu après rechargement : ')
      await expect(carteTicket(celluleDe(s, jj)).first(), `relu après rechargement : ${quoi} — ticket toujours sur son jour`).toBeVisible(V)
      await expect(carteTicket(celluleDe(s, cibleJ.getDate())), `relu après rechargement : ${quoi} — rien sur le jour cible`).toHaveCount(0)
      expect(await dateDuTicket(), `relu (API) : ${quoi} — date_tournee inchangée`).toBe(aujourdhui)
    }
    // Témoin Technicien responsable (sav_gerer) : les trois gestes et le contrôle de création rapide.
    await attribuer(te)
    const s = await ecranDe(page, suivi, testInfo, te)
    for (const passe of PASSES) {
      const fiche = await detail(s, passe)
      await expect(fiche.getByRole('button', { name: 'Fusionner', exact: true }), `${passe}Technicien responsable : « Fusionner »`).toBeVisible(V)
      await expect(fiche.getByRole('button', { name: 'Convertir en opportunité CRM' }), `${passe}Technicien responsable : « Convertir en opportunité CRM »`).toBeVisible(V)
      await expect(fiche.getByRole('button', { name: 'Nouveau prêt' }), `${passe}Technicien responsable : « Nouveau prêt »`).toBeVisible(V)
      sans403(s, `${passe}Technicien responsable détail du ticket`)
    }
    for (const passe of PASSES) {
      await calendrier(s, passe)
      const creer = await survol(s)
      await expect(creer.first(), `${passe}Technicien responsable calendrier : « Créer un ticket ce jour » au survol`).toBeVisible(V)
      sans403(s, `${passe}Technicien responsable calendrier`)
    }
    // Témoin : le MÊME glisser appelle replanifier (200) et le ticket change de jour, relu après rechargement.
    {
      await calendrier(s, '')
      await expect(carteTicket(celluleDe(s, jj)).first(), 'Technicien responsable glisser : ticket sur son jour avant le glisser').toBeVisible(V)
      s.reseau.length = 0
      const ecrit = reponse(s.p, REPLANIFIER, 'POST')
      await glisserTicket(s)
      const rep = await ecrit
      expect(rep.status(), 'Technicien responsable glisser : replanifier accepté').toBe(200)
      await expect(carteTicket(celluleDe(s, cibleJ.getDate())).first(), 'Technicien responsable glisser : ticket sur le jour cible').toBeVisible(V)
      expect(await dateDuTicket(), 'relu (API) : Technicien responsable — date_tournee = jour cible').toBe(cibleYmd)
      await charger(s, '/sav', 'relu')
      await s.p.getByRole('radio', { name: 'Calendrier' }).click()
      await expect(s.p.getByRole('button', { name: "Aujourd'hui" }), 'relu après rechargement : calendrier rendu').toBeVisible(V)
      await expect(carteTicket(celluleDe(s, cibleJ.getDate())).first(), 'relu après rechargement : Technicien responsable — ticket sur le jour cible').toBeVisible(V)
      await expect(carteTicket(celluleDe(s, jj)), 'relu après rechargement : Technicien responsable — plus sur le jour d\'origine').toHaveCount(0)
    }
  } finally {
    await py(`from apps.sav.models import Ticket
from apps.crm.models import Client
try: Ticket.objects.filter(pk=${t.id}).delete()
except Exception as exc: print('nettoyage ticket', exc)
try: Client.objects.filter(pk=${cl.id}).delete()
except Exception as exc: print('nettoyage client', exc)
sortie(1)`).catch(() => null)
  }
})

// ───────────────────────── ADRG156 : propriétaire désactivé ─────────────────────────
etape('PF4-ADRG156-proprietaire-desactive', ['ADRG156'], async ({ testInfo }) => {
  const m = marque()
  const pro = await compteDe('Directeur', 'adrg156di')
  const anonyme = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  OUVERTS.push(() => anonyme.dispose())
  let rapportId = 0
  /** Passage hebdomadaire RÉEL (`email_saved_reports`), lundi 06 h Casablanca, courrier doublé ; limité à CE rapport. */
  const passage = async () => py(`from apps.reporting import scheduled_reports as sr
from zoneinfo import ZoneInfo
envoyer = mock.Mock(return_value=True)
lundi = datetime.datetime(2026, 4, 13, 6, 0, tzinfo=ZoneInfo('Africa/Casablanca'))
orig = sr._rapport_est_du
with mock.patch.object(sr, '_casablanca_now', return_value=lundi), \\
     mock.patch.object(sr, '_is_email_configured', return_value=True), \\
     mock.patch.object(sr, '_send_report_email', envoyer), \\
     mock.patch.object(sr, '_rapport_est_du', lambda r, n: r.pk == ${rapportId} and orig(r, n)):
    n = sr.email_saved_reports()
from apps.reporting.models import EnvoiRapport, SavedReport
r = SavedReport.objects.get(pk=${rapportId})
sortie(dict(n=n, appels=envoyer.call_count, last=str(r.last_sent_at),
            envois=list(EnvoiRapport.objects.filter(saved_report=r).order_by('id').values_list('statut', 'erreur'))))`)
  try {
    const cree = await py(`from apps.reporting.models import SavedReport
r = SavedReport.objects.create(company_id=${SOC}, owner_id=${pro.id}, name=${J(`Hebdo ADRG156 ${m}`)}, target_kind='sales',
    schedule='weekly', recipients='direction@exemple.ma')
from apps.reporting.diffusion_views import make_report_token
sortie(dict(id=r.pk, jeton=make_report_token(r)))`)
    rapportId = cree.id
    const lien = `${API}/reporting/rapports-partages/${cree.jeton}/`
    const desactive = async (actif) => py(`U.objects.filter(pk=${pro.id}).update(is_active=${actif ? 'True' : 'False'})
sortie(1)`)
    // Propriétaire désactivé : aucun envoi, une ligne echec motivée, last_sent_at nul, lien 404.
    await desactive(false)
    const a = await passage()
    expect(a.appels, `propriétaire désactivé : _send_report_email jamais appelé (${J(a)})`).toBe(0)
    expect(a.envois, `propriétaire désactivé : une seule ligne echec motivée (${J(a)})`).toEqual([['echec', 'Propriétaire du rapport désactivé : envoi suspendu.']])
    expect(a.last, 'propriétaire désactivé : last_sent_at nul').toBe('None')
    const l404 = await anonyme.get(lien, T)
    expect(l404.status(), 'propriétaire désactivé : lien public 404').toBe(404)
    expect((await l404.json()).detail, 'propriétaire désactivé : message du lien').toBe('Rapport indisponible.')
    const relu = await py(`from apps.reporting.models import EnvoiRapport
sortie(list(EnvoiRapport.objects.filter(saved_report_id=${rapportId}).values_list('statut', flat=True)))`)
    expect(relu, 'relu : une seule ligne echec').toEqual(['echec'])
    // Témoin : propriétaire réactivé ⇒ le rapport part, le lien répond 200.
    await desactive(true)
    const b = await passage()
    expect(b.appels, `propriétaire réactivé : le rapport est envoyé (${J(b)})`).toBe(1)
    expect(b.n, 'propriétaire réactivé : un envoi compté').toBe(1)
    expect(b.envois.map((x) => x[0]), 'propriétaire réactivé : journal echec puis envoye').toEqual(['echec', 'envoye'])
    const l200 = await anonyme.get(lien, T)
    expect(l200.status(), 'propriétaire réactivé : lien public 200').toBe(200)
  } finally {
    await py(`from apps.reporting.models import SavedReport
SavedReport.objects.filter(pk=${rapportId}).delete()
sortie(1)`).catch(() => null)
  }
})

// ───────────────────────── ADRG157 : widget de métrique nommée ─────────────────────────
etape('PF4-ADRG157-widget-metrique', ['ADRG157'], async ({ testInfo }) => {
  const m = marque()
  const re = await compteDe('Commercial responsable', 'adrg157re')
  const di = await compteDe('Directeur', 'adrg157di')
  expect(re.codes.includes('stock_export'), 'Given : Commercial responsable sans stock_export').toBe(false)
  expect(di.codes.includes('stock_export'), 'Given : Directeur avec stock_export').toBe(true)
  const apiR = await apiDe(testInfo, re)
  const apiD = await apiDe(testInfo, di)
  const nomProduit = `Onduleur ADRG157 ${m}`
  const donnees = await py(`from apps.semantic.models import MetricDefinition
from apps.stock.models import Produit
from core.models import Dashboard
cle = 'stock_qte_${m}'
md = MetricDefinition.objects.create(company_id=${SOC}, cle=cle, libelle='Stock', dataset='stock_produits',
    mesure={'field': 'quantite_stock', 'agg': 'sum'})
p = Produit.objects.create(company_id=${SOC}, nom=${J(nomProduit)}, sku='A157-${m}', prix_vente=100, quantite_stock=3)
d = Dashboard.objects.create(company_id=${SOC}, titre=${J(`Tableau ADRG157 ${m}`)}, partage=True,
    layout={'widgets': [{'id': 'm', 'titre': 'Stock', 'type': 'metrique', 'metrique': cle, 'group_by': ['nom']}]})
sortie(dict(md=md.pk, p=p.pk, d=d.pk))`)
  const corps = { name: `Stock ADRG157 ${m}`, target_kind: 'dashboard', cible_id: donnees.d, schedule: 'weekly', recipients: 'x@exemple.ma' }
  const url = `${API}/reporting/saved-reports/`
  let creeD = null
  let rapportR = 0
  try {
    const refuse = await apiR.post(url, { ...T, data: corps })
    expect(refuse.status(), 'Commercial responsable : programmer le tableau de métrique stock refusé').toBe(403)
    expect(await refuse.text(), 'Commercial responsable : refus du jeu de données').toContain('Accès au jeu de données refusé.')
    const liste = await lireJson(await apiR.get(url, T), 'rapports du Commercial responsable')
    const noms = (Array.isArray(liste) ? liste : liste.results || []).map((x) => x.name)
    expect(noms, 'relu : aucun rapport du Commercial responsable à ce nom').not.toContain(corps.name)
    // Témoin Directeur : 201.
    const ok = await apiD.post(url, { ...T, data: corps })
    expect(ok.status(), 'Directeur : même programmation acceptée').toBe(201)
    creeD = (await ok.json()).id
    // Rendu : un rapport du Commercial responsable ne rend pas le nom du produit ; widget en bloc d'erreur.
    const rendu = await py(`from apps.reporting import scheduled_reports as sr
from apps.reporting.models import SavedReport
from core.models import Dashboard
r = SavedReport.objects.create(company_id=${SOC}, owner_id=${re.id}, name=${J(`Rendu ADRG157 ${m}`)}, target_kind='dashboard',
    cible_id=${donnees.d}, schedule='weekly', recipients='x@exemple.ma')
html_re = sr.rendre_dashboard_html(r, Dashboard.objects.get(pk=${donnees.d}))
r.owner_id = ${di.id}; r.save()
html_di = sr.rendre_dashboard_html(SavedReport.objects.get(pk=r.pk), Dashboard.objects.get(pk=${donnees.d}))
sortie(dict(r=r.pk, re=html_re, di=html_di))`)
    rapportR = rendu.r
    expect(rendu.re.includes(nomProduit), 'rendu (propriétaire Commercial responsable) : sans le nom du produit').toBe(false)
    expect(rendu.re, 'rendu (propriétaire Commercial responsable) : widget en bloc d\'erreur').toContain('<h2>Stock</h2><p class="erreur">Accès au jeu de données refusé.</p>')
    expect(rendu.di.includes(nomProduit), 'rendu (témoin, propriétaire Directeur) : le nom du produit est rendu').toBe(true)
  } finally {
    if (creeD) await apiD.delete(`${url}${creeD}/`, T).catch(() => undefined)
    await py(`from apps.reporting.models import SavedReport
from apps.semantic.models import MetricDefinition
from apps.stock.models import Produit
from core.models import Dashboard
SavedReport.objects.filter(pk=${rapportR}).delete()
SavedReport.objects.filter(cible_id=${donnees.d}).delete()
Dashboard.objects.filter(pk=${donnees.d}).delete()
MetricDefinition.objects.filter(pk=${donnees.md}).delete()
Produit.objects.filter(pk=${donnees.p}).delete()
sortie(1)`).catch(() => null)
  }
})

// ───────────────────────── ADRG158 : rapport figé « stock » ─────────────────────────
etape('PF4-ADRG158-rapport-stock', ['ADRG158'], async ({ page, suivi, testInfo }) => {
  const re = await compteDe('Commercial responsable', 'adrg158re')
  const di = await compteDe('Directeur', 'adrg158di')
  expect(re.codes.includes('stock_export'), 'Given : Commercial responsable sans stock_export').toBe(false)
  expect(di.codes.includes('stock_export'), 'Given : Directeur avec stock_export').toBe(true)
  const apiR = await apiDe(testInfo, re)
  const apiD = await apiDe(testInfo, di)
  const MOTIF = "Stock (droit d'export du stock requis)"
  const stockUrl = `${API}/reporting/reports/stock/`
  const onglet = (s, nom) => s.p.getByRole('tab', { name: nom, exact: true })
  const ouvrirStock = async (s, passe) => {
    await charger(s, '/rapports')
    await expect(s.p.getByRole('heading', { name: 'Rapports' }).first(), `${passe}${s.c.nomRole} : écran Rapports`).toBeVisible(V)
    await onglet(s, 'Stock').click()
    await expect(s.p.getByText('Valorisation (vente)').first(), `${passe}${s.c.nomRole} : onglet Stock rendu`).toBeVisible(V)
    await calme(s.p)
  }
  const optionStock = async (s, passe, formulaire) => {
    if (formulaire === 'rapports') {
      await charger(s, '/rapports')
      await onglet(s, 'Mes rapports').click()
      await s.p.getByRole('button', { name: 'Nouveau rapport' }).click()
      await expect(s.p.getByText('Nouveau rapport sauvegardé'), `${passe}${s.c.nomRole} : formulaire Nouveau rapport`).toBeVisible(V)
      return s.p.locator('select option[value="stock"]')
    }
    await charger(s, '/reporting/envois-programmes')
    await expect(s.p.getByRole('heading', { name: 'Envois programmés' }), `${passe}${s.c.nomRole} : écran des envois programmés`).toBeVisible(V)
    await s.p.getByRole('button', { name: 'Nouvel envoi' }).click()
    await expect(s.p.getByTestId('envoi-form-carte'), `${passe}${s.c.nomRole} : formulaire Nouvel envoi`).toBeVisible(V)
    return s.p.locator('#ep-kind option[value="stock"]')
  }
  const propre = (s, quoi) => {
    expect(refus(s.reseau), `${quoi} : aucune réponse refusée (${J(s.reseau)})`).toEqual([])
    expect(s.consoles, `${quoi} : console propre`).toEqual([])
  }
  // API : refus PROVOQUÉ par l'appel direct (contexte API, hors page).
  const x = await apiR.get(`${stockUrl}?export=xlsx`, T)
  expect(x.status(), 'Commercial responsable : export xlsx du stock refusé').toBe(403)
  const corpsX = await x.json()
  expect(corpsX.code, 'Commercial responsable : code droit_manquant').toBe('droit_manquant')
  expect(String(corpsX.detail), 'Commercial responsable : détail nomme stock_export').toContain('stock_export')
  expect((await apiR.get(stockUrl, T)).status(), 'Commercial responsable : JSON du stock 200').toBe(200)
  expect((await apiD.get(`${stockUrl}?export=xlsx`, T)).status(), 'Directeur : export xlsx du stock 200').toBe(200)
  // Commercial responsable : écrans.
  const s = await ecranDe(page, suivi, testInfo, re)
  for (const passe of PASSES) {
    await ouvrirStock(s, passe)
    await expect(s.p.getByRole('button', { name: 'Exporter Excel' }), `${passe}Commercial responsable : aucun « Exporter Excel » sur l'onglet Stock`).toHaveCount(0)
    propre(s, `${passe}Commercial responsable /rapports Stock`)
    for (const f of ['rapports', 'envois']) {
      const opt = await optionStock(s, passe, f)
      await expect(opt, `${passe}Commercial responsable (${f}) : option Stock grisée`).toBeDisabled()
      await expect(opt, `${passe}Commercial responsable (${f}) : motif affiché`).toHaveText(MOTIF)
      propre(s, `${passe}Commercial responsable ${f}`)
    }
  }
  // Témoin Directeur.
  const d = await ecranDe(page, suivi, testInfo, di)
  for (const passe of PASSES) {
    await ouvrirStock(d, passe)
    await expect(d.p.getByRole('button', { name: 'Exporter Excel' }).first(), `${passe}Directeur : « Exporter Excel » présent sur l'onglet Stock`).toBeVisible(V)
    propre(d, `${passe}Directeur /rapports Stock`)
    for (const f of ['rapports', 'envois']) {
      const opt = await optionStock(d, passe, f)
      await expect(opt, `${passe}Directeur (${f}) : option Stock activée`).toBeEnabled()
      await expect(opt, `${passe}Directeur (${f}) : libellé « Stock »`).toHaveText('Stock')
      propre(d, `${passe}Directeur ${f}`)
    }
  }
})
