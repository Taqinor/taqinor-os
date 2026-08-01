// APX8 — LA GATE DE DENSITÉ : les chiffres du fondateur deviennent des specs.
// ----------------------------------------------------------------------------
// APX2/3/4/5/7 ont TOUS renvoyé leur mesure en pixels ici : « la MESURE
// appartient à la gate APX8 ». C'est donc le seul endroit du dépôt où les
// promesses de densité sont vérifiées sur l'app RÉELLE, dans un vrai moteur de
// rendu (jsdom ne calcule ni hauteur ni media-query — aucun test unitaire ne
// peut prouver ceci).
//
// L'ÉTAT D'AVANT, mesuré par le fondateur (2026-08-01) :
//   • carte kanban lead 120-150 px au repos, contre ~60-70 px chez Odoo
//     → 3-4 cartes visibles par colonne en 1366×768 (delta ×2,3) ;
//   • chrome vertical ≈ 286 px avant la première carte ;
//   • `.kb-col` figée à 272 px → la 6ᵉ étape (COLD) hors champ presque partout ;
//   • vue liste : 33 à 65 px PAR LIGNE selon le lead (deux lignes voisines
//     n'avaient même pas la même hauteur).
//
// MÉTHODE — capacité DÉRIVÉE, pas comptage de cartes seedées.
// On mesure la hauteur RÉELLE d'une carte au repos et la hauteur RÉELLEMENT
// disponible, puis on en déduit combien de cartes tiennent. Deux raisons :
//   1. le résultat ne dépend d'AUCUN volume de données (la base e2e est
//      partagée et mutée par les specs précédents — compter des cartes
//      seedées ferait dépendre la gate de l'ordre d'exécution) ;
//   2. c'est exactement la promesse du fondateur (« on voit beaucoup de leads
//      d'un coup »), sans y mêler la question « y a-t-il assez de leads ? ».
//
// TEST DU TEST — +40 px de padding sur `.kb-card--lead` fait passer le slot de
// ~84 px à ~124 px : la capacité 1440×900 tombe de ~8 à 5, sous le seuil de 7,
// et la gate rougit. Vérifiable en une ligne de CSS.
//
// SEUILS — volontairement DÉGRADÉS par rapport aux cibles annoncées, et la
// mesure réelle est ENREGISTRÉE à chaque run (annotations Playwright, visibles
// dans le rapport HTML). Un runner CI partagé ne rend pas au pixel près comme
// un poste de dev : une gate qui frise sa cible est une gate qui clignote. Les
// seuils restent très en dessous de l'état d'avant, donc un ré-épaississement
// est capté ; c'est un plancher, pas l'objectif.
//
// PROJETS/VIEWPORTS — ce fichier n'est matché que par le projet `chromium`
// (les projets `mobile`, `mobile-safari` et `tablet` ont un `testMatch`
// explicite sur leur propre spec) : chaque bloc DÉCLARE donc son viewport, et
// les blocs tactiles déclarent `hasTouch`/`isMobile`, ce qui fait matcher
// `(hover: none)` / `(pointer: coarse)` dans Chromium — exactement le
// mécanisme sur lequel repose le projet `mobile` de la config.
//
// ANCRAGES — aucun sélecteur inventé : `.kb-board`, `.kb-col`, `.kb-col-body`,
// `article.kb-card`, `tr.lv-row`, `.lv-wrap`, `.header-title` viennent des
// specs verts (leads-board.spec.js, helpers.js, mobile.spec.js) ou du bloc CSS
// de la tâche APX correspondante ; `[data-dt-table]` vient de
// datatable-breakpoint.spec.js. Les 6 étapes ne sont JAMAIS écrites en dur :
// leur nombre vient de `STAGE_LABELS` (miroir de STAGES.py, règle #2).
import { test, expect } from '@playwright/test'
import { STAGE_LABELS , boutonNouveauLead } from './helpers'

// Tolérance sous-pixel (même valeur que LB33) : un layout borné rapporte 0-2 px
// d'arrondi ; une vraie régression se compte en dizaines de px.
const PX = 4

// design/theme.js — la préférence de densité vit dans ce localStorage et est
// appliquée au <html> au démarrage (ThemeProvider → initTheme → applyDensity).
const DENSITY_KEY = 'taqinor-density'

