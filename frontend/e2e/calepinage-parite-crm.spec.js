// CAL222 — PARITÉ CRM : le geste existant ne bouge pas.
//
// LA SÉMANTIQUE DE RÉFÉRENCE est `ouvrirConceptionToiture`
// (`features/crm/workspace/LeadWorkspace.jsx`), déclenchée par l'action
// `toiture-3d` du menu « ⋯ » de l'IdentityRail (« Concevoir la toiture (3D) ») :
//
//   1 brouillon  → ouvre DIRECTEMENT `/ventes/devis/<id>/design` ;
//   N brouillons → n'en devine AUCUN : le commercial départage
//                  (`ChoisirDevisPourDesign`, `data-testid=pv22-choix-devis`) ;
//   0 brouillon  → en CRÉE un via `POST /ventes/devis/auto/` puis l'ouvre ;
//   422          → le message FRANÇAIS du serveur, tel quel, et la seule sortie
//                  est le générateur complet (`pv22-devis-auto-impossible`).
//
// La décision D2 du Groupe CAL exige que l'introduction du module autonome ne
// change RIEN à ce geste. Cette spec l'exécute sur le DOM RÉEL, après
// l'introduction du module.
//
// POURQUOI LES RÉPONSES SONT INTERCEPTÉES. Les quatre branches dépendent
// entièrement de ce que le serveur répond à `GET /ventes/devis/?lead=<id>` et à
// `POST /ventes/devis/auto/`. Fabriquer quatre états de base de données réels
// (et le 422) demanderait de muter la base partagée et rendrait la spec
// dépendante de l'ordre d'exécution — exactement ce que la configuration
// (`workers: 1`, une seule base semée) demande d'éviter. On intercepte donc ces
// DEUX routes, une branche à la fois, et on vérifie le COMPORTEMENT DE L'ÉCRAN :
// c'est lui, et lui seul, que D2 gèle. Aucune temporisation n'est utilisée —
// chaque attente porte sur une condition observable.
import { test, expect } from '@playwright/test'
import { uniq, gotoLeads, createLead, openLead } from './helpers'

const ROUTE_LISTE = '**/api/django/ventes/devis/?*'
const ROUTE_AUTO = '**/api/django/ventes/devis/auto/'

/** Sert une liste de devis figée pour `GET /ventes/devis/?lead=…`. */
async function servirBrouillons(page, lignes) {
  await page.route(ROUTE_LISTE, (route) => {
    if (route.request().method() !== 'GET') return route.fallback()
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(lignes),
    })
  })
}

/** Le geste de référence : menu « ⋯ » → « Concevoir la toiture (3D) ». */
async function ouvrirConceptionToiture(page) {
  await page.locator('.lw-rail-actions-more').first().click()
  await page.getByRole('menuitem', { name: /Concevoir la toiture/ }).click()
}

/** Un lead frais, ouvert dans son espace de travail. */
async function leadOuvert(page, etiquette) {
  await gotoLeads(page)
  const nom = await createLead(page, {
    nom: uniq(etiquette), facture: 900, ville: 'Casablanca',
  })
  await openLead(page, nom)
  return nom
}

const devis = (id, reference, statut = 'brouillon') => ({
  id, reference, statut, date_creation: '2026-01-05', lead: null,
})

