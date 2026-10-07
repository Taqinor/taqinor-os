// Shared helpers + constants for the Taqinor OS E2E suite.
// Selectors mirror the REAL components (no data-testids exist in the app, so we
// lean on visible text, placeholders, stable CSS classes and ARIA roles).
import { execFileSync } from 'node:child_process'
import { existsSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test as base } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

// Seeded by `manage.py seed_demo` (company "TAQINOR Démo"). Throwaway only.
export const ADMIN = { username: 'demo_admin', password: 'Demo@2026!' }
export const SECOND_USER = 'demo_resp'

export const AUTH_FILE = 'e2e/.auth/admin.json'

// ── CAD177 — session partagée qui SURVIT à une matrice longue ──────────────
// `auth.setup.js` se connecte UNE fois et fige les cookies dans AUTH_FILE ;
// chaque test rouvre un contexte depuis ce fichier. Deux faits du backend
// rendent ce fichier périssable sur la matrice COMPLÈTE de release-verify
// (~60 min, contre ~5 min pour le shard par-merge) :
//   1. l'access JWT vit 30 min (ERR87) et le refresh TOURNE à usage unique
//      (ROTATE_REFRESH_TOKENS + BLACKLIST_AFTER_ROTATION) : dès qu'un test
//      rafraîchit dans SON contexte, le refresh du fichier est en liste noire ;
//   2. une déconnexion (même cliquée par le singe gremlins) révoque la
//      session côté serveur (AUD408 — l'access meurt aussitôt).
// Run 36990128960 : le singe a cliqué « Déconnexion » sur /admin/impersonation
// à 09:46 → les 18 modules @monkey suivants, les 20 tests mobile et les 3
// tablette sont tous tombés sur /login (refresh 401). Ce n'est pas un défaut
// produit — c'est l'état de test partagé qui était périmé. Le remède : avant
// chaque test qui s'appuie sur AUTH_FILE, vérifier la session et, si elle est
// morte ou proche de l'expiration, la rafraîchir (ou se reconnecter par l'API)
// puis RÉÉCRIRE le fichier — les tests suivants repartent d'un état valide.
const MARGE_EXPIRATION_S = 10 * 60

function secondesRestantesAccess(cookies) {
  const access = cookies.find((c) => c.name === 'access_token')
  if (!access) return -1
  try {
    const charge = JSON.parse(
      Buffer.from(access.value.split('.')[1], 'base64url').toString('utf8'))
    return charge.exp - Math.floor(Date.now() / 1000)
  } catch {
    return -1
  }
}

/** Connexion par l'API (cookies posés dans `requete`, contexte API ou
 *  `page.request`). Le throttle « login » (5/min/IP) peut répondre 429 :
 *  on réessaie à intervalles jusqu'à ce que le serveur accepte — une
 *  condition observée, jamais une pause aveugle. */
export async function connexionApi(requete, { username, password } = ADMIN) {
  await expect(async () => {
    const res = await requete.post('/api/django/token/', { data: { username, password } })
    expect(res.status(), `connexion API de ${username}`).toBe(200)
  }).toPass({ intervals: [5_000, 10_000, 15_000], timeout: 75_000 })
}

/** Session vivante dans `requete` ? (`/auth/me/` 200). */
async function sessionVivante(requete) {
  // CAD177 : délai dur — un /auth/me/ qui pend échoue vite au lieu de consommer
  // le budget entier du test.
  return (await requete.get('/api/django/auth/me/', { timeout: 20_000 })).ok()
}

/** Rafraîchit AUTH_FILE si sa session est morte ou expire bientôt. */
export async function rafraichirEtatPartage(playwright, baseURL) {
  const ctx = await playwright.request.newContext({ baseURL, storageState: AUTH_FILE })
  try {
    const avant = (await ctx.storageState()).cookies
    if (secondesRestantesAccess(avant) > MARGE_EXPIRATION_S && await sessionVivante(ctx)) {
      return
    }
    const refresh = await ctx.post('/api/django/auth/token/refresh/', { data: {} })
    if (!(refresh.ok() && await sessionVivante(ctx))) {
      await connexionApi(ctx)
      expect(await sessionVivante(ctx), 'session admin après reconnexion').toBeTruthy()
    }
    // Les drapeaux localStorage du setup (bannière PWA, accueil vu) restent :
    // seul le jeu de cookies est remplacé.
    const ancien = JSON.parse(readFileSync(AUTH_FILE, 'utf8'))
    const { cookies } = await ctx.storageState()
    writeFileSync(AUTH_FILE, JSON.stringify({ ...ancien, cookies }, null, 2))
  } finally {
    await ctx.dispose()
  }
}

