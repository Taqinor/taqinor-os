// E12 — Credit notes: create an avoir from a posted invoice. The action lives on
// the factures list (window.prompt for the motif, then a success alert); the new
// avoir then appears under Ventes → Avoirs.
import { test, expect } from '@playwright/test'

test('E12: create an avoir from a posted invoice', async ({ page }) => {
  // Accept the motif prompt, then the "Avoir créé" alert.
  page.on('dialog', (d) => d.accept(d.type() === 'prompt' ? 'E2E avoir' : ''))

  await page.goto('/ventes/factures')
  const row = page.locator('tr', { hasText: 'FAC-DEMO-0001' }) // seeded émise invoice
  await expect(row).toBeVisible()
  await row.getByRole('button', { name: 'Avoir' }).click()

  await page.goto('/ventes/avoirs')
  await expect(page.getByRole('heading', { name: /Avoirs/ })).toBeVisible()
  await expect(page.locator('table.data-table tbody tr').first()).toBeVisible()
  await expect(page.locator('table.data-table')).toContainText('FAC-DEMO-0001')
})
