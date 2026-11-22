import { test, expect } from '@playwright/test'
import { uniq, API_DJANGO, lireJson, telephoneMobileUnique } from './helpers'

const CAL = `${API_DJANGO}/calepinage`
async function carteRefusee(context) {
  await context.route(/\/calepinage\/calepinages\/\d+\/design-context\//, async (route) => {
    const reelle = await route.fetch()
    const corps = await reelle.json()
    corps.carte = { ...(corps.carte || {}), available: true, maptilerKey: 'cle-factice', mapboxToken: null }
    await route.fulfill({ response: reelle, json: corps })
  })
  await context.route(/https:\/\/api\.maptiler\.com\//, (route) => route.fulfill({ status: 403, contentType: 'application/json', body: '{}' }))
}
test.use({ viewport: { width: 1440, height: 900 }, hasTouch: false })
test('dbg', async ({ page }) => {
  test.setTimeout(300000)
  page.on('dialog', (d) => { console.log('DIALOG', d.type(), d.message()); void d.accept() })
  await carteRefusee(page.context())
  await page.goto('/apps')
  await expect(page.getByRole('heading', { name: 'Mes applications' })).toBeVisible({ timeout: 30000 })
  const T = { timeout: 120000 }
  const lead = await lireJson(await page.request.post(`${API_DJANGO}/crm/leads/`, { ...T, data: { nom: uniq('ZZG'), ville: 'Casablanca', telephone: telephoneMobileUnique(), type_installation: 'residentiel', facture_hiver: '800' } }), 'lead')
  const cal = await lireJson(await page.request.post(`${CAL}/calepinages/`, { ...T, data: { lead: lead.id, titre: uniq('ZZG') } }), 'cal')
  await lireJson(await page.request.get(`${CAL}/calepinages/${cal.id}/design-context/`, T), 'dc')
  await page.goto(`/calepinage/${cal.id}`)
  await expect.poll(() => page.evaluate(() => Boolean(window.__taqinorRoofBooted)), { timeout: 240000 }).toBe(true)
  await page.locator('#rp9-map canvas').first().scrollIntoViewIfNeeded()
  await page.waitForTimeout(1500)
  const etat = async (q) => console.log(q, JSON.stringify(await page.evaluate(() => ({ status: document.querySelector('#rp9-status')?.innerText, undo: !document.querySelector('#rp9-undo-point')?.hidden, finish: !document.querySelector('#rp9-finish')?.disabled, clearDisabled: document.querySelector('#rp9-clear')?.disabled, surf: document.body.innerText.match(/Surface : [^\n]*/)?.[0] ?? null }))))
  await etat('A0')
  const pts = [[600, 520], [720, 520], [720, 610]]
  for (const [x, y] of pts) { await page.mouse.click(x, y); await page.waitForTimeout(350) }
  await etat('A1 trois clics')
  await page.locator('#rp9-finish').click(); await page.waitForTimeout(1200)
  await etat('A2 ferme')
  const els = await page.evaluate(() => [...document.querySelectorAll('#rp9-map *')].filter((e) => !e.matches('canvas, canvas *') ).map((e) => e.tagName + '.' + (e.className?.baseVal ?? e.className) + '#' + e.id).filter((t) => !/ctrl|Ctrl/.test(t)).slice(0, 40))
  console.log('DOMMAP', JSON.stringify(els))
})
