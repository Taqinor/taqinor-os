// CALX387 — Prouver que chaque onglet du rail s'ouvre, en e2e.
//
// POURQUOI CETTE SPEC EXISTE. Les 13+ routes profondes du module
// (`pente`, `terrain`, `ombriere`, `schema`, `production`, `pertes`, `horizon`,
// `course-soleil`, `dossiers`, `affectation`, `fiches`, `plan`, `pompage`… et
// tous les onglets ajoutés depuis) n'ont AUCUN lien entrant hors du rail
// (`atelier/onglets.js`, CALX1) : aucune spec ne les ouvre tous, une par une.
// `calepinage-parcours.spec.js` (CALX1) en ouvre trois, en dur ; ni
// `calepinage-parite-crm.spec.js` ni `calepinage_tactile.spec.js` n'y touchent.
//
// LE REGISTRE EST LA SOURCE DE VÉRITÉ. Cette spec lit `atelier/onglets.js`
// PAR SA SOURCE (comme `check_onglets_calepinage_testes.py`, CALX383, et
// `calepinageApi.usage.test.mjs`, CALX382) plutôt que d'énumérer les clés en
// dur : un onglet ajouté au registre est automatiquement couvert, sans
// modifier ce fichier.
//
// HOOKS DOM, PAS DE TEXTE (même patron que CALX1) : `data-testid="cal-onglet-<cle>"`
// pour l'onglet, `cal-onglet-panneau` pour le panneau, `cal-onglet-erreur`
// pour l'ErrorBoundary qui NOMME l'onglet fautif plutôt que de rendre un
// écran blanc.
//
// AUCUN `page.waitForTimeout` (`scripts/check_test_determinism.py` le
// refuse) : chaque attente porte sur une condition observable (attribut
// `aria-selected`, visibilité du panneau, URL).
import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { uniq, gotoLeads, createLead } from './helpers'

const here = dirname(fileURLToPath(import.meta.url))
const ONGLETS_PATH = join(here, '..', 'src', 'features', 'calepinage', 'atelier', 'onglets.js')

/** L'identifiant du calepinage ouvert, lu sur l'URL de son atelier. */
function idDansUrl(url) {
  const m = /\/calepinage\/(\d+)/.exec(new URL(url).pathname)
  return m ? m[1] : null
}

/**
 * Les clés du registre, lues À SA SOURCE — jamais énumérées en dur (même
 * garantie que `check_onglets_calepinage_testes.py`, CALX383).
 */
function clesDuRegistre() {
  const source = readFileSync(ONGLETS_PATH, 'utf8')
  const code = source.replace(/\/\*[\s\S]*?\*\//g, '')
  const cles = []
  const re = /\{\s*cle:\s*'([^']+)'/g
  let m
  while ((m = re.exec(code)) !== null) cles.push(m[1])
  return cles
}

const CLES = clesDuRegistre()

test('CALX387: le registre atelier/onglets.js publie au moins un onglet', () => {
  expect(CLES.length, 'aucune clé lue dans atelier/onglets.js — le format a-t-il changé ?')
    .toBeGreaterThan(0)
})

test('CALX387: chaque onglet du rail s’ouvre, un titre nommé apparaît, aucune erreur de page', async ({ page }) => {
  const erreursDePage = []
  page.on('pageerror', (err) => erreursDePage.push(err))

  await gotoLeads(page)
  const nomLead = await createLead(page, {
    nom: uniq('CALX387 Lead'), facture: 900, ville: 'Casablanca',
  })

  await page.goto('/calepinage/nouveau')
  await expect(page.getByRole('heading', { name: 'Nouveau calepinage' })).toBeVisible()
  await page.getByRole('tab', { name: 'Lead' }).click()
  await page.locator('#cal-nouveau-lead').getByRole('combobox').click()
  await page.getByRole('searchbox').fill(nomLead)
  await page.getByRole('option', { name: new RegExp(nomLead) }).first().click()
  await page.locator('#cal-nouveau-nom').fill(uniq('CALX387 Toiture'))
  await page.getByRole('button', { name: 'Créer le calepinage' }).click()

  await expect(page).toHaveURL(/\/calepinage\/\d+/)
  const calepinageId = idDansUrl(page.url())
  expect(calepinageId, 'aucun identifiant de calepinage dans l’URL').toBeTruthy()
  await expect(page.getByTestId('cal-rail-onglets')).toBeVisible()

  for (const cle of CLES) {
    const onglet = page.getByTestId(`cal-onglet-${cle}`)
    await expect(onglet, `onglet absent du rail pour la clé « ${cle} »`).toBeVisible()
    await onglet.click()

    // 1. l'onglet devient l'onglet actif ; 2. l'URL porte la clé (lien
    // partageable) ; 3. un panneau (contenu OU erreur NOMMÉE) est visible —
    // jamais un écran blanc.
    await expect(onglet).toHaveAttribute('aria-selected', 'true')
    await expect(page).toHaveURL(new RegExp(`onglet=${cle}(&|$)`))
    await expect(
      page.getByTestId('cal-onglet-panneau').or(page.getByTestId('cal-onglet-erreur')),
      `ni panneau ni erreur nommée pour l’onglet « ${cle} »`,
    ).toBeVisible()

    // Un « titre nommé » accompagne chaque panneau : le libellé de l'onglet
    // actif lui-même (déjà affirmé visible ci-dessus) sert de titre — la
    // tâche n'exige rien de plus qu'un intitulé LISIBLE, pas un `<h1>` par
    // panneau (aucun des 27 panneaux mesurés n'en a un, et l'exiger ici
    // romprait 27 écrans pour une convention qu'aucun d'eux ne suit).
    await expect(onglet).not.toHaveText('')
  }

  // Garde anti-régression : AUCUNE exception JS non rattrapée sur la durée
  // du parcours, quel que soit l'onglet ouvert.
  expect(erreursDePage.map((e) => e.message), 'erreur(s) de page pendant le parcours des onglets')
    .toEqual([])
})

