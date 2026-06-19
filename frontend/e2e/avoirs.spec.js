// E12 — Credit notes: create an avoir from a posted invoice. The action lives on
// the factures list: the "Avoir" button opens a modal (total or per-line partial),
// then a success alert; the new avoir appears under Ventes → Avoirs.
import { test, expect } from '@playwright/test'

test('E12: create an avoir from a posted invoice', async ({ page }) => {
  // Accept the "Avoir créé" success alert.
  page.on('dialog', (d) => d.accept())

  await page.goto('/ventes/factures')
  const row = page.locator('tr', { hasText: 'FAC-DEMO-0001' }) // seeded émise invoice
  await expect(row).toBeVisible()
  await row.getByRole('button', { name: 'Avoir' }).click()

  // New modal: create a full credit note for the whole invoice.
  const totalBtn = page.getByRole('button', { name: 'Avoir total' })
  await expect(totalBtn).toBeVisible()
  await totalBtn.click()
  // Modal closes once the POST succeeds.
  await expect(totalBtn).toBeHidden()

  await page.goto('/ventes/avoirs')
  await expect(page.getByRole('heading', { name: /Avoirs/ })).toBeVisible()
  await expect(page.locator('table.data-table tbody tr').first()).toBeVisible()
  await expect(page.locator('table.data-table')).toContainText('FAC-DEMO-0001')
})
