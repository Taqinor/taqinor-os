// E11 — Duplicate detection: the doublons view renders and merging a cluster
// completes. We seed a fresh cluster (two identical leads) so a group always
// exists, then merge it.
import { test, expect } from '@playwright/test'
import { gotoLeads, uniq } from './helpers'

test('E11: doublons view renders and merging a cluster completes', async ({ page }) => {
  await gotoLeads(page)
  const name = uniq('Doublon')
  const phone = '06' + String(Date.now()).slice(-8)

  // Two identical leads → one duplicate cluster (matched on phone + name).
  for (let i = 0; i < 2; i += 1) {
    await page.getByRole('button', { name: '+ Nouveau lead' }).click()
    const modal = page.locator('[role="dialog"]').filter({ has: page.locator('.modal-title') })
    await modal.locator('#lf-nom').fill(name)
    await modal.locator('.form-group', { hasText: 'Téléphone' }).locator('input').fill(phone)
    await modal.getByRole('button', { name: 'Créer le lead' }).click()
    await expect(page.locator('[role="dialog"]').filter({ has: page.locator('.modal-title') })).toHaveCount(0)
  }

  await page.getByRole('button', { name: '🔀 Doublons' }).click()
  const panel = page.locator('.dbl-panel')
  await expect(panel.getByRole('heading', { name: /Doublons/ })).toBeVisible()

  const cluster = panel.locator('.dbl-cluster', { hasText: name })
  await expect(cluster).toBeVisible({ timeout: 20_000 })

  page.on('dialog', (d) => d.accept()) // confirm the merge
  await cluster.getByRole('button', { name: /Fusionner le groupe/ }).click()
  // A successful merge archives the absorbed leads, so the panel reloads and the
  // duplicate cluster disappears (the inline "Groupe fusionné" badge is only
  // shown transiently before that reload). A failed merge would keep it.
  await expect(panel.locator('.dbl-cluster', { hasText: name })).toHaveCount(0)
})