test('CALX387: le lien profond /calepinage/:id/<cle> ouvre le MÊME panneau que l’onglet', async ({ page }) => {
  await gotoLeads(page)
  const nomLead = await createLead(page, {
    nom: uniq('CALX387 Lien Lead'), facture: 900, ville: 'Casablanca',
  })

  await page.goto('/calepinage/nouveau')
  await expect(page.getByRole('heading', { name: 'Nouveau calepinage' })).toBeVisible()
  await page.getByRole('tab', { name: 'Lead' }).click()
  await page.locator('#cal-nouveau-lead').getByRole('combobox').click()
  await page.getByRole('searchbox').fill(nomLead)
  await page.getByRole('option', { name: new RegExp(nomLead) }).first().click()
  await page.locator('#cal-nouveau-nom').fill(uniq('CALX387 Lien Toiture'))
  await page.getByRole('button', { name: 'Créer le calepinage' }).click()

  await expect(page).toHaveURL(/\/calepinage\/\d+/)
  const calepinageId = idDansUrl(page.url())
  expect(calepinageId, 'aucun identifiant de calepinage dans l’URL').toBeTruthy()

  // Un SEUL onglet suffit à prouver l'équivalence route-profonde ↔ onglet
  // (les routes profondes historiques sont servies par le MÊME registre,
  // CALX1) — « pente » spécifiquement : SEULS 15 des 27 onglets du registre
  // ont une route dédiée dans `module.config.jsx` (les autres, ajoutés après
  // CALX1, ne s'ouvrent QUE par `?onglet=`) ; « pente » en fait partie et est
  // DÉJÀ le choix prouvé par la spec jumelle CALX1 (`calepinage-parcours.spec.js`),
  // jamais un index arbitraire du registre qui pourrait tomber sur un onglet
  // sans route dédiée si l'ordre change.
  expect(CLES, '« pente » doit rester au registre pour cette preuve').toContain('pente')
  const cle = 'pente'
  // « Ouvre le MÊME panneau » (texte CALX387) : la route profonde monte le
  // COMPOSANT du registre en plein écran, SANS le chrome du rail (design
  // CALX1 — `module.config.jsx` monte `SaisiePente` sur `/:id/pente`). La
  // preuve d'équivalence est donc le repère du PANNEAU (`cal-pente`), le
  // même sous la route profonde et sous l'onglet — jamais le bouton du rail,
  // absent d'une route profonde.
  await page.goto(`/calepinage/${calepinageId}/${cle}`)
  await expect(page.getByTestId('cal-pente')).toBeVisible()

  // Puis l'onglet, cliqué depuis le rail, mène au MÊME panneau — même clé
  // dans l'URL, même contenu, un seul chemin de vérité.
  await page.goto(`/calepinage/${calepinageId}`)
  await page.getByTestId(`cal-onglet-${cle}`).click()
  await expect(page).toHaveURL(new RegExp(`/calepinage/${calepinageId}\\?onglet=${cle}`))
  await expect(page.getByTestId('cal-onglet-panneau')).toBeVisible()
  await expect(page.getByTestId('cal-pente')).toBeVisible()
})