test.describe('CAL222 — les quatre branches de `ouvrirConceptionToiture`', () => {
  test('1 brouillon → ouvre directement sa conception', async ({ page }) => {
    await leadOuvert(page, 'CAL222 Un')
    await servirBrouillons(page, [devis(4242, 'DEV-CAL222-1')])

    await ouvrirConceptionToiture(page)

    // Ouverture DIRECTE : ni choix, ni dialogue de blocage.
    await expect(page).toHaveURL(/\/ventes\/devis\/4242\/design/)
    await expect(page.getByTestId('pv22-choix-devis')).toHaveCount(0)
    await expect(page.getByTestId('pv22-devis-auto-impossible')).toHaveCount(0)
  })

  test('N brouillons → le commercial départage, aucun n’est deviné', async ({ page }) => {
    await leadOuvert(page, 'CAL222 Plusieurs')
    await servirBrouillons(page, [
      devis(4243, 'DEV-CAL222-A'), devis(4244, 'DEV-CAL222-B'),
    ])

    await ouvrirConceptionToiture(page)

    const choix = page.getByTestId('pv22-choix-devis')
    await expect(choix).toBeVisible()
    // Mode strict : DEUX entrées portent un libellé de devis. On les apparie
    // toutes les deux avant d'en choisir une.
    await expect(choix.getByRole('button', { name: /DEV-CAL222-A/ })).toBeVisible()
    await expect(choix.getByRole('button', { name: /DEV-CAL222-B/ })).toBeVisible()
    // Et surtout : RIEN n'a été ouvert tant que le choix n'est pas fait.
    await expect(page).not.toHaveURL(/\/design/)

    await choix.getByRole('button', { name: /DEV-CAL222-B/ }).click()
    await expect(page).toHaveURL(/\/ventes\/devis\/4244\/design/)
  })

  test('0 brouillon → en crée un, puis l’ouvre', async ({ page }) => {
    await leadOuvert(page, 'CAL222 Zero')
    await servirBrouillons(page, [])
    await page.route(ROUTE_AUTO, (route) => route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({ id: 4245, reference: 'DEV-CAL222-AUTO' }),
    }))

    await ouvrirConceptionToiture(page)

    await expect(page).toHaveURL(/\/ventes\/devis\/4245\/design/)
    await expect(page.getByTestId('pv22-choix-devis')).toHaveCount(0)
  })

  test('422 → le message du serveur, et la seule sortie est le générateur', async ({ page }) => {
    await leadOuvert(page, 'CAL222 Refus')
    await servirBrouillons(page, [])
    const messageServeur = 'Ce lead n’a ni facture ni ville : aucun devis ne peut être dimensionné.'
    await page.route(ROUTE_AUTO, (route) => route.fulfill({
      status: 422,
      contentType: 'application/json',
      body: JSON.stringify({ detail: messageServeur }),
    }))

    await ouvrirConceptionToiture(page)

    // Le message du SERVEUR, mot pour mot — jamais une phrase réécrite.
    await expect(page.getByTestId('pv22-devis-auto-impossible'))
      .toHaveText(messageServeur)
    await expect(page).not.toHaveURL(/\/design/)

    // La seule sortie : le générateur complet, avec le lead déjà porté.
    await page.getByRole('button', { name: 'Ouvrir le générateur' }).click()
    await expect(page).toHaveURL(/\/ventes\/devis\/nouveau\?lead=/)
  })
})

/* ============================================================================
   CALX47 — LA PORTE NEUVE DU MODULE CALEPINAGE, À CÔTÉ DE L'ANCIENNE.
   ----------------------------------------------------------------------------
   `module.config.jsx` disait noir sur blanc que « cette porte N'EXISTE PAS
   aujourd'hui » : aucun lien de `features/crm` ne menait à `/calepinage/…`.
   CALX47 en ajoute une, dans le MÊME sélecteur d'actions — et la décision D2
   exige que le geste existant n'en soit pas modifié d'un iota : les quatre
   branches ci-dessus restent la preuve de celui-là.

   POURQUOI LA RÉPONSE EST INTERCEPTÉE. `POST calepinages/depuis-lead/` est
   IDEMPOTENT côté serveur et rend `{calepinage, reference, nom, lead, cree}`.
   Fabriquer l'état de base réel (lead + calepinage) demanderait de muter la
   base partagée et rendrait la spec dépendante de l'ordre d'exécution —
   exactement ce que la configuration (`workers: 1`) demande d'éviter. On
   intercepte donc CETTE route et on vérifie le COMPORTEMENT DE L'ÉCRAN :
   l'atelier du module s'ouvre sur l'identifiant RENDU, jamais sur un
   identifiant deviné.

   L'ATELIER S'OUVRE DANS UN NOUVEL ONGLET (comme la fiche client, LW14) : la
   spec attend donc l'événement `page` du contexte, jamais une navigation de
   l'onglet courant. */
