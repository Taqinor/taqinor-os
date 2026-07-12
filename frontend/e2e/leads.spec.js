// E3 lead lifecycle · E5 inline bill editing · E6 reassignment · E7 stage moves.
import { test, expect } from '@playwright/test'
import {
  gotoLeads, setLeadsView, createLead, openLead, closeLeadModal,
  generateAutoDevis, uniq, ADMIN, SECOND_USER,
  assertNoSeriousA11yViolations,
} from './helpers'

const modalXl = (page) => page.locator('[role="dialog"]').filter({ has: page.locator('.modal-title') })

test('E3: create a lead, see it in list + kanban, open it', async ({ page }) => {
  await gotoLeads(page)
  const name = await createLead(page, { nom: uniq('Lifecycle') })

  await setLeadsView(page, 'kanban')
  await expect(page.locator('article.kb-card', { hasText: name })).toBeVisible()

  await setLeadsView(page, 'liste')
  await expect(page.locator('tr.lv-row', { hasText: name })).toBeVisible()

  await openLead(page, name)
  await expect(modalXl(page).locator('.modal-title')).toContainText(name)
  await closeLeadModal(page)
})

test('E5: inline bill editing on a lead saves and reflects', async ({ page }) => {
  await gotoLeads(page)
  const name = await createLead(page, { nom: uniq('Bill') }) // no bill yet
  await openLead(page, name)
  const modal = modalXl(page)

  // The subbar shows "+ Renseigner la facture" until a bill exists.
  await modal.locator('.lead-bill-view').click()
  const billInput = modal.locator('input.lead-bill-input').first()
  await billInput.fill('800')
  // The input is controlled by React state read by the save handler — make sure
  // that state has committed before saving (else it persists an empty bill).
  await expect(billInput).toHaveValue('800')
  await modal.getByRole('button', { name: 'Enregistrer' }).click()

  // Saved value is shown back, formatted (e.g. "800 MAD").
  await expect(modal.locator('.lead-bill-view')).toContainText('800')
  await closeLeadModal(page)
})

test('E6: reassign a lead from a kanban card and from the lead view', async ({ page }) => {
  await gotoLeads(page)
  await setLeadsView(page, 'kanban')
  const name = await createLead(page, { nom: uniq('Reassign') })

  // ── from the kanban card (immediate PATCH) ──
  const card = page.locator('article.kb-card', { hasText: name })
  await expect(card).toBeVisible()
  await card.locator('.ap-trigger').click()
  await page.locator('.ap-menu .ap-item', { hasText: SECOND_USER }).click()
  await expect(card.locator('.ap-trigger')).toHaveAttribute('title', new RegExp(SECOND_USER))

  // ── from the lead view (picker + save) ──
  await openLead(page, name)
  const modal = modalXl(page)
  // VX71 — scan axe DYNAMIQUE : le lead EN ÉDITION (dialog ouvert, picker
  // assignee monté) est un état qu'un scan statique de build ne voit jamais.
  await assertNoSeriousA11yViolations(page, { include: '[role="dialog"]' })
  const respGroup = modal.locator('.form-group', { hasText: 'Responsable' })
  await respGroup.locator('.ap-trigger').click()
  await page.locator('.ap-menu .ap-item', { hasText: ADMIN.username }).click()
  await modal.getByRole('button', { name: 'Mettre à jour' }).click()
  await expect(modalXl(page)).toHaveCount(0)

  await openLead(page, name)
  await expect(
    modalXl(page).locator('.form-group', { hasText: 'Responsable' }).locator('.ap-name'),
  ).toContainText(ADMIN.username)
  await closeLeadModal(page)
})

test('E7: move a lead between stages, including into Signé', async ({ page }) => {
  await gotoLeads(page)
  // Needs a devis so the Signé dialog can record the accepted quote.
  const name = await createLead(page, { nom: uniq('Stage'), facture: 950 })
  await openLead(page, name)
  await generateAutoDevis(page)
  await page.locator('.ldp-panel .modal-close').click()
  await closeLeadModal(page)

  // Stage moves happen inline in the list (the canonical control besides kanban).
  await setLeadsView(page, 'liste')
  const row = page.locator('tr.lv-row', { hasText: name })

  // NEW → CONTACTED (a plain transition).
  await row.locator('.ie-cell').filter({ hasText: 'Nouveau' }).click()
  await page.locator('select.ie-input').selectOption({ label: 'Contacté' })
  await page.keyboard.press('Tab') // blur → commit
  await expect(row).toContainText('Contacté')

  // → Signé opens the acceptance dialog (A2) instead of moving directly.
  await row.locator('.ie-cell').filter({ hasText: 'Contacté' }).click()
  await page.locator('select.ie-input').selectOption({ label: 'Signé' })
  await page.keyboard.press('Tab')

  const dialog = page.locator('.modal', { hasText: 'Passer en « Signé »' })
  await expect(dialog).toBeVisible()
  const devisSelect = dialog.locator('#sd-devis')
  const values = await devisSelect
    .locator('option')
    .evaluateAll((opts) => opts.map((o) => o.value).filter(Boolean))
  expect(values.length).toBeGreaterThan(0)
  await devisSelect.selectOption(values[0])
  // Two-option devis require an explicit battery choice.
  const optionRadios = dialog.locator('input[name="sd-option"]')
  if (await optionRadios.count()) {
    await optionRadios.first().check()
  }
  // The label uses a typographic apostrophe (l’acceptation) — match either.
  await dialog.getByRole('button', { name: /Confirmer l['’]acceptation/ }).click()
  await expect(dialog).toHaveCount(0)

  await expect(page.locator('tr.lv-row', { hasText: name })).toContainText('Signé')
})

// VX71 — a11y DYNAMIQUE : le FORMULAIRE EN ERREUR (soumission avec Nom vide)
// est un état affiché uniquement après interaction — un scan statique ne le
// rend jamais. Le formulaire est `noValidate` (règle générateur de devis) :
// la validation « Nom requis » est gérée côté React (LeadForm.jsx).
test('VX71: lead form validation error state has no serious/critical a11y violation', async ({ page }) => {
  await gotoLeads(page)
  await page.getByRole('button', { name: '+ Nouveau lead' }).click()
  const modal = page.locator('[role="dialog"]').filter({ has: page.locator('.modal-title') })
  await expect(modal.getByRole('heading', { name: 'Nouveau lead' })).toBeVisible()

  // Nom laissé vide → soumission déclenche l'erreur inline.
  await modal.getByRole('button', { name: 'Créer le lead' }).click()
  await expect(modal.getByText('Nom requis')).toBeVisible()

  await assertNoSeriousA11yViolations(page, { include: '[role="dialog"]' })

  await modal.locator('.modal-close').first().click()
})
