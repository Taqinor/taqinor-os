// LB33 — Régression « le board tient dans l'écran » (bug P0 fondateur, recon2-03).
//
// Le board kanban grandissait sur des MILLIERS de px (8 649 mesurés) : la page
// défilait verticalement et la scrollbar horizontale gisait SOUS le fold — il
// fallait « scroller tout en bas pour aller à droite ». Le fix (index.css :
// `.layout-content > .route-fade:has(> .lp-page){height:100%}` + la chaîne flex
// `.lp-page` / `.lp-view-area` / `.kb-board` / `.kb-col-body`, piloté par
// `data-view`) borne le shell au viewport et déplace le scroll DANS les vues
// denses. jsdom ne calcule AUCUNE hauteur/media-query : seul un vrai navigateur
// prouve ces invariants — d'où ce spec Playwright, tout en mesure (aucun
// screenshot). Il ÉCHOUE si l'on retire la règle `:has(> .lp-page)` (le shell se
// remet à défiler sur des milliers de px → invariant 1 rouge) : garde vérifiable
// en la commentant une fois.
//
// Invariants prouvés (blueprint D1/D6, §STRATÉGIE E2E) :
//   1. En kanban, le scrolleur du shell (`.layout-content`, overflow-y:auto) ne
//      déborde PAS verticalement (scrollHeight ≈ clientHeight) — même avec 20+
//      cartes dans une colonne (c'est CE cas qui débordait sans le fix).
//   2. La scrollbar horizontale du board (`.kb-board`) vit DANS le viewport, et
//      le board défile en X sans jamais faire défiler la page.
//   3. Une `.kb-col-body` défile verticalement (20+ cartes).
//   4. En liste, le `thead` reste épinglé en haut du scrolleur après défilement.
import { test, expect } from '@playwright/test'
import { gotoLeads, setLeadsView, createLead, uniq } from './helpers'

// Tolérance sous-pixel : un layout borné peut rapporter 0-2px d'arrondi ; la
// régression, elle, rouvre des MILLIERS de px — la marge sépare proprement
// « borné » de « cassé » sans jamais friser.
const PX = 4

test('LB33: le board kanban tient dans l’écran et défile en interne (jamais la page)', async ({ page }) => {
  // 20 créations réelles : une colonne assez haute pour DÉBORDER le viewport si
  // elle n'était pas bornée (le seuil qui rend l'invariant 1 sensible à la
  // régression). Coûteux → test.slow().
  test.slow()
  await gotoLeads(page)

  const names = []
  for (let i = 0; i < 20; i += 1) {
    // Créations séquentielles voulues : un seul board, une seule colonne à remplir.
    names.push(await createLead(page, { nom: uniq('Board') }))
  }

  await setLeadsView(page, 'kanban')
  const board = page.locator('.kb-board')
  await expect(board).toBeVisible()
  // La colonne « Nouveau » (1re du funnel) porte les 20 leads créés ; on la cible
  // par un nom créé pour ne dépendre d'AUCUN compteur de seed.
  const newBody = page.locator('.kb-col-body').filter({ hasText: names[0] })
  await expect(newBody).toBeVisible()

  // ── Invariant 1 : le scrolleur du shell ne déborde pas verticalement. ────────
  // `.layout-content` (overflow-y:auto) est CE qui débordait sur des milliers de
  // px quand la chaîne de hauteur était cassée (`:has(> .lp-page)` retiré).
  const shell = await page.locator('.layout-content').first().evaluate((el) => ({
    scrollHeight: el.scrollHeight, clientHeight: el.clientHeight,
  }))
  expect(
    shell.scrollHeight - shell.clientHeight,
    'le shell (.layout-content) ne défile pas verticalement en kanban',
  ).toBeLessThanOrEqual(PX)

  // ── Invariant 2 : la scrollbar horizontale du board vit DANS le viewport… ────
  const vp = page.viewportSize()
  const boardBox = await board.boundingBox()
  expect(boardBox, 'le board a une boundingBox').toBeTruthy()
  expect(
    boardBox.y + boardBox.height,
    'le bas du board (là où vit sa scrollbar horizontale) tient dans le viewport',
  ).toBeLessThanOrEqual(vp.height + PX)

  // … et le board défile en X sans faire défiler la PAGE (6 colonnes STAGES.py à
  // largeur fixe débordent la largeur visible au desktop → scroll horizontal réel).
  const boardScroll = await board.evaluate((el) => ({
    scrollWidth: el.scrollWidth, clientWidth: el.clientWidth,
  }))
  expect(
    boardScroll.scrollWidth,
    'le board a plus de colonnes que sa largeur visible (scroll horizontal réel)',
  ).toBeGreaterThan(boardScroll.clientWidth + PX)
  await board.evaluate((el) => { el.scrollLeft = el.scrollWidth })
  const afterX = await board.evaluate((el) => el.scrollLeft)
  expect(afterX, 'le board a bien défilé horizontalement').toBeGreaterThan(0)
  const pageScrollX = await page.evaluate(
    () => window.scrollX || document.documentElement.scrollLeft || 0,
  )
  expect(pageScrollX, 'défiler le board ne fait jamais défiler la page en X').toBe(0)
  const pageOverflowX = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(pageOverflowX, 'aucun débordement horizontal au niveau page').toBeLessThanOrEqual(1)

  // ── Invariant 3 : une colonne défile verticalement (20+ cartes). ────────────
  const colMetrics = await newBody.evaluate((el) => ({
    scrollHeight: el.scrollHeight, clientHeight: el.clientHeight,
  }))
  expect(
    colMetrics.scrollHeight,
    'la colonne « Nouveau » déborde son corps (20+ cartes → corps scrollable)',
  ).toBeGreaterThan(colMetrics.clientHeight + PX)
  await newBody.evaluate((el) => { el.scrollTop = el.scrollHeight })
  const colTop = await newBody.evaluate((el) => el.scrollTop)
  expect(colTop, 'le corps de colonne a bien défilé verticalement').toBeGreaterThan(0)

  // ── Invariant 4 : en liste, le thead reste épinglé en haut du scrolleur. ────
  await setLeadsView(page, 'liste')
  const wrap = page.locator('.lv-wrap')
  await expect(wrap).toBeVisible()
  const thead = page.locator('.lv-table thead')
  await expect(thead).toBeVisible()
  // Position du thead AVANT défilement (il est déjà en haut de la table).
  const theadYBefore = (await thead.boundingBox()).y
  // Défile la table tout en bas — les 20+ lignes garantissent un vrai débordement.
  await wrap.evaluate((el) => { el.scrollTop = el.scrollHeight })
  const wrapScrolled = await wrap.evaluate((el) => el.scrollTop)
  expect(wrapScrolled, 'la liste déborde réellement et a défilé').toBeGreaterThan(0)
  // Sticky prouvé : le thead N'A PAS bougé avec le contenu (sinon il serait remonté
  // hors de vue) — sa position à l'écran reste ~inchangée après le défilement.
  const theadBoxAfter = await thead.boundingBox()
  expect(theadBoxAfter, 'le thead a une boundingBox après défilement').toBeTruthy()
  expect(
    Math.abs(theadBoxAfter.y - theadYBefore),
    'le thead reste épinglé en haut du scrolleur .lv-wrap après défilement',
  ).toBeLessThanOrEqual(PX)
  await expect(thead).toBeInViewport()
})
