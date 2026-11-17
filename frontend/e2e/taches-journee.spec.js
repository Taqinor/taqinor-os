// TCH133 (1/2) — Tâches, bout en bout : LA JOURNÉE (Aujourd'hui) sur la vraie pile.
//
// Parcours joués ici (spec-7 « Parcours chiffrés » 3, 4, 7, 15 ; accessibilité (1) et (8)) :
//   Garder ces N → focus sur « Prévu » → ★ (3 au plus) → cocher (annonce « Fait : … », Annuler) → Reporter → Alléger.
// NON joués ici, parce qu'ils demandent l'horloge ou un push : le bilan d'hier (carte avant 12 h), la carte de
// 15 h, le rappel reçu — ils sont rejoués en ACCEPTATION EN DIRECT (TCH137, règle 3-bis), jamais en CI.
//
// Chaque test repart d'un compte effacé (`reinitialiser`) et crée ses propres tâches (titres uniques) : les
// tests sont indépendants de l'ordre et rejouables.
import { test, expect } from '@playwright/test'
import {
  annonce, attendreAujourdhui, creerProjet, creerTaches, jourServeur, ligne, lireTache, ouvrirActions,
  reinitialiser, section, titreUnique, toast,
} from './taches-aides'

/** Un projet actif de 4 tâches sans jour : Proposé les montre toutes (objectif 5, rien de gardé). */
async function journeeDeQuatre(page) {
  await reinitialiser(page)
  const projet = await creerProjet(page, titreUnique('Chantier'))
  const titres = ['Appeler le fournisseur', 'Commander les rails', 'Relire le contrat', 'Envoyer le devis']
    .map((t) => titreUnique(t))
  const taches = await creerTaches(page, titres, { projet_id: projet.id })
  return { projet, titres, taches }
}

