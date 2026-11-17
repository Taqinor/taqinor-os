// aerr11 : AERR69 (palette) et AERR114 « Suppr » sous une boîte — specs jouées SEULES (leur FAIL ne couvre rien, il ne doit pas
// faire tomber l'enregistrement de aerr10).
// Preuves en direct ÉCRAN du groupe AERR, vague 6 (runner GitHub, essai du 16/11/2026) : les tâches « code livré, preuve
// en direct due » AERR1 (Note de débit et Encaissements — l'écran Factures est déjà joué par aerr3, Remises par aerr6),
// AERR69 (palette ⌘K), AERR114 (confirmations nommées des suppressions : gabarit, relevé, pose réelle), AERR120 (fiche
// lead pleine page : « Signé » refusé) et AERR132 (fiche produit à stock négatif).
// Chaque étape joue le geste À L'ÉCRAN sous un compte d'un rôle LIVRÉ (relu par son nom dans la société démo, connexion par
// /token/ comme aerr3.spec.js), PROVOQUE le refus ou la panne (route Playwright déclarée AVANT par `suivi.attendre`),
// AFFIRME ce que la clause nomme, relit la base (API / shell Django) et recharge. Données propres créées par les vraies
// routes ou le shell Django ; une facture à numéro légal reste sur la base jetable du runner.
// AERR114 : la clause « Suppr tapé sous une boîte posée sur l'atelier n'appelle aucune action » exige le constructeur 3D
// (carte MapTiler, absente du runner : `builderApi.raccourcis` vide ⇒ aucun gestionnaire à appeler, preuve vide) — NON
// jouée ici ; les trois confirmations nommées (gabarit, pose réelle, relevé) le sont.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, connexionApi, assurerSessionPage, telephoneMobileUnique, STAGE_LABELS } from '../helpers.js'