/** `test` dont l'état partagé (AUTH_FILE) est garanti vivant au démarrage de
 *  chaque test. Un `test.use({ storageState: {...} })` explicite (test à
 *  froid) passe tel quel. À utiliser par les specs des projets qui tournent
 *  APRÈS le gros projet `chromium` (monkey, mobile, mobile-safari, tablet). */
export const testSessionFraiche = base.extend({
  storageState: async ({ storageState, playwright, baseURL }, fournir) => {
    if (storageState === AUTH_FILE) await rafraichirEtatPartage(playwright, baseURL)
    await fournir(storageState)
  },
})

/** VX156 — premier login à froid : le « moment d'accueil » (WelcomeMoment,
 *  modale one-shot plein écran) s'ouvre et intercepte les clics tant qu'il
 *  n'est pas fermé. Un test qui part d'un contexte VIERGE (sans le drapeau
 *  `taqinor:welcome:seen:v1` du storageState partagé) le voit donc à chaque
 *  fois : on vérifie qu'il est là, puis on le ferme comme l'utilisateur. */
export async function fermerMomentAccueil(page) {
  const accueil = page.getByRole('dialog', { name: 'Bienvenue chez Taqinor' })
  await expect(accueil).toBeVisible({ timeout: 20_000 })
  await accueil.getByRole('button', { name: 'Commencer' }).click()
  await expect(accueil).toBeHidden()
}

/** Dans un test déjà lancé (ex. le singe qui enchaîne les écrans) : si la
 *  session de CE contexte a été coupée (déconnexion cliquée), on se reconnecte
 *  par l'API avant l'écran suivant. */
export async function assurerSessionPage(page) {
  if (await sessionVivante(page.request)) return
  await connexionApi(page.request)
}

export const STAGE_LABELS = {
  NEW: 'Nouveau',
  CONTACTED: 'Contacté',
  QUOTE_SENT: 'Devis envoyé',
  FOLLOW_UP: 'Relance',
  SIGNED: 'Signé',
  COLD: 'Froid',
}

// Unique-ish suffix so created records never collide across specs/reruns.
let _seq = 0
export function uniq(prefix) {
  _seq += 1
  return `${prefix} ${Date.now().toString(36)}${_seq}`
}

// ── Auth ────────────────────────────────────────────────────────────────────
export async function uiLogin(page, { username, password } = ADMIN) {
  await page.goto('/login')
  await page.getByPlaceholder('Entrez votre identifiant').fill(username)
  await page.locator('input[type="password"]').fill(password)
  await page.getByRole('button', { name: 'Se connecter →' }).click()
}

// ── Leads ─────────────────────────────────────────────────────────────────
// Le nom « + Nouveau lead » est porte par TROIS controles selon l'etat :
// le bouton d'en-tete (desktop), le bouton flottant (mobile) et l'action
// de coach de l'etat vide du kanban (quand la societe n'a AUCUN lead).
// On vise donc explicitement celui de l'en-tete de page : sinon un run qui
// tombe sur une base sans lead resout deux elements et Playwright echoue en
// mode strict — ce qui n'a rien a voir avec ce que le test verifie.
export function boutonNouveauLead(page) {
  // Desktop : le bouton vit dans l'en-tete de page. Mobile : l'en-tete n'en
  // rend AUCUN (LB47) et l'action canonique est le bouton flottant. Les deux
  // ne coexistent jamais, donc `.or()` resout toujours a UN seul element —
  // tout en excluant l'action de coach de l'etat vide du kanban, qui porte le
  // meme nom accessible et faisait echouer le mode strict sur une base sans lead.
  return page.locator('.lp-header-actions')
    .getByRole('button', { name: '+ Nouveau lead' })
    .or(page.locator('.fab-button[aria-label="+ Nouveau lead"]'))
}

export async function gotoLeads(page) {
  await page.goto('/crm/leads')
  await expect(boutonNouveauLead(page)).toBeVisible()
}

// view: 'kanban' | 'liste'
// LB32 — ViewSwitcher rebâti sur ui/Segmented (role="radiogroup" > role="radio",
// pas des <button> nus) : le sélecteur suit le nouveau rôle ARIA réel. Le nom
// accessible pinné ('Vue kanban'/'Vue liste') est inchangé (blueprint §STRATÉGIE
// E2E, mis à jour DANS la tâche qui a touché ce hook).
export async function setLeadsView(page, view) {
  const label = view === 'liste' ? 'Vue liste' : 'Vue kanban'
  await page.getByRole('radio', { name: label }).click()
}