const NB_ETAPES = Object.keys(STAGE_LABELS).length

/** Force la densité « compacte » AVANT le boot de l'app (donc avant tout rendu). */
async function densiteCompacte(page) {
  await page.addInitScript((cle) => {
    try { window.localStorage.setItem(cle, 'compact') } catch { /* stockage indisponible */ }
  }, DENSITY_KEY)
}

/** Note une mesure dans le rapport Playwright (elle est LUE, jamais assertée). */
function noter(info, quoi, valeur) {
  info.annotations.push({ type: 'densité', description: `${quoi} = ${valeur}` })
}

/**
 * Ouvre le board leads sur une vue EXPLICITE.
 *
 * On passe par `?view=` (lu par `readViewFromParams`, urlFilters.js) plutôt que
 * par le sélecteur de vue : l'URL prime sur la session ET sur la « vue par
 * défaut du compte » (LB49), donc la gate mesure toujours la vue qu'elle croit
 * mesurer, quel que soit l'état laissé par un spec précédent. C'est aussi la
 * SEULE façon de choisir la vue sous 768 px, où le ViewSwitcher n'est pas rendu
 * (LeadsPage `{!isMobile && <ViewSwitcher …>}`) — le helper `setLeadsView` y
 * échouerait.
 *
 * L'ancre de disponibilité est celle de `gotoLeads` : « + Nouveau lead », nom
 * accessible porté par le bouton d'en-tête au bureau ET par le FAB au
 * téléphone (LB47), donc valable aux deux largeurs.
 */
async function ouvrirLeads(page, vue) {
  await page.goto(`/crm/leads?view=${vue}`)
  await expect(boutonNouveauLead(page)).toBeVisible()
}

/**
 * Géométrie du kanban : hauteur d'une carte au repos, place disponible dans la
 * colonne la plus peuplée, et capacité qui en découle.
 *
 * Le board est l'UNIQUE scrolleur vertical depuis LB41 (le corps de colonne ne
 * scrolle plus) : la place réellement offerte à une colonne va donc du haut de
 * son corps jusqu'au bas de la zone cliente du board.
 */
