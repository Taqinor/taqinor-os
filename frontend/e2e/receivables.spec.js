// E13 — Payment follow-ups, aged receivables, and a customer statement all
// render (they can legitimately be empty for the seed — "renders" is the bar).
import { test, expect } from '@playwright/test'

test('E13: relances, aged receivables and a customer statement all render', async ({ page }) => {
  await page.goto('/ventes/relances')
  await expect(page.getByRole('heading', { name: /Relances/ })).toBeVisible()

  await page.goto('/reporting/balance-agee')
  await expect(page.getByRole('heading', { name: 'Balance âgée' })).toBeVisible()

  // The customer statement is keyed by client id — fetch one over the API using
  // the session cookies the page already carries.
  const res = await page.request.get('/api/django/crm/clients/')
  expect(res.ok()).toBeTruthy()
  const data = await res.json()
  const clients = data.results ?? data
  expect(clients.length).toBeGreaterThan(0)

  await page.goto(`/reporting/archive/client/${clients[0].id}`)
  await expect(page.getByRole('heading', { name: /Archive documentaire/ })).toBeVisible()
})