const leadModal = (page) => page.locator('[role="dialog"]').filter({ has: page.locator('.modal-title') })

// Create a lead through the modal. Returns its display name (its nom).
// `facture` (winter bill, MAD) makes the lead "devis-ready" for residential.
export async function createLead(page, { nom, facture, ville = 'Casablanca' } = {}) {
  const name = nom || uniq('Lead E2E')
  await boutonNouveauLead(page).click()
  const modal = leadModal(page)
  await expect(modal.getByRole('heading', { name: 'Nouveau lead' })).toBeVisible()
  // Nom = the required Contact field. Target its stable id (#lf-nom) rather
  // than a CSS class: VX89/VX224 migrated it to the ui-core <Input> (no
  // legacy `form-control` class), but the id is a preserved contract.
  await modal.locator('#lf-nom').fill(name)
  if (facture != null) {
    await modal.getByPlaceholder('ex: 650').fill(String(facture))
  }
  // Ville par défaut (29/08/2026) : le dimensionnement passe TOUT ENTIER par
  // le moteur horaire, qui exige un ancrage de productible — un lead sans
  // ville ni GPS est désormais REFUSÉ par le devis auto (comportement voulu).
  // Les leads réels du tunnel portent toujours ville/GPS ; les fixtures e2e
  // suivent (même règle que les fixtures backend, leçon #86 : ancrer la
  // ville). Passer `ville: null` pour créer volontairement un lead sans ville.
  if (ville) {
    await modal.locator('#lf-ville').fill(ville)
  }
  await modal.getByRole('button', { name: 'Créer le lead' }).click()
  await expect(leadModal(page)).toHaveCount(0)
  return name
}

// Open a lead (works from kanban card or list row) into the edit modal.
export async function openLead(page, name) {
  const card = page.locator('article.kb-card', { hasText: name }).first()
  const row = page.locator('tr.lv-row', { hasText: name }).first()
  // Wait for the lead to render in whichever view is active (avoids racing the
  // post-create refetch), then click its NAME — the row's other cells are
  // inline-editors that stop propagation and would not open the lead.
  await expect(card.or(row)).toBeVisible()
  if (await card.isVisible()) {
    await card.locator('.kb-card-name').click()
  } else {
    await row.locator('.lv-lead-name').click()
  }
  await expect(leadModal(page).locator('.modal-title')).toContainText('Lead —')
}

export async function closeLeadModal(page) {
  await leadModal(page).locator('.modal-close').first().click()
  await expect(leadModal(page)).toHaveCount(0)
}

// ── VX71 — a11y DYNAMIQUE (extension de YHARD8, qui ne scanne que du statique) ─
// Scan axe-core APRÈS une interaction réelle (dialog ouvert, menu ouvert,
// formulaire en erreur, toast) : seuls les scans statiques (build) existaient
// jusqu'ici — un état atteint uniquement via interaction (ex. un dialog monté
// au clic) n'était jamais couvert. `include` restreint le scan à la zone
// pertinente (ex. le dialog ouvert) pour rester rapide et ciblé. Échoue
// SEULEMENT sur `serious`/`critical` (anti-flake : `moderate`/`minor` sont du
// bruit connu, pas un contrat gardé ici).
export async function assertNoSeriousA11yViolations(page, { include } = {}) {
  let builder = new AxeBuilder({ page })
  if (include) builder = builder.include(include)
  const results = await builder.analyze()
  const serious = results.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')
  expect(
    serious,
    serious.map((v) => `${v.id} (${v.impact}) — ${v.nodes.length} nœud(s)`).join('\n'),
  ).toEqual([])
}

// Generate the automatic devis from an already-open lead edit modal and wait for
// the PDF preview to actually render (no broken-file fallback).
export async function generateAutoDevis(page) {
  const modal = leadModal(page)
  // Le libellé accessible est « Devis automatique » : l'éclair est une icône
  // <Zap aria-hidden> (VX), pas un emoji dans le texte — ne pas le chercher.
  const autoBtn = modal.getByRole('button', { name: 'Devis automatique' })
  await expect(autoBtn).toBeEnabled()
  await autoBtn.click()
  // The inline panel renders the PDF on <canvas> via pdf.js.
  await expect(page.locator('.ldp-pdf-area canvas').first()).toBeVisible({ timeout: 45_000 })
  await expect(page.locator('.ldp-fallback')).toHaveCount(0)
}

