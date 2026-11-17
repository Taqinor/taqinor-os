// aerr12b : AERR114 « Suppr » tapé sous une boîte posée par-dessus l'atelier — jouée SEULE (un FAIL ne couvre rien et ne
// doit pas faire tomber l'enregistrement de aerr12). Reprise de l'étape de aerr11 (run bca23e792 : `#rp9-obstacle` non cliquable
// en 20 s) : le bouton est actionné par son gestionnaire (installation de la scène, pas le geste prouvé), le tracé du toit est
// fermé au besoin, l'état de l'atelier est journalisé. Le geste prouvé (touche « Suppr » sous la palette ⌘K ouverte) est réel.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage } from '../helpers.js'

const etape = groupe('AERR', ['AERR114'])
fermerDjangoApresTout()
test.describe.configure({ timeout: 600_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const apres = []
test.afterEach(async () => { for (const f of apres.splice(0)) await f().catch((e) => console.log(`[nettoyage] ${e.message}`)) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`

// ═══ AERR114 (suite) — « Suppr » tapé sous une boîte posée par-dessus l'atelier n'appelle aucune action ═══
// Montage de l'atelier sans clé carte secrète : comme acal4.spec.js (vague 6), la réponse réelle de `design-context` est
// relue et sa `carte` surchargée par une clé factice ; MapTiler répond 403 (fond de repli local). Un obstacle est dessiné
// à la souris (il est alors SÉLECTIONNÉ : `#rp9-obs-delete` visible) ; la palette ⌘K (boîte Radix) est ouverte par-dessus,
// le focus quitte son champ, « Suppr » est tapé : l'obstacle doit rester sélectionné. Témoin : boîte fermée, « Suppr » ⇒ supprimé.
etape('PF12.114-AERR114-suppr', ['AERR114'], async ({ page, context, suivi }) => {
  const m = marque()
  const cal = await py(`from decimal import Decimal as D
from apps.crm.models import Lead
from apps.calepinage.models import Calepinage
from apps.calepinage.tests.test_acal_multi_pans import _layout, _zone
from apps.ventes.domain.geometrie import layout_hash
co = U.objects.get(username='demo_admin').company
lead = Lead.objects.create(company=co, nom='ACC AERR114 ${m}', ville='Casablanca', type_installation='residentiel', facture_hiver=D('900'))
lay = _layout(_zone(1, 16, 90.0), _zone(2, 8, 270.0))
lay.update({'scenario': 'reseau', 'panelWatt': 710, 'result': {'panels': 24, 'kwc': 17.04}})
c = Calepinage.objects.create(company=co, lead_id=lead.pk, titre='ACC AERR114 ${m}', roof_layout=lay, layout_hash=layout_hash(lay))
sortie({'id': c.pk})`)
  apres.push(() => py(`from apps.calepinage.models import Calepinage
Calepinage.objects.filter(pk=${cal.id}).delete()`))
  await context.route(new RegExp(`/calepinage/calepinages/${cal.id}/design-context/`), async (route) => {
    const reelle = await route.fetch()
    const corps = await reelle.json()
    corps.carte = { ...(corps.carte || {}), available: true, maptilerKey: 'cle-factice-aerr114', mapboxToken: null }
    await route.fulfill({ response: reelle, json: corps })
  })
  suivi.attendre(/api\.maptiler\.com/, 403)
  await context.route(/https:\/\/api\.maptiler\.com\//, (route) => route.fulfill({ status: 403, contentType: 'application/json', body: '{"message":"Invalid key"}' }))
  await page.setViewportSize({ width: 1600, height: 1000 })
  await page.goto(`/calepinage/${cal.id}`)
  await expect(page.getByRole('button', { name: 'Enregistrer le calepinage' }), 'atelier booté (scène hydratée)').toBeEnabled({ timeout: 180_000 })
  const cv = page.locator('canvas.maplibregl-canvas').first()
  const bb = await cv.boundingBox()
  const statutAtelier = () => page.locator('#rp9-status').innerText().catch(() => '(statut illisible)')
  console.log(`[AERR114] statut atelier au boot : ${(await statutAtelier()).slice(0, 200)}`)
  const bouton = page.locator('#rp9-obstacle')
  await bouton.waitFor({ state: 'attached', timeout: 60_000 })
  console.log(`[AERR114] #rp9-obstacle visible : ${await bouton.isVisible()} ; cadre : ${JSON.stringify(await bouton.boundingBox())}`)
  // Gestionnaire du bouton (installation de la scène, pas le geste prouvé) : actionné sans dépendre de sa visibilité.
  await bouton.dispatchEvent('click')
  if (/Fermez d.abord le trac/.test(await statutAtelier())) {
    // Toit non fermé par l'hydratation : 4 sommets puis fermeture sur le 1er.
    const pts = [[0.35, 0.35], [0.65, 0.35], [0.65, 0.65], [0.35, 0.65]]
    for (const [fx, fy] of pts) await page.mouse.click(bb.x + bb.width * fx, bb.y + bb.height * fy)
    await page.mouse.click(bb.x + bb.width * pts[0][0], bb.y + bb.height * pts[0][1])
    await bouton.dispatchEvent('click')
  }
  console.log(`[AERR114] statut après « obstacle » : ${(await statutAtelier()).slice(0, 200)}`)
  // Dessin d'un obstacle : glisser sur la carte ⇒ l'obstacle est sélectionné.
  const x = bb.x + bb.width * 0.5
  const y = bb.y + bb.height * 0.5
  await page.mouse.move(x, y)
  await page.mouse.down()
  await page.mouse.move(x + 60, y + 40, { steps: 8 })
  await page.mouse.move(x + 120, y + 80, { steps: 8 })
  await page.mouse.up()
  const supprimerObs = page.locator('#rp9-obs-delete')
  await expect(supprimerObs, 'un obstacle est sélectionné (bouton « Supprimer » de l\'obstacle visible)').toBeVisible({ timeout: 20_000 })
  // Boîte Radix par-dessus : la palette ⌘K ; le focus quitte son champ de saisie.
  await bouton.dispatchEvent('click') // quitte le mode dessin sans toucher à l'obstacle
  await page.keyboard.press('Control+k')
  const palette = page.getByRole('dialog', { name: 'Palette de commandes' })
  await expect(palette, 'boîte posée par-dessus l\'atelier').toBeVisible({ timeout: 30_000 })
  await page.evaluate(() => { document.activeElement?.blur?.(); document.querySelector('[role="dialog"][aria-label="Palette de commandes"]')?.focus() })
  await page.keyboard.press('Delete')
  await page.keyboard.press('Backspace')
  // Le raccourci de l'atelier agit de façon SYNCHRONE dans l'écouteur `keydown` (état React, aucun appel réseau) :
  // deux images peintes après les frappes ⇒ une suppression éventuelle est déjà rendue.
  await page.evaluate(() => new Promise((ok) => requestAnimationFrame(() => requestAnimationFrame(ok))))
  await expect(supprimerObs, '« Suppr » sous la boîte : l\'obstacle reste sélectionné (aucune action appelée)').toBeVisible()
  // Témoin : boîte fermée, « Suppr » agit.
  await page.keyboard.press('Escape')
  await expect(palette).toHaveCount(0)
  await page.evaluate(() => document.activeElement?.blur?.())
  await page.keyboard.press('Delete')
  await expect(supprimerObs, 'témoin : boîte fermée, « Suppr » supprime l\'obstacle').toBeHidden({ timeout: 15_000 })
})
