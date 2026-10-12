// E11 — Duplicate detection: the doublons view renders and merging a cluster
// completes. We seed a fresh cluster (two identical leads) so a group always
// exists, then merge it.
import { test, expect } from '@playwright/test'
import { gotoLeads, uniq , boutonNouveauLead } from './helpers'

test('E11: doublons view renders and merging a cluster completes', async ({ page }) => {
  await gotoLeads(page)
  const name = uniq('Doublon')
  const phone = '06' + String(Date.now()).slice(-8)

  // Two identical leads → one duplicate cluster (matched on phone + name).
  for (let i = 0; i < 2; i += 1) {
    await boutonNouveauLead(page).click()
    const modal = page.locator('[role="dialog"]').filter({ has: page.locator('.modal-title') })
    await modal.locator('#lf-nom').fill(name)
    // LW39 (suite) — FormField du workspace ne rend plus `.form-group` : id stable.
    await modal.locator('#lf-telephone').fill(phone)
    await modal.getByRole('button', { name: 'Créer le lead' }).click()
    await expect(page.locator('[role="dialog"]').filter({ has: page.locator('.modal-title') })).toHaveCount(0)
  }

  // LB (refonte leads, VX145b/LB26) — « Doublons » a été démoté de bouton
  // d'en-tête vers un item du menu « ⋯ » (Plus d'actions), icône GitMerge au
  // lieu de l'emoji 🔀 : on ouvre le menu puis on choisit l'item (même patron
  // Radix que mobile.spec E16+). Le nom accessible de l'item est « Doublons »
  // (+ le compteur de groupes s'il est >0) → match par regex, robuste au badge.
  await page.getByRole('button', { name: "Plus d'actions" }).click()
  await page.getByRole('menuitem', { name: /Doublons/ }).click()
  const panel = page.locator('.dbl-panel')
  await expect(panel.getByRole('heading', { name: /Doublons/ })).toBeVisible()

  const cluster = panel.locator('.dbl-cluster', { hasText: name })
  await expect(cluster).toBeVisible({ timeout: 20_000 })

  // CAD177 — ALEA22 (2c2e4c08f) : la confirmation n'est plus le `window.confirm`
  // natif mais la boîte maison `useConfirmDialog()` (DoublonsPanel.jsx) — un
  // `page.on('dialog')` n'en voit rien et la fusion restait en attente. On
  // confirme dans la boîte, par son bouton, comme l'utilisateur.
  await cluster.getByRole('button', { name: /Fusionner le groupe/ }).click()
  const confirmation = page.getByRole('alertdialog', { name: 'Fusionner ces doublons ?' })
  await expect(confirmation).toBeVisible()
  await confirmation.getByRole('button', { name: 'Fusionner', exact: true }).click()
  // A successful merge archives the absorbed leads, so the panel reloads and the
  // duplicate cluster disappears (the inline "Groupe fusionné" badge is only
  // shown transiently before that reload). A failed merge would keep it.
  await expect(panel.locator('.dbl-cluster', { hasText: name })).toHaveCount(0)
})
