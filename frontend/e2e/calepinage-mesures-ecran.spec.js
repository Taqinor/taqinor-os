// ACAL385 — Mesures de l'atelier Calepinage, avec cliquet sur une base committée.
// Mesure : (a) contrôles visibles au premier écran, (b) tailles de texte
// distinctes, (c) cibles interactives < 44 px, (d) gestes lead -> production.
// `CAL_MESURES_ECRIRE=1` écrit calepinage-mesures-ecran.baseline.json ; sinon
// la spec échoue si une mesure dépasse la base (la base ne remonte qu'à la main).
// Sans base committée la spec est rouge (voulu : test rouge d'abord).
import { test, expect } from '@playwright/test'
import { readFileSync, writeFileSync, existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { uniq, gotoLeads, createLead } from './helpers'

const here = dirname(fileURLToPath(import.meta.url))
const BASE = join(here, 'calepinage-mesures-ecran.baseline.json')
const API = '/api/django/calepinage'
const ECRIRE = process.env.CAL_MESURES_ECRIRE === '1'
const CLES = ['controles_visibles', 'tailles_texte_distinctes', 'cibles_sous_44px', 'gestes_lead_production']

test('ACAL385: mesures de l’atelier ≤ base committée', async ({ page }) => {
  let gestes = 0
  const geste = async (action) => { gestes += 1; return action() }

  await gotoLeads(page)
  const nomLead = await createLead(page, { nom: uniq('ACAL385 Lead'), facture: 900, ville: 'Casablanca' })

  // ── gestes : du lead à la production lue ──
  await page.goto('/calepinage/nouveau')
  await geste(() => page.getByRole('tab', { name: 'Lead' }).click())
  await geste(() => page.locator('#cal-nouveau-lead').getByRole('combobox').click())
  await geste(() => page.getByRole('searchbox').fill(nomLead))
  await geste(() => page.getByRole('option', { name: new RegExp(nomLead) }).first().click())
  await geste(() => page.locator('#cal-nouveau-nom').fill(uniq('ACAL385 Toiture')))
  await geste(() => page.getByRole('button', { name: 'Créer le calepinage' }).click())
  await expect(page).toHaveURL(/\/calepinage\/\d+/)
  const id = /\/calepinage\/(\d+)/.exec(new URL(page.url()).pathname)[1]
  await expect(page.getByTestId('cal-rail-onglets')).toBeVisible()
  await page.waitForLoadState('networkidle').catch(() => {})

  const ctx = await page.request.get(`${API}/calepinages/${id}/design-context/`)
  const carte = ctx.ok() && !!(await ctx.json())?.carte?.available

  // ── (a)(b)(c) : premier écran de l'atelier, sans scroll ──
  const mesures = await page.evaluate(() => {
    const SEL = 'button, a[href], input, select, textarea, [role=tab]'
    const vw = window.innerWidth
    const vh = window.innerHeight
    const visible = (el) => {
      const r = el.getBoundingClientRect()
      const cs = getComputedStyle(el)
      return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'
        && r.bottom > 0 && r.right > 0 && r.top < vh && r.left < vw
    }
    const ctrls = [...document.querySelectorAll(SEL)].filter(visible)
    const tailles = new Set()
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      if (!n.nodeValue.trim() || !n.parentElement || !visible(n.parentElement)) continue
      tailles.add(getComputedStyle(n.parentElement).fontSize)
    }
    const petits = ctrls.filter((el) => {
      const r = el.getBoundingClientRect()
      return Math.min(r.width, r.height) < 44
    })
    return { controles_visibles: ctrls.length, tailles_texte_distinctes: tailles.size, cibles_sous_44px: petits.length }
  })

  // ── (d) production lue ──
  await geste(() => page.getByTestId('cal-onglet-production').click())
  await expect(page.getByTestId('cal-onglet-panneau')).toBeVisible()

  const actuel = { carte_disponible: carte, ...mesures, gestes_lead_production: gestes }

  if (ECRIRE) {
    writeFileSync(BASE, `${JSON.stringify(actuel, null, 2)}\n`)
    return
  }
  expect(existsSync(BASE), 'base absente : lancer une fois avec CAL_MESURES_ECRIRE=1 puis committer le JSON').toBeTruthy()
  const base = JSON.parse(readFileSync(BASE, 'utf8'))
  test.skip(base.carte_disponible !== carte,
    `base mesurée avec carte_disponible=${base.carte_disponible}, cet environnement l’a à ${carte} : mesures non comparables`)
  for (const cle of CLES) {
    expect(actuel[cle], `${cle} : ${actuel[cle]} dépasse la base ${base[cle]}`).toBeLessThanOrEqual(base[cle])
  }
})