test.describe('Tâches — la journée', () => {
  test('Garder ces 4 : tout passe dans Prévu, le focus y va, la progression ne bouge pas', async ({ page }) => {
    const { titres, taches } = await journeeDeQuatre(page)
    await attendreAujourdhui(page)

    // Proposé : les 4 tâches du projet, rien de gardé, 0 sur l'objectif par défaut (5)
    await expect(page.getByRole('button', { name: /^0 sur 5 faites\. Détail de la journée$/ })).toBeVisible()
    for (const tache of taches) await expect(ligne(page, tache.id)).toBeVisible()
    await expect(section(page, 'Prévu')).toHaveCount(0)

    await page.getByRole('button', { name: 'Garder ces 4', exact: true }).first().click()

    // « Garder » : toast, invite ★, focus sur Prévu (critère 8 de spec-7 « Accessibilité »)
    await expect(toast(page)).toContainText('4 gardées')
    await expect(section(page, 'Prévu')).toBeVisible()
    await expect(section(page, 'Prévu')).toBeFocused()
    await expect(page.getByText('Touche ★ pour ton essentiel')).toBeVisible()
    for (const titre of titres) await expect(section(page, 'Prévu').getByText(titre, { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: /^0 sur 5 faites\. Détail de la journée$/ })).toBeVisible()

    // côté serveur : les 4 sont prévues AUJOURD'HUI (le jour du serveur), aucune n'est faite
    const jour = await jourServeur(page)
    for (const tache of taches) {
      const lue = await lireTache(page, tache.id)
      expect(lue.jour_prevu, `« ${tache.titre} » prévue aujourd'hui`).toBe(jour)
      expect(lue.statut).toBe('a_faire')
    }
  })

  test('★★★ : trois essentielles au plus, la 4e est refusée à voix haute', async ({ page }) => {
    const { titres } = await journeeDeQuatre(page)
    await attendreAujourdhui(page)
    await page.getByRole('button', { name: 'Garder ces 4', exact: true }).first().click()
    await expect(section(page, 'Prévu')).toBeVisible()

    for (const titre of titres.slice(0, 3)) {
      await section(page, 'Prévu').getByRole('checkbox', { name: `Essentielle : ${titre}` }).click()
      await expect(section(page, 'Essentiel').getByText(titre, { exact: true })).toBeVisible()
    }
    // la progression lit « essentiel 0 sur 3 » (aucune faite)
    await expect(page.getByRole('button', { name: /^0 sur 5 faites, essentiel 0 sur 3\. Détail de la journée$/ })).toBeVisible()

    // la 4e ★ : refusée, la ligne reste dans Prévu et la région `role=status` le dit
    await section(page, 'Prévu').getByRole('checkbox', { name: `Essentielle : ${titres[3]}` }).click()
    await expect(annonce(page)).toContainText('3 au plus.')
    await expect(section(page, 'Prévu').getByText(titres[3], { exact: true })).toBeVisible()
    await expect(section(page, 'Essentiel').getByText(titres[3], { exact: true })).toHaveCount(0)
  })

  test('Cocher : « Fait : … » est annoncé, la progression avance, Annuler défait, le serveur suit', async ({ page }) => {
    const { titres, taches } = await journeeDeQuatre(page)
    await attendreAujourdhui(page)
    await page.getByRole('button', { name: 'Garder ces 4', exact: true }).first().click()
    await expect(section(page, 'Prévu')).toBeVisible()
    await section(page, 'Prévu').getByRole('checkbox', { name: `Essentielle : ${titres[0]}` }).click()
    await section(page, 'Prévu').getByRole('checkbox', { name: `Essentielle : ${titres[1]}` }).click()
    await expect(page.getByRole('button', { name: /^0 sur 5 faites, essentiel 0 sur 2\./ })).toBeVisible()

    const caseA = ligne(page, taches[0].id).getByRole('checkbox', { name: `Marquer « ${titres[0]} » comme faite` })
    await caseA.click()
    await expect(caseA).toBeChecked()
    // critère (1) : le lecteur d'écran entend « Fait : <titre> » ; la progression lit 1 sur 5, essentiel 1 sur 2
    await expect(annonce(page)).toContainText(`Fait : ${titres[0]}`)
    await expect(page.getByRole('button', { name: /^1 sur 5 faites, essentiel 1 sur 2\./ })).toBeVisible()
    await expect(toast(page)).toContainText('Faite')
    await expect.poll(async () => (await lireTache(page, taches[0].id)).statut).toBe('fait')

    // Annuler : la case revient, la progression aussi, le serveur rouvre la tâche
    await toast(page).getByRole('button', { name: 'Annuler' }).click()
    await expect(caseA).not.toBeChecked()
    await expect(page.getByRole('button', { name: /^0 sur 5 faites, essentiel 0 sur 2\./ })).toBeVisible()
    await expect.poll(async () => (await lireTache(page, taches[0].id)).statut).toBe('a_faire')
  })

  test('Reporter : la ligne dit où elle va, le serveur la prévoit plus tard, Annuler la rend', async ({ page }) => {
    const { titres, taches } = await journeeDeQuatre(page)
    await attendreAujourdhui(page)
    await page.getByRole('button', { name: 'Garder ces 4', exact: true }).first().click()
    await expect(section(page, 'Prévu')).toBeVisible()

    const cible = ligne(page, taches[3].id)
    await ouvrirActions(page, cible, titres[3])
    await page.getByRole('menuitem', { name: /^Reporter à / }).click()

    await expect(cible).toContainText('→')
    await expect(toast(page)).toContainText('Reportée à')
    await expect(annonce(page)).toContainText('Reportée à')
    const jour = await jourServeur(page)
    await expect.poll(async () => (await lireTache(page, taches[3].id)).jour_prevu > jour).toBeTruthy()

    await toast(page).getByRole('button', { name: 'Annuler' }).click()
    await expect(cible).not.toContainText('→')
    await expect.poll(async () => (await lireTache(page, taches[3].id)).jour_prevu).toBe(jour)
  })

  test('Alléger ma journée : on coche ce qu\'on GARDE, le reste retourne aux projets sans report', async ({ page }) => {
    const { titres, taches } = await journeeDeQuatre(page)
    await attendreAujourdhui(page)
    await page.getByRole('button', { name: 'Garder ces 4', exact: true }).first().click()
    await expect(section(page, 'Prévu')).toBeVisible()

    await page.getByRole('button', { name: "Plus d'actions" }).click()
    await page.getByRole('menuitem', { name: 'Alléger ma journée' }).click()
    const feuille = page.getByRole('dialog', { name: 'Alléger ma journée' })
    await expect(feuille).toBeVisible()
    // rien n'est coché d'avance : le bouton ne propose rien tant qu'on n'a rien gardé
    for (const titre of titres) await expect(feuille.getByRole('checkbox', { name: `Sélectionner : ${titre}` })).not.toBeChecked()
    await expect(feuille.getByRole('button', { name: 'Garder ces 0' })).toBeVisible()

    await feuille.getByRole('checkbox', { name: `Sélectionner : ${titres[1]}` }).click()
    await feuille.getByRole('button', { name: 'Garder celle-ci' }).click()

    await expect(feuille).toHaveCount(0)
    await expect(toast(page)).toContainText('3 retournées aux projets')
    // la tâche gardée reste dans Prévu, les trois autres ont quitté la journée
    await expect(section(page, 'Prévu').getByText(titres[1], { exact: true })).toBeVisible()
    for (const titre of [titres[0], titres[2], titres[3]]) {
      await expect(section(page, 'Prévu').getByText(titre, { exact: true })).toHaveCount(0)
    }
    // côté serveur : retournées sans jour et SANS compter de report ; la gardée reste prévue aujourd'hui
    const jour = await jourServeur(page)
    for (const rang of [0, 2, 3]) {
      const lue = await lireTache(page, taches[rang].id)
      expect(lue.jour_prevu, `« ${titres[rang]} » retournée à son projet`).toBeNull()
      expect(lue.reports, `« ${titres[rang]} » : aucun report compté`).toBe(0)
    }
    expect((await lireTache(page, taches[1].id)).jour_prevu).toBe(jour)
  })
})
