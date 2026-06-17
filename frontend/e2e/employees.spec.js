// E8 — Employee management: create + edit an employee, upload a photo, and
// reach the password-reset action.
import { test, expect } from '@playwright/test'
import { uniq } from './helpers'

// 1×1 transparent PNG.
const PNG_1x1 =
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='

test('E8: create + edit an employee, upload a photo, reach password reset', async ({ page }) => {
  await page.goto('/admin/users')
  await expect(page.getByRole('heading', { name: 'Gestion des utilisateurs' })).toBeVisible()

  const username = uniq('emp').replace(/\s+/g, '_').toLowerCase()
  await page.getByRole('button', { name: '+ Nouvel utilisateur' }).click()

  const form = page.locator('form').filter({
    has: page.getByRole('button', { name: 'Créer', exact: true }),
  })
  await form.locator('input:not([type])').first().fill(username) // username
  await form.locator('input[type="email"]').fill(`${username}@e2e.local`)
  await form.locator('input[type="password"]').fill('Az9ployxQ!') // passes Django validators
  await form.getByRole('button', { name: 'Créer', exact: true }).click()

  const row = page.locator('tr', { hasText: username })
  await expect(row).toBeVisible()

  // Edit.
  await row.getByRole('button', { name: 'Modifier' }).click()
  const modal = page.locator('.modal')
  await expect(modal.getByRole('heading', { name: new RegExp(`Employé — ${username}`) })).toBeVisible()

  // Photo upload — set files on the hidden input directly (clicking the visible
  // button would open a native chooser that can't be driven headlessly).
  const [resp] = await Promise.all([
    page.waitForResponse((r) => r.url().includes('/avatar/') && r.request().method() === 'POST'),
    modal.locator('input[type="file"]').setInputFiles({
      name: 'avatar.png',
      mimeType: 'image/png',
      buffer: Buffer.from(PNG_1x1, 'base64'),
    }),
  ])
  expect(resp.ok()).toBeTruthy()

  // Password-reset action is reachable (set-a-new-password field in the modal).
  await expect(modal.getByText('Nouveau mot de passe')).toBeVisible()
})
