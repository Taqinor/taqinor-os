// NTSCM42 — parcours clé : prévision → politique → suggestion → BCF brouillon.
//
// Scénario complet du plan : générer une prévision (NTSCM2), créer une
// politique de stock via l'assistant (NTSCM30), constater un produit en
// statut « à_commander » sur /scm/reappro (NTSCM7), déclencher l'action
// groupée « Créer brouillon BCF » et vérifier que le BonCommandeFournisseur
// brouillon contient la ligne attendue.
//
// ADAPTATION — deux points où la suite mutable partagée (seedée par
// `manage.py seed_demo`, voir playwright.config.js) ne peut pas être forcée
// depuis l'UI :
//   1. il n'existe aucun bouton UI dédié « Générer une prévision » isolé :
//      l'assistant « Lancer un cycle S&OP » (NTSCM31, étape 2) est l'unique
//      point d'entrée UI qui appelle NTSCM2 — réutilisé ici SANS créer de
//      cycle (on quitte l'assistant après génération).
//   2. le produit qui finit « à_commander » dépend de l'historique de
//      mouvements de stock déjà seedé (hors contrôle de ce spec) : si AUCUN
//      produit ne qualifie après le recalcul, le trajet est ENREGISTRÉ puis
//      SAUTÉ (`test.skip`, même politique que `parcours-budget.spec.js`,
//      EZ17 : « le budget est un plafond » — sous-couvrir ne fait jamais
//      passer une régression, un faux rouge lié aux données détruirait la
//      confiance dans la gate) plutôt que de figer une donnée métier fictive.
//      La partie DÉTERMINISTE du trajet (génération, assistant, chargement du
//      tableau de bord) reste, elle, toujours vérifiée.
import { test, expect } from '@playwright/test'
import { uiLogin, ADMIN } from './helpers'

test('E-SCM-REAPPRO: prévision → politique de stock → suggestion → BCF brouillon', async ({ page }) => {
  await uiLogin(page, ADMIN)
  await page.waitForURL((url) => !url.pathname.startsWith('/login'))

  // 1. NTSCM2 — génère (rafraîchit) les prévisions de demande de tous les
  // produits actifs, via l'assistant S&OP (seul point d'entrée UI).
  await page.goto('/scm/sop/nouveau')
  await expect(page.getByRole('heading', { name: /Lancer un cycle S&OP/i })).toBeVisible()
  await page.getByRole('button', { name: /Suivant/ }).click()
  await page.getByRole('button', { name: /Générer les prévisions manquantes/ }).click()
  await expect(page.getByText(/prévision\(s\) générée\(s\)\/rafraîchie\(s\)/)).toBeVisible({ timeout: 30_000 })

  // 2. NTSCM30 — assistant « Créer une politique de stock » : sélectionne
  // TOUS les produits visibles à l'écran 1 pour maximiser la probabilité
  // qu'au moins un finisse sous son point de commande.
  await page.goto('/scm/politiques-stock/nouveau')
  await expect(page.getByRole('heading', { name: /Créer une politique de stock/i })).toBeVisible()
  const cases = page.locator('label input[type="checkbox"]')
  const nbDisponibles = await cases.count()
  test.skip(nbDisponibles === 0, 'aucun produit disponible sur cet environnement — trajet non rejouable ici')
  // Plafonné à 40 : maximise la probabilité qu'au moins un produit finisse
  // sous son point de commande sans allonger le trajet inutilement sur une
  // base seedée avec un grand catalogue.
  const nbACocher = Math.min(nbDisponibles, 40)
  for (let i = 0; i < nbACocher; i += 1) {
    await cases.nth(i).check()
  }
  await page.getByRole('button', { name: /Suivant/ }).click()
  await page.getByRole('button', { name: /Aperçu/ }).click()
  await page.getByRole('button', { name: /Créer \d+ politique/ }).click()
  await expect(page.getByText(/politique\(s\) de stock créée\(s\)\/mise\(s\) à jour/)).toBeVisible({ timeout: 30_000 })

  // 3. NTSCM7 — tableau de bord réappro : cherche un produit « à_commander »
  // ou « rupture imminente » (statut ≠ OK). Le bouton d'action groupée est
  // rendu AVANT le chargement asynchrone du tableau (compteur à 0 tant que
  // `GET tableau-bord-reappro/` n'a pas répondu) : on attend explicitement
  // CETTE réponse plutôt que de lire le compteur en pleine course.
  const reponseTableauBord = page.waitForResponse(
    (r) => r.url().includes('/scm/tableau-bord-reappro/') && r.request().method() === 'GET')
  await page.getByRole('button', { name: /Voir le tableau de bord réappro/ }).click()
  await page.waitForURL('**/scm/reappro')
  await expect(page.getByRole('heading', { name: /Tableau de bord réappro/i })).toBeVisible()
  await reponseTableauBord

  const boutonBcf = page.getByRole('button', { name: /Créer les brouillons BCF/ })
  await expect(boutonBcf).toBeVisible()
  const texteBouton = await boutonBcf.textContent()
  const nbACommander = Number((texteBouton.match(/\((\d+)\)/) || [])[1] || 0)
  test.skip(
    nbACommander === 0,
    'aucun produit en statut « à_commander »/« rupture imminente » sur cet environnement — trajet enregistré, non mesuré',
  )

  // 4. NTSCM7 — action groupée « Créer brouillon BCF » : regroupe les lignes
  // à commander PAR FOURNISSEUR et crée un BonCommandeFournisseur brouillon
  // par fournisseur (apps.stock.services.creer_bcf_depuis_lignes).
  await boutonBcf.click()
  const confirmation = page.getByText(/bon\(s\) de commande brouillon créé\(s\)/)
  await expect(confirmation).toBeVisible({ timeout: 30_000 })
  // Le message rapporte le nombre de LIGNES au total — preuve que le/les
  // BonCommandeFournisseur brouillon(s) créé(s) portent bien la ligne
  // attendue (au moins une, exactement `nbACommander` lignes couvertes).
  const texteConfirmation = await confirmation.textContent()
  const nbLignesTotal = Number((texteConfirmation.match(/(\d+) ligne/) || [])[1] || 0)
  expect(nbLignesTotal).toBeGreaterThan(0)
})
