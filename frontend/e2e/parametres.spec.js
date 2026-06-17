// E14 — Paramètres: settings pages load, changing a setting saves and is
// reflected (persists across a reload).
import { test, expect } from '@playwright/test'

test('E14: settings load, a change saves and is reflected', async ({ page }) => {
  await page.goto('/parametres')
  // The Save button only renders once the profile has loaded.
  await expect(page.getByRole('button', { name: 'Enregistrer' })).toBeVisible({ timeout: 20_000 })

  const email = page.locator('input[name="email"]')
  await expect(email).toBeVisible()
  const newEmail = `e2e-${Date.now()}@taqinor.local`
  await email.fill(newEmail)

  await page.getByRole('button', { name: 'Enregistrer' }).click()
  await expect(page.getByText('Profil enregistré avec succès.')).toBeVisible()

  // Reflected after a reload (persisted server-side).
  await page.reload()
  await expect(page.locator('input[name="email"]')).toHaveValue(newEmail)
})
