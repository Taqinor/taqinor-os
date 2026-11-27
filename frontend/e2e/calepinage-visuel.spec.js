// ACAL384 — Base visuelle du module Calepinage (@visual), clair + sombre.
// Même mécanique que visual.spec.js (SHOT, thème sombre par localStorage,
// mode présentation éteint). Tourne dans `e2e-full` / `visual-baselines` de
// release-verify.yml (`--grep @visual`), jamais dans le shard par-merge.
// Images de référence : `--update-snapshots`, relues puis committées par Reda
// sous calepinage-visuel.spec.js-snapshots/ (sans elles, la spec est rouge).
// Écrans : liste, atelier (rail + étape toit = page /calepinage/:id), onglets
// production et documents (le registre atelier/onglets.js n'a pas de clé `toit`).
import { test, expect } from '@playwright/test'
import { AUTH_FILE, uniq, gotoLeads, createLead } from './helpers'

const API = '/api/django/calepinage'
const SHOT = { fullPage: true, animations: 'disabled', maxDiffPixelRatio: 0.02 }
const THEMES = ['clair', 'sombre']

test.describe.configure({ mode: 'serial' })

let calepinageId = null
let designContextOk = false

// Fond de repli ACAL377 (même montage que acceptation/acal6.spec.js::carteRefusee) : le serveur
// « publie » une clé factice, le style d'imagerie répond 403 -> l'atelier dessine sur son fond de
// repli, sans MapTiler, de façon déterministe (le runner n'a aucune clé).
async function carteRefusee(context) {
  await context.route(/\/calepinage\/calepinages\/\d+\/design-context\//, async (route) => {
    const reelle = await route.fetch()
    const corps = await reelle.json()
    corps.carte = { ...(corps.carte || {}), available: true, maptilerKey: 'cle-factice-acal384', mapboxToken: null }
    await route.fulfill({ response: reelle, json: corps })
  })
  await context.route(/https:\/\/api\.maptiler\.com\//, (route) => route.fulfill({
    status: 403, contentType: 'application/json', body: '{"message":"Invalid key"}',
  }))
}

test.beforeAll(async ({ browser }, testInfo) => {
  const ctx = await browser.newContext({
    baseURL: testInfo.project.use.baseURL, storageState: AUTH_FILE,
  })
  const page = await ctx.newPage()
  try {
    await gotoLeads(page)
    const nomLead = await createLead(page, { nom: uniq('ACAL384 Lead'), facture: 900, ville: 'Casablanca' })
    await page.goto('/calepinage/nouveau')
    await page.getByRole('tab', { name: 'Lead' }).click()
    await page.locator('#cal-nouveau-lead').getByRole('combobox').click()
    await page.getByRole('searchbox').fill(nomLead)
    await page.getByRole('option', { name: new RegExp(nomLead) }).first().click()
    await page.locator('#cal-nouveau-nom').fill(uniq('ACAL384 Toiture'))
    await page.getByRole('button', { name: 'Créer le calepinage' }).click()
    await page.waitForURL(/\/calepinage\/\d+/)
    calepinageId = /\/calepinage\/(\d+)/.exec(new URL(page.url()).pathname)?.[1] ?? null
    const res = await page.request.get(`${API}/calepinages/${calepinageId}/design-context/`)
    designContextOk = res.ok()
  } finally {
    await ctx.close()
  }
})

// Même précondition que visual.spec.js : mode présentation éteint.
test.beforeEach(async ({ page }) => {
  const me = await page.request.get('/api/django/auth/me/')
  if (!me.ok()) return
  const moi = await me.json()
  if (!moi?.company_mode_presentation_actif) return
  const r = await page.request.patch(`/api/django/companies/${moi.company_id}/`, {
    data: { mode_presentation_actif: false },
  })
  expect(r.ok(), `mode présentation éteint (${r.status()})`).toBeTruthy()
})

const ECRANS = [
  { nom: 'liste', carte: false, chemin: () => '/calepinage',
    pret: (page) => expect(page.locator('.header-title')).toBeVisible() },
  { nom: 'atelier-rail-toit', carte: true, chemin: (id) => `/calepinage/${id}`,
    pret: (page) => expect(page.getByTestId('cal-rail-onglets')).toBeVisible() },
  { nom: 'production', carte: true, panneau: true, chemin: (id) => `/calepinage/${id}?onglet=production`,
    pret: (page) => expect(page.getByTestId('cal-onglet-panneau')).toBeVisible() },
  { nom: 'documents', carte: true, panneau: true, chemin: (id) => `/calepinage/${id}?onglet=documents`,
    pret: (page) => expect(page.getByTestId('cal-onglet-panneau')).toBeVisible() },
]

for (const theme of THEMES) {
  for (const ecran of ECRANS) {
    test(`${ecran.nom} — capture ${theme}`, { tag: '@visual' }, async ({ page }) => {
      test.skip(ecran.carte && !designContextOk,
        'design-context illisible : l’atelier ne peut pas booter même sur le fond de repli (ACAL377)')
      test.skip(calepinageId == null, 'calepinage de départ non créé (beforeAll)')
      if (theme === 'sombre') {
        await page.addInitScript(() => {
          try { localStorage.setItem('taqinor-theme', 'dark') } catch { /* mode privé */ }
        })
      }
      if (ecran.carte) await carteRefusee(page.context())
      await page.goto(ecran.chemin(calepinageId))
      await ecran.pret(page)
      if (ecran.carte) {
        await expect(page.getByTestId('cal-enregistrer-calepinage').getByRole('button', { name: /Enregistrer le calepinage/ }))
          .toBeEnabled({ timeout: 240_000 })
        await expect(page.locator('#rp9-status')).not.toHaveText(/^Chargement/)
      }
      await page.waitForLoadState('networkidle').catch(() => {})
      // Noms/dates dérivent d'uniq() et de l'horloge : masqués (inerte si rien ne matche).
      const nomUniq = page.getByText(/ACAL384/) // noms issus de uniq() : masqués
      const nom = `calepinage-${ecran.nom}-${theme}.png`
      if (ecran.nom === 'liste') {
        await expect(page).toHaveScreenshot(nom, { ...SHOT, mask: [page.locator('tbody'), page.locator('[role=row]')] })
      } else if (ecran.panneau) {
        // Le contenu de l'onglet vit sous la carte, dans un conteneur qui défile : la capture
        // « page entière » ne le verrait pas (run 44828700657 : 3 PNG identiques). On capture le panneau.
        const panneau = page.getByTestId('cal-onglet-panneau')
        await panneau.scrollIntoViewIfNeeded()
        await expect(panneau).toHaveScreenshot(nom, { animations: 'disabled', maxDiffPixelRatio: 0.02, mask: [nomUniq] })
      } else {
        await expect(page).toHaveScreenshot(nom, { ...SHOT, mask: [page.locator('#rp9-map'), nomUniq] })
      }
    })
  }
}
