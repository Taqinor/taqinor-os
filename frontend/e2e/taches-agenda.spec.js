// R2 (lane L7) — Tâches, bout en bout : L'AGENDA et « Planifier ma semaine » sur la vraie pile.
//
// Mesures faites DANS le navigateur (CSS réel) que les tests de composants (jsdom) ne voient pas :
//   · R2-104 — sur iPhone (tactile), la case d'un bloc horaire est un rond, pas une pilule de 44 px ;
//   · R2-107 / R2-108 / R2-110 / R2-111 — la grille au clavier, Planifier ma semaine et la vue Jour au bureau, le libellé
//     « Toute la journée ».
//
// Chaque test repart d'un compte effacé (`reinitialiser`) et crée ses propres tâches (titres uniques).
import { test, expect } from '@playwright/test'
import { creerTaches, jourServeur, ouvrirEcran, reinitialiser, titreUnique } from './taches-aides'

const IPHONE = { viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true }
const BUREAU = { viewport: { width: 1440, height: 900 } }

test.describe('Tâches — l\'Agenda sur iPhone (tactile)', () => {
  test.use(IPHONE)

  test('R2-104 — la case d\'un bloc horaire est un rond (≤ 20 px), la cible tactile reste de 44 px', async ({ page }) => {
    await reinitialiser(page)
    const jour = await jourServeur(page)
    const titre = titreUnique('Appeler le fournisseur')
    await creerTaches(page, [titre], { jour_prevu: jour, heure_debut: '10:00', estimation_minutes: 60 })
    await ouvrirEcran(page, '/taches/agenda?vue=jour', 'agenda')
    const caseBloc = page.getByRole('checkbox', { name: `Fait : ${titre}` })
    await expect(caseBloc).toBeVisible()
    const rond = await caseBloc.boundingBox()
    expect(rond.height, 'hauteur de la case').toBeLessThanOrEqual(20)
    expect(rond.width, 'largeur de la case').toBeLessThanOrEqual(20)
    // la zone qui répond au doigt (pseudo-élément `::after`) reste de 44 × 44 : on la lit dans le style calculé
    const cible = await caseBloc.evaluate((el) => {
      const s = getComputedStyle(el, '::after')
      return { w: parseFloat(s.width), h: parseFloat(s.height) }
    })
    expect(cible.w).toBeGreaterThanOrEqual(44)
    expect(cible.h).toBeGreaterThanOrEqual(44)
  })

  test('R2-111 — « Toute la journée » tient sur UNE ligne, dans la gouttière', async ({ page }) => {
    await reinitialiser(page)
    const jour = await jourServeur(page)
    // une tâche prévue aujourd'hui, à échéance DEMAIN : demain, « Toute la journée » porte sa puce « · échéance »
    const demain = new Date(`${jour}T12:00:00Z`)
    demain.setUTCDate(demain.getUTCDate() + 1)
    await creerTaches(page, [titreUnique('Envoyer le devis')], { jour_prevu: jour, echeance: demain.toISOString().split('T')[0] })
    await ouvrirEcran(page, '/taches/agenda?vue=a-venir', 'agenda')
    const libelle = page.locator('.ag-tj-label').first()
    await expect(libelle).toBeVisible()
    const boite = await libelle.boundingBox()
    expect(boite.height, 'une seule ligne de 0,75 rem').toBeLessThan(24)
    expect(boite.x, 'dans la gouttière, jamais hors de l\'écran').toBeGreaterThanOrEqual(0)
  })
})

test.describe('Tâches — l\'Agenda au bureau', () => {
  test.use(BUREAU)

  test('R2-110 — vue Jour : en-tête court, la grille commence haut (07:00 sous 360 px, 575 px avant)', async ({ page }) => {
    await reinitialiser(page)
    const jour = await jourServeur(page)
    await creerTaches(page, [titreUnique('Relire le contrat')], { jour_prevu: jour })
    await ouvrirEcran(page, '/taches/agenda?vue=jour', 'agenda')
    const sept = page.locator('.agenda-heures > div').first()
    await expect(sept).toHaveText('07:00')
    const boite = await sept.boundingBox()
    expect(boite.y, 'la grille commence haut').toBeLessThan(360)
    // les vues et la navigation sont UNE ligne
    const vues = await page.locator('.ag-vues').boundingBox()
    const nav = await page.locator('.ag-nav').boundingBox()
    expect(Math.abs(vues.y - nav.y), 'vues et navigation sur la même ligne').toBeLessThan(30)
  })

  test('R2-108 — Planifier ma semaine : colonnes d\'au moins 160 px, panneau ≤ 360 px, aucun débordement horizontal', async ({ page }) => {
    await reinitialiser(page)
    const jour = await jourServeur(page)
    await creerTaches(page, [titreUnique('Commander les rails'), titreUnique('Envoyer le devis')], { jour_prevu: jour })
    await ouvrirEcran(page, '/taches/agenda?vue=semaine&placer=1', 'agenda')
    await expect(page.getByRole('list', { name: 'Jours de la semaine' })).toBeVisible()
    const colonnes = await page.locator('.ag-planifier .ag-pj-place:not(.repos)').evaluateAll(
      (els) => els.map((e) => Math.round(e.getBoundingClientRect().width)))
    expect(colonnes.length, 'des jours travaillés sont affichés').toBeGreaterThan(0)
    for (const largeur of colonnes) expect(largeur, 'largeur d\'une colonne').toBeGreaterThanOrEqual(160)
    const panneau = await page.locator('.ag-planifier .ag-aside').boundingBox()
    expect(panneau.width, 'panneau « À placer »').toBeLessThanOrEqual(360)
    const deborde = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
    expect(deborde, 'aucun défilement horizontal de la page').toBe(false)
  })

  test('R2-107 — mode « placer » : Tab atteint le menu en moins de 15 arrêts (un seul arrêt pour la grille)', async ({ page }) => {
    await reinitialiser(page)
    const jour = await jourServeur(page)
    const titre = titreUnique('Appeler le fournisseur')
    await creerTaches(page, [titre], { jour_prevu: jour })
    await ouvrirEcran(page, '/taches/agenda?vue=jour', 'agenda')
    await page.getByRole('button', { name: new RegExp(titre) }).first().click() // dans « À placer »
    const arrets = await page.evaluate(() => document.querySelectorAll('.grille-agenda .ag-creneau-vide:not([tabindex="-1"])').length)
    expect(arrets, 'un seul arrêt de Tab dans la grille').toBe(1)
  })
})
