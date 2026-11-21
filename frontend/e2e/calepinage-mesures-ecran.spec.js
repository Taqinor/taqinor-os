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
import { execSync } from 'node:child_process'
import { uniq, gotoLeads, createLead } from './helpers'

const here = dirname(fileURLToPath(import.meta.url))
const BASE = join(here, 'calepinage-mesures-ecran.baseline.json')
const ECRIRE = process.env.CAL_MESURES_ECRIRE === '1'
const CLES = ['controles_visibles', 'tailles_texte_distinctes', 'cibles_sous_44px', 'gestes_lead_production']

// Atelier mesuré sur le FOND DE REPLI (ACAL377), comme acceptation/acal6.spec.js::carteRefusee :
// le runner n'a pas de clé MapTiler, la base est donc `carte_disponible: false`.
async function carteRefusee(context) {
  await context.route(/\/calepinage\/calepinages\/\d+\/design-context\//, async (route) => {
    const reelle = await route.fetch()
    const corps = await reelle.json()
    corps.carte = { ...(corps.carte || {}), available: true, maptilerKey: 'cle-factice-acal385', mapboxToken: null }
    await route.fulfill({ response: reelle, json: corps })
  })
  await context.route(/https:\/\/api\.maptiler\.com\//, (route) => route.fulfill({
    status: 403, contentType: 'application/json', body: '{"message":"Invalid key"}',
  }))
}

// ── ACAL478 : mesure du premier écran, partagée par les deux cas ──
async function mesurerPremierEcran(page) {
  return page.evaluate(() => {
    const SEL = 'button, a[href], input, select, textarea, [role=tab]'
    const vw = window.innerWidth
    const vh = window.innerHeight
    const visible = (el) => {
      const r = el.getBoundingClientRect()
      const cs = getComputedStyle(el)
      return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'
        && r.bottom > 0 && r.right > 0 && r.top < vh && r.left < vw
    }
    return [...document.querySelectorAll(SEL)].filter(visible).length
  })
}

// La base se met à jour par FUSION : chaque cas n'écrit que sa part.
function lireBase() {
  return existsSync(BASE) ? JSON.parse(readFileSync(BASE, 'utf8')) : {}
}
function fusionnerBase(part) {
  writeFileSync(BASE, `${JSON.stringify({ ...lireBase(), ...part }, null, 2)}
`)
}

test.describe.configure({ mode: 'serial' })

test('ACAL385: mesures de l’atelier ≤ base committée', async ({ page }) => {
  await carteRefusee(page.context())
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
  await expect(page.getByTestId('cal-rail-onglets')).toBeVisible()
  await expect(page.getByTestId('cal-enregistrer-calepinage').getByRole('button', { name: /Enregistrer le calepinage/ }))
    .toBeEnabled({ timeout: 240_000 })
  await expect(page.locator('#rp9-status')).not.toHaveText(/^Chargement/)
  await page.waitForLoadState('networkidle').catch(() => {})

  const carte = false // fond de repli forcé (cf. carteRefusee)

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
  await geste(() => page.getByTestId('cal-etape-resultats').click())
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

// ACAL478 — budget de simplicité du MODE GUIDÉ (mode expert éteint, par défaut).
// Seuls les « 5 étapes » viennent du squelette du complément ; tous les autres
// seuils sont LUS dans `mode_guide` de la base (mesurés, jamais tapés ici).
test('ACAL478: budget du mode guidé', async ({ page }) => {
  await carteRefusee(page.context())
  await gotoLeads(page)
  const nomLead = await createLead(page, { nom: uniq('ACAL478 Lead'), facture: 900, ville: 'Casablanca' })

  await page.goto('/calepinage/nouveau')
  await page.getByRole('tab', { name: 'Lead' }).click()
  await page.locator('#cal-nouveau-lead').getByRole('combobox').click()
  await page.getByRole('searchbox').fill(nomLead)
  await page.getByRole('option', { name: new RegExp(nomLead) }).first().click()
  await page.locator('#cal-nouveau-nom').fill(uniq('ACAL478 Toiture'))
  await page.getByRole('button', { name: 'Créer le calepinage' }).click()
  await expect(page).toHaveURL(/\/calepinage\/\d+/)
  await expect(page.getByTestId('cal-rail-onglets')).toBeVisible()
  await expect(page.getByTestId('cal-enregistrer-calepinage').getByRole('button', { name: /Enregistrer le calepinage/ }))
    .toBeEnabled({ timeout: 240_000 })
  await expect(page.locator('#rp9-status')).not.toHaveText(/^Chargement/)
  await page.waitForLoadState('networkidle').catch(() => {})

  // Le mode expert est éteint (état d'un utilisateur neuf).
  await expect(page.getByTestId('cal-mode-expert')).not.toBeChecked()

  const etapes = await page.locator('[data-testid="cal-rail-etapes"] button').count()
  const controles = await mesurerPremierEcran(page)

  if (ECRIRE) {
    let commit = process.env.GITHUB_SHA || ''
    if (!commit) { try { commit = execSync('git rev-parse HEAD').toString().trim() } catch { commit = 'inconnu' } }
    fusionnerBase({
      mode_guide: {
        mesure_le: new Date().toISOString().slice(0, 10),
        commit_mesure: commit,
        etapes,
        controles_premier_ecran: controles,
      },
    })
  }

  // Chemin lead -> production : AUCUNE saisie, aucun détour par `fiches`/`reglages`.
  await page.getByTestId('cal-etape-resultats').click()
  await page.getByTestId('cal-onglet-production').click()
  await expect(page.getByTestId('cal-onglet-panneau')).toBeVisible()
  for (const cle of ['fiches', 'reglages']) {
    await expect(page.locator(`[data-testid="cal-onglet-${cle}"][aria-selected="true"]`),
      `l'onglet ${cle} ne doit pas être requis avant un premier résultat`).toHaveCount(0)
  }

  expect(etapes, `le mode guidé compte ${etapes} étapes (budget : 5)`).toBeLessThanOrEqual(5)
  const base = lireBase().mode_guide
  expect(base, 'section mode_guide absente : lancer une fois avec CAL_MESURES_ECRIRE=1 puis committer le JSON').toBeTruthy()
  expect(controles, `contrôles du premier écran : ${controles} dépasse la base ${base.controles_premier_ecran}`)
    .toBeLessThanOrEqual(base.controles_premier_ecran)
})
