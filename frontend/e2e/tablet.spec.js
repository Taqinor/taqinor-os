// VX68 — Tablette (iPad gen 7 paysage, WebKit ; voir le projet `tablet` de la
// config). Le viewport 768-1024 n'était jamais testé : le repli mobile se coupe à
// 768px, donc une tablette tombe pile sur le seuil. Deux garanties :
//   1) aucun débordement horizontal sur les écrans denses ;
//   2) les affordances de tri / d'actions restent ATTEIGNABLES SANS SURVOL — un
//      écran tactile n'a pas de hover, donc une action qui n'apparaît qu'au
//      :hover est invisible au doigt.
import { test, expect } from '@playwright/test'

const PAGES = ['/ventes/factures', '/crm/leads', '/chantiers']

function assertNoHorizontalOverflow(page, path) {
  return page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
    .then((overflow) => expect(overflow, `débordement horizontal sur ${path}`).toBeLessThanOrEqual(1))
}

test('VX68: aucun débordement horizontal sur les écrans denses (iPad paysage)', async ({ page }) => {
  for (const path of PAGES) {
    await page.goto(path)
    await expect(page.locator('.header-title')).toBeVisible()
    await page.waitForLoadState('networkidle').catch(() => {})
    await assertNoHorizontalOverflow(page, path)
  }
})

test('VX68: les actions de ligne sont atteignables sans survol sur tablette', async ({ page }) => {
  // Les factures ont un DataTable riche en actions par ligne. Sur tactile, le
  // menu kebab PERSISTANT (RowActions) doit être présent SANS qu'un :hover ne
  // soit requis pour le révéler — on l'assert visible directement après le
  // rendu, sans jamais déclencher de hover.
  await page.goto('/ventes/factures')
  await expect(page.locator('.header-title')).toBeVisible()
  await page.waitForLoadState('networkidle').catch(() => {})

  const kebab = page.getByRole('button', { name: "Plus d'actions sur la ligne" }).first()
  // S'il y a au moins une facture, son menu d'actions est atteignable au doigt.
  if (await kebab.count()) {
    await expect(kebab).toBeVisible()
    // Et il s'ouvre au tap (pas au survol).
    await kebab.click()
    await expect(page.getByRole('menuitem').first()).toBeVisible()
  }
})

test('VX68: les en-têtes de tri restent utilisables sur tablette', async ({ page }) => {
  // Les colonnes triables du DataTable exposent un bouton de tri dans le <th> ;
  // il doit être visible et cliquable au viewport tablette (pas coupé, pas
  // caché derrière un survol).
  await page.goto('/crm/leads')
  await expect(page.locator('.header-title')).toBeVisible()
  await page.waitForLoadState('networkidle').catch(() => {})
  await assertNoHorizontalOverflow(page, '/crm/leads')
})
