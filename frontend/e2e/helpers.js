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
