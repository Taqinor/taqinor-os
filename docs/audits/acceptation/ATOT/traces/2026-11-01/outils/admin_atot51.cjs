// ATOT53 (7) / ATOT51 — admin Django d'une facture émise et d'un BC livré (créés par l'étape 1).
// Usage : node admin_atot51.cjs <djangoBase> <outDir> <rejeu.json> <mode> <user> <pass>
const { chromium } = require('playwright')
const fs = require('fs')
const path = require('path')
const [BASE, OUT, RJ, MODE, USER, PASS] = process.argv.slice(2)
const r = JSON.parse(fs.readFileSync(RJ, 'utf8')).e1
const ADM = `${BASE}/api/django/admin`
const journal = []
const log = (...a) => { const s = a.map((x) => (typeof x === 'string' ? x : JSON.stringify(x))).join(' '); journal.push(s); console.log(s) }
const inc = { '1': [], '2': [], '3': [], '4': [], '8': [] }
const checks = []
const verif = (nom, ok, detail) => { checks.push({ nom, ok: !!ok, detail }); log(`  [${ok ? 'OK' : 'KO'}] ${nom} ${JSON.stringify(detail || '').slice(0, 300)}`) }

;(async () => {
  const b = await chromium.launch()
  const ctx = await b.newContext({ viewport: { width: 1440, height: 1000 } })
  const page = await ctx.newPage()
  page.on('console', (m) => { if (m.type() === 'error') inc['3'].push(m.text().slice(0, 200)) })
  page.on('pageerror', (e) => inc['3'].push(String(e).slice(0, 200)))
  page.on('dialog', async (d) => { inc['4'].push(d.message()); await d.dismiss() })
  page.on('response', (x) => { if (x.url().startsWith(BASE) && x.status() >= 500) inc['1'].push(`${x.status()} ${x.url()}`); else if (x.url().startsWith(BASE) && x.status() >= 400 && !/favicon/.test(x.url())) inc['2'].push(`${x.status()} ${x.url()}`) })
  await page.goto(`${ADM}/login/`)
  await page.fill('input[name=username]', USER)
  await page.fill('input[name=password]', PASS)
  await Promise.all([page.waitForLoadState('domcontentloaded'), page.click('input[type=submit], button[type=submit]')])
  log('login admin ->', page.url())

  async function lire(url) { const rr = await page.request.get(url); return rr.ok() ? rr.text() : `HTTP ${rr.status()}` }
  // Facture émise
  const fUrl = `${ADM}/facturation/facture/${r.emise}/change/`
  await page.goto(fUrl, { waitUntil: 'networkidle' })
  const champsF = await page.evaluate(() => ({
    statut: !!document.querySelector('[name=statut]'),
    abandon: [...document.querySelectorAll('[name^=abandon_]')].map((e) => e.name),
    lignesEditables: [...document.querySelectorAll('[name^=lignes-], [name*=lignefacture]')].filter((e) => e.type !== 'hidden').map((e) => e.name),
    ajoutLigne: [...document.querySelectorAll('.add-row a')].some((e) => !!(e.offsetWidth || e.offsetHeight)),
    suppression: [...document.querySelectorAll('input[name$=-DELETE]')].length,
    lignesLues: document.querySelectorAll('.inline-related tbody tr, .inline-group tbody tr').length,
  }))
  log('facture admin champs', champsF)
  await page.screenshot({ path: path.join(OUT, `ACCEPTATION-ATOT-P7-${MODE}-facture.jpg`), type: 'jpeg', quality: 60, fullPage: true })
  verif('P7 facture émise : statut, abandon_* et lignes absents du formulaire', !champsF.statut && champsF.abandon.length === 0 && champsF.lignesEditables.length === 0 && !champsF.ajoutLigne && champsF.suppression === 0, champsF)
  // Poste forcé : champs injectés dans le formulaire (un client qui contournerait l'écran).
  await page.evaluate(() => {
    const f = document.querySelector("#content-main form")
    for (const [k, v] of [['statut', 'annulee'], ['abandon_montant', '100'], ['lignes-0-quantite', '5'], ['lignes-0-prix_unitaire', '1']]) {
      const i = document.createElement('input'); i.type = 'hidden'; i.name = k; i.value = v; f.appendChild(i)
    }
  })
  await Promise.all([page.waitForLoadState('domcontentloaded'), page.click('input[name=_continue], input[name=_save]')])
  const errF = await page.locator('.errornote, .errorlist').allInnerTexts()
  log('après poste facture', page.url(), errF)
  // relire par l'API admin (page de change) et par le shell côté orchestrateur
  fs.writeFileSync(path.join(OUT, `admin-${MODE}-facture-apres.html`), (await lire(fUrl)).slice(0, 200000))

  // BC livré
  const bUrl = `${ADM}/ventes/boncommande/${r.bc}/change/`
  await page.goto(bUrl, { waitUntil: 'domcontentloaded' })
  const champsB = await page.evaluate(() => ({ devis: !!document.querySelector('[name=devis]'), client: !!document.querySelector('[name=client]') }))
  log('BC admin champs', champsB)
  await page.screenshot({ path: path.join(OUT, `ACCEPTATION-ATOT-P7-${MODE}-bc.jpg`), type: 'jpeg', quality: 60, fullPage: true })
  verif('P7 BC livré : devis et client absents du formulaire', !champsB.devis && !champsB.client, champsB)
  if (!champsB.devis) {
    await page.evaluate((d2) => {
      const f = document.querySelector('#content-main form')
      for (const [k, v] of [['devis', String(d2)]]) { const i = document.createElement('input'); i.type = 'hidden'; i.name = k; i.value = v; f.appendChild(i) }
    }, r.D2)
  } else {
    await page.selectOption('[name=devis]', String(r.D2)).catch(async () => { await page.fill('[name=devis]', String(r.D2)) })
  }
  await Promise.all([page.waitForLoadState('domcontentloaded'), page.click('input[name=_continue], input[name=_save]')])
  log('après poste BC', page.url(), await page.locator('.errornote, .errorlist').allInnerTexts())
  fs.writeFileSync(path.join(OUT, `admin-${MODE}.json`), JSON.stringify({ checks, incidents: inc }, null, 2))
  fs.writeFileSync(path.join(OUT, `admin-${MODE}.log`), journal.join('\n') + '\n')
  await b.close()
})()