// ── AOF187 — AO (Appel d'offres) ────────────────────────────────────────────
// Le module `ao` est sorti du MVP solaire (Groupe SOLMVP) : coquillage backend
// + retrait du frontend (SOLMVP15/32/40). Tous les helpers `data-ao-*` de ce
// bloc (routes, ouverture d'affaire démo, onglets de fiche, outils d'atelier,
// verdict, variantes, pièces, contrôles) n'avaient plus aucun appelant depuis
// que les specs `ao-*.spec.js` sont parties avec eux (SOLMVP30b) — retirés
// avec les specs (SOLMVP42, 2026-09-21). La recette de retour d'un module
// (docs/parked-modules.md) republie ces helpers en même temps que l'écran.

// ── PACT8 — Fumée des écrans : les routes LUES, jamais tenues à la main ─────
//
// Constat du 03/08/2026 : `AO_ROUTES.dashboard = '/ao'` est DÉCLARÉ plus haut
// dans ce fichier et AUCUNE spec ne le visite — l'écran qui a planté en
// production n'est ouvert par aucun test, nulle part. Une liste d'écrans tenue
// à la main périme le jour même où elle est écrite.
//
// Ces fonctions lisent donc la SOURCE DE VÉRITÉ : les `routes:` des
// `features/<app>/module.config.jsx`, exactement les déclarations que
// `router/moduleRoutes.jsx` monte dans l'application. Ajouter un écran l'ajoute
// à la fumée ; en supprimer un l'en retire. Rien à maintenir.
//
// Lecture par expression régulière et non par `import` : importer un
// `module.config.jsx` tirerait tout l'arbre React (imports paresseux compris)
// dans le processus Playwright. `path:` n'apparaît QUE dans les entrées de
// route (la navigation utilise `to:`), donc l'extraction est sans ambiguïté.

const DOSSIER_FEATURES = fileURLToPath(new URL('../src/features/', import.meta.url))

// `path: '/x/y'` — guillemets simples uniquement (convention du dépôt, vérifiée).
const MOTIF_ROUTE = /path:\s*'([^']+)'/g

// Un segment `:param` ne peut pas être visité à l'aveugle : un identifiant
// inventé ouvrirait un écran « introuvable » légitime, donc un rouge sur du
// code CORRECT. Ces routes restent couvertes par les specs de parcours
// (devis, ao-parcours, leads…), qui les ouvrent avec de VRAIES données.
export const estRouteParametree = (chemin) => chemin.includes(':')

// [{ module: 'stock', chemin: '/stock/mouvements' }, …] — trié, dédupliqué.
export function routesDesModules({ inclureParametrees = false } = {}) {
  const routes = []
  const vues = new Set()
  for (const entree of readdirSync(DOSSIER_FEATURES, { withFileTypes: true })) {
    if (!entree.isDirectory()) continue
    const config = join(DOSSIER_FEATURES, entree.name, 'module.config.jsx')
    if (!existsSync(config)) continue
    for (const trouve of readFileSync(config, 'utf8').matchAll(MOTIF_ROUTE)) {
      const chemin = trouve[1]
      if (!chemin.startsWith('/')) continue
      if (!inclureParametrees && estRouteParametree(chemin)) continue
      if (vues.has(chemin)) continue
      vues.add(chemin)
      routes.push({ module: entree.name, chemin })
    }
  }
  return routes.sort((a, b) => (a.module === b.module
    ? a.chemin.localeCompare(b.chemin)
    : a.module.localeCompare(b.module)))
}

// Regroupe par module : un test Playwright par module donne un rouge qui NOMME
// l'application fautive, et un budget de temps par test plutôt qu'un unique
// test de 300 navigations qui expirerait avant de rien dire.
export function routesParModule(options) {
  const parModule = new Map()
  for (const { module, chemin } of routesDesModules(options)) {
    if (!parModule.has(module)) parModule.set(module, [])
    parModule.get(module).push(chemin)
  }
  return parModule
}

// Titre de `components/RouteErrorBoundary.jsx` — l'écran de récupération FR
// affiché quand une page plante au rendu (`.map is not a function`, « objects
// are not valid as a React child »…). Sa présence EST le défaut.
export const TITRE_ECRAN_ERREUR = 'Une erreur est survenue'

// ── Parcours de lead pro / agricole (AGR423, CIQ424, CIQ521) ────────────────
// Briques PARTAGÉES des specs « aller-retour en direct » : aucune ne simule le
// réseau, toutes parlent à la vraie pile locale (`seed_demo`).
export const API_DJANGO = '/api/django'

