// E10 — File attachments: attach a file to a lead, confirm the upload succeeds,
// and confirm the stored file is openable/downloadable afterward (same-origin
// Django proxy, the B1 fix).
import { test, expect } from '@playwright/test'
import { gotoLeads, createLead, openLead, uniq } from './helpers'

const PDF_BYTES = '%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'

test('E10: attach a file to a lead, then open/download it', async ({ page }) => {
  await gotoLeads(page)
  const name = await createLead(page, { nom: uniq('Attach') })
  await openLead(page, name)
  const modal = page.locator('[role="dialog"]').filter({ has: page.locator('.modal-title') })

  const fname = `e2e-${Date.now()}.pdf`
  const [resp] = await Promise.all([
    page.waitForResponse((r) => r.url().includes('/attachments') && r.request().method() === 'POST'),
    modal.locator('input[type="file"]').setInputFiles({
      name: fname,
      mimeType: 'application/pdf',
      buffer: Buffer.from(PDF_BYTES),
    }),
  ])
  expect(resp.ok()).toBeTruthy()

  // The uploaded file shows as a link…
  const link = modal.locator('a.att-name', { hasText: fname })
  await expect(link).toBeVisible()

  // …and the stored object is reachable (200) through the same-origin proxy.
  const href = await link.getAttribute('href')
  expect(href).toBeTruthy()
  const dl = await page.request.get(href)
  expect(dl.ok()).toBeTruthy()
})
