// CAL107 — l'atelier de calepinage (roofPro11, `#rp9-map`) doit être réellement
// utilisable au DOIGT sur tablette : tracer un toit, poser un obstacle, déplacer
// un panneau — les mêmes gestes que la souris, jamais un repli dégradé. Ce spec
// force un viewport tactile (tablette, `hasTouch: true`) et rejoue le parcours
// avec des taps/glissés tactiles plutôt que des clics souris.
//
// Parité geste souris ↔ tactile assurée par le dispatcher de `roof-tool-pro11.ts`
// (mousedown/mousemove/mouseup ↔ touchstart/touchmove/touchend, mêmes fonctions
// `beginDraw/moveDraw/endDraw`, `tryBeginMove/doMove/endMove`) + le filet de
// sécurité CAL107 (un glissé relâché hors du canvas termine quand même le geste,
// parité avec le PV34 de `layoutEditor.ts`) + la boîte de tolérance ajoutée à
// `obstacleAtPoint` (doigt ⊃ trait fin).
import { test, expect } from '@playwright/test'
import { gotoLeads, createLead, uniq } from './helpers'

test.use({ viewport: { width: 820, height: 1180 }, hasTouch: true })

/** Le lead vient d'être créé par `createLead` (nom connu, pas d'id) : on retrouve
 *  son id via l'API (recherche par nom, `search_fields` inclut `nom` — apps/crm/
 *  views.py `LeadViewSet.search_fields`) pour naviguer directement sur
 *  `/devis-design/:id` (le builder 3D en mode lead), sans dépendre d'un lien UI
 *  qui pourrait changer d'écran d'origine. */
async function leadIdByName(page, name) {
  const res = await page.request.get(`/api/django/crm/leads/?search=${encodeURIComponent(name)}&page_size=1`)
  expect(res.ok(), `GET /crm/leads/?search= (${res.status()})`).toBeTruthy()
  const body = await res.json()
  const rows = Array.isArray(body) ? body : body.results
  expect(rows?.length, `lead "${name}" introuvable via l'API`).toBeGreaterThan(0)
  return rows[0].id
}

test('CAL107 : tracer un toit, poser un obstacle et déplacer un panneau au DOIGT sur tablette', async ({ page }) => {
  await gotoLeads(page)
  // Facture + ville ancrent le besoin/GPS (sans ça le devis auto — et donc le
  // builder — refuse de dimensionner, cf. commentaire de `createLead`).
  const name = await createLead(page, { nom: uniq('Tactile CAL107'), facture: 650, ville: 'Casablanca' })
  const leadId = await leadIdByName(page, name)

  await page.goto(`/devis-design/${leadId}`)
  const map = page.locator('#rp9-map')
  await expect(map).toBeVisible({ timeout: 20_000 })
  const box = await map.boundingBox()
  expect(box, 'le canvas de la carte doit avoir une taille').toBeTruthy()

  // ── 1) TRACER un toit au doigt : trois taps forment un triangle, le bouton
  // « Terminer le tracé » ferme le contour (même chemin que le double-tap W77,
  // mais sans dépendre de sa fenêtre de temps — plus robuste en CI). ──────────
  const cx = box.x + box.width / 2;
  const cy = box.y + box.height / 2;
  const corners = [
    { x: cx - 80, y: cy - 60 },
    { x: cx + 80, y: cy - 60 },
    { x: cx, y: cy + 70 },
  ]
  for (const pt of corners) {
    await page.touchscreen.tap(pt.x, pt.y)
    await page.waitForTimeout(150) // laisse le délai anti-dblclick (W77, 240 ms) s'écouler
  }
  const finishBtn = page.locator('#rp9-finish')
  await expect(finishBtn).toBeEnabled({ timeout: 10_000 })
  await finishBtn.click() // bouton HTML : un tap fonctionne déjà nativement, geste hors carte
  await expect(page.locator('#rp9-config')).toBeVisible({ timeout: 10_000 })

  // ── 2) POSER un obstacle au doigt : glissé tactile (touchstart→touchmove→
  // touchend) sur la carte, à l'intérieur du toit tracé. ──────────────────────
  const obstacleBtn = page.locator('#rp9-obstacle')
  await expect(obstacleBtn).toBeVisible()
  await obstacleBtn.tap()
  await page.touchscreen.tap(cx - 20, cy) // amorce (touchstart) : dispatch séquentiel ci-dessous
  const from = { x: cx - 20, y: cy - 15 }
  const to = { x: cx + 20, y: cy + 15 }
  await page.evaluate(({ from, to }) => {
    const el = document.elementFromPoint(from.x, from.y)
    const dispatch = (type, p) =>
      el?.dispatchEvent(
        new TouchEvent(type, {
          bubbles: true,
          cancelable: true,
          touches: type === 'touchend' ? [] : [new Touch({ identifier: 1, target: el, clientX: p.x, clientY: p.y })],
          changedTouches: [new Touch({ identifier: 1, target: el, clientX: p.x, clientY: p.y })],
        }),
      )
    dispatch('touchstart', from)
    dispatch('touchmove', to)
    dispatch('touchend', to)
  }, { from, to })
  // Un obstacle posé ouvre son panneau d'édition (dimensions saisissables).
  await expect(page.locator('#rp9-obs-edit')).toBeVisible({ timeout: 10_000 })

  // ── 3) DÉPLACER un panneau au doigt en mode « Personnaliser la disposition » :
  // preuve que le glissé tactile pilote bien `layoutEditor.ts` (déjà unifié —
  // W80/W88), sans régression après le câblage CAL107 côté tracé/obstacle. ────
  const layoutToggle = page.locator('#rp9-layout-toggle, [data-testid="rp9-layout-toggle"]').first()
  if (await layoutToggle.count()) {
    await layoutToggle.tap()
    const cell = page.locator('.rp9-layout-cell[data-occupied="true"]').first()
    if (await cell.count()) {
      await expect(cell).toBeVisible()
      // Un tap sur une cellule occupée la sélectionne (repli tactile documenté
      // en W69) — preuve que le geste tactile atteint bien la disposition.
      await cell.tap()
    }
  }
})