/** Corps JSON d'une réponse API, ou un échec qui NOMME l'appel et le statut. */
export async function lireJson(res, quoi) {
  expect(res.ok(), `${quoi} → HTTP ${res.status()} ${await res.text()}`).toBeTruthy()
  return res.json()
}

/** Liste d'une réponse DRF paginée ou non. */
export const listeDe = (corps) => (Array.isArray(corps) ? corps : (corps?.results || []))

let _chiffresSeq = 0
const chiffres = (n) => { _chiffresSeq += 1; return String(Date.now() + _chiffresSeq).slice(-n) }
/** Mobile marocain E.164 UNIQUE (la cadence ne démarre pas sur un doublon). */
export const telephoneMobileUnique = () => `+2126${chiffres(8)}`
/** Fixe marocain E.164 UNIQUE (05 2x xx xx xx). */
export const telephoneFixeUnique = () => `+21252${chiffres(7)}`

/** `AAAA-MM-JJ` dans `n` jours. */
export function isoDansJours(n) {
  const d = new Date()
  d.setDate(d.getDate() + n)
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const j = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${j}`
}

// Secret du récepteur de leads du site (`WEBSITE_LEAD_WEBHOOK_SECRET`, fermé
// tant qu'il est vide). La pile e2e doit le poser ET exporter le même
// `E2E_WEBHOOK_SECRET` à Playwright ; sans cela le récepteur répond 401 et les
// specs qui en dépendent se SAUTENT en le disant (jamais un faux vert).
export const SECRET_WEBHOOK_E2E = process.env.E2E_WEBHOOK_SECRET || 'e2e-webhook-secret'

/** Poste un payload du site sur le vrai webhook. Renvoie `{ status, corps }`. */
export async function posterWebhookSite(request, payload) {
  const res = await request.post(`${API_DJANGO}/crm/webhooks/website-leads/`, {
    data: { idempotencyKey: globalThis.crypto.randomUUID(), consent: true, ...payload },
    headers: { 'X-Webhook-Secret': SECRET_WEBHOOK_E2E },
  })
  let corps = null
  try { corps = await res.json() } catch { /* corps non JSON */ }
  return { status: res.status(), corps }
}

/** Nombre de pages d'un PDF lu par pdfjs. Le moteur sert du PDF 1.7 à flux
 *  d'objets compressés (`/Type /Page` n'apparaît plus en clair) : compter les
 *  objets à la regex rendait 0 (nocturne 37585800165, CIQ665). */
export async function nombrePagesPdf(octets) {
  const pdfjs = await import('pdfjs-dist/legacy/build/pdf.mjs')
  const doc = await pdfjs.getDocument({
    data: new Uint8Array(octets), useSystemFonts: true, disableFontFace: true,
  }).promise
  return doc.numPages
}

/** Ouvre la fiche chantier sur l'onglet « Jalons & gates » : depuis APX25 la
 *  fiche est en 6 onglets et le parcours, la fiche de recette (CH3/AGR613) et
 *  le pack de remise ne vivent que dans cet onglet (l'« Aperçu » s'ouvre par
 *  défaut). */
export async function ouvrirJalonsChantier(page, chantierId) {
  await page.goto(`/chantiers?id=${chantierId}`)
  await page.getByRole('tab', { name: /Jalons/ }).click({ timeout: 30_000 })
  await expect(page.getByTestId('ch6-recette')).toBeVisible({ timeout: 30_000 })
}

/** Texte brut d'un PDF (pdfjs-dist, déjà une dépendance du frontend). */
export async function textePdf(octets) {
  const pdfjs = await import('pdfjs-dist/legacy/build/pdf.mjs')
  const doc = await pdfjs.getDocument({
    data: new Uint8Array(octets), useSystemFonts: true, disableFontFace: true,
  }).promise
  let texte = ''
  for (let i = 1; i <= doc.numPages; i += 1) {
    const page = await doc.getPage(i)
    const contenu = await page.getTextContent()
    texte += `${contenu.items.map((it) => it.str).join(' ')}\n`
  }
  return texte
}

// Mois de consommation d'un site commercial (kWh), profil saisonnier plausible.
export const KWH_COMMERCIAL = [9800, 9200, 10100, 10800, 12500, 14800, 17200, 17600, 14900, 12100, 10200, 9900]

/** Choisit le MARCHÉ du générateur. QX23 : dès que des lignes existent (la
 *  table par défaut du simulateur en pose une fois le stock chargé), changer
 *  de marché demande confirmation (« Changer de marché ? ») — on la confirme
 *  quand elle s'ouvre, puis on exige le marché coché. */
export async function choisirMarche(page, nom) {
  const radio = page.getByRole('radio', { name: nom })
  await radio.click()
  const confirmation = page.getByRole('alertdialog', { name: 'Changer de marché ?' })
  await expect.poll(async () => (await confirmation.isVisible()) || (await radio.isChecked()))
    .toBeTruthy()
  if (await confirmation.isVisible()) {
    await confirmation.getByRole('button', { name: 'Changer de marché' }).click()
  }
  await expect(radio).toBeChecked()
}

/** Le PROFIL DÉCLARÉ minimal que le moteur C&I exige (D-CIQ-2, CIQ131 :
 *  « profil déclaré exigé », aucun archétype supposé ; CIQ222 : « aucun prix
 *  plat supposé » sans contrat) : jours ouverts lundi→samedi, plage des jours
 *  ouvrés 8 h → 18 h, contrat BT patenté (grille ONEE officielle) — en MT le
 *  contrat est le Tarif Général, reconnu par la tension. Sans ces saisies
 *  l'aperçu serveur rend `taille: null` + une alerte BLOQUANTE
 *  (`profil_declare_exige`, puis `jours_ouverts_non_declares`, `tarif_omis`)
 *  — constaté au nocturne CAD177.
 *  Et une TAILLE SAISIE (D-QJR5-13, souveraine) : le catalogue `seed_catalogue`
 *  porte des articles C&I « prix à renseigner » (D-CIQ-12, jamais chiffrés
 *  par la démo), sur lesquels le BALAYAGE s'arrête (`prix_manquants`,
 *  bloquant) ; la taille saisie est calculée telle quelle, ses lignes
 *  chiffrées posées par Auto-remplir (même chemin que CIQ127, 20 kWc). */
export async function declarerProfilCi(page, { contrat = 'bt_patente', tailleKwc = '20' } = {}) {
  for (let i = 0; i < 6; i += 1) await page.getByTestId(`gen-ci-jour-${i}`).check()
  await page.getByTestId('gen-ci-plage-ouvre-debut').fill('8')
  await page.getByTestId('gen-ci-plage-ouvre-fin').fill('18')
  if (contrat) await page.locator('#gen-tarif-contrat').selectOption(contrat)
  if (tailleKwc) await page.locator('#gen-ci-taille').fill(tailleKwc)
}

/** Crée un devis COMMERCIAL par le vrai générateur, depuis un lead : profil
 *  déclaré (12 mois, calendrier, contrat) → Auto-remplir (aperçu serveur) →
 *  « Créer le devis ». Le client est résolu côté serveur depuis le lead.
 *  Renvoie l'id du devis. */
export async function creerDevisCommercialDepuisLead(page, leadId) {
  await page.goto(`/ventes/devis/nouveau?lead=${leadId}`)
  await expect(page.getByRole('heading', { name: 'Générateur de Devis Solaire' }))
    .toBeVisible({ timeout: 30_000 })
  await choisirMarche(page, /Commercial/)
  await expect(page.getByTestId('ci-profil')).toBeVisible()
  for (let i = 0; i < 12; i += 1) await page.locator(`#gen-ci-kwh-${i}`).fill(String(KWH_COMMERCIAL[i]))
  await declarerProfilCi(page)
  await expect(page.getByTestId('ci-taille-retenue')).toBeVisible({ timeout: 45_000 })
  const auto = page.waitForResponse((r) => r.request().method() === 'POST'
    && /\/ventes\/etude-ci\/preview\/$/.test(new URL(r.url()).pathname))
  await page.getByTestId('btn-auto-remplir').click()
  await auto
  const creation = page.waitForResponse((r) => r.request().method() === 'POST'
    && /\/ventes\/devis\/atomic\/$/.test(new URL(r.url()).pathname) && r.status() < 300)
  await page.locator('#gen-form').getByRole('button', { name: /Créer le devis/ }).click()
  const cree = await (await creation).json()
  const id = cree.id ?? cree.devis?.id
  expect(id, 'identifiant du devis créé').toBeTruthy()
  return id
}

