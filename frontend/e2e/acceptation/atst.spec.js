// Preuves en direct du groupe ATST (audit PF7 « tests qui ne prouvent rien », dossier
// docs/audits/2026-11-11-parcours-PF7.md) jouées AU NAVIGATEUR. Une seule tâche du groupe a une
// preuve d'écran : ATST27 (garde de sortie + brouillon local du générateur en création). Les autres
// preuves du groupe (sondes hôtes, gardes `scripts/check_*.py` et leurs mutants, tests Django non
// tagués, lecture de l'alerte nocturne) sont rejouées hors navigateur et fusionnées dans le même
// enregistrement (`_enregistrement.js --etapes-supplementaires`).
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { assurerSessionPage } from '../helpers.js'

const etape = groupe('ATST', ['ATST27'])
const CLE = 'taqinor:draft:devis:new'
const LIGNES = 'table.lines-table tbody tr[data-line-key]'
test.describe.configure({ timeout: 300_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })

/** Onglet observé comme `suivi.surveiller` (oracles 1-3), SAUF le dialogue `beforeunload` : c'est
 *  précisément ce que l'étape attend (la confirmation du navigateur à la fermeture). Tout AUTRE
 *  dialogue natif reste un incident de l'oracle 4. */
function ongletObserve(onglet, suivi, origine, vus) {
  onglet.on('response', (r) => {
    const s = r.status()
    if (s >= 400 && r.url().startsWith(origine)) {
      suivi.incidents.push({ oracle: s >= 500 ? '1' : '2', texte: `${r.request().method()} ${r.url()} → ${s}` })
    }
  })
  onglet.on('console', (msg) => {
    if (msg.type() === 'error') suivi.incidents.push({ oracle: '3', texte: `console.error : ${msg.text()}` })
  })
  onglet.on('pageerror', (e) => suivi.incidents.push({ oracle: '3', texte: `pageerror : ${e.message}` }))
  onglet.on('dialog', async (d) => {
    if (d.type() === 'beforeunload') {
      vus.push(d.type())
      await d.accept().catch(() => undefined) // « Quitter » : l'onglet se ferme
      return
    }
    suivi.incidents.push({ oracle: '4', texte: `dialogue natif ${d.type()} : ${d.message()}` })
    await d.dismiss().catch(() => undefined)
  })
}

etape('PF7.3-ATST27', ['ATST27'], async ({ page, context, suivi, testInfo }) => {
  // Given : aucun brouillon de création dans ce navigateur.
  await page.goto('/dashboard')
  await page.evaluate((k) => window.localStorage.removeItem(k), CLE)

  // Onglet 1 : /ventes/devis/nouveau vierge.
  const origine = new URL(testInfo.project.use.baseURL).origin
  const vus = []
  const onglet = await context.newPage()
  ongletObserve(onglet, suivi, origine, vus)
  await onglet.goto('/ventes/devis/nouveau')
  await expect(onglet.locator('#gen-form')).toBeVisible({ timeout: 60_000 })
  await onglet.waitForLoadState('networkidle', { timeout: 90_000 }).catch(() => undefined)
  await onglet.waitForTimeout(2_000)
  // Observation (pas une assertion — hors ATST27, c'est ATST56, ouverte) : un brouillon existe-t-il
  // déjà avant toute saisie (composition par défaut comptée comme une saisie) ?
  const avant = await onglet.evaluate((k) => window.localStorage.getItem(k), CLE)
  testInfo.annotations.push({ type: 'observation ATST56', description: `brouillon avant saisie : ${avant ? 'PRÉSENT' : 'absent'}` })
  console.log(`[ATST27] brouillon avant toute saisie : ${avant ? 'PRÉSENT' : 'absent'}`)

  // When : ajouter une ligne et taper une désignation.
  const designation = `ATST27 câble ${Date.now().toString(36)}`
  const avantLignes = await onglet.locator(LIGNES).count()
  await onglet.getByRole('button', { name: 'Ajouter ligne' }).first().click()
  await expect(onglet.locator(LIGNES)).toHaveCount(avantLignes + 1)
  const champ = onglet.locator(LIGNES).last().locator('td[data-label="Désignation"] input')
  await champ.click()
  await champ.fill(designation)
  await expect(champ).toHaveValue(designation)

  // Le brouillon local porte la ligne tapée (persistance : relue dans localStorage).
  await expect.poll(async () => onglet.evaluate((k) => {
    try { return (JSON.parse(window.localStorage.getItem(k) || 'null')?.data?.lines || []).map((l) => l.designation) } catch { return [] }
  }, CLE), { timeout: 20_000, message: 'brouillon taqinor:draft:devis:new écrit avec la désignation' }).toContain(designation)

  // Then (1) : fermer l'onglet ⇒ le navigateur demande confirmation (beforeunload).
  await onglet.close({ runBeforeUnload: true })
  await expect.poll(() => vus.length, { timeout: 15_000, message: 'dialogue beforeunload à la fermeture' }).toBeGreaterThan(0)
  await expect.poll(() => onglet.isClosed(), { timeout: 15_000 }).toBe(true)

  // Then (2) : rouvrir ⇒ le brouillon est proposé, et le reprendre rend la ligne tapée.
  await page.goto('/ventes/devis/nouveau')
  await expect(page.locator('#gen-form')).toBeVisible({ timeout: 60_000 })
  const bandeau = page.getByTestId('draft-restore-banner')
  await expect(bandeau, 'bandeau « Un brouillon non enregistré … a été retrouvé »').toBeVisible({ timeout: 30_000 })
  await expect(bandeau).toContainText('brouillon non enregistré')
  await bandeau.getByRole('button', { name: 'Reprendre le brouillon' }).click()
  await expect(page.locator(`${LIGNES} td[data-label="Désignation"] input`).last()).toHaveValue(designation, { timeout: 15_000 })
  // Nettoyage : le contexte Playwright est jetable (storageState relu, jamais réécrit) ; la clé est retirée quand même.
  await page.evaluate((k) => window.localStorage.removeItem(k), CLE)
})
