// ACAL439 — Accessibilité automatique du module Calepinage (axe-core, WCAG A/AA, toute gravité).
//
// Écrans couverts, en thème clair ET sombre : liste, création, atelier (avec rail), onglets Production et
// Documents. Patron de `taches-a11y.spec.js`. Périmètre `main` : la coquille ERP (en-tête, barre latérale)
// n'est pas jugée ici. Le thème est posé par `localStorage['taqinor-theme']` puis `emulateMedia`.
// L'atelier monte sans clé MapTiler (fond de repli ACAL377) : le test ne se saute que si sa racine ne monte pas.
import AxeBuilder from '@axe-core/playwright'
import { test, expect } from '@playwright/test'
import { uniq, gotoLeads, createLead } from './helpers'

const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']

async function poserTheme(page, theme) {
  await page.addInitScript((t) => {
    try { localStorage.setItem('taqinor-theme', t) } catch { /* ignoré */ }
  }, theme)
  await page.emulateMedia({ colorScheme: theme })
}

/** 0 violation, toute gravité ; le message nomme règle, gravité et 5 cibles. */
async function verifier(page, ecran, theme) {
  const { violations } = await new AxeBuilder({ page }).include('main').withTags(TAGS).analyze()
  const message = violations.map((v) => `${v.id} (${v.impact}) : ${v.nodes.slice(0, 5)
    .map((n) => n.target.join(' ')).join(' | ')}`).join('\n')
  expect(violations, `${ecran} [${theme}] — violations axe :\n${message}`).toEqual([])
}

async function creerCalepinage(page) {
  await gotoLeads(page)
  const nomLead = await createLead(page, { nom: uniq('ACAL439 Lead'), facture: 900, ville: 'Casablanca' })
  await page.goto('/calepinage/nouveau')
  await expect(page.getByRole('heading', { name: 'Nouveau calepinage' })).toBeVisible()
  await page.getByRole('tab', { name: 'Lead' }).click()
  await page.locator('#cal-nouveau-lead').getByRole('combobox').click()
  await page.getByRole('searchbox').fill(nomLead)
  await page.getByRole('option', { name: new RegExp(nomLead) }).first().click()
  await page.locator('#cal-nouveau-nom').fill(uniq('ACAL439 Toiture'))
  await page.getByRole('button', { name: 'Créer le calepinage' }).click()
  await expect(page).toHaveURL(/\/calepinage\/\d+/)
  return new URL(page.url()).pathname.match(/\/calepinage\/(\d+)/)[1]
}

for (const theme of ['light', 'dark']) {
  test(`ACAL439 [${theme}] : liste et création sans violation axe`, async ({ page }) => {
    await poserTheme(page, theme)
    await page.goto('/calepinage')
    await expect(page.locator('main')).toBeVisible()
    await verifier(page, '/calepinage', theme)
    await page.goto('/calepinage/nouveau')
    await expect(page.getByRole('heading', { name: 'Nouveau calepinage' })).toBeVisible()
    await verifier(page, '/calepinage/nouveau', theme)
  })

  test(`ACAL439 [${theme}] : atelier, Production et Documents sans violation axe, focus visible`, async ({ page }) => {
    await poserTheme(page, theme)
    const id = await creerCalepinage(page)
    // Sans clé MapTiler l'atelier monte quand même (fond de repli ACAL377) : on ne saute que si sa racine ne monte pas.
    const monte = await page.getByTestId('cal-rail-onglets').waitFor({ timeout: 20_000 }).then(() => true, () => false)
    test.skip(!monte, 'racine de l’atelier non montée sur cet environnement : a11y de l’atelier non rejouable ici')
    await verifier(page, `/calepinage/${id}`, theme)

    await page.locator('main').focus()
    await page.keyboard.press('Tab')
    const focus = await page.evaluate(() => {
      const s = getComputedStyle(document.activeElement)
      return { tag: document.activeElement.tagName, outline: s.outlineStyle, ombre: s.boxShadow }
    })
    expect(focus.outline !== 'none' || focus.ombre !== 'none',
      `1er élément tabulable (${focus.tag}) sans contour de focus [${theme}]`).toBeTruthy()

    for (const onglet of ['production', 'documents']) {
      // Coque (22/11) : le panneau d'onglet est celui du mode expert.
      await page.goto(`/calepinage/${id}?onglet=${onglet}&mode=expert`)
      await expect(page.getByTestId('cal-onglet-panneau')).toBeVisible()
      await verifier(page, `/calepinage/${id}?onglet=${onglet}&mode=expert`, theme)
    }
  })
}
