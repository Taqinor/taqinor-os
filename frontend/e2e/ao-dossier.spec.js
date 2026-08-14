// AOF187 (2/3 et 3/3) — Variantes + dossier de dépôt.
//
// Repose sur l'affaire de démonstration plantée par `seed_ao_demo` (AOF186,
// construite depuis les goldens FRDISI d'AOF183) : comparer des variantes et
// assembler un dossier exige un jeu de données riche (3 bâtiments, 28
// obstacles, calepinages déjà calculés) qu'il serait ni réaliste ni stable de
// reconstruire dans un test — voir le commentaire d'AOF187 dans
// ao-parcours.spec.js pour le choix inverse (affaire fraîche) du scénario 1.
//
// Stabilité (Done= AOF187) : aucune assertion sur la date du jour, aucun nom
// accessible dérivé d'une icône — voir le commentaire d'en-tête de helpers.js.
//
// ── CORRECTION 14/08/2026 — « Variantes » et « Dossier » sont des ONGLETS ────
// Ce spec cliquait `getByRole('link', { name: /Variantes|Dossier/ })`. Or la
// fiche affaire rend ses sections en onglets Radix (`role="tab"`,
// `AffaireDetail.jsx` → `RecordShell` → `ui/Tabs.jsx`) : « Variantes » ne
// résolvait rien, et « Dossier » résolvait vers l'entrée de nav GLOBALE
// « Dossiers » (`/ao/dossiers`), un simple `EmptyState` d'aiguillage — le spec
// quittait la fiche pour un écran qui ne contient ni pièce ni contrôle.
import { test, expect } from '@playwright/test'
import {
  openAoDemoAffaire, ouvrirOngletAffaire, aoVariante, firstAoControleBloquant,
} from './helpers'

test('AOF187 (2/3): comparer deux variantes, en retenir une, constater la péremption des pièces', async ({ page }) => {
  await openAoDemoAffaire(page)
  await ouvrirOngletAffaire(page, 'Variantes')

  const retenue = aoVariante(page, 'retenue')
  const alternative = aoVariante(page, 'alternative')
  await expect(retenue).toBeVisible()
  await expect(alternative).toBeVisible()

  // Une pièce du pack est publiée (à jour) AVANT de rebasculer la variante
  // retenue — la péremption qu'on va constater plus bas n'a de sens que si la
  // pièce n'était PAS déjà périmée au départ.
  await ouvrirOngletAffaire(page, 'Dossier')
  const uneQuelconquePiece = page.locator('[data-ao-piece]').first()
  await expect(uneQuelconquePiece).toBeVisible()
  const etatAvant = await uneQuelconquePiece.getAttribute('data-ao-etat')
  expect(etatAvant).not.toBe('perime')

  // On retient l'alternative à la place de la variante actuellement retenue —
  // ce changement de paramètres invalide toute pièce déjà générée.
  await ouvrirOngletAffaire(page, 'Variantes')
  await alternative.getByRole('button', { name: /Retenir cette variante/ }).click()
  await expect(alternative).toHaveAttribute('data-ao-variante', 'retenue')

  await ouvrirOngletAffaire(page, 'Dossier')
  await expect(page.locator('[data-ao-piece][data-ao-etat="perime"]').first()).toBeVisible()
})

test('AOF187 (3/3): un contrôle rouge bloque le ZIP AVEC son motif, corriger puis générer', async ({ page }) => {
  await openAoDemoAffaire(page)
  await ouvrirOngletAffaire(page, 'Dossier')

  const controle = firstAoControleBloquant(page)
  await expect(controle).toBeVisible()
  const motif = (await controle.textContent())?.trim()
  expect(motif).toBeTruthy()

  const genererZip = page.getByRole('button', { name: /Générer le ZIP|Télécharger le dossier/ })
  await expect(genererZip).toBeDisabled()
  // Le motif du blocage est visible à côté de l'action — jamais un blocage
  // silencieux (« bouton mort » sans explication).
  await expect(page.getByText(motif, { exact: false })).toBeVisible()

  // Corrige le contrôle en suivant son lien vers l'écran source, puis revient.
  await controle.getByRole('link', { name: /Corriger/ }).click()
  const champARevoir = page.locator('[aria-invalid="true"], .field-error').first()
  if (await champARevoir.count()) {
    await champARevoir.fill('Valeur corrigée AOF187')
    await page.getByRole('button', { name: /Enregistrer/ }).click()
  }

  // Le lien « Corriger » a fait QUITTER la fiche (écran source de la pièce) :
  // on ne peut donc pas revenir par un onglet — on rouvre l'affaire depuis la
  // liste, puis son onglet « Dossier ». Retour déterministe, sans pari sur
  // l'historique de navigation.
  await openAoDemoAffaire(page)
  await ouvrirOngletAffaire(page, 'Dossier')
  await expect(page.locator('[data-ao-controle][data-ao-etat="bloquant"]')).toHaveCount(0)

  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: /Générer le ZIP|Télécharger le dossier/ }).click(),
  ])
  expect(download.suggestedFilename()).toMatch(/\.zip$/i)
})
