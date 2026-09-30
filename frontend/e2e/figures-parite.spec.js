// QA-FIGURES — un même chiffre est IDENTIQUE à l'écran, dans l'API et dans la
// charge utile de la page publique (le PDF et ses marqueurs sont couverts côté
// backend par apps/ventes/tests/test_figures_parite.py, sur le même vocabulaire).
//
// 12 des 30 bugs « chiffre faux » de l'audit QA (docs/decisions/COUV-HOR/
// audit-qa-complet.md) étaient le MÊME chiffre différent d'une surface à
// l'autre, presque tous trouvés par le fondateur. Cette spec crée un devis
// résidentiel AVEC facture par la vraie interface (le chemin factures ÷ barème
// de DEV-202609-0113), lit TOUS les chiffres marqués `data-figure` à l'écran,
// relit le même devis par l'API interne et par la charge utile publique (jeton
// INTERNE : aucune notification, aucun changement de statut), et compare avec
// les tolérances de figures.py. Tout chiffre marqué demain est couvert ici sans
// une ligne de plus.
//
// Pas de `sleep` : l'écran du générateur converge (aperçu local → étude horaire
// serveur) ; `expect.poll` relit l'écran jusqu'à ce qu'il n'y ait plus d'écart
// ou que le délai expire — seul un écart PERSISTANT fait échouer.
import { test, expect } from '@playwright/test'
import {
  gotoLeads, createLead, openLead, generateAutoDevis, uniq,
} from './helpers'
import {
  FIGURE_KEYS, clesDuVocabulairePython, clesInconnues, comparer,
  figuresDepuisDevisApi, figuresDepuisProposition, identitesComparees,
  lireFiguresPage,
} from './figures'

const CREATION_DEVIS = /\/api\/django\/ventes\/devis\/(auto\/)?$/

test('QA-FIGURES : le jumeau JS suit le vocabulaire de figures.py', () => {
  expect(Object.keys(FIGURE_KEYS).sort()).toEqual(clesDuVocabulairePython())
})

test('QA-FIGURES : écran, API et proposition publique affichent les mêmes chiffres', async ({ page }) => {
  test.setTimeout(150_000)
  await gotoLeads(page)
  const name = await createLead(page, { nom: uniq('Figures'), facture: 900 })
  await openLead(page, name)

  // L'identifiant du devis créé, lu sur la RÉPONSE de création (jamais deviné
  // dans une liste partagée par les autres specs).
  const creation = page.waitForResponse((r) => r.request().method() === 'POST'
    && CREATION_DEVIS.test(new URL(r.url()).pathname) && r.status() < 300)
  await generateAutoDevis(page)
  const devisId = (await (await creation).json()).id
  expect(devisId, 'identifiant du devis créé').toBeTruthy()

  // ── Surfaces JSON ─────────────────────────────────────────────────────────
  const detail = await page.request.get(`/api/django/ventes/devis/${devisId}/`)
  expect(detail.ok()).toBeTruthy()
  const apiDevis = figuresDepuisDevisApi(await detail.json())

  // Jeton INTERNE (L-INTPREV) : même charge utile que le client, sans trace
  // d'ouverture, sans notification ; `envoi` absent → aucun changement de statut.
  const lien = await page.request.post(`/api/django/ventes/devis/${devisId}/share-link/`, { data: {} })
  expect(lien.ok()).toBeTruthy()
  const { token_interne: jeton } = await lien.json()
  expect(jeton, 'jeton interne de la proposition').toBeTruthy()
  const data = await page.request.get(`/api/django/public/proposal/${jeton}/data/`)
  expect(data.ok()).toBeTruthy()
  const proposition = figuresDepuisProposition(await data.json())

  // ── Écran : l'éditeur complet du MÊME devis ──────────────────────────────
  await page.getByRole('button', { name: /Édition complète/ }).click()
  await expect(page.locator('[data-figure="total_ttc"]').first()).toBeVisible({ timeout: 45_000 })

  let surfaces = null
  await expect.poll(async () => {
    const ecran = await lireFiguresPage(page)
    surfaces = { ecran, api_devis: apiDevis, proposition }
    return comparer(surfaces)
  }, {
    message: 'le même chiffre diffère entre l\'écran, l\'API et la proposition publique',
    timeout: 30_000,
  }).toEqual([])

  expect(clesInconnues(surfaces.ecran), 'clés data-figure hors vocabulaire').toEqual([])
  // Le test ne prouve rien s'il ne confronte rien : les totaux par option et
  // la production doivent être lus sur au moins deux surfaces.
  const comparees = [...identitesComparees(surfaces)]
  expect(comparees.some((id) => id.startsWith('total_ttc@')), comparees.join(', ')).toBe(true)
  expect(comparees.some((id) => id.startsWith('production_annuelle_kwh')), comparees.join(', ')).toBe(true)
})