const ROUTE_DEPUIS_LEAD = '**/api/django/calepinage/calepinages/depuis-lead/'

/** Le geste NEUF : menu « ⋯ » → « Ouvrir dans le module Calepinage ». */
async function ouvrirModuleCalepinage(page) {
  await page.locator('.lw-rail-actions-more').first().click()
  await page.getByRole('menuitem', { name: /Ouvrir dans le module Calepinage/ })
    .click()
}

test.describe('CALX47 — ouvrir le module Calepinage depuis la fiche du lead', () => {
  test('l’entrée neuve ouvre l’atelier du MODULE, sur l’id rendu', async ({ page, context }) => {
    await leadOuvert(page, 'CALX47 Module')
    await page.route(ROUTE_DEPUIS_LEAD, (route) => route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        calepinage: 9101, reference: 'CAL-2609-9101',
        nom: 'Calepinage CALX47', lead: 1, cree: true,
      }),
    }))

    const ongletPromis = context.waitForEvent('page')
    await ouvrirModuleCalepinage(page)
    const atelier = await ongletPromis
    await expect(atelier).toHaveURL(/\/calepinage\/9101/)
  })

  test('deux ouvertures successives mènent au MÊME calepinage', async ({ page, context }) => {
    await leadOuvert(page, 'CALX47 Idempotent')
    // Le serveur rend le MÊME identifiant au second appel (`cree: false`).
    let appels = 0
    await page.route(ROUTE_DEPUIS_LEAD, (route) => {
      appels += 1
      return route.fulfill({
        status: appels === 1 ? 201 : 200,
        contentType: 'application/json',
        body: JSON.stringify({
          calepinage: 9102, reference: 'CAL-2609-9102',
          nom: 'Calepinage CALX47', lead: 1, cree: appels === 1,
        }),
      })
    })

    const premier = context.waitForEvent('page')
    await ouvrirModuleCalepinage(page)
    await expect(await premier).toHaveURL(/\/calepinage\/9102/)

    const second = context.waitForEvent('page')
    await ouvrirModuleCalepinage(page)
    await expect(await second).toHaveURL(/\/calepinage\/9102/)
  })

  test('l’ancienne entrée ouvre TOUJOURS l’ancien atelier (D2)', async ({ page }) => {
    await leadOuvert(page, 'CALX47 Ancien geste')
    await servirBrouillons(page, [devis(4246, 'DEV-CALX47-1')])

    await ouvrirConceptionToiture(page)

    // Le geste historique n'a pas bougé d'un champ : même écran, même URL.
    await expect(page).toHaveURL(/\/ventes\/devis\/4246\/design/)
    await expect(page).not.toHaveURL(/\/calepinage\//)
  })

  test('refus serveur : le motif est DIT, et rien n’est ouvert', async ({ page }) => {
    await leadOuvert(page, 'CALX47 Refus')
    const messageServeur = 'Lead introuvable (#999).'
    await page.route(ROUTE_DEPUIS_LEAD, (route) => route.fulfill({
      status: 400,
      contentType: 'application/json',
      body: JSON.stringify({ lead: messageServeur }),
    }))

    await ouvrirModuleCalepinage(page)

    // Le message du SERVEUR, précédé du geste qu'il concerne.
    await expect(page.getByText(/Module Calepinage/)).toBeVisible()
    await expect(page.getByText(/Lead introuvable/)).toBeVisible()
    await expect(page).not.toHaveURL(/\/calepinage\//)
  })
})
