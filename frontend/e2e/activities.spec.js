// E9 — Typed activities: log an activity on a lead (assigned to me, due today)
// and see it in the cockpit (/activites).
import { test, expect } from '@playwright/test'
import { gotoLeads, createLead, openLead, uniq, ADMIN } from './helpers'

test('E9: log an activity and see it in the cockpit', async ({ page }) => {
  await gotoLeads(page)
  const name = await createLead(page, { nom: uniq('Activity') })
  await openLead(page, name)
  const modal = page.locator('[role="dialog"]').filter({ has: page.locator('.modal-title') })

  // LW13/LW19 — les activités vivent dans un onglet du rail contexte (blueprint D3).
  await modal.getByRole('tab', { name: /Activités/ }).click()
  await modal.getByRole('button', { name: /Planifier une activité/ }).click()
  const summary = uniq('Appel')
  const actForm = modal.locator('.act-form')

  // Assign to the logged-in admin so it lands in their cockpit.
  await actForm.locator('.ap-trigger').click()
  await page.locator('.ap-menu .ap-item', { hasText: ADMIN.username }).click()
  await actForm.locator('input[placeholder="ex: Appeler pour la visite"]').fill(summary)
  await actForm.getByRole('button', { name: 'Créer' }).click()

  // Shows in the lead's own activity list…
  await expect(modal.locator('.act-list')).toContainText(summary)

  // …and in the cockpit.
  await page.goto('/activites')
  await expect(page.getByText(summary)).toBeVisible()
})
