// ODY32 — A11Y ET BUDGET PERF DU PARADIGME « ERP-Apps ».
// ----------------------------------------------------------------------------
// Trois garanties, sur les deux écrans que le paradigme a créés (le Menu
// d'accueil et la coquille en immersion), en thème CLAIR et en thème SOMBRE :
//   1. axe-core ne relève aucune violation `serious`/`critical` ;
//   2. le focus voyage proprement — entrer dans une app pose le focus sur le
//      CONTENU, en ressortir par le ⊞ le rend à la TUILE d'origine ;
//   3. les budgets de perception sont mesurés et consignés.
//
// Aucune dépendance nouvelle : l'assertion axe passe par le helper MAISON
// `assertNoSeriousA11yViolations` (e2e/helpers.js, VX71), et le thème sombre est
// forcé au boot via `localStorage['taqinor-theme']` — le mécanisme exact de
// visual.spec.js.
import { test, expect } from '@playwright/test'
import { assertNoSeriousA11yViolations } from './helpers'

const MENU = '/apps'
// CRM : l'app la plus riche du seed (nav, cockpit, badges) — la coquille en
// immersion y est la plus chargée, donc la plus exigeante pour axe.
const APP = { cle: 'crm', label: 'CRM' }

const tuile = (page, cle) => page.locator(`.home-menu-cell[data-app="${cle}"] .home-menu-tile`)

async function forcerSombre(page) {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-theme', 'dark') } catch { /* mode privé */ }
  })
}

for (const theme of ['clair', 'sombre']) {
  test(`ODY32: axe — Menu d’accueil et coquille d’app, thème ${theme}`, async ({ page }) => {
    if (theme === 'sombre') await forcerSombre(page)

    // 1) Le Menu d'accueil, entièrement peint (grille + recherche + sections).
    await page.goto(MENU)
    await expect(page.getByRole('heading', { name: 'Mes applications' })).toBeVisible()
    await expect(tuile(page, APP.cle)).toBeVisible()
    if (theme === 'sombre') {
      await expect(page.locator('html')).toHaveClass(/dark/)
    }
    // Scans CIBLÉS, comme partout dans cette suite (leads/devis/mobile) : on
    // garde ce que CETTE tâche possède, on n'hérite pas du bruit d'écrans
    // voisins qui ont leurs propres gardes.
    await assertNoSeriousA11yViolations(page, { include: '.home-menu' })

    // 2) La coquille en immersion (sidebar de l'app + topbar portant son
    //    identité, son fil d'Ariane et la sortie ⊞).
    await tuile(page, APP.cle).click()
    await expect(page.locator('aside.sidebar')).toHaveAttribute('data-app', APP.cle)
    await expect(page.locator('.header-title')).toBeVisible()
    await assertNoSeriousA11yViolations(page, { include: 'aside.sidebar' })
    await assertNoSeriousA11yViolations(page, { include: 'header.header' })
  })
}

test('ODY32: le focus fait l’aller-retour — contenu à l’entrée, tuile à la sortie', async ({ page }) => {
  await page.goto(MENU)
  await expect(page.getByRole('heading', { name: 'Mes applications' })).toBeVisible()

  // ── Aller : entrer dans une app pose le focus sur le CONTENU ─────────────
  // `RouteFocus` (VX197) déplace le focus sur `<main id="contenu">` à chaque
  // navigation SPA : après une entrée d'app, le Tab suivant part du contenu,
  // pas du header.
  await tuile(page, APP.cle).click()
  await expect(page.locator('aside.sidebar')).toHaveAttribute('data-app', APP.cle)
  await expect(page.locator('.header-title')).toBeVisible()
  await expect.poll(
    () => page.evaluate(() => document.activeElement?.id || ''),
    { message: 'le focus est passé au contenu après l’entrée dans l’app' },
  ).toBe('contenu')

  // ── L'app annonce discrètement la bascule (ODY32) ────────────────────────
  // Région polite dédiée, distincte de l'annonce de nom d'écran de RouteFocus :
  // elle ne parle que quand on CHANGE d'application.
  const annonce = page.locator('#taqinor-app-annonce')
  await expect(annonce).toHaveAttribute('aria-live', 'polite')
  await expect(annonce).toHaveText(`Application ${APP.label}`)

  // ── Retour : le ⊞ rend le focus à la tuile d'origine ─────────────────────
  await page.getByRole('button', { name: 'Toutes les apps' }).click()
  await expect(page).toHaveURL(/\/apps/)
  await expect(page.getByRole('heading', { name: 'Mes applications' })).toBeVisible()
  await expect.poll(
    async () => page.evaluate(
      () => document.activeElement?.closest('.home-menu-cell')?.getAttribute('data-app') || '',
    ),
    { message: 'le focus est revenu sur la tuile de l’app quittée' },
  ).toBe(APP.cle)
})

