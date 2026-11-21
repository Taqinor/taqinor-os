// ACAL423 — l'atelier de calepinage (`.rp9-host`) doit rester utilisable au téléphone
// (390 × 844) : aucun défilement horizontal de la page, aucune cible tactile (bouton ou
// puce visible) sous 44 px de haut. Même méthode que `mobile.spec.js` (VNT81) :
// `scrollWidth - innerWidth`. La carte peut être absente (ERR121, aucune clé MapTiler) :
// `#rp9-map` reste un conteneur, la mesure porte sur le DOM du builder.
import { test, expect } from '@playwright/test'
import { gotoLeads, createLead, uniq } from './helpers'

test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true })

test('ACAL423 : atelier à 390 px — pas de défilement horizontal, cibles ≥ 44 px', async ({ page }) => {
  await gotoLeads(page)
  const name = await createLead(page, { nom: uniq('Atelier tel ACAL423'), facture: 650, ville: 'Casablanca' })
  const res = await page.request.get(`/api/django/crm/leads/?search=${encodeURIComponent(name)}&page_size=1`)
  expect(res.ok(), `GET /crm/leads/?search= (${res.status()})`).toBeTruthy()
  const body = await res.json()
  const rows = Array.isArray(body) ? body : body.results
  expect(rows?.length, `lead "${name}" introuvable via l'API`).toBeGreaterThan(0)

  await page.goto(`/devis-design/${rows[0].id}`)
  await expect(page.locator('.rp9-host').first()).toBeVisible({ timeout: 20_000 })

  const debordement = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(debordement, 'défilement horizontal de la page (px)').toBeLessThanOrEqual(0)

  const petites = await page.evaluate(() => {
    const out = []
    for (const el of document.querySelectorAll('.rp9-host button, .rp9-host .rp9-chip')) {
      const r = el.getBoundingClientRect()
      if (r.width === 0 || r.height === 0) continue // non visible
      if (r.height < 44) out.push(`${el.id || el.className || el.tagName} (${Math.round(r.height)} px)`)
    }
    return out
  })
  expect(petites, 'boutons et puces de moins de 44 px de haut').toEqual([])
})