const etape = groupe('AERR', ['AERR69', 'AERR114'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
const SOC = `U.objects.get(username='demo_admin').company_id`
test.describe.configure({ timeout: 600_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const ouverts = []
const apres = []
test.afterEach(async () => {
  for (const c of ouverts.splice(0)) await c.close().catch(() => undefined)
  for (const f of apres.splice(0)) await f().catch((e) => console.log(`[nettoyage] ${e.message}`))
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const pad = (n) => String(n).padStart(2, '0')
const _isoJour = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
const toast = (p, texte) => p.locator('[data-sonner-toast]').filter({ hasText: texte })

/** Compte d'essai du rôle LIVRÉ `nomRole` de la société démo ; renvoie son id. */
const compteRole = (nom, nomRole) => py(`from apps.roles.models import Role
r = Role.objects.get(company_id=${SOC}, nom=${J(nomRole)})
u = compte(${J(nom)}, role=r.pk, societe=${SOC})
sortie(u.id)`)

/** Écran sous le compte `nom` : contexte neuf (accueil et visites vus, SW bloqué), observé ; la page demo_admin est
 *  refermée (la capture montre l'écran du rôle). `api` = requêtes de CE compte (même jarre de cookies). */
async function ecran(page, suivi, testInfo, nom) {
  if (!page.isClosed()) await page.close()
  const u = testInfo.project.use
  const ctx = await page.context().browser().newContext({
    baseURL: u.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
    viewport: { width: 1600, height: 1000 },
  })
  ouverts.push(ctx)
  await ctx.addInitScript(() => {
    try {
      localStorage.setItem('taqinor-pwa-install-dismissed', '1'); localStorage.setItem('taqinor:welcome:seen:v1', '1')
      const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Casablanca', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date())
      const v = (t) => parts.find((x) => x.type === t).value
      localStorage.setItem('taqinor.prechargementTournee', `${v('year')}-${v('month')}-${v('day')}`)
    } catch { /* mode privé */ }
  })
  await connexionApi(ctx.request, { username: nom, password: MDP_ESSAI })
  const visites = await ctx.request.get(`${API}/onboarding/tours/`, T)
  if (visites.ok()) {
    for (const v of await visites.json()) {
      if (!v.vu) await ctx.request.post(`${API}/onboarding/tours/${v.tour_key}/vu/`, T)
    }
  }
  return { p: suivi.surveiller(await ctx.newPage()), api: ctx.request, ctx }
}

/** Route tenue : chaque requête qui passe attend `lacher()`, puis `issue(route)` (abort par défaut). */
function _porte() {
  let lacher
  let signaler
  const ouverte = new Promise((r) => { lacher = r })
  const arrivee = new Promise((r) => { signaler = r })
  return {
    arrivee, lacher: () => lacher(),
    gestion: (issue = (route) => route.abort('failed')) => async (route) => { signaler(); await ouverte; await issue(route) },
  }
}
/** Compteur de requêtes (méthode(s) + chemin) observées par la page. */
function compteur(p, methodes, cheminOk) {
  const c = { n: 0, corps: [], urls: [] }
  p.on('request', (r) => {
    if (!methodes.includes(r.method())) return
    const u = new URL(r.url())
    if (!cheminOk(u.pathname, u)) return
    c.n += 1
    c.urls.push(`${r.method()} ${u.pathname}${u.search}`)
    c.corps.push(r.postData() || '')
  })
  return c
}

/** Leads de la société démo, propriétaire `owner` ; `liste` = champs du modèle. Renvoie leurs pk. */
const creerLeads = (owner, liste) => py(`from apps.crm.models import Lead
out = []
for d in json.loads(${J(J(liste))}):
    out.append(Lead.objects.create(company_id=${SOC}, owner_id=${owner}, **d).pk)
sortie(out)`)
const supprimerLeads = (pks) => py(`from apps.crm.models import Lead
try:
    from apps.ventes.models import Devis
    Devis.all_objects.filter(lead_id__in=${J(pks)}).delete() if hasattr(Devis, 'all_objects') else Devis.objects.filter(lead_id__in=${J(pks)}).delete()
except Exception as exc:
    print('devis', exc)
for pk in ${J(pks)}:
    try: Lead.all_objects.filter(pk=pk).delete()
    except Exception as exc: print('nettoyage', pk, exc)`)
const etapeLead = (lead) => py(`from apps.crm.models import Lead
sortie(Lead.objects.get(pk=${lead}).stage)`)

// ═══ AERR69 — palette ⌘K : « Changer le stage » ⇒ toast nommé + « Annuler » ; vers « Signé » une boîte nommée d'abord ═══
async function lancerChangerStage(p) {
  await p.keyboard.press('Control+k')
  const champ = p.getByRole('textbox', { name: 'Recherche rapide' })
  await expect(champ, 'palette ouverte').toBeVisible({ timeout: 30_000 })
  await champ.fill('Changer le stage')
  await p.getByText('Changer le stage du lead sélectionné').first().click()
}
etape('PF12.69-AERR69', ['AERR69'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr69_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const [A, B, C] = await creerLeads(cr, [
    { nom: `Karim B. ${m}`, prenom: '', telephone: telephoneMobileUnique(), stage: 'CONTACTED' },
    { nom: `Relance ${m}`, prenom: '', telephone: telephoneMobileUnique(), stage: 'FOLLOW_UP' },
    { nom: `Panne ${m}`, prenom: '', telephone: telephoneMobileUnique(), stage: 'CONTACTED' },
  ])
  apres.push(() => supprimerLeads([A, B, C]))
  const { p, api } = await ecran(page, suivi, testInfo, nom)
  const patchsDe = (id) => compteur(p, ['PATCH'], (ch) => ch === `${API}/crm/leads/${id}/`)
  const ouvrirFiche = async (id, nomLead) => {
    await p.goto(`/crm/leads?lead=${id}`)
    await expect(p.getByText(nomLead).first(), `fiche de ${nomLead} affichée`).toBeVisible({ timeout: 60_000 })
  }

  // (1) Lead CONTACTED : un PATCH {stage: QUOTE_SENT}, toast « <nom> → Devis envoyé » + « Annuler » qui le remet en CONTACTED.
  const pa = patchsDe(A)
  await ouvrirFiche(A, `Karim B. ${m}`)
  await lancerChangerStage(p)
  const t = toast(p, `Karim B. ${m} → ${STAGE_LABELS.QUOTE_SENT}`).first()
  await expect(t, 'toast nommé « <nom du lead> → Devis envoyé »').toBeVisible({ timeout: 30_000 })
  await expect(t.getByRole('button', { name: 'Annuler' }), 'toast avec « Annuler »').toBeVisible()
  await expect.poll(() => pa.n, { timeout: 15_000 }).toBe(1)
  expect(JSON.parse(pa.corps[0]), 'PATCH de l\'avancée').toEqual({ stage: 'QUOTE_SENT' })
  expect(await etapeLead(A), 'base : avancé en QUOTE_SENT').toBe('QUOTE_SENT')
  const retour = p.waitForResponse((r) => r.request().method() === 'PATCH' && r.url().endsWith(`/crm/leads/${A}/`) && r.request().postData() !== pa.corps[0], T)
  // « Annuler » cliqué À LA SOURIS (fiche ouverte en fenêtre modale : sa couche modale pose `pointer-events:none` sur le
  // toast, le clic tombe sur la couche). Constaté au run 43978374413 : s'il est bloqué, l'étape le DIT (défaut) puis
  // déclenche le bouton par son gestionnaire pour juger le reste de la clause (appel inverse, base).
  let clicBloque = false
  await t.getByRole('button', { name: 'Annuler' }).click({ timeout: 2500 }).catch(() => { clicBloque = true })
  if (clicBloque) {
    testInfo.annotations.push({ type: 'défaut AERR69', description: '« Annuler » du toast non cliquable à la souris : la couche de la fiche ouverte (modale) intercepte le clic' })
    await t.getByRole('button', { name: 'Annuler' }).dispatchEvent('click')
  }
  const rep = await retour
  expect(JSON.parse(rep.request().postData()), '« Annuler » PATCHe l\'étape d\'origine').toMatchObject({ stage: 'CONTACTED' })
  // DÉFAUT connu (C-AERR-VER2-219) : l'appel inverse part SANS `undo: true` — le serveur refuse un recul sans lui (409).
  // Relevé sans interrompre l'étape, pour juger aussi (2) et (3) ; l'étape reste FAIL (verdict en fin d'étape).
  const defauts = []
  if (rep.status() >= 300) {
    defauts.push(`« Annuler » refusé par le serveur : ${rep.status()} ${(await rep.text()).slice(0, 200)} — corps envoyé ${rep.request().postData()}`)
  } else {
    await expect.poll(() => etapeLead(A), { timeout: 30_000, message: 'base : retour en CONTACTED' }).toBe('CONTACTED')
    const relu = await lireJson(await api.get(`${API}/crm/leads/${A}/`, T), 'lead relu')
    expect(relu.stage, 'persistance : le lead relu est en CONTACTED').toBe('CONTACTED')
  }
  if (clicBloque) defauts.push('« Annuler » du toast non cliquable à la souris sur la fiche ouverte (`?lead=<id>`) : la couche modale intercepte le clic')

  // (2) Lead en Relance : une boîte nommée AVANT tout passage en « Signé » ; « Annuler » ⇒ aucun PATCH.
  const pb = patchsDe(B)
  await ouvrirFiche(B, `Relance ${m}`)
  await lancerChangerStage(p)
  const boite = p.getByRole('alertdialog')
  await expect(boite, 'boîte nommée avant « Signé »').toBeVisible({ timeout: 30_000 })
  await expect(boite).toContainText(`Passer « Relance ${m} » en « ${STAGE_LABELS.SIGNED} » ?`)
  expect(pb.n, 'la boîte précède tout PATCH').toBe(0)
  await boite.getByRole('button', { name: 'Annuler' }).click()
  await expect(boite).toHaveCount(0)
  await p.waitForTimeout(1500)
  expect(pb.n, '« Annuler » : aucun PATCH').toBe(0)
  expect(await etapeLead(B), 'base : le lead reste en FOLLOW_UP').toBe('FOLLOW_UP')

  // (3) Échec serveur : UN SEUL toast (celui de l'intercepteur global).
  suivi.attendre(new RegExp(`/api/django/crm/leads/${C}/$`), 500)
  await p.route((u) => u.pathname === `${API}/crm/leads/${C}/`, (route) => (route.request().method() === 'PATCH'
    ? route.fulfill({ status: 500, contentType: 'application/json', body: J({ detail: 'panne injectée AERR69' }) })
    : route.fallback()))
  const pc = patchsDe(C)
  await ouvrirFiche(C, `Panne ${m}`)
  await lancerChangerStage(p)
  await expect.poll(() => pc.n, { timeout: 30_000 }).toBeGreaterThanOrEqual(1)
  await expect(p.locator('[data-sonner-toast]').first(), 'l\'échec est dit').toBeVisible({ timeout: 15_000 })
  await p.waitForTimeout(2500)
  expect(await p.locator('[data-sonner-toast]').count(), 'un seul message pour un échec (aucun toast qui double celui de l\'intercepteur)').toBe(1)
  expect(await etapeLead(C), 'base : rien d\'écrit sur échec').toBe('CONTACTED')
  expect(defauts, '« Annuler » du toast remet le lead en CONTACTED (clic souris, appel accepté par le serveur)').toEqual([])
})

// ═══ AERR114 (suite) — « Suppr » tapé sous une boîte posée par-dessus l'atelier n'appelle aucune action ═══
// Montage de l'atelier sans clé carte secrète : comme acal4.spec.js (vague 6), la réponse réelle de `design-context` est
// relue et sa `carte` surchargée par une clé factice ; MapTiler répond 403 (fond de repli local). Un obstacle est dessiné
// à la souris (il est alors SÉLECTIONNÉ : `#rp9-obs-delete` visible) ; la palette ⌘K (boîte Radix) est ouverte par-dessus,
// le focus quitte son champ, « Suppr » est tapé : l'obstacle doit rester sélectionné. Témoin : boîte fermée, « Suppr » ⇒ supprimé.
etape('PF12.114-AERR114-suppr', ['AERR114'], async ({ page, context, suivi }) => {
  const m = marque()
  const cal = await py(`from decimal import Decimal as D
from apps.crm.models import Lead
from apps.calepinage.models import Calepinage
from apps.calepinage.tests.test_acal_multi_pans import _layout, _zone
from apps.ventes.domain.geometrie import layout_hash
co = U.objects.get(username='demo_admin').company
lead = Lead.objects.create(company=co, nom='ACC AERR114 ${m}', ville='Casablanca', type_installation='residentiel', facture_hiver=D('900'))
lay = _layout(_zone(1, 16, 90.0), _zone(2, 8, 270.0))
lay.update({'scenario': 'reseau', 'panelWatt': 710, 'result': {'panels': 24, 'kwc': 17.04}})
c = Calepinage.objects.create(company=co, lead_id=lead.pk, titre='ACC AERR114 ${m}', roof_layout=lay, layout_hash=layout_hash(lay))
sortie({'id': c.pk})`)
  apres.push(() => py(`from apps.calepinage.models import Calepinage
Calepinage.objects.filter(pk=${cal.id}).delete()`))
  await context.route(new RegExp(`/calepinage/calepinages/${cal.id}/design-context/`), async (route) => {
    const reelle = await route.fetch()
    const corps = await reelle.json()
    corps.carte = { ...(corps.carte || {}), available: true, maptilerKey: 'cle-factice-aerr114', mapboxToken: null }
    await route.fulfill({ response: reelle, json: corps })
  })
  suivi.attendre(/api\.maptiler\.com/, 403)
  await context.route(/https:\/\/api\.maptiler\.com\//, (route) => route.fulfill({ status: 403, contentType: 'application/json', body: '{"message":"Invalid key"}' }))
  await page.setViewportSize({ width: 1600, height: 1000 })
  await page.goto(`/calepinage/${cal.id}`)
  await expect(page.getByRole('button', { name: 'Enregistrer le calepinage' }), 'atelier booté (scène hydratée)').toBeEnabled({ timeout: 180_000 })
  const cv = page.locator('canvas.maplibregl-canvas').first()
  const bb = await cv.boundingBox()
  // Le bloc « Obstacles » n'est montré qu'une fois le toit fermé : si l'hydratation ne l'a pas ouvert, on trace un toit
  // (4 sommets puis fermeture sur le 1er).
  if (!(await page.locator('#rp9-obstacle').isVisible())) {
    const pts = [[0.35, 0.35], [0.65, 0.35], [0.65, 0.65], [0.35, 0.65]]
    for (const [fx, fy] of pts) await page.mouse.click(bb.x + bb.width * fx, bb.y + bb.height * fy)
    await page.mouse.click(bb.x + bb.width * pts[0][0], bb.y + bb.height * pts[0][1])
    await page.waitForTimeout(1500)
  }
  console.log(`[AERR114] bloc Obstacles visible : ${await page.locator('#rp9-obstacle').isVisible()}`)
  // Dessin d'un obstacle : mode obstacle puis glisser sur la carte ⇒ l'obstacle est sélectionné.
  await page.locator('#rp9-obstacle').click({ timeout: 20_000 })
  const x = bb.x + bb.width * 0.5
  const y = bb.y + bb.height * 0.5
  await page.mouse.move(x, y)
  await page.mouse.down()
  await page.mouse.move(x + 60, y + 40, { steps: 8 })
  await page.mouse.move(x + 120, y + 80, { steps: 8 })
  await page.mouse.up()
  const supprimerObs = page.locator('#rp9-obs-delete')
  await expect(supprimerObs, 'un obstacle est sélectionné (bouton « Supprimer » de l\'obstacle visible)').toBeVisible({ timeout: 20_000 })
  // Boîte Radix par-dessus : la palette ⌘K ; le focus quitte son champ de saisie.
  await page.locator('#rp9-obstacle').click() // quitte le mode dessin sans toucher à l'obstacle
  await page.keyboard.press('Control+k')
  const palette = page.getByRole('dialog', { name: 'Palette de commandes' })
  await expect(palette, 'boîte posée par-dessus l\'atelier').toBeVisible({ timeout: 30_000 })
  await page.evaluate(() => { document.activeElement?.blur?.(); document.querySelector('[role="dialog"][aria-label="Palette de commandes"]')?.focus() })
  await page.keyboard.press('Delete')
  await page.keyboard.press('Backspace')
  await page.waitForTimeout(1000)
  await expect(supprimerObs, '« Suppr » sous la boîte : l\'obstacle reste sélectionné (aucune action appelée)').toBeVisible()
  // Témoin : boîte fermée, « Suppr » agit.
  await page.keyboard.press('Escape')
  await expect(palette).toHaveCount(0)
  await page.evaluate(() => document.activeElement?.blur?.())
  await page.keyboard.press('Delete')
  await expect(supprimerObs, 'témoin : boîte fermée, « Suppr » supprime l\'obstacle').toBeHidden({ timeout: 15_000 })
})
