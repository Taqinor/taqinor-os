// NTDMO38 — le reset démo (`/companies/{id}/reset-demo/`, NTDMO7) ne casse
// JAMAIS une société RÉELLE voisine. C'est le garde-fou non-régression le
// plus critique du groupe NTDMO : une purge cross-tenant serait un incident
// de données grave (voir le commentaire de `_delete_cascading`/`reset_demo`,
// authentication/views.py + management/commands/reset_demo_company.py).
//
// Deux sociétés distinctes, jamais confondues :
//   - `taqinor-demo` (`est_demo=False` malgré son nom — voir helpers.js/
//     ADMIN) : la société RÉELLE voisine, partagée par le reste de la suite.
//     Ce spec ne la MODIFIE jamais, il compte seulement ses leads avant/après.
//   - `taqinor-demo-full` (`est_demo=True`, admin `demo_admin_full`) : SEULE
//     cible du reset, seedée en fixture par `manage.py seed_demo_company`
//     (.github/workflows/release-verify.yml — même patron que
//     `seed_ao_demo --company taqinor-demo` déjà présent pour AO ; `Faker`,
//     dev-only, y est installé ponctuellement pour cette étape). Comme
//     `leads.spec.js`, ce spec vit en e2e COMPLET (release-verify), pas dans
//     le palier smoke par-merge de ci.yml (qui ne seed pas
//     `taqinor-demo-full`).
import { test, expect } from '@playwright/test'
import { uiLogin, ADMIN } from './helpers'

test.use({ storageState: { cookies: [], origins: [] } })

const DEMO_FULL_ADMIN = { username: 'demo_admin_full', password: 'DemoFull@2026!' }

async function leadCount(page) {
  const res = await page.request.get('/api/django/crm/leads/?page_size=1')
  expect(res.ok(), `GET /crm/leads/ (${res.status()})`).toBeTruthy()
  const body = await res.json()
  return typeof body.count === 'number' ? body.count : (Array.isArray(body) ? body.length : 0)
}

test('NTDMO38 — reset-demo sur taqinor-demo-full laisse taqinor-demo strictement intact', async ({ page }) => {
  // 1) Baseline sur la société RÉELLE voisine, AVANT tout reset.
  await uiLogin(page, ADMIN)
  await expect(page).toHaveURL(/\/apps/, { timeout: 30_000 })
  const before = await leadCount(page)
  expect(before, 'la société réelle voisine a des leads seedés (seed_demo)')
    .toBeGreaterThan(0)

  // 2) Change d'identité vers l'admin de la société DÉMO ciblée par le reset
  //    (jamais la même société que ci-dessus).
  await page.context().clearCookies()
  await uiLogin(page, DEMO_FULL_ADMIN)
  await expect(page).toHaveURL(/\/apps/, { timeout: 30_000 })

  await page.goto('/parametres')
  await page.getByRole('button', { name: 'Démo & Onboarding' }).click()
  await expect(page.getByTestId('demo-reset-card')).toBeVisible({ timeout: 20_000 })
  await page.getByRole('button', { name: 'Réinitialiser les données de démonstration' }).click()

  // Confirmation destructive (AlertDialog Radix, ui/ConfirmProvider) — jamais
  // un window.confirm natif.
  const confirmDialog = page.getByRole('alertdialog')
  await expect(confirmDialog).toBeVisible()
  await confirmDialog.getByRole('button', { name: 'Réinitialiser' }).click()

  // Le reset (purge cascade + re-seed ~40 enregistrements) est synchrone côté
  // serveur ici (pas de worker Celery dans ce job e2e) — délai généreux.
  await expect(page.getByText('Données de démonstration réinitialisées.'))
    .toBeVisible({ timeout: 60_000 })

  // 3) Revient sur la société RÉELLE voisine : ses leads sont STRICTEMENT
  //    inchangés — la preuve que le reset est resté scopé à sa propre société.
  await page.context().clearCookies()
  await uiLogin(page, ADMIN)
  await expect(page).toHaveURL(/\/apps/, { timeout: 30_000 })
  const after = await leadCount(page)
  expect(after, 'aucun lead de la société réelle voisine perdu ni ajouté par le reset démo')
    .toBe(before)
})
