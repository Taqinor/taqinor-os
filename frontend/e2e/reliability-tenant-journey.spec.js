// NTOBS29 — parcours e2e « admin tenant consulte sa fiabilité de bout en
// bout » : Paramètres → Fiabilité → onglets Sauvegardes / Limites & usage /
// SLA → téléchargement du PDF SLA complet (NTOBS3).
//
// NOTE POUR LE PROCHAIN LOT (frontend) : ce spec est écrit contre le
// CONTRAT décrit par le plan (onglets Sauvegardes/Limites & usage/SLA sous
// Paramètres → Fiabilité, badge SLA du mois courant NTOBS16, bouton « Voir
// le rapport complet ») — l'écran lui-même (NTOBS19/32) n'existe pas encore
// dans cette base (hors périmètre de cette lane, `frontend/src` appartient à
// une autre lane) : les sélecteurs par rôle/texte ci-dessous sont donc
// tolérants (regex insensibles à la casse, mêmes libellés que le plan) mais
// N'ONT PAS pu être vérifiés contre un rendu réel. À ajuster dès que
// l'écran atterrit si un libellé diverge.
import { statSync } from 'node:fs'
import { expect, test } from '@playwright/test'

test('NTOBS29: admin tenant consulte sa fiabilité de bout en bout', async ({ page }) => {
  await page.goto('/parametres')

  // Onglet/section « Fiabilité » — même patron de navigation que les autres
  // sections de Paramètres (ex. E14 pour le profil société). Le lien peut
  // être un <a> ou un bouton d'onglet selon l'implémentation finale de
  // l'écran (NTOBS19/32, hors périmètre de cette lane).
  const ouvrirFiabilite = page.getByRole('link', { name: /fiabilité/i })
    .or(page.getByRole('button', { name: /fiabilité/i }))
  await ouvrirFiabilite.first().click()
  await expect(page.getByRole('heading', { name: /fiabilité/i })).toBeVisible({ timeout: 20_000 })

  // Onglet Sauvegardes — voit la dernière sauvegarde + statut du drill (NTOBS5).
  await page.getByRole('tab', { name: /sauvegardes/i }).click()
  await expect(page.getByText(/dernière sauvegarde|drill de restauration/i)).toBeVisible({ timeout: 20_000 })

  // Onglet Limites & usage — au moins une barre de progression (NTOBS8).
  await page.getByRole('tab', { name: /limites.*usage/i }).click()
  await expect(page.getByRole('progressbar').first()).toBeVisible({ timeout: 20_000 })

  // Onglet SLA — badge du mois courant (NTOBS16) puis rapport complet (NTOBS3).
  await page.getByRole('tab', { name: /^sla$/i }).click()
  await expect(page.getByText(/disponibilité|uptime/i).first()).toBeVisible({ timeout: 20_000 })

  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: /voir le rapport complet/i }).click(),
  ])
  expect(download.suggestedFilename()).toMatch(/\.pdf$/i)
  const path = await download.path()
  expect(path).not.toBeNull()
  expect(statSync(path).size).toBeGreaterThan(0)
})
