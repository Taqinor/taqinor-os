// Shared helpers + constants for the Taqinor OS E2E suite.
// Selectors mirror the REAL components (no data-testids exist in the app, so we
// lean on visible text, placeholders, stable CSS classes and ARIA roles).
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
export async function gotoLeads(page) {
  await page.goto('/crm/leads')
  await expect(page.getByRole('button', { name: '+ Nouveau lead' })).toBeVisible()
}

// view: 'kanban' | 'liste'
export async function setLeadsView(page, view) {
  const label = view === 'liste' ? 'Vue liste' : 'Vue kanban'
  await page.getByRole('button', { name: label }).click()
}

const leadModal = (page) => page.locator('[role="dialog"]').filter({ has: page.locator('.modal-title') })

// Create a lead through the modal. Returns its display name (its nom).
// `facture` (winter bill, MAD) makes the lead "devis-ready" for residential.
export async function createLead(page, { nom, facture } = {}) {
  const name = nom || uniq('Lead E2E')
  await page.getByRole('button', { name: '+ Nouveau lead' }).click()
  const modal = leadModal(page)
  await expect(modal.getByRole('heading', { name: 'Nouveau lead' })).toBeVisible()
  // Nom = the first .form-control input (Contact section, required field).
  await modal.locator('input.form-control').first().fill(name)
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