// ── Budgets de perception ───────────────────────────────────────────────────
// Les CIBLES du paradigme sont locales et exigeantes (Menu d'accueil : LCP
// < 1,5 s à froid ; entrée d'app : aucune tâche longue > 200 ms). Un runner CI
// partagé est plusieurs fois plus lent qu'un poste : y asserter ces seuils
// produirait un rouge aléatoire — le pire garde-fou possible. Ce test MESURE
// donc toujours, CONSIGNE la valeur dans le rapport (annotation + console, ce
// sont les chiffres à reporter au DONE LOG), et n'échoue que sur un plafond
// franchement dégradé, qui ne peut plus être du bruit de machine : une page
// qui met plus de 6 s à peindre, ou une tâche qui gèle le fil principal plus
// d'une seconde, est une VRAIE régression, pas un runner lent.
const LCP_PLAFOND_CI = 6000
const TACHE_PLAFOND_CI = 1000

function consigner(nom, valeur, cible) {
  const ligne = `${nom} = ${valeur} ms (cible locale ${cible} ms)`
  test.info().annotations.push({ type: 'budget', description: ligne })
  console.log(`[ODY32] ${ligne}`)
}

test('ODY32: budgets mesurés — LCP du Menu d’accueil, tâches longues à l’entrée', async ({ page }) => {
  // 1) LCP du Menu d'accueil. `largest-contentful-paint` est natif Chromium ;
  //    `buffered: true` récupère l'entrée même si l'observateur est posé après
  //    la peinture. Le Menu d'accueil ne fait AUCUNE requête bloquante (ODY2),
  //    ce qu'on vérifie indirectement : sa peinture ne dépend d'aucun réseau.
  await page.goto(MENU)
  await expect(page.getByRole('heading', { name: 'Mes applications' })).toBeVisible()
  const lcp = await page.evaluate(() => new Promise((resolve) => {
    let dernier = 0
    try {
      const obs = new PerformanceObserver((liste) => {
        for (const e of liste.getEntries()) dernier = e.startTime
      })
      obs.observe({ type: 'largest-contentful-paint', buffered: true })
    } catch { /* API absente : on retombe sur le repli ci-dessous */ }
    // Laisse une frame ou deux au navigateur pour livrer l'entrée bufferisée.
    setTimeout(() => resolve(Math.round(dernier)), 500)
  }))
  consigner('Menu d’accueil — LCP', lcp, 1500)
  expect(lcp, 'le Menu d’accueil peint dans un délai plausible').toBeLessThan(LCP_PLAFOND_CI)

  // 2) Tâches longues pendant l'ENTRÉE dans une app (chunk de route + rendu de
  //    la coquille). On observe `longtask` pendant la seule transition.
  await page.evaluate(() => {
    window.__ody32Taches = []
    try {
      const obs = new PerformanceObserver((liste) => {
        for (const e of liste.getEntries()) window.__ody32Taches.push(Math.round(e.duration))
      })
      obs.observe({ type: 'longtask', buffered: false })
    } catch { /* API absente : liste vide, le test reste vert */ }
  })
  await tuile(page, APP.cle).click()
  await expect(page.locator('aside.sidebar')).toHaveAttribute('data-app', APP.cle)
  await expect(page.locator('.header-title')).toBeVisible()
  const taches = await page.evaluate(() => window.__ody32Taches || [])
  const pire = taches.length ? Math.max(...taches) : 0
  consigner('Entrée d’app — pire tâche longue', pire, 200)
  expect(pire, 'aucune tâche ne gèle le fil principal à l’entrée d’une app')
    .toBeLessThan(TACHE_PLAFOND_CI)
})
