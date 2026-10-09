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
//     (.github/workflows/release-verify.yml ; `Faker`, dev-only, y est
//     installé ponctuellement pour cette étape). Comme `leads.spec.js`, ce
//     spec vit en e2e COMPLET (release-verify), pas dans le palier smoke
//     par-merge de ci.yml (qui ne seed pas `taqinor-demo-full`).
import { test, expect } from '@playwright/test'
import { uiLoginJusquAuxApps, fermerMomentAccueil, rafraichirEtatPartage, AUTH_FILE } from './helpers'

test.use({ storageState: { cookies: [], origins: [] } })

const DEMO_FULL_ADMIN = { username: 'demo_admin_full', password: 'DemoFull@2026!' }

async function leadCount(requete) {
  const res = await requete.get('/api/django/crm/leads/?page_size=1')
  expect(res.ok(), `GET /crm/leads/ (${res.status()})`).toBeTruthy()
  const body = await res.json()
  return typeof body.count === 'number' ? body.count : (Array.isArray(body) ? body.length : 0)
}

test('NTDMO38 — reset-demo sur taqinor-demo-full laisse taqinor-demo strictement intact', async ({ page, playwright, baseURL }) => {
  // CAD177 — budget de la connexion rejouée (jusqu'à 90 s) + le reset.
  test.setTimeout(180_000)
  // CAD177 — les comptes de la société RÉELLE voisine se lisent par l'API
  // avec la session admin PARTAGÉE (AUTH_FILE, revérifiée), plus par deux
  // connexions UI : juste après les 4 connexions à froid de
  // demo-first-login, la 6e connexion de la minute tombait sur le throttle
  // « login » 5/min/IP (run 36990128960 : POST /token/ 429, « Requête
  // ralentie »). La seule connexion UI restante est celle du sujet du test :
  // l'admin de la société démo qui déclenche le reset.
  await rafraichirEtatPartage(playwright, baseURL)
  const adminReel = await playwright.request.newContext({ baseURL, storageState: AUTH_FILE })

  // 1) Baseline sur la société RÉELLE voisine, AVANT tout reset.
  const before = await leadCount(adminReel)
  expect(before, 'la société réelle voisine a des leads seedés (seed_demo)')
    .toBeGreaterThan(0)

  // 2) Change d'identité vers l'admin de la société DÉMO ciblée par le reset
  //    (jamais la même société que ci-dessus).
  await page.context().clearCookies()
  // CAD177 — juste après demo-first-login, cette connexion tombait encore
  // dans la minute du throttle « login » (429, nocturne 37803204581) :
  // attendue puis rejouée jusqu'à `/apps`.
  await uiLoginJusquAuxApps(page, DEMO_FULL_ADMIN)
  // CAD177 — premier login à froid : moment d'accueil VX156 à fermer.
  await fermerMomentAccueil(page)

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
  const after = await leadCount(adminReel)
  await adminReel.dispose()
  expect(after, 'aucun lead de la société réelle voisine perdu ni ajouté par le reset démo')
    .toBe(before)
})
