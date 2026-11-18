// TCH152 — Tâches, bout en bout : AUJOURD'HUI AU BUREAU (1440 × 900) sur la vraie pile.
//
// Parcours joués ici (maquette `ecran-aujourdhui-matin.html`, spec-3 §1 « Placer à une heure » : 1 glisser) :
//   les trois colonnes (Mes projets · la liste · l'Agenda du jour) mesurées à 1440 px, puis glisser une ligne sur une
//   heure de l'Agenda → `planifier/` → « Placée à 10:00 · Annuler » → Annuler.
// NON joué ici : l'iPhone (aucune colonne : `Aujourdhui.test.jsx` / `ColonneBureau.test.jsx`, avec `matchMedia`),
// la ligne « maintenant » (horloge) — acceptation en direct.
//
// Le compte est effacé au départ (`reinitialiser`) et la spec crée elle-même son projet et sa tâche (titres uniques) :
// rejouable, indépendante de l'ordre des autres specs.
import { test, expect } from '@playwright/test'
import {
  attendreAujourdhui, creerProjet, creerTaches, jourServeur, ligne, lireTache, reinitialiser, titreUnique, toast,
} from './taches-aides'

test.use({ viewport: { width: 1440, height: 900 } })

const HEURE = '10:00'
/** Les créneaux de la grille sont l'un après l'autre toutes les 30 min depuis 07:00 : 10:00 est le septième (rang 6). */
const RANG_10H = 6

async function journeeAvecUneTache(page) {
  await reinitialiser(page)
  const jour = await jourServeur(page)
  const projet = await creerProjet(page, titreUnique('Chantier'))
  const [tache] = await creerTaches(page, [titreUnique('Appeler le fournisseur')], { projet_id: projet.id, jour_prevu: jour })
  await attendreAujourdhui(page)
  return { jour, projet, tache }
}

test.describe('Tâches — Aujourd\'hui au bureau', () => {
  test('à 1440 px : Mes projets à gauche, la liste au centre, l\'Agenda du jour à droite, sans défilement horizontal', async ({ page }) => {
    const { projet, tache } = await journeeAvecUneTache(page)
    const agenda = page.getByRole('complementary', { name: 'Agenda du jour' })
    const projets = page.getByRole('navigation', { name: 'Mes projets' })
    const laLigne = ligne(page, tache.id)
    await expect(agenda).toBeVisible()
    await expect(projets).toBeVisible()
    await expect(laLigne).toBeVisible()
    await expect(projets.getByRole('link', { name: new RegExp(projet.nom) })).toBeVisible()
    await expect(agenda.getByText('Glisse une tâche sur un créneau pour lui donner une heure.')).toBeVisible()

    const [boiteAgenda, boiteProjets, boiteLigne] = await Promise.all([agenda.boundingBox(), projets.boundingBox(), laLigne.boundingBox()])
    expect(boiteAgenda.width, "l'Agenda du jour fait une colonne d'environ 380 px").toBeGreaterThanOrEqual(340)
    expect(boiteAgenda.width).toBeLessThanOrEqual(420)
    expect(boiteProjets.x + boiteProjets.width, 'Mes projets est à gauche de la liste').toBeLessThanOrEqual(boiteLigne.x + 1)
    expect(boiteAgenda.x, "l'Agenda est à droite de la liste").toBeGreaterThanOrEqual(boiteLigne.x + boiteLigne.width - 1)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'aucun défilement horizontal').toBe(true)
  })

  test('glisser une ligne sur 10:00 : planifier/ écrit l\'heure, le toast « Placée à 10:00 », Annuler la retire', async ({ page }) => {
    const { jour, tache } = await journeeAvecUneTache(page)
    const laLigne = ligne(page, tache.id)
    await expect(laLigne).toBeVisible()
    await expect(laLigne.locator('.heure')).toHaveCount(0)
    expect((await lireTache(page, tache.id)).heure_debut).toBeNull()

    const creneau = page.locator('.tch-bureau-agenda .ag-creneau-vide').nth(RANG_10H)
    await laLigne.dragTo(creneau, { sourcePosition: { x: 8, y: 6 } })

    await expect(toast(page)).toContainText(`Placée à ${HEURE}`)
    await expect(laLigne.locator('.heure')).toHaveText(HEURE)
    await expect(page.locator('.tch-bureau-agenda').getByRole('checkbox', { name: `Fait : ${tache.titre}` })).toBeVisible()
    const posee = await lireTache(page, tache.id)
    expect(posee.jour_prevu, 'toujours aujourd\'hui').toBe(jour)
    expect(posee.heure_debut, 'l\'heure du créneau déposé').toMatch(new RegExp(`^${HEURE}`))

    // le geste de retour : « Annuler » rend la tâche sans heure, ici et sur le serveur
    await toast(page).getByRole('button', { name: 'Annuler' }).click()
    await expect(laLigne.locator('.heure')).toHaveCount(0)
    await expect(page.locator('.tch-bureau-agenda').getByRole('checkbox', { name: `Fait : ${tache.titre}` })).toHaveCount(0)
    await expect.poll(async () => (await lireTache(page, tache.id)).heure_debut).toBeNull()
  })
})
