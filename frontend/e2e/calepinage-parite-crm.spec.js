// CAL222 / CALX47 / ACAL904 — LA PORTE DU CALEPINAGE DEPUIS LA FICHE DU LEAD.
//
// HISTOIRE. CAL222 gelait (décision D2) le geste `toiture-3d` du menu « ⋯ » de
// l'IdentityRail (« Concevoir la toiture (3D) ») ; CALX47 avait ajouté à côté
// une entrée « Ouvrir dans le module Calepinage ». ACAL904 (constats
// T1-S1-001 / T1-S1-027 : deux portes concurrentes, et la première renvoyait
// un 409 de devis automatique sur un lead sans facture) a retiré ces DEUX
// entrées du menu au profit d'UN bouton visible sans menu, « Dessiner le
// toit », qui ouvre le calepinage du lead (D-ACAL-12 : le même à chaque fois).
//
// Les quatre branches de `ouvrirConceptionToiture` (`LeadWorkspace.jsx`) n'ont
// plus de déclencheur dans le rail : elles restent prouvées par le test
// unitaire `features/crm/workspace/LeadWorkspace.toiture3d.test.jsx`. Cette
// spec prouve, sur le DOM RÉEL, la porte qui les remplace.
//
// POURQUOI LA RÉPONSE EST INTERCEPTÉE. `POST calepinages/depuis-lead/` est
// IDEMPOTENT côté serveur et rend `{calepinage, reference, nom, lead, cree}`.
// Fabriquer l'état de base réel (lead + calepinage) demanderait de muter la
// base partagée et rendrait la spec dépendante de l'ordre d'exécution —
// exactement ce que la configuration (`workers: 1`) demande d'éviter. On
// intercepte donc CETTE route et on vérifie le COMPORTEMENT DE L'ÉCRAN :
// l'atelier du module s'ouvre sur l'identifiant RENDU, jamais sur un
// identifiant deviné. Aucune temporisation : chaque attente porte sur une
// condition observable.
//
// L'ATELIER S'OUVRE DANS UN NOUVEL ONGLET (comme la fiche client, LW14) : la
// spec attend donc l'événement `page` du contexte, jamais une navigation de
// l'onglet courant.
import { test, expect } from '@playwright/test'
import { uniq, gotoLeads, createLead, openLead } from './helpers'

const ROUTE_DEPUIS_LEAD = '**/api/django/calepinage/calepinages/depuis-lead/'
const ROUTE_AUTO = '**/api/django/ventes/devis/auto/'

/** Un lead frais, ouvert dans son espace de travail. */
async function leadOuvert(page, etiquette, champs = { facture: 900 }) {
  await gotoLeads(page)
  const nom = await createLead(page, {
    nom: uniq(etiquette), ville: 'Casablanca', ...champs,
  })
  await openLead(page, nom)
  return nom
}

/** Le bouton visible du rail (ACAL904) — son libellé peut porter « 📍 ». */
function boutonDessinerLeToit(page) {
  return page.getByRole('button', { name: /^Dessiner le toit/ }).first()
}

/** Le geste : un clic sur « Dessiner le toit », sans ouvrir de menu. */
async function dessinerLeToit(page) {
  await boutonDessinerLeToit(page).click()
}

/** Sert la réponse idempotente de `depuis-lead/` (même id à chaque appel). */
async function servirCalepinage(page, id) {
  let appels = 0
  await page.route(ROUTE_DEPUIS_LEAD, (route) => {
    appels += 1
    return route.fulfill({
      status: appels === 1 ? 201 : 200,
      contentType: 'application/json',
      body: JSON.stringify({
        calepinage: id, reference: `CAL-2609-${id}`,
        nom: 'Calepinage ACAL904', lead: 1, cree: appels === 1,
      }),
    })
  })
}

test.describe('ACAL904 — une seule porte visible : « Dessiner le toit »', () => {
  test('le bouton est visible sans menu ; plus d’entrées jumelles dans « ⋯ »', async ({ page }) => {
    await leadOuvert(page, 'ACAL904 Porte')

    await expect(boutonDessinerLeToit(page)).toBeVisible()
    await page.locator('.lw-rail-actions-more').first().click()
    await expect(page.getByRole('menu')).toBeVisible()
    await expect(page.getByRole('menuitem', { name: /Concevoir la toiture/ }))
      .toHaveCount(0)
    await expect(page.getByRole('menuitem', { name: /Ouvrir dans le module Calepinage/ }))
      .toHaveCount(0)
  })

  test('un lead SANS facture ouvre le toit, jamais un devis automatique', async ({ page, context }) => {
    await leadOuvert(page, 'ACAL904 Sans facture', {})
    await servirCalepinage(page, 9100)
    let devisAuto = 0
    await page.route(ROUTE_AUTO, (route) => {
      devisAuto += 1
      return route.fallback()
    })

    const ongletPromis = context.waitForEvent('page')
    await dessinerLeToit(page)
    const atelier = await ongletPromis
    await expect(atelier).toHaveURL(/\/calepinage\/9100/)
    expect(devisAuto).toBe(0)
  })
})

test.describe('CALX47 — ouvrir le module Calepinage depuis la fiche du lead', () => {
  test('la porte ouvre l’atelier du MODULE, sur l’id rendu', async ({ page, context }) => {
    await leadOuvert(page, 'CALX47 Module')
    await servirCalepinage(page, 9101)

    const ongletPromis = context.waitForEvent('page')
    await dessinerLeToit(page)
    const atelier = await ongletPromis
    await expect(atelier).toHaveURL(/\/calepinage\/9101/)
  })

  test('deux ouvertures successives mènent au MÊME calepinage', async ({ page, context }) => {
    await leadOuvert(page, 'CALX47 Idempotent')
    // Le serveur rend le MÊME identifiant au second appel (`cree: false`).
    await servirCalepinage(page, 9102)

    const premier = context.waitForEvent('page')
    await dessinerLeToit(page)
    await expect(await premier).toHaveURL(/\/calepinage\/9102/)

    const second = context.waitForEvent('page')
    await dessinerLeToit(page)
    await expect(await second).toHaveURL(/\/calepinage\/9102/)
  })

  test('refus serveur : le motif est DIT, et rien n’est ouvert', async ({ page }) => {
    await leadOuvert(page, 'CALX47 Refus')
    const messageServeur = 'Lead introuvable (#999).'
    await page.route(ROUTE_DEPUIS_LEAD, (route) => route.fulfill({
      status: 400,
      contentType: 'application/json',
      body: JSON.stringify({ lead: messageServeur }),
    }))

    await dessinerLeToit(page)

    // Le message du SERVEUR, précédé du geste qu'il concerne.
    await expect(page.getByText(/Module Calepinage/)).toBeVisible()
    await expect(page.getByRole('alert').filter({ hasText: /Lead introuvable/ })).toBeVisible()
    await expect(page).not.toHaveURL(/\/calepinage\//)
  })
})
