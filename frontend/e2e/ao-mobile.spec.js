// AOF190 — Mode MOBILE (375 px) : le refus explicite des éditions lourdes est
// un choix de design assumé, pas une lacune — voir ModeMobile.jsx.
//
// Force le viewport à 375 px (le project Playwright `mobile` matche ce fichier
// via `mobile\.spec\.js` mais est câblé à 390x844 — cf. AOF190 qui nomme
// explicitement 375, la largeur historique la plus contraignante).
import { test, expect } from '@playwright/test'
import { openAoDemoAffaire, ouvrirAoToituresMobile } from './helpers'

test.use({ viewport: { width: 375, height: 667 } })

test('AOF190: aucun débordement horizontal sur les écrans AO à 375 px', async ({ page }) => {
  await openAoDemoAffaire(page)
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(overflow, 'débordement horizontal AO à 375px').toBeLessThanOrEqual(1)
})

test('AOF190: chaque édition lourde affiche son refus AVEC la raison (jamais un bouton mort)', async ({ page }) => {
  await openAoDemoAffaire(page)
  await ouvrirAoToituresMobile(page)

  const refus = page.locator('[data-ao-tiroir^="refus-mobile-"]')
  // `count()` ne patiente pas : on attend que le mode mobile soit RÉELLEMENT
  // monté avant de compter, sinon un comptage trop tôt renverrait 0.
  await expect(refus.first()).toBeVisible()
  const total = await refus.count()
  expect(total, 'au moins un refus explicite est affiché sur mobile').toBeGreaterThan(0)

  for (let i = 0; i < total; i += 1) {
    const bloc = refus.nth(i)
    await expect(bloc).toBeVisible()
    await expect(bloc).toContainText('Disponible sur écran large')
    // La raison n'est jamais vide : « Disponible sur écran large » seul, sans
    // complément, serait un bouton mort reformulé.
    const texte = (await bloc.textContent())?.trim() || ''
    expect(texte.length, 'la raison du refus doit accompagner le message').toBeGreaterThan(
      'Disponible sur écran large'.length,
    )
  }
})

test('AOF190: la capture (photo → repère) reste disponible sur mobile malgré le refus des éditions lourdes', async ({ page }) => {
  await openAoDemoAffaire(page)
  await ouvrirAoToituresMobile(page)
  await expect(page.getByText('Photo → repère')).toBeVisible()
})
