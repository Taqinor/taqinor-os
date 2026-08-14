// Shared helpers + constants for the Taqinor OS E2E suite.
// Selectors mirror the REAL components (no data-testids exist in the app, so we
// lean on visible text, placeholders, stable CSS classes and ARIA roles).
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

// Seeded by `manage.py seed_demo` (company "TAQINOR Démo"). Throwaway only.
export const ADMIN = { username: 'demo_admin', password: 'Demo@2026!' }
export const SECOND_USER = 'demo_resp'

export const AUTH_FILE = 'e2e/.auth/admin.json'

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
export async function createLead(page, { nom, facture } = {}) {
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
// Selectors lean on the STABLE `data-ao-*` hook contract frozen in AOF8
// (frontend/src/features/ao/E2E_HOOKS.md : -canvas, -outil, -verdict, -compte,
// -tiroir, -variante, -piece, -controle, -repere, -provenance, -etat) rather
// than on route/label guesses that will drift as the ao-toiture/ao-calepinage/
// ao-dossier screens land. Deliberately avoids the two flaky causes already
// catalogued in this repo: no date-of-day math (a "today" comparison flakes at
// midnight) and no accessible name derived from an icon/emoji (an icon swap
// silently breaks a `getByRole` name match) — every lookup here is either a
// `data-ao-*` attribute or a plain, stable FR string.
export const AO_ROUTES = {
  dashboard: '/ao',
  affaires: '/ao/affaires',
  toitures: '/ao/toitures',
  calepinages: '/ao/calepinages',
  dossiers: '/ao/dossiers',
  bibliotheque: '/ao/bibliotheque',
}

// Nom stable planté par `seed_ao_demo` (AOF186, rejouable, construit DEPUIS les
// goldens FRDISI d'AOF183) — on ne matche qu'une SOUS-CHAÎNE pour tolérer un
// préfixe/suffixe de référence sans casser le spec si la fabrique de référence
// change son format exact.
export const AO_DEMO_MARKER = 'FRDISI'

export async function gotoAo(page, path) {
  await page.goto(path)
  await expect(page.locator('.header-title')).toBeVisible()
}

// Ouvre l'affaire de démonstration plantée par `seed_ao_demo` depuis la liste
// des affaires (recherche par sous-chaîne stable, jamais par position/index).
//
// `visible=true` n'est PAS de la ceinture-bretelles : le `DataTable` (M154)
// monte DEUX arbres pour les mêmes lignes — la table bureau
// (`hidden … dt-desktop:block`, donc `display:none` sous 768 px) PUIS, plus
// bas dans le DOM, les cartes mobiles (`data-dt-cards`, `dt-desktop:hidden`).
// `getByText(...)` matche indifféremment les deux (la visibilité n'est
// évaluée qu'au moment de l'action), donc `.first()` désignait, en viewport
// téléphone, la cellule MASQUÉE de la table bureau : un clic qui ne devient
// jamais actionnable et expire au bout du timeout, sans jamais dire pourquoi.
// On ne retient donc que l'occurrence réellement PEINTE — un seul et même
// helper reste juste sur les deux viewports.
export async function openAoDemoAffaire(page) {
  await gotoAo(page, AO_ROUTES.affaires)
  const affaire = page
    .getByText(AO_DEMO_MARKER, { exact: false })
    .locator('visible=true')
    .first()
  // Assertion AVANT le clic : si le seed n'a pas tourné (ou si la liste
  // n'imprime plus la référence acheteur), le rouge NOMME la cause au lieu de
  // se présenter comme un « locator.click a expiré » muet.
  await expect(
    affaire,
    `l'affaire de démonstration « ${AO_DEMO_MARKER} » est listée sur ${AO_ROUTES.affaires}`
    + ' (manage.py seed_ao_demo --confirmer)',
  ).toBeVisible()
  await affaire.click()
}

// ── Onglets de la FICHE AFFAIRE — correction du 14/08/2026 ──────────────────
//
// LE DÉFAUT RÉPARÉ ICI. Les sections d'une affaire (Toitures & relevés,
// Calepinages, Bordereau, Dossier, Variantes…) ne sont pas des LIENS :
// `features/ao/AffaireDetail.jsx` les passe en `tabs` à `RecordShell` →
// `ui/module/DetailShell.jsx` → `ui/Tabs.jsx`, qui monte des
// `@radix-ui/react-tabs` `Trigger` — donc `role="tab"`, jamais `role="link"`.
// Un `getByRole('link', { name: /Bordereau/ })` ne pouvait pas les atteindre.
//
// PIRE QUE LE ROUGE : sur le viewport bureau, ce locator résolvait quand même
// pour trois de ces noms — vers l'entrée de NAVIGATION GLOBALE du module
// (`features/ao/module.config.jsx`) : « Toitures & relevés » → `/ao/toitures`,
// « Calepinages » → `/ao/calepinages`, « Dossiers » → `/ao/dossiers`. Les specs
// quittaient donc silencieusement la fiche et balayaient un AUTRE écran tout en
// se déclarant verts. On vise le rôle RÉEL, et on prouve qu'on est resté sur la
// fiche : un onglet change de panneau, jamais d'écran.
//
// `nomOnglet` est le libellé EXACT déclaré dans `AffaireDetail.jsx` — pas une
// sous-chaîne : un onglet renommé doit produire un rouge qui NOMME la cause,
// pas un locator qui glisse vers un voisin.
export async function ouvrirOngletAffaire(page, nomOnglet) {
  const SUR_LA_FICHE = /\/ao\/affaires\/\d+/
  await expect(
    page,
    'un onglet de fiche affaire ne s’ouvre que depuis /ao/affaires/<id>',
  ).toHaveURL(SUR_LA_FICHE)

  const onglet = page.getByRole('tab', { name: nomOnglet })
  await expect(
    onglet,
    `l'onglet « ${nomOnglet} » est rendu par la fiche affaire (AffaireDetail.jsx → RecordShell)`,
  ).toBeVisible()
  await onglet.click()
  await expect(
    onglet,
    `l'onglet « ${nomOnglet} » devient l'onglet actif`,
  ).toHaveAttribute('aria-selected', 'true')

  // La garde qui ferme définitivement la porte au faux vert d'origine.
  await expect(
    page,
    `ouvrir l'onglet « ${nomOnglet} » ne doit PAS quitter la fiche affaire`,
  ).toHaveURL(SUR_LA_FICHE)

  // Panneaux montés en `lazy` + `Suspense`. `data-ao-panneau-differe`
  // (E2E_HOOKS.md §2.14) EST le repère prévu pour ça : il doit céder la place
  // au contenu réel — s'il persiste, le panneau ne se monte pas.
  await expect(
    page.locator('[data-ao-panneau-differe]'),
    `le panneau de l'onglet « ${nomOnglet} » a fini de se charger`,
  ).toHaveCount(0)

  // Radix ne monte QUE le panneau actif : ce locator en désigne exactement un.
  return page.getByRole('tabpanel')
}

// Rejoint l'atelier « Toitures & relevés » DEPUIS LE POUCE (paradigme ODY6 :
// sur mobile, la nav de l'app active EST la barre basse).
//
// Pourquoi pas un `getByRole('link', { name: /Toiture/ })` global : sous
// 768 px la coquille rend DEUX destinations portant ce nom accessible — le
// lien de la Sidebar (tiroir hors-champ par `transform: translateX(-105%)`,
// donc toujours présent dans l'arbre d'accessibilité) ET l'onglet de
// `nav.bottom-tabbar`. Un locator global viole le mode strict de Playwright ;
// sur bureau il n'en voyait qu'un (`.bottom-tabbar { display: none }`), d'où
// une ambiguïté qui n'apparaît QUE sur les projets mobiles.
//
// L'onglet direct existe toujours : `BottomTabBar.splitAppTabs` garde les 3
// premières sections de l'app en accès direct dès qu'elle en a plus de 4, et
// « Toitures & relevés » est la 3e entrée de nav du module AO.
export async function ouvrirAoToituresMobile(page) {
  const tabbar = page.locator('nav.bottom-tabbar')
  await expect(tabbar, "la barre d'onglets de l'app AO est rendue au pouce").toBeVisible()
  await tabbar.getByRole('link', { name: /Toiture/ }).click()
  await expect(page).toHaveURL(/\/ao\/toitures/)
}

// Sélectionne un outil de l'atelier toiture/calepinage (`data-ao-outil="…"`).
export async function selectAoOutil(page, outil) {
  await page.locator(`[data-ao-outil="${outil}"]`).click()
}

// Pose un point sur le canvas de traçage/relevé (`data-ao-canvas`) à des
// coordonnées RELATIVES à sa boîte — jamais des pixels d'écran absolus.
export async function clickAoCanvas(page, { x, y }) {
  await page.locator('[data-ao-canvas]').click({ position: { x, y } })
}

// Ouvre un tiroir de paramètres nommé (`data-ao-tiroir="…"`).
export async function openAoTiroir(page, nom) {
  await page.locator(`[data-ao-tiroir="${nom}"]`).click()
}

// Attend le verdict du calepinage — un recalcul SERVEUR, jamais un chiffre
// estimé côté client, donc potentiellement asynchrone — et renvoie son état
// (`data-ao-etat` : 'ok' | 'avertissement' | 'bloquant').
export async function waitAoVerdict(page) {
  const verdict = page.locator('[data-ao-verdict]')
  await expect(verdict).toBeVisible({ timeout: 30_000 })
  return verdict.getAttribute('data-ao-etat')
}

// Cartes de variante (`data-ao-variante="…"` : ex. 'retenue' | 'alternative').
export function aoVariante(page, cle) {
  return page.locator(`[data-ao-variante="${cle}"]`)
}

// Lignes de pièce du dossier (`data-ao-piece`, état `data-ao-etat`).
export function aoPiece(page, cle) {
  return page.locator(`[data-ao-piece="${cle}"]`)
}

// Premier contrôle de cohérence à l'état BLOQUANT dans le dossier
// (`data-ao-controle[data-ao-etat="bloquant"]`).
export function firstAoControleBloquant(page) {
  return page.locator('[data-ao-controle][data-ao-etat="bloquant"]').first()
}

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
