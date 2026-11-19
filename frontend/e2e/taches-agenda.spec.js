// R2 (lane L7) — Tâches, bout en bout : L'AGENDA et « Planifier ma semaine » sur la vraie pile.
//
// Mesures faites DANS le navigateur (CSS réel) que les tests de composants (jsdom) ne voient pas :
//   · R2-104 — sur iPhone (tactile), la case d'un bloc horaire est un rond, pas une pilule de 44 px.
//
// Chaque test repart d'un compte effacé (`reinitialiser`) et crée ses propres tâches (titres uniques).
import { test, expect } from '@playwright/test'
import { creerTaches, jourServeur, ouvrirEcran, reinitialiser, titreUnique } from './taches-aides'

const IPHONE = { viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true }

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
})
