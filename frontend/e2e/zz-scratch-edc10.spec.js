// SCRATCH (temporaire, supprimé avant la PR) — instrumentation d'EDC10 « page
// pleine à 1 366 px » : largeur de chaque colonne, état des polices et
// largeur du wrap à plusieurs moments, avec et sans police de marque.
import { test, expect } from '@playwright/test'
import {
  gotoLeads, createLead, openLead, generateAutoDevis, uniq, API_DJANGO, lireJson, listeDe,
} from './helpers'

const GRAND_ECRAN = { width: 1600, height: 1000 }
const PORTABLE = { width: 1366, height: 768 }

async function dump(page, moment) {
  const d = await page.evaluate(() => {
    const wrap = document.querySelector('.lines-table-wrap')
    const table = wrap?.querySelector('table')
    const r = (el) => Math.round(el.getBoundingClientRect().width * 10) / 10
    const ths = [...(table?.querySelectorAll('thead th') || [])].map((th) => ({
      t: th.textContent.trim(), w: r(th), sw: th.scrollWidth,
      spec: th.style.width || th.style.minWidth || '',
    }))
    const rows = [...(table?.querySelectorAll('tbody tr') || [])].map((tr) => [...tr.children].map((td) => ({
      l: td.dataset.label || '', w: r(td), sw: td.scrollWidth,
      kids: [...td.children].map((k) => `${k.tagName.toLowerCase()}:${r(k)}/${k.scrollWidth}`).join(' '),
      txt: td.textContent.trim().replace(/\s+/g, ' ').slice(0, 48),
    })))
    const faces = [...document.fonts].map((f) => `${f.family}/${f.weight}/${f.status}`)
    return {
      fontsStatus: document.fonts.status,
      hanken: document.fonts.check('13px "Hanken Grotesk"'),
      archivo: document.fonts.check('13px Archivo'),
      faces,
      bodyFont: getComputedStyle(document.body).fontFamily.slice(0, 80),
      tdFont: table ? getComputedStyle(table.querySelector('tbody td') || table).fontFamily.slice(0, 80) : '',
      wrap: wrap ? { sw: wrap.scrollWidth, cw: wrap.clientWidth, deborde: wrap.dataset.deborde, tableW: table ? r(table) : null } : null,
      docW: document.documentElement.clientWidth,
      rail: getComputedStyle(document.querySelector('.gen-summary-rail') || document.body).display,
      ths, nRows: rows.length, rows: rows.slice(0, 6),
    }
  })
  console.log(`[EDC10-SCRATCH ${moment}] ${JSON.stringify(d)}`)
  return d
}

async function devisDuLead(page) {
  const ref = (await page.locator('.ldp-ref').first().textContent())?.trim()
  expect(ref).toBeTruthy()
  let devis = null
  let url = `${API_DJANGO}/ventes/devis/`
  for (let p = 0; p < 3 && url && !devis; p += 1) {
    const corps = await lireJson(await page.request.get(url), 'liste des devis')
    devis = listeDe(corps).find((d) => d.reference === ref) || null
    url = corps?.next || null
  }
  expect(devis).toBeTruthy()
  return devis
}

async function parcours(page, etiquette) {
  await page.setViewportSize(GRAND_ECRAN)
  await gotoLeads(page)
  const nom = await createLead(page, { nom: uniq('EDCsc'), facture: 900 })
  await openLead(page, nom)
  await generateAutoDevis(page)
  const devis = await devisDuLead(page)
  await page.setViewportSize(PORTABLE)
  await page.goto(`/ventes/devis/nouveau?edit=${devis.id}`)
  await expect(page.locator('.gen-root')).toBeVisible()
  await dump(page, `${etiquette} gen-root`)
  await expect(page.getByRole('toolbar', { name: /Actions du devis/ })).toBeVisible()
  await expect(page.locator('tr[data-line-key]').first()).toBeVisible()
  const t0 = await dump(page, `${etiquette} lignes`)
  await page.evaluate(() => document.fonts.ready)
  await dump(page, `${etiquette} fonts.ready`)
  await page.waitForLoadState('networkidle').catch(() => {})
  await page.waitForTimeout(1500)
  const t1 = await dump(page, `${etiquette} settled`)
  console.log(`[EDC10-SCRATCH ${etiquette} RESUME] lignes=${t0.wrap?.sw}/${t0.wrap?.cw} hanken=${t0.hanken} → settled=${t1.wrap?.sw}/${t1.wrap?.cw} hanken=${t1.hanken}`)
}

test.describe('SCRATCH EDC10 — mesures', () => {
  test.setTimeout(150_000)

  test('police de marque chargée normalement', async ({ page }) => {
    await parcours(page, 'normal')
  })

  test('polices woff2 bloquées (repli = période swap)', async ({ page }) => {
    await page.route('**/*.woff2', (route) => route.abort())
    await parcours(page, 'sans-police')
  })
})
