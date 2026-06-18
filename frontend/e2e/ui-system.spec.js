// Refonte UI (Groupes F + G) — vérifie la vitrine /ui : rendu des primitifs,
// thème clair/sombre, densité, overlay (Dialog), toast, et zéro erreur console.
// La page /ui est publique (sans auth ni backend) : on se place en état non
// authentifié pour ne dépendre de rien d'autre que le build frontend.
import { test, expect } from '@playwright/test'

test.use({ storageState: { cookies: [], origins: [] } })

test('UI system: /ui renders primitives, theme, density, dialog, toast', async ({ page }) => {
  const errors = []
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(m.text())
  })
  page.on('pageerror', (e) => errors.push(String(e)))

  await page.goto('/ui')

  // Rendu de base
  await expect(page.getByRole('heading', { name: 'Taqinor — Système UI' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Principal' })).toBeVisible()

  // Thème : passer en sombre -> classe .dark sur <html>
  await page.getByRole('button', { name: 'Sombre' }).click()
  await expect.poll(() => page.evaluate(() => document.documentElement.classList.contains('dark'))).toBe(true)
  // Revenir en clair
  await page.getByRole('button', { name: 'Clair' }).click()
  await expect.poll(() => page.evaluate(() => document.documentElement.classList.contains('dark'))).toBe(false)

  // Densité : Compact -> data-density=compact
  await page.getByRole('radio', { name: 'Compact' }).click()
  await expect.poll(() => page.evaluate(() => document.documentElement.getAttribute('data-density'))).toBe('compact')

  // Overlay : ouvrir un Dialog, vérifier le titre, fermer avec Échap
  await page.getByRole('button', { name: 'Ouvrir un dialog' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByText('Confirmer le devis')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toBeHidden()

  // Toast : déclencher un toast de succès
  await page.getByRole('button', { name: 'Toast succès' }).click()
  await expect(page.getByText('Enregistré')).toBeVisible()

  // Santé : aucune erreur console / page
  expect(errors, `erreurs console: ${errors.join(' | ')}`).toEqual([])
})
