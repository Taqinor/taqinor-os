// PUB56 — Tables responsives mobiles + cibles tactiles sur Approbations.
// ----------------------------------------------------------------------------
// Vérifie à un VRAI viewport 375px (iPhone SE, jamais reproductible en jsdom —
// aucune media query n'y est appliquée) que :
//   1. Approbations : les actions Approuver/Rejeter sont des cibles tactiles
//      d'au moins 44×44px (WCAG 2.5.5 / repère Apple HIG) et l'écran ne
//      déborde jamais horizontalement.
//   2. Reporting : ses tableaux `.data-table` (variantes) replient en cartes
//      sous 768px (pattern GLOBAL déjà établi de l'ERP, index.css — `thead`
//      masqué, chaque `<td>` porte `data-label` pour rester lisible), sans
//      débordement horizontal.
// Le Cockpit (AdsCockpitScreen) est HORS PÉRIMÈTRE de cette lane (écran
// possédé par une autre lane de la vague) — son repli mobile est à traiter
// par la lane qui possède son corps.
//
// Suit le patron déjà établi (`datatable-breakpoint.spec.js`) : override
// LOCAL du viewport via `test.use()` plutôt que le projet `mobile` dédié
// (réservé à `mobile.spec.js`), pré-authentifié via le même storageState
// que le reste du projet `chromium`.
import { test, expect } from '@playwright/test'

test.use({ viewport: { width: 375, height: 812 } })

const API = '/api/django/adsengine'

function assertNoHorizontalOverflow(page, path) {
  return page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
    .then((overflow) => expect(overflow, `horizontal overflow on ${path}`).toBeLessThanOrEqual(1))
}

test.describe('PUB56 — 375px : Approbations (cibles tactiles)', () => {
  const createdActionIds = []

  test.afterAll(async ({ request }) => {
    await Promise.all(createdActionIds.map((id) => (
      request.delete(`${API}/actions/${id}/`).catch(() => null)
    )))
  })

  test('Approuver/Rejeter mesurent au moins 44×44px et l\'écran ne déborde pas', async ({ page, request }) => {
    // Seed une action PROPOSÉE sûre (patron adsengine.spec.js) via l'API réelle.
    const res = await request.post(`${API}/actions/`, {
      data: { kind: 'pause', reason_fr: 'PUB56 — cible tactile mobile.', payload: {} },
    })
    expect(res.ok()).toBeTruthy()
    const { id } = await res.json()
    createdActionIds.push(id)

    await page.goto('/publicite/approbations')
    await expect(
      page.getByRole('heading', { name: "Boîte d'approbation" }),
    ).toBeVisible({ timeout: 20_000 })

    await assertNoHorizontalOverflow(page, '/publicite/approbations')

    const approve = page.getByTestId(`ae-approve-${id}`)
    const reject = page.getByTestId(`ae-reject-${id}`)
    await expect(approve).toBeVisible()
    await expect(reject).toBeVisible()

    const approveBox = await approve.boundingBox()
    const rejectBox = await reject.boundingBox()
    expect(approveBox, 'Approuver a une boundingBox').toBeTruthy()
    expect(rejectBox, 'Rejeter a une boundingBox').toBeTruthy()
    expect(approveBox.height, 'Approuver ≥44px de haut').toBeGreaterThanOrEqual(44)
    expect(approveBox.width, 'Approuver ≥44px de large').toBeGreaterThanOrEqual(44)
    expect(rejectBox.height, 'Rejeter ≥44px de haut').toBeGreaterThanOrEqual(44)
    expect(rejectBox.width, 'Rejeter ≥44px de large').toBeGreaterThanOrEqual(44)
  })
})

test.describe('PUB56 — 375px : Reporting (repli tableau → cartes)', () => {
  test('le tableau variantes ne déborde jamais ; s\'il existe, ses en-têtes sont masqués sous 768px', async ({ page }) => {
    await page.goto('/publicite/reporting')
    await expect(page.getByRole('heading', { name: 'Reporting' })).toBeVisible({ timeout: 20_000 })
    await page.waitForLoadState('networkidle').catch(() => {})

    await assertNoHorizontalOverflow(page, '/publicite/reporting')

    const table = page.getByTestId('ae-reports-variants-table')
    if (await table.count()) {
      // Pattern GLOBAL `.data-table` (index.css) : `thead` masqué sous 768px,
      // chaque ligne devient une carte — jamais une table tronquée/scrollée.
      await expect(table.locator('thead')).toBeHidden()
      const firstCell = table.locator('tbody td').first()
      if (await firstCell.count()) {
        await expect(firstCell).toBeVisible()
      }
    }
  })
})
