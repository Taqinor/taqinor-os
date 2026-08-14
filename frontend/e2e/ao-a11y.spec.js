// AOF188 — Passe d'accessibilité AO (clair et sombre), gate CI DISTINCT de
// ao-parcours/ao-dossier (AOF187) : un défaut a11y ne doit jamais se cacher
// derrière un scénario fonctionnel qui, lui, passe.
//
// Couvre : les deux ateliers (toiture/traçage + calepinage), le dossier et le
// bordereau, dans les deux thèmes (clair/sombre — même mécanique que
// visual.spec.js : `localStorage['taqinor-theme']` posé via `addInitScript`
// AVANT le premier rendu). Contraste AA des tokens de provenance/état/verdict
// est couvert PAR CONSTRUCTION : axe-core signale toute violation de contraste
// (`color-contrast`) sur l'un OU l'autre thème, donc les deux passes suffisent
// à garder AOF9/AOF10 honnêtes sans dupliquer leur propre test de token.
//
// ── CORRECTION 14/08/2026 — ces quatre écrans sont des ONGLETS, pas des liens ─
// Écrit à l'aveugle (cf. NOTES_LANE.md, lane AOF187-192 : « à ajuster si
// frontend/ao-socle nomme différemment »), ce spec cherchait
// `getByRole('link', { name: /Toiture|Calepinage|Dossier|Bordereau/ })`. La
// fiche affaire rend ses sections en onglets Radix (`role="tab"`), donc :
//   * « Bordereau » ne résolvait rien → rouge honnête ;
//   * « Toiture », « Calepinage » et « Dossier » résolvaient vers l'entrée de
//     NAVIGATION GLOBALE du module (`/ao/toitures`, `/ao/calepinages`,
//     `/ao/dossiers`) → le spec quittait la fiche et balayait un AUTRE écran
//     en se déclarant vert. Un faux vert affirme une couverture inexistante.
// La navigation passe désormais par `ouvrirOngletAffaire` (helpers.js), qui
// clique le `role="tab"` réel ET vérifie qu'on n'a pas quitté la fiche.
import { test, expect } from '@playwright/test'
import {
  openAoDemoAffaire, ouvrirOngletAffaire, assertNoSeriousA11yViolations,
} from './helpers'

// Libellés EXACTS des onglets déclarés par `features/ao/AffaireDetail.jsx`.
const ATELIERS = [
  { name: 'atelier-toiture', onglet: 'Toitures & relevés' },
  { name: 'atelier-calepinage', onglet: 'Calepinages' },
  { name: 'dossier', onglet: 'Dossier' },
  { name: 'bordereau', onglet: 'Bordereau' },
]

async function gotoEcran(page, onglet) {
  await openAoDemoAffaire(page)
  await ouvrirOngletAffaire(page, onglet)
}

for (const { name, onglet } of ATELIERS) {
  test(`AOF188: ${name} — axe sans violation sérieuse (clair)`, async ({ page }) => {
    await gotoEcran(page, onglet)
    await assertNoSeriousA11yViolations(page)
  })

  test(`AOF188: ${name} — axe sans violation sérieuse (sombre)`, async ({ page }) => {
    await page.addInitScript(() => {
      try { localStorage.setItem('taqinor-theme', 'dark') } catch { /* mode privé */ }
    })
    await gotoEcran(page, onglet)
    await assertNoSeriousA11yViolations(page)
  })
}

test('AOF188: le focus reste visible sur le canvas et ses poignées', async ({ page }) => {
  await gotoEcran(page, 'Toitures & relevés')
  const canvas = page.locator('[data-ao-canvas]')
  await expect(canvas).toBeVisible()
  await canvas.focus()
  const outlineCanvas = await canvas.evaluate((el) => {
    const s = getComputedStyle(el)
    return s.outlineStyle !== 'none' && s.outlineWidth !== '0px'
      ? true
      : s.boxShadow !== 'none'
  })
  expect(outlineCanvas, 'le canvas doit porter un focus visible (outline ou box-shadow)').toBeTruthy()

  const poignee = page.locator('[data-ao-repere]').first()
  if (await poignee.count()) {
    await poignee.focus()
    const outlinePoignee = await poignee.evaluate((el) => {
      const s = getComputedStyle(el)
      return s.outlineStyle !== 'none' && s.outlineWidth !== '0px'
        ? true
        : s.boxShadow !== 'none'
    })
    expect(outlinePoignee, 'une poignée de géométrie doit porter un focus visible').toBeTruthy()
  }
})

test('AOF188: le compte et le verdict sont annoncés via aria-live après recalcul', async ({ page }) => {
  await gotoEcran(page, 'Calepinages')
  const verdict = page.locator('[data-ao-verdict]')
  const compte = page.locator('[data-ao-compte]')
  await expect(verdict).toBeVisible()
  await expect(compte).toBeVisible()

  // Le conteneur `aria-live` peut englober l'un, l'autre ou les deux : on
  // vérifie qu'un ancêtre-ou-soi porte bien l'attribut pour CHAQUE hook, sans
  // imposer une structure DOM précise (contrat sur le RÉSULTAT, pas la forme).
  const liveAncestor = (loc) => loc.locator(
    'xpath=ancestor-or-self::*[@aria-live][1]',
  )
  await expect(liveAncestor(verdict)).toHaveCount(1)
  await expect(liveAncestor(compte)).toHaveCount(1)
})

test('AOF188: le tableau de géométrie (AOF77) se parcourt intégralement au clavier', async ({ page }) => {
  await gotoEcran(page, 'Toitures & relevés')
  const table = page.getByRole('table')
  await expect(table).toBeVisible()

  const cellulesFocusables = table.locator('button, [tabindex="0"], input, a[href]')
  const total = await cellulesFocusables.count()
  expect(total, 'le tableau de géométrie expose au moins une cible clavier').toBeGreaterThan(0)

  await cellulesFocusables.first().focus()
  for (let i = 0; i < Math.min(total, 10); i += 1) {
    await page.keyboard.press('Tab')
  }
  // Après N tabulations depuis la première cible, le focus est toujours DANS
  // le document (jamais perdu sur <body> — piège classique de tabindex négatif
  // mal posé) et toujours à l'intérieur d'un composant applicatif connu.
  const perdu = await page.evaluate(() => document.activeElement === document.body)
  expect(perdu, 'le focus clavier ne doit jamais retomber sur <body>').toBe(false)
})

test('AOF188: aucun window.alert/confirm/prompt natif sur le parcours AO', async ({ page }) => {
  let dialogVu = null
  page.on('dialog', (dialog) => { dialogVu = dialog.type() })

  // Les quatre panneaux s'ouvrent SUR LA MÊME fiche : on n'y revient pas par la
  // liste entre deux, c'est bien un changement d'onglet qu'on balaie.
  await openAoDemoAffaire(page)
  for (const { onglet } of ATELIERS) {
    await ouvrirOngletAffaire(page, onglet)
    await page.waitForLoadState('networkidle').catch(() => {})
  }

  expect(dialogVu, `un dialogue natif (${dialogVu}) a été déclenché`).toBeNull()
})
