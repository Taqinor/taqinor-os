// NTOBS29 — parcours e2e « admin tenant consulte sa fiabilité de bout en
// bout » : Paramètres → Sauvegardes (NTOBS5) → Limites & usage (NTOBS8) →
// SLA (NTOBS16).
//
// CAD177 : le spec d'origine visait un lien « Fiabilité » + des onglets
// (Sauvegardes / Limites & usage / SLA) qui n'ont JAMAIS existé : NTOBS5/8/16
// ont livré TROIS pages indépendantes de Paramètres
// (/parametres/sauvegardes, /parametres/limites-usage, /parametres/sla), chacune
// avec son lien de navigation (features/parametres/module.config.jsx). Le
// spec suit désormais ces écrans réels. L'étape « téléchargement du PDF SLA »
// est retirée : SlaReportPage documente que l'export PDF
// (GET /core/sla/<periode>/export-pdf/) n'y est « non branché » — rien à
// télécharger tant que ce bouton n'existe pas.
import { expect, test } from '@playwright/test'

test('NTOBS29: admin tenant consulte sa fiabilité de bout en bout', async ({ page }) => {
  // Sauvegardes — dernier test de restauration (NTOBS5).
  await page.goto('/parametres/sauvegardes')
  await expect(page.getByRole('heading', { name: 'Sauvegardes' })).toBeVisible({ timeout: 20_000 })
  await expect(page.getByText('Dernier test de restauration')).toBeVisible({ timeout: 20_000 })

  // Limites & usage — écran lecture seule (NTOBS8).
  await page.goto('/parametres/limites-usage')
  await expect(page.getByRole('heading', { name: 'Limites & usage' })).toBeVisible({ timeout: 20_000 })

  // SLA — rapport mensuel (NTOBS16) : un rapport ou l'état vide explicite.
  await page.goto('/parametres/sla')
  await expect(page.getByRole('heading', { name: 'Rapport SLA' })).toBeVisible({ timeout: 20_000 })
  await expect(
    page.getByText(/% disponible|Aucun rapport SLA généré/).first()
  ).toBeVisible({ timeout: 20_000 })
})