async function mesurerKanban(page) {
  const board = page.locator('.kb-board')
  await expect(board).toBeVisible()
  // On vise la colonne qui porte le plus de cartes — c'est elle qui incarne la
  // promesse « je vois mon pipeline d'un regard ».
  const geo = await board.evaluate((b) => {
    const colonnes = [...b.querySelectorAll('.kb-col:not(.kb-col-collapsed)')]
    let corps = null
    let cartes = []
    for (const col of colonnes) {
      const c = [...col.querySelectorAll('article.kb-card')]
      if (c.length > cartes.length) { cartes = c; corps = col.querySelector('.kb-col-body') }
    }
    if (!corps) return { cartes: [], colonnes: colonnes.length }
    const cs = getComputedStyle(corps)
    const gap = parseFloat(cs.rowGap) || parseFloat(cs.gap) || 0
    const rb = b.getBoundingClientRect()
    const padBas = parseFloat(getComputedStyle(b).paddingBottom) || 0
    return {
      colonnes: colonnes.length,
      gap,
      // Bas de la zone cliente du board (sa scrollbar horizontale et son
      // padding bas ne sont pas de la place pour des cartes).
      dispo: (rb.top + b.clientHeight - padBas) - corps.getBoundingClientRect().top,
      cartes: cartes.map((c) => c.getBoundingClientRect().height),
      premiereCarteY: cartes[0].getBoundingClientRect().top,
      basBoard: rb.top + rb.height,
    }
  })
  expect(geo.cartes.length, 'au moins une carte lead est rendue (seed_demo en crée 3)')
    .toBeGreaterThan(0)
  // La carte la PLUS HAUTE décide : la capacité doit tenir pour tous les leads,
  // pas seulement pour le plus court.
  const carteMax = Math.max(...geo.cartes)
  const slot = carteMax + geo.gap
  return {
    ...geo,
    carteMax: Math.round(carteMax),
    // Combien de slots entiers tiennent (le dernier n'a pas de gouttière après).
    capacite: Math.floor((geo.dispo + geo.gap) / slot),
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// 1440×900 — LE VIEWPORT DE RÉFÉRENCE (celui où les chiffres ont été promis)
// ═══════════════════════════════════════════════════════════════════════════
test.describe('APX8 — densité, viewport de référence 1440×900', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  test('le board kanban tient 7+ cartes par étape, avec un chrome repris', async ({ page }, info) => {
    await ouvrirLeads(page, 'kanban')
    const m = await mesurerKanban(page)

    noter(info, 'carte lead au repos (px, la plus haute)', m.carteMax)
    noter(info, 'hauteur disponible par colonne (px)', Math.round(m.dispo))
    noter(info, 'cartes par colonne (capacité dérivée)', m.capacite)

    // (a) La carte au repos. Contrat APX2 : 3 lignes, ~76 px. Le plafond ci-
    //     dessous est un DÉTECTEUR de ré-épaississement (l'état d'avant était
    //     120-150 px), pas la cible.
    expect(m.carteMax, 'la carte lead au repos reste franchement sous son état d’avant (120-150 px)')
      .toBeLessThanOrEqual(104)

    // (b) LA promesse du fondateur : « on voit beaucoup de leads d'un coup ».
    expect(m.capacite, 'cartes visibles par étape en 1440×900').toBeGreaterThanOrEqual(7)

    // (c) Le chrome vertical (tout ce qui n'est PAS de la carte) : 286 px
    //     mesurés avant APX3, ~228 px après. C'est un TRIPWIRE anti-retour en
    //     arrière, pas la cible : la hauteur de la rangée de contrôles et celle
    //     de la rangée de facettes (rendue seulement quand des facettes
    //     existent — donc dépendante des données de la base e2e partagée)
    //     entrent dans ce total, et une gate calée sur 228 clignoterait pour
    //     une raison qui n'est pas de la densité. Le vrai gardien du chiffre,
    //     c'est (b) : la capacité, qui dépend du chrome ET de la carte.
    const chrome = Math.round(m.premiereCarteY + (900 - m.basBoard))
    noter(info, 'chrome vertical (px)', chrome)
    expect(chrome, 'le chrome vertical du board ne revient jamais à ses 286 px d’avant')
      .toBeLessThan(286)
  })

  test('les 6 étapes du funnel tiennent d’un regard en plein écran', async ({ page }) => {
    await ouvrirLeads(page, 'kanban')
    const board = page.locator('.kb-board')
    await expect(board).toBeVisible()

    // APX4 a livré un calque plein écran LOCAL à l'écran leads (position:fixed,
    // inset:0) et NON un repli de la sidebar globale : le plan demandait
    // « sidebar repliée », le code a fait mieux sans toucher la préférence
    // globale de Layout — c'est ce que la gate mesure. Le bouton est ciblé par
    // sa classe : son nom accessible bascule entre « Plein écran » et
    // « Quitter le plein écran », deux libellés dont l'un contient l'autre
    // (le mode strict de Playwright cherche une SOUS-CHAÎNE).
    const bouton = page.locator('.lp-fullscreen-btn')
    await expect(bouton).toBeVisible()
    await bouton.click()
    await expect(page.locator('.lp-page--fullscreen')).toHaveCount(1)

    // Toutes les étapes de STAGES.py sont rendues (règle #2 : jamais une liste
    // d'étapes écrite ici — on lit le miroir e2e).
    await expect(page.locator('.kb-col')).toHaveCount(NB_ETAPES)
    // …et elles tiennent SANS défilement horizontal : 6×204 + 5×12 = 1284 px
    // requis, ~1400 px offerts par le calque plein écran.
    const largeur = await board.evaluate((el) => ({
      scrollWidth: el.scrollWidth, clientWidth: el.clientWidth,
    }))
    expect(
      largeur.scrollWidth,
      `les ${NB_ETAPES} étapes tiennent dans la largeur en plein écran (aucun scroll horizontal)`,
    ).toBeLessThanOrEqual(largeur.clientWidth + PX)

    // Hygiène : on ressort du mode (Échap, comme un utilisateur).
    await page.keyboard.press('Escape')
    await expect(page.locator('.lp-page--fullscreen')).toHaveCount(0)
  })

  test('la vue Liste tient UNE ligne par lead, toutes de la même hauteur', async ({ page }, info) => {
    await densiteCompacte(page)
    await ouvrirLeads(page, 'liste')
    // La préférence a bien été prise au boot : sans elle, le comptage ne
    // mesurerait pas ce qu'on croit.
    await expect(page.locator('html')).toHaveAttribute('data-density', 'compact')

    const wrap = page.locator('.lv-wrap')
    await expect(wrap).toBeVisible()
    await expect(page.locator('tr.lv-row').first()).toBeVisible()

    const m = await wrap.evaluate((el) => {
      const lignes = [...el.querySelectorAll('tr.lv-row')]
        .map((r) => r.getBoundingClientRect().height)
        .filter((h) => h > 0)
      const thead = el.querySelector('thead')
      return {
        lignes,
        thead: thead ? thead.getBoundingClientRect().height : 0,
        dispo: el.clientHeight,
      }
    })
    expect(m.lignes.length, 'au moins une ligne de lead est rendue').toBeGreaterThan(0)

    const hMax = Math.max(...m.lignes)
    const hMin = Math.min(...m.lignes)
    const capacite = Math.floor((m.dispo - m.thead) / hMax)
    noter(info, 'ligne de liste (px, min → max)', `${Math.round(hMin)} → ${Math.round(hMax)}`)
    noter(info, 'lignes visibles (capacité dérivée)', capacite)

    // (a) LE gain d'APX5 que rien d'autre ne garde : une seule hauteur de
    //     ligne. Avant, la cellule Lead s'empilait sur 3 lignes SELON LE LEAD
    //     (33 à 65 px) — deux voisines n'avaient pas la même hauteur. Cette
    //     assertion est indépendante du rendu de police : elle compare le
    //     tableau à lui-même.
    expect(
      hMax - hMin,
      'toutes les lignes de la liste ont la même hauteur (une seule rangée par lead)',
    ).toBeLessThanOrEqual(PX)

    // (b) Le comptage. Cible annoncée : 18+. Plancher gardé ici : 16 — très
    //     au-dessus des ~10 lignes que donnaient les cellules à 65 px.
    expect(capacite, 'lignes de leads visibles en 1440×900, densité compacte')
      .toBeGreaterThanOrEqual(16)
  })

  // « La densité promise vaut pour les apps nommées par le fondateur, pas que
  // pour les leads » — mêmes viewports, SEUILS DOUX (le mot du plan).
  // Ces deux écrans sont bâtis sur le moteur DataTable, dont la hauteur de
  // ligne est DÉJÀ pilotée par la préférence de densité (ARC49/53, APX34) : la
  // gate n'y refait pas le travail des tests du moteur, elle ENREGISTRE la
  // mesure et pose un plafond de catastrophe. On n'y asserte volontairement
  // PAS l'uniformité des lignes (elle vaut pour la vue Liste des leads, qu'
  // APX5 a explicitement mise à une seule rangée) : ici un libellé produit qui
  // passe à la ligne est un contenu légitime, pas une régression de densité.
  for (const cible of [
    { nom: 'liste des devis', url: '/ventes/devis', plafond: 76 },
    // Le catalogue Stock porte une vignette produit de 40 px (APX18) : sa
    // ligne est légitimement plus haute que celle d'une table de documents.
    { nom: 'catalogue Stock', url: '/stock', plafond: 92 },
  ]) {
    test(`densité douce — ${cible.nom}`, async ({ page }, info) => {
      await densiteCompacte(page)
      await page.goto(cible.url)
      await expect(page.locator('.header-title')).toBeVisible()
      await page.waitForLoadState('networkidle').catch(() => {})

      const table = page.locator('[data-dt-table]').first()
      // Écran sans table rendue (repli cartes, liste vide, module absent) :
      // il n'y a rien à mesurer — on l'enregistre plutôt que d'inventer un
      // échec. La densité des leads, elle, reste gardée dur au-dessus.
      if (!(await table.count())) {
        noter(info, `${cible.nom}`, 'aucune table rendue — mesure sautée')
        return
      }
      const lignes = await table.evaluate((el) => [...el.querySelectorAll('tbody tr[aria-rowindex]')]
        .map((r) => r.getBoundingClientRect().height)
        .filter((h) => h > 0))
      if (!lignes.length) {
        noter(info, `${cible.nom}`, 'aucune ligne — mesure sautée')
        return
      }
      const hMax = Math.max(...lignes)
      const hMin = Math.min(...lignes)
      noter(info, `${cible.nom} — ligne (px, min → max)`, `${Math.round(hMin)} → ${Math.round(hMax)}`)
      noter(info, `${cible.nom} — lignes rendues`, lignes.length)

      expect(hMax, `${cible.nom} : la ligne reste dense`).toBeLessThanOrEqual(cible.plafond)
    })
  }
})

// ═══════════════════════════════════════════════════════════════════════════
// 1280×720 — LE PLANCHER CI (le projet `chromium` tourne à cette taille)
// ═══════════════════════════════════════════════════════════════════════════
test.describe('APX8 — plancher CI 1280×720', () => {
  test.use({ viewport: { width: 1280, height: 720 } })

  test('5+ cartes par étape même sur le viewport le plus court', async ({ page }, info) => {
    await ouvrirLeads(page, 'kanban')
    const m = await mesurerKanban(page)
    noter(info, '1280×720 — carte au repos (px)', m.carteMax)
    noter(info, '1280×720 — cartes par colonne', m.capacite)
    expect(m.capacite, 'cartes visibles par étape en 1280×720').toBeGreaterThanOrEqual(5)
  })
})

// ═══════════════════════════════════════════════════════════════════════════
// TACTILE — c'est `hover:none` qui décide, JAMAIS une largeur (contrat APX7)
// ═══════════════════════════════════════════════════════════════════════════
// Le téléphone ET la tablette partagent la MÊME anatomie : les deux blocs
// ci-dessous vérifient donc la même promesse à deux largeurs très différentes.
// `hasTouch` + `isMobile` font matcher `(hover: none)` / `(pointer: coarse)`
// dans Chromium — le mécanisme exact du projet `mobile` de la config.
for (const appareil of [
  { nom: 'téléphone 390×844', viewport: { width: 390, height: 844 }, mini: 4 },
  { nom: 'tablette 1024×768', viewport: { width: 1024, height: 768 }, mini: 4 },
]) {
  test.describe(`APX8 — anatomie tactile, ${appareil.nom}`, () => {
    test.use({ viewport: appareil.viewport, hasTouch: true, isMobile: true })

    test('la carte tactile reste dense et ses actions sont atteignables sans survol', async ({ page }, info) => {
      await ouvrirLeads(page, 'kanban')
      const m = await mesurerKanban(page)
      noter(info, `${appareil.nom} — carte au repos (px)`, m.carteMax)
      noter(info, `${appareil.nom} — cartes par colonne`, m.capacite)

      // La rangée d'actions 44×44 d'APX7 vit SUR la ligne du montant : la carte
      // tactile passe d'environ 125 px à environ 90 px. Le plafond capte un
      // retour à l'ancienne anatomie (où `.kb-quick` ajoutait +36 px permanents).
      expect(m.carteMax, 'la carte tactile ne retrouve pas son épaisseur d’avant (~125 px)')
        .toBeLessThanOrEqual(112)
      expect(m.capacite, `cartes visibles par étape sur ${appareil.nom}`)
        .toBeGreaterThanOrEqual(appareil.mini)

      // Atteignabilité SANS survol (VX68) : la rangée d'actions rapides est
      // visible dès le rendu, sans qu'aucun hover n'ait été déclenché.
      // Elle peut être remplacée par le cadenas PII selon les permissions du
      // compte — les deux prouvent que la zone est rendue au repos.
      const quick = page.locator('article.kb-card .kb-quick').first()
      await expect(quick, 'la rangée d’actions tactiles est rendue au repos').toBeVisible()
      const bouton = quick.locator('.kb-quick-btn').first()
      if (await bouton.count()) {
        await expect(bouton).toBeVisible()
        const box = await bouton.boundingBox()
        expect(box, 'l’action tactile a une boîte réelle').toBeTruthy()
        // Cible tactile (LB17) : 44 px visés, 40 gardés ici pour absorber
        // l'arrondi de mise à l'échelle du device emulation.
        expect(Math.min(box.width, box.height), 'cible tactile de l’action rapide')
          .toBeGreaterThanOrEqual(40)
      }
    })
  })
}