// ── Parcours « site professionnel » (CIQ650, CIQ665) ────────────────────────
// PNG 1×1 valide : une vraie photo de slot (magic-bytes contrôlés par le serveur).
export const PNG_1PX = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg==',
  'base64')

// Mois de consommation d'un site industriel (kWh) : le profil commercial ×12.
export const KWH_INDUSTRIEL = KWH_COMMERCIAL.map((v) => v * 12)

/** Lit les mesures d'un exemple du contrat PARTAGÉ `visite_terrain.json` (jamais
 *  un jeu de valeurs écrit à la main : le contrat est la source). Copie neuve. */
export function mesuresContratVisite(cleExemple) {
  const url = new URL(
    '../../backend/django_core/apps/visites/contract_samples/visite_terrain.json', import.meta.url)
  const contrat = JSON.parse(readFileSync(fileURLToPath(url), 'utf-8'))
  expect(contrat[cleExemple]?.mesures, `exemple « ${cleExemple} » du contrat visite_terrain`).toBeTruthy()
  return JSON.parse(JSON.stringify(contrat[cleExemple].mesures))
}

/** Exécute du Python dans `manage.py shell` : `E2E_DJANGO_EXEC` s'il est posé, sinon
 *  le conteneur `django_core` du compose local, sinon le Django de l'hôte (job e2e
 *  de la CI : `backend/django_core`). Une ligne de code ; échec = erreur nommée. */
