import { test, expect } from '@playwright/test'

// ── Régression VISUELLE (@visual) ───────────────────────────────────────────
// Ces captures tournent UNIQUEMENT dans release-verify.yml (manuel + nightly),
// jamais dans le smoke e2e par-merge (ci.yml). Au tout premier run il n'existe
// pas de baseline : `--update-snapshots` les génère, et le workflow les uploade
// en artefact `visual-baselines`. Le fondateur relit ces images puis les commit
// sous e2e/**-snapshots/ — la comparaison pixel devient alors un vrai garde-fou.
//
// Le projet `chromium` est pré-authentifié (storageState) et dépend de `setup`,
// donc ces tests s'exécutent connectés sur la base démo déterministe (seed_demo).

test('dashboard — capture de référence', { tag: '@visual' }, async ({ page }) => {
  await page.goto('/dashboard')
  await expect(page.getByRole('heading', { name: 'Tableau de bord' })).toBeVisible()
  await expect(page).toHaveScreenshot('dashboard.png', {
    fullPage: true,
    animations: 'disabled',
    // Tolérance : la base démo est déterministe mais l'anti-aliasing varie un peu.
    maxDiffPixelRatio: 0.02,
  })
})
