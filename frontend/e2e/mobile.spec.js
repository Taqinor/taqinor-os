// E16 — Mobile pass (iPhone viewport, see the `mobile` project in the config):
// no horizontal overflow on key pages, and the full nav menu is reachable
// (verifies the C1 cut-off-menu fix).
import { test, expect } from '@playwright/test'
import { uniq } from './helpers'

const PAGES = ['/dashboard', '/crm/leads', '/ventes/factures', '/parametres']

test('E16: no horizontal overflow on key pages', async ({ page }) => {
  for (const path of PAGES) {
    await page.goto(path)
    await expect(page.locator('.header-title')).toBeVisible()
    await page.waitForLoadState('networkidle').catch(() => {})
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    )
    expect(overflow, `horizontal overflow on ${path}`).toBeLessThanOrEqual(1)
  }
})

test('E16: the full navigation menu is reachable on mobile', async ({ page }) => {
  await page.goto('/dashboard')
  await expect(page.locator('.header-title')).toBeVisible()

  // Open the drawer (hamburger only shows at mobile widths).
  await page.getByRole('button', { name: 'Ouvrir le menu' }).click()

  // The last items (admin-only, at the very bottom) must be reachable, i.e. the
  // menu scrolls inside the safe area instead of clipping them.
  const settings = page.getByRole('link', { name: 'Paramètres' })
  await settings.scrollIntoViewIfNeeded()
  await expect(settings).toBeVisible()

  const logout = page.getByRole('button', { name: 'Déconnexion' })
  await logout.scrollIntoViewIfNeeded()
  await expect(logout).toBeVisible()
})

// E16+ — Régression iPhone : un modal d'édition (haut) doit TENIR dans l'écran et
// rester scrollable, pas déborder hors du viewport avec ses boutons hors d'atteinte.
// (Pendant e2e du correctif Dialog/AlertDialog ; le contrat de classes est, lui,
// verrouillé côté composant par src/ui/modal-viewport.test.jsx.) On réutilise le
// parcours éprouvé d'E8 (créer puis éditer un utilisateur) pour ouvrir un modal réel.
test('E16+: an edit modal fits the iPhone viewport (no off-screen crop)', async ({ page }) => {
  await page.goto('/admin/users')
  await expect(page.getByRole('heading', { name: 'Gestion des utilisateurs' })).toBeVisible()

  const username = uniq('m16').replace(/\s+/g, '_').toLowerCase()
  await page.getByRole('button', { name: '+ Nouvel utilisateur' }).click()
  const createForm = page.locator('form').filter({
    has: page.getByRole('button', { name: 'Créer', exact: true }),
  })
  await createForm.locator('input:not([type])').first().fill(username)
  await createForm.locator('input[type="email"]').fill(`${username}@e2e.local`)
  await createForm.locator('input[type="password"]').fill('Az9ployxQ!')
  await createForm.getByRole('button', { name: 'Créer', exact: true }).click()

  // M154 — Au format iPhone (< 640px), le DataTable des utilisateurs replie ses
  // lignes en CARTES (`[data-dt-cards]`) ; la table desktop passe en
  // `display:none`, donc le sélecteur `tr` n'est plus visible. On cible la carte
  // par son nom d'utilisateur, on ouvre le menu kebab PERSISTANT de la ligne
  // (RowActions — les actions rapides sont masquées au toucher), puis « Modifier ».
  const card = page.locator('[data-dt-cards] > div').filter({ hasText: username })
  await expect(card).toBeVisible()
  await card.getByRole('button', { name: "Plus d'actions sur la ligne" }).click()
  await page.getByRole('menuitem', { name: 'Modifier' }).click()

  const modal = page.locator('.modal')
  await expect(modal).toBeVisible()

  // Cœur du test iPhone : le modal ne déborde pas verticalement hors de l'écran.
  const box = await modal.boundingBox()
  const vp = page.viewportSize()
  expect(box, 'le modal a une boundingBox').toBeTruthy()
  expect(box.y, 'le haut du modal est visible').toBeGreaterThanOrEqual(-1)
  expect(
    box.y + box.height,
    'le bas du modal tient dans le viewport iPhone',
  ).toBeLessThanOrEqual(vp.height + 1)

  // L'action critique (réinitialiser le mot de passe) reste atteignable.
  const pwd = modal.getByText('Nouveau mot de passe', { exact: true })
  await pwd.scrollIntoViewIfNeeded()
  await expect(pwd).toBeVisible()
})