export function executerDansDjango(code) {
  const surmesure = process.env.E2E_DJANGO_EXEC
  const tentatives = []
  if (surmesure) {
    const [cmd, ...args] = surmesure.split(' ')
    tentatives.push({ cmd, args: [...args, 'python'], cwd: undefined })
  } else {
    tentatives.push({ cmd: 'docker', args: ['compose', 'exec', '-T', 'django_core', 'python'], cwd: undefined })
    tentatives.push({
      cmd: process.platform === 'win32' ? 'python' : 'python3', args: [],
      cwd: fileURLToPath(new URL('../../backend/django_core', import.meta.url)),
    })
  }
  const echecs = []
  for (const { cmd, args, cwd } of tentatives) {
    try {
      return execFileSync(cmd, [...args, 'manage.py', 'shell', '-c', code],
        { stdio: 'pipe', cwd, timeout: 120_000 }).toString()
    } catch (err) {
      echecs.push(`${cmd}: ${String(err.stderr || err.message).slice(0, 300)}`)
    }
  }
  throw new Error(`manage.py shell inaccessible (E2E_DJANGO_EXEC) — ${echecs.join(' | ')}`)
}

/** Planifie une visite technique depuis la fiche du lead, par la vraie fenêtre.
 *  Renvoie le texte de l'avertissement « visite sans devis » affiché avant. */
export async function planifierVisiteDepuisLead(page, leadId, jours = 3) {
  await page.goto(`/crm/leads/${leadId}`)
  const tete = page.locator('section.lw-section[data-nav-id="visite"] .lw-section-head')
  await expect(tete, 'section « visite » de la fiche').toBeVisible({ timeout: 30_000 })
  if ((await tete.getAttribute('aria-expanded')) === 'false') await tete.click()
  const avertissement = page.getByTestId('visite-sans-devis')
  await expect(avertissement).toBeVisible({ timeout: 30_000 })
  const texte = await avertissement.textContent()
  await page.getByRole('button', { name: 'Planifier la visite technique' }).click()
  await page.locator('#pv-date-prevue').fill(isoDansJours(jours))
  await page.getByRole('button', { name: 'Planifier la visite', exact: true }).click()
  await expect(page.getByTestId('section-visite-row').first()).toBeVisible({ timeout: 30_000 })
  return texte || ''
}

/** Saisit les mesures d'une visite `ci` (comptage d'abord : le niveau constaté
 *  décide des catégories MT servies), puis une vraie photo dans chaque slot requis.
 *  Renvoie la visite relue par le serveur (complétude comprise). */
export async function remplirVisiteCi(request, visiteId, mesures) {
  const ordre = Object.keys(mesures).sort((a, b) => (b === 'comptage') - (a === 'comptage'))
  for (const categorie of ordre) {
    const valeurs = mesures[categorie]
    if (!valeurs || !Object.keys(valeurs).length) continue
    await lireJson(await request.patch(`${API_DJANGO}/visites/visites/${visiteId}/mesures/`,
      { data: { categorie, valeurs } }), `mesures « ${categorie} »`)
  }
  const visite = await lireJson(
    await request.get(`${API_DJANGO}/visites/visites/${visiteId}/`), 'visite')
  for (const bloc of visite.checklist) {
    for (const slot of bloc.slots.filter((s) => s.requis)) {
      for (let i = 0; i < (slot.min_photos || 1); i += 1) {
        await lireJson(await request.post(`${API_DJANGO}/visites/visites/${visiteId}/photos/`, {
          multipart: {
            slot_code: slot.code,
            fichier: { name: `${slot.code}-${i}.png`, mimeType: 'image/png', buffer: PNG_1PX },
          },
        }), `photo « ${slot.code} »`)
      }
    }
  }
  return lireJson(await request.get(`${API_DJANGO}/visites/visites/${visiteId}/`), 'visite complétée')
}

