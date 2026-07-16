// E4 — Devis from a lead: generate it (automatic + modifiable), confirm the PDF
// preview really renders (no broken-file icon), it appears in the lead's devis
// list, and download works.
import { test, expect } from '@playwright/test'
import {
  gotoLeads, createLead, openLead, generateAutoDevis, uniq,
  assertNoSeriousA11yViolations,
} from './helpers'

test('E4: generate a devis from a lead, preview renders, download works', async ({ page }) => {
  await gotoLeads(page)
  const name = await createLead(page, { nom: uniq('Devis'), facture: 900 })
  await openLead(page, name)

  // Automatic generation + the PDF preview rendered on <canvas> (no fallback).
  await generateAutoDevis(page)

  // Modifiable: the full editor is reachable from the same panel.
  await expect(page.getByRole('button', { name: /Édition complète/ })).toBeVisible()

  // VX71 — scan axe DYNAMIQUE sur le dialog PDF/devis réellement ouvert (état
  // atteignable seulement après l'interaction, jamais couvert par un scan statique).
  await assertNoSeriousA11yViolations(page, { include: '.ldp-body' })

  // Download produces a PDF file.
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: /Télécharger le PDF/ }).click(),
  ])
  expect(download.suggestedFilename()).toMatch(/\.pdf$/i)

  // The new devis now shows in this lead's devis list (header badge count).
  await page.locator('.ldp-header .modal-close').click()
  await expect(page.locator('.lead-devis-badge')).toContainText(/[1-9]\d* devis/)
})
