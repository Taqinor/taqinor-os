// Captures d'écran des étapes (après rechargement) + oracles de page 1-4, 7, 8.
// Usage : node captures.cjs <front> <outDir> <json [{nom, url, recherche, attendu:[textes]}]>
const { chromium } = require('playwright')
const fs = require('fs')
const path = require('path')
const [FRONT, OUT, SPEC] = process.argv.slice(2)
const items = JSON.parse(fs.readFileSync(SPEC, 'utf8'))
;(async () => {
  const b = await chromium.launch()
  const ctx = await b.newContext({ baseURL: FRONT, serviceWorkers: 'block', viewport: { width: 1440, height: 900 } })
  const page = await ctx.newPage()
  const res = []
  let inc = { '1': [], '2': [], '3': [], '4': [], '7': [], '8': [] }
  page.on('console', (m) => { if (m.type() === 'error') inc['3'].push(m.text().slice(0, 200)) })
  page.on('pageerror', (e) => inc['3'].push(String(e).slice(0, 200)))
  page.on('dialog', async (d) => { inc['4'].push(d.message()); await d.dismiss() })
  page.on('response', (x) => { if (!x.url().startsWith(FRONT)) return; if (x.status() >= 500) inc['1'].push(`${x.status()} ${x.url()}`); else if (x.status() >= 400) inc['2'].push(`${x.status()} ${x.url()}`) })
  await page.goto('/login')
  await page.getByPlaceholder('Entrez votre identifiant').fill('demo_admin')
  await page.locator('input[type="password"]').fill('Demo@2026!')
  await page.getByRole('button', { name: 'Se connecter →' }).click()
  await page.waitForURL(/\/apps/, { timeout: 60000 })
  await page.evaluate(() => { try { localStorage.setItem('taqinor-pwa-install-dismissed', '1'); localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch {} })
  for (const it of items) {
    inc = { '1': [], '2': [], '3': [], '4': [], '7': [], '8': [] }
    await page.goto(it.url, { waitUntil: 'domcontentloaded' })
    await page.reload({ waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {})
    const plus = page.getByRole('button', { name: 'Plus tard' })
    if (await plus.count()) await plus.first().click().catch(() => {})
    if (it.recherche) {
      const s = page.getByPlaceholder(/Référence, client/).first()
      await s.fill(it.recherche).catch(() => {})
      await page.waitForTimeout(1500)
      await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {})
    }
    const texte = await page.locator('body').innerText()
    if (/Une erreur est survenue/.test(texte)) inc['8'].push('écran cassé')
    if (/prix_achat|prix d'achat/i.test(texte)) inc['7'].push('prix_achat visible')
    const manquants = (it.attendu || []).filter((t) => !texte.includes(t))
    const f = path.join(OUT, `ACCEPTATION-ATOT-${it.nom}.jpg`)
    await page.screenshot({ path: f, type: 'jpeg', quality: 60 })
    res.push({ nom: it.nom, url: it.url, manquants, incidents: inc, extrait: texte.slice(0, 1500) })
    console.log(it.nom, 'manquants', manquants, JSON.stringify(inc))
  }
  fs.writeFileSync(path.join(OUT, 'captures.json'), JSON.stringify(res, null, 2))
  await b.close()
})()