/** Crée un devis INDUSTRIEL par le vrai générateur depuis un lead (profil déclaré
 *  12 mois, tension MT) → Auto-remplir (aperçu serveur) → « Créer le devis ». */
export async function creerDevisIndustrielDepuisLead(page, leadId, { tension = 'mt' } = {}) {
  await page.goto(`/ventes/devis/nouveau?lead=${leadId}`)
  await expect(page.getByRole('heading', { name: 'Générateur de Devis Solaire' }))
    .toBeVisible({ timeout: 30_000 })
  await choisirMarche(page, /Industriel/)
  await expect(page.getByTestId('ci-profil')).toBeVisible()
  await expect(page.getByTestId('ci-industriel-mt')).toBeVisible()
  for (let i = 0; i < 12; i += 1) await page.locator(`#gen-ci-kwh-${i}`).fill(String(KWH_INDUSTRIEL[i]))
  await page.locator('#gen-ci-tension').selectOption(tension)
  // Calendrier + taille saisie (voir declarerProfilCi) ; en MT le contrat est
  // le Tarif Général, reconnu par la tension.
  await declarerProfilCi(page, { contrat: tension === 'mt' ? null : 'bt_patente' })
  await expect(page.getByTestId('ci-taille-retenue')).toBeVisible({ timeout: 45_000 })
  const auto = page.waitForResponse((r) => r.request().method() === 'POST'
    && /\/ventes\/etude-ci\/preview\/$/.test(new URL(r.url()).pathname))
  await page.getByTestId('btn-auto-remplir').click()
  await auto
  const creation = page.waitForResponse((r) => r.request().method() === 'POST'
    && /\/ventes\/devis\/atomic\/$/.test(new URL(r.url()).pathname) && r.status() < 300)
  await page.locator('#gen-form').getByRole('button', { name: /Créer le devis/ }).click()
  const cree = await (await creation).json()
  const id = cree.id ?? cree.devis?.id
  expect(id, 'identifiant du devis créé').toBeTruthy()
  return id
}

/** Ajoute les trois documents de sécurité (plan de prévention, analyse de risques,
 *  permis de travail en hauteur) AVEC une révision : aucune API ne les expose (le
 *  module QHSE est parqué), le gate de CIQ623 les lit en base. */
export function ajouterDocumentsHse(chantierId) {
  executerDansDjango(
    'import datetime; from apps.installations.models import Installation, DocumentProjet, RevisionDocument; '
    + `i = Installation.objects.get(pk=${Number(chantierId)}); `
    + '[RevisionDocument.objects.create(company=i.company, indice="A", date_revision=datetime.date.today(), '
    + 'document=DocumentProjet.objects.create(company=i.company, installation=i, type_doc=t, titre="E2E " + t)) '
    + 'for t in ("plan_prevention", "analyse_risques", "permis_travail_hauteur")]')
}

/** Ouvre (ou retrouve) le compte portail du client, lui pose un mot de passe connu et
 *  renvoie un contexte API CONNECTÉ en client (à `dispose()` par l'appelant). */
export async function contextePortailClient(playwright, request, baseURL, clientId, motDePasse) {
  const existants = listeDe(await lireJson(await request.get(`${API_DJANGO}/portail/comptes-portail/`),
    'comptes portail'))
  const compte = existants.find((c) => c.client === clientId)
    ?? await lireJson(await request.post(`${API_DJANGO}/portail/comptes-portail/`,
      { data: { client: clientId } }), 'compte portail du client')
  const prov = await lireJson(await request.post(
    `${API_DJANGO}/portail/comptes-portail/${compte.id}/provisionner-acces/`, { data: {} }), 'accès portail')
  executerDansDjango(
    'from django.contrib.auth import get_user_model as g; '
    + `u = g().objects.get(username=${JSON.stringify(prov.username)}); `
    + `u.set_password(${JSON.stringify(motDePasse)}); u.save()`)
  const portail = await playwright.request.newContext({ baseURL })
  const login = await portail.post(`${API_DJANGO}/token/`,
    { data: { username: prov.username, password: motDePasse } })
  expect(login.status(), 'connexion du client portail').toBe(200)
  return portail
}
