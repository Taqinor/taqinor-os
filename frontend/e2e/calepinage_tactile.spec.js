// CAL107 — l'atelier de calepinage (roofPro11, `#rp9-map`) doit être réellement
// utilisable au DOIGT sur tablette : tracer un toit, poser un obstacle, déplacer
// un panneau — les mêmes gestes que la souris, jamais un repli dégradé. Ce spec
// force un viewport tactile (tablette, `hasTouch: true`) et rejoue le parcours
// avec des taps/glissés tactiles plutôt que des clics souris.
//
// Parité geste souris ↔ tactile assurée par le dispatcher de `roof-tool-pro11.ts`
// (mousedown/mousemove/mouseup ↔ touchstart/touchmove/touchend, mêmes fonctions
// `beginDraw/moveDraw/endDraw`, `tryBeginMove/doMove/endMove`) + le filet de
// sécurité CAL107 (un glissé relâché hors du canvas termine quand même le geste,
// parité avec le PV34 de `layoutEditor.ts`) + la boîte de tolérance ajoutée à
// `obstacleAtPoint` (doigt ⊃ trait fin).
import { test, expect } from '@playwright/test'
import { gotoLeads, createLead, uniq, API_DJANGO, lireJson, telephoneMobileUnique } from './helpers'

test.use({ viewport: { width: 820, height: 1180 }, hasTouch: true })

/** Le lead vient d'être créé par `createLead` (nom connu, pas d'id) : on retrouve
 *  son id via l'API (recherche par nom, `search_fields` inclut `nom` — apps/crm/
 *  views.py `LeadViewSet.search_fields`) pour naviguer directement sur
 *  `/devis-design/:id` (le builder 3D en mode lead), sans dépendre d'un lien UI
 *  qui pourrait changer d'écran d'origine. */
async function leadIdByName(page, name) {
  const res = await page.request.get(`/api/django/crm/leads/?search=${encodeURIComponent(name)}&page_size=1`)
  expect(res.ok(), `GET /crm/leads/?search= (${res.status()})`).toBeTruthy()
  const body = await res.json()
  const rows = Array.isArray(body) ? body : body.results
  expect(rows?.length, `lead "${name}" introuvable via l'API`).toBeGreaterThan(0)
  return rows[0].id
}

test('CAL107 : tracer un toit, poser un obstacle et déplacer un panneau au DOIGT sur tablette', async ({ page }) => {
  await gotoLeads(page)
  // Facture + ville ancrent le besoin/GPS (sans ça le devis auto — et donc le
  // builder — refuse de dimensionner, cf. commentaire de `createLead`).
  const name = await createLead(page, { nom: uniq('Tactile CAL107'), facture: 650, ville: 'Casablanca' })
  const leadId = await leadIdByName(page, name)

  // ERR121 — sans clé MapTiler (CI comme local) `ToitureDesign.boot()` avorte
  // (« Carte indisponible ») : `#rp9-map` reste un simple conteneur sans canvas
  // ni gestionnaire, « Terminer » reste désactivé au clic souris comme au
  // toucher. Ce n'est PAS un défaut tactile : même garde `test.skip` que
  // `calepinage-parcours.spec.js`, la vérité venant du SERVEUR.
  const cfgRes = await page.request.get('/api/django/ventes/roof-config/')
  const cfg = cfgRes.ok() ? await cfgRes.json() : {}
  test.skip(!(cfg?.available && cfg?.maptilerKey),
    'carte indisponible sur cet environnement (aucune clé MapTiler publiée par le '
    + 'serveur) : le constructeur ne boote pas — parité tactile CAL107 non rejouable ici')

  await page.goto(`/devis-design/${leadId}`)
  const map = page.locator('#rp9-map')
  await expect(map).toBeVisible({ timeout: 20_000 })
  // H7 — la carte de la page devis est plus haute que la fenêtre de la tablette (820 × 1180) : elle est amenée dans
  // la fenêtre, et les taps visent le centre de sa partie VISIBLE (le centre de la boîte entière tombait hors écran).
  await map.scrollIntoViewIfNeeded()
  const box = await map.boundingBox()
  expect(box, 'le canvas de la carte doit avoir une taille').toBeTruthy()
  const hautVisible = Math.max(box.y, 0)
  const basVisible = Math.min(box.y + box.height, page.viewportSize().height)
  expect(basVisible - hautVisible, 'au moins 200 px de carte visibles pour le triangle').toBeGreaterThanOrEqual(200)

  // ── 1) TRACER un toit au doigt : trois taps forment un triangle, le bouton
  // « Terminer le tracé » ferme le contour (même chemin que le double-tap W77,
  // mais sans dépendre de sa fenêtre de temps — plus robuste en CI). ──────────
  const cx = box.x + box.width / 2;
  const cy = hautVisible + (basVisible - hautVisible) / 2;
  const corners = [
    { x: cx - 80, y: cy - 60 },
    { x: cx + 80, y: cy - 60 },
    { x: cx, y: cy + 70 },
  ]
  // Le tracé tactile pose un sommet par tap ; entre deux taps le délai anti-dblclick
  // (W77, 240 ms) doit s'écouler. On attend une CONDITION observable (le bouton
  // « annuler le dernier point » reflète le sommet posé) plutôt qu'un sommeil fixe.
  const undoPoint = page.locator('#rp9-undo-point')
  for (const pt of corners) {
    await page.touchscreen.tap(pt.x, pt.y)
    await expect(undoPoint).toBeEnabled({ timeout: 10_000 })
    await page.waitForFunction(
      (since) => Date.now() - since >= 260, Date.now(), { polling: 50 },
    )
  }
  const finishBtn = page.locator('#rp9-finish')
  await expect(finishBtn).toBeEnabled({ timeout: 10_000 })
  await finishBtn.click() // bouton HTML : un tap fonctionne déjà nativement, geste hors carte
  await expect(page.locator('#rp9-config')).toBeVisible({ timeout: 10_000 })

  // ── 2) POSER un obstacle au doigt : glissé tactile (touchstart→touchmove→
  // touchend) sur la carte, à l'intérieur du toit tracé. ──────────────────────
  const obstacleBtn = page.locator('#rp9-obstacle')
  await expect(obstacleBtn).toBeVisible()
  await obstacleBtn.tap()
  await page.touchscreen.tap(cx - 20, cy) // amorce (touchstart) : dispatch séquentiel ci-dessous
  const from = { x: cx - 20, y: cy - 15 }
  const to = { x: cx + 20, y: cy + 15 }
  await page.evaluate(({ from, to }) => {
    const el = document.elementFromPoint(from.x, from.y)
    const dispatch = (type, p) =>
      el?.dispatchEvent(
        new TouchEvent(type, {
          bubbles: true,
          cancelable: true,
          touches: type === 'touchend' ? [] : [new Touch({ identifier: 1, target: el, clientX: p.x, clientY: p.y })],
          changedTouches: [new Touch({ identifier: 1, target: el, clientX: p.x, clientY: p.y })],
        }),
      )
    dispatch('touchstart', from)
    dispatch('touchmove', to)
    dispatch('touchend', to)
  }, { from, to })
  // Un obstacle posé ouvre son panneau d'édition (dimensions saisissables).
  await expect(page.locator('#rp9-obs-edit')).toBeVisible({ timeout: 10_000 })

  // ── 3) DÉPLACER un panneau au doigt en mode « Personnaliser la disposition » :
  // preuve que le glissé tactile pilote bien `layoutEditor.ts` (déjà unifié —
  // W80/W88), sans régression après le câblage CAL107 côté tracé/obstacle. ────
  const layoutToggle = page.locator('#rp9-layout-toggle, [data-testid="rp9-layout-toggle"]').first()
  if (await layoutToggle.count()) {
    await layoutToggle.tap()
    const cell = page.locator('.rp9-layout-cell[data-occupied="true"]').first()
    if (await cell.count()) {
      await expect(cell).toBeVisible()
      // Un tap sur une cellule occupée la sélectionne (repli tactile documenté
      // en W69) — preuve que le geste tactile atteint bien la disposition.
      await cell.tap()
    }
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL988 — la matrice des GESTES DE CARTE (garde K-GESTE), une ligne (test.step) par geste et par appareil :
//   souris 1440×900 : molette, molette + Alt, clic coin, double-clic de fermeture, glisser un coin, « + » / « − »,
//                     plein écran ;
//   iPhone 390×844 (Chromium tactile, puis WebKit iPhone 13 si le navigateur est installé) : clic (tap) coin,
//                     « + » / « − », plein écran, un doigt (la page défile), deux doigts (la carte bouge), pincer.
// Chaque échec nomme le geste ET l'appareil. Fond de repli (comme calepinage-mesures-ecran.spec.js) : clé de carte
// factice, aucune imagerie. La carte n'expose ni zoom ni centre : ils se LISENT par le document que l'atelier
// enregistre — on pose trois coins à des pixels fixes, on enregistre, et les degrés par pixel (zoom) et la
// position du premier coin (déplacement) se lisent dans `roof_layout.outline` ([lat, lng]).
// ════════════════════════════════════════════════════════════════════════════
const CAL = `${API_DJANGO}/calepinage`
const T120 = { timeout: 120_000 }

async function carteRefusee(context) {
  await context.route(/\/calepinage\/calepinages\/\d+\/design-context\//, async (route) => {
    try {
      const reelle = await route.fetch()
      const corps = await reelle.json()
      corps.carte = { ...(corps.carte || {}), available: true, maptilerKey: 'cle-factice-acal988', mapboxToken: null }
      await route.fulfill({ response: reelle, json: corps })
    } catch { /* page ou contexte fermés pendant la requête : rien à servir */ }
  })
  await context.route(/https:\/\/api\.maptiler\.com\//, (route) => route.fulfill({
    status: 403, contentType: 'application/json', body: '{"message":"Invalid key"}',
  }))
}

// Calepinage jetable, SANS toit (la carte est vide : on y trace), créé par l'API (plus fiable que le formulaire).
async function calepinageVide(request) {
  const lead = await lireJson(await request.post(`${API_DJANGO}/crm/leads/`, {
    ...T120,
    data: { nom: uniq('ACAL988'), ville: 'Casablanca', telephone: telephoneMobileUnique(), type_installation: 'residentiel', facture_hiver: '800' },
  }), 'lead')
  const cal = await lireJson(await request.post(`${CAL}/calepinages/`, { ...T120, data: { lead: lead.id, titre: uniq('ACAL988') } }), 'calepinage')
  await lireJson(await request.get(`${CAL}/calepinages/${cal.id}/design-context/`, T120), 'design-context (amorce)')
  return cal.id
}

// Ouvre l'atelier, attend que la carte ait démarré, amène la carte dans la fenêtre. Renvoie la liste vivante des
// `pageerror` (un geste qui lève une exception est un échec nommé).
async function ouvrirAtelierGestes(page, id) {
  const erreurs = []
  // Les échecs réseau d'arrière-plan (sondes de notifications pendant un redémarrage du serveur : « due to access
  // control checks » sous WebKit) ne sont pas des exceptions de geste.
  page.on('pageerror', (e) => { if (!/access control checks|Failed to fetch|Load failed|NetworkError/.test(e.message)) erreurs.push(e.message) })
  await page.goto('/apps')
  await expect(page.getByRole('heading', { name: 'Mes applications' })).toBeVisible({ timeout: 30_000 })
  // Coque (22/11) : ce test agit sur les contrôles du constructeur — en expert ils sont tous visibles, comme avant.
  await page.goto(`/calepinage/${id}?mode=expert`)
  await expect.poll(() => page.evaluate(() => Boolean(window.__taqinorRoofBooted)), { timeout: 240_000 }).toBe(true)
  await expect(page.locator('#rp9-status')).not.toHaveText(/^Chargement/)
  await page.locator('#rp9-map canvas').first().scrollIntoViewIfNeeded()
  await page.waitForLoadState('networkidle').catch(() => {})
  return erreurs
}

// Trois coins à des pixels FIXES dans la zone libre de la carte (là où le canvas reçoit le clic, ni puce ni
// contrôle) : A, B à 120 px à droite de A, C à 90 px sous B. Renvoie leurs coordonnées d'écran.
async function coinsLibres(page) {
  const libres = await page.evaluate(() => {
    const canvas = document.querySelector('#rp9-map canvas')
    const b = canvas.getBoundingClientRect()
    const ok = (x, y) => document.elementFromPoint(x, y) === canvas
    for (let y = Math.max(b.top, 0) + 20; y < Math.min(b.bottom, innerHeight) - 100; y += 10) {
      for (let x = b.left + 20; x < b.right - 140; x += 10) {
        if (ok(x, y) && ok(x + 120, y) && ok(x + 120, y + 90) && ok(x + 60, y + 45)) return [[x, y], [x + 120, y], [x + 120, y + 90]]
      }
    }
    return null
  })
  expect(libres, 'une zone libre de 120×90 px sur la carte').toBeTruthy()
  return libres.map(([x, y]) => ({ x, y }))
}

// Geste « clic coin » ×3, puis fermeture du contour (double-clic sur le dernier coin à la souris ; « Terminer le
// tracé » au doigt). `poser` = (x, y) => Promise : clic souris ou tap.
async function tracerContour(page, coins, poser, { doubleClic = false } = {}) {
  for (const { x, y } of coins) {
    await poser(x, y)
    await expect(page.locator('#rp9-undo-point')).toBeVisible()
    await page.waitForFunction((depuis) => Date.now() - depuis >= 300, Date.now(), { polling: 50 }) // anti-double-clic (W77)
  }
  await expect(page.locator('#rp9-finish')).toBeEnabled()
  if (doubleClic) await page.mouse.dblclick(coins[2].x, coins[2].y)
  else await page.locator('#rp9-finish').click()
  await expect(page.locator('#rp9-config')).toBeVisible()
  await expect(page.locator('#rp9-finish')).toBeDisabled() // contour fermé
}

// Enregistre et relit le contour : [[lat, lng], …] dans l'ordre des coins posés.
async function contourEnregistre(page, id) {
  // On attend la réponse de l'écriture du document (sinon la relecture rendrait l'enregistrement précédent).
  const ecriture = page.waitForResponse((r) => /\/calepinages\/\d+\/layout\/$/.test(r.url()) && r.request().method() === 'POST', { timeout: 60_000 })
  await page.getByTestId('cal-enregistrer-calepinage').getByRole('button', { name: /Enregistrer le calepinage/ }).click()
  expect((await ecriture).status(), 'écriture du document de conception').toBeLessThan(300)
  await expect(page.getByTestId('cal-erreur-enregistrement')).toHaveCount(0, { timeout: 30_000 })
  let contour = null
  await expect.poll(async () => {
    const lu = await lireJson(await page.request.get(`${CAL}/calepinages/${id}/layout/`, T120), 'layout')
    contour = lu?.roof_layout?.outline ?? null
    return Array.isArray(contour) ? contour.length : 0
  }, { intervals: [750], timeout: 60_000 }).toBeGreaterThanOrEqual(3)
  return contour
}

// Attend que la carte ait fini de bouger (animation de zoom, inertie) : trois captures du canvas, espacées de
// 250 ms, identiques. `deRef` = capture d'avant le geste : on attend d'abord (au plus 4 s) que la carte ait
// changé — un geste sans effet visible (Alt + molette hors calage) ne change rien et ne doit pas échouer.
async function attendreCarteImmobile(page, deRef = null) {
  const canvas = page.locator('#rp9-map canvas').first()
  const lire = async () => (await canvas.screenshot({ animations: 'disabled' })).toString('base64')
  if (deRef) await expect.poll(lire, { intervals: [100], timeout: 4_000 }).not.toBe(deRef).catch(() => {})
  let derniere = null
  let identiques = 0
  await expect.poll(async () => {
    const cette = await lire()
    identiques = cette === derniere ? identiques + 1 : 0
    derniere = cette
    return identiques
  }, { intervals: [250], timeout: 30_000, message: 'la carte finit de bouger' }).toBeGreaterThanOrEqual(2)
}

// Défilement de la page : l'ERP défile dans son conteneur de contenu (jamais `window`) — on lit le premier
// ancêtre défilant de la carte, à défaut `window.scrollY`.
async function defilement(page) {
  return page.evaluate(() => {
    for (let el = document.querySelector('#rp9-map')?.parentElement; el; el = el.parentElement) {
      const o = getComputedStyle(el).overflowY
      if ((o === 'auto' || o === 'scroll') && el.scrollHeight > el.clientHeight + 1) return el.scrollTop
    }
    return window.scrollY
  })
}

// Centre de la partie VISIBLE de la carte (là où l'on applique un geste).
async function centreCarte(page) {
  const b = await page.locator('#rp9-map canvas').first().boundingBox()
  const haut = Math.max(b.y, 0)
  const bas = Math.min(b.y + b.height, page.viewportSize().height)
  return { x: b.x + b.width / 2, y: haut + (bas - haut) / 2 }
}

// Une carte VIERGE par mesure (« Effacer » ne rend pas le contour : une fois fermé, la carte n'accepte plus de
// coin) : on ouvre un calepinage neuf, on applique le geste sur la carte vide, puis on pose trois coins à des
// pixels fixes et on lit le document enregistré. La vue de départ de la carte est la même à chaque ouverture : les
// degrés par pixel (zoom, plus petit = plus proche) et la position du coin A se comparent d'une carte à l'autre.
async function mesurerApres(page, poser, appliquer = null, options = {}, nom = '') {
  const id = await calepinageVide(page.request)
  const erreurs = await ouvrirAtelierGestes(page, id)
  if (appliquer) await appliquer(erreurs)
  const coins = await coinsLibres(page)
  await tracerContour(page, coins, poser, options)
  const contour = await contourEnregistre(page, id)
  const echelle = Math.abs(contour[1][1] - contour[0][1]) / 120
  console.log(`[ACAL988] mesure ${nom || 'carte'} : ${echelle.toExponential(3)} deg/px, coin A ${contour[0].map((v) => v.toFixed(5)).join(' ; ')}`)
  return { id, erreurs, coins, contour, echelle, coinA: contour[0] }
}

// « + » ou « − » : le CENTRE du bouton reçoit le clic de zoom, pas la puce « Plein écran » (T1-F1-002).
async function centreRecoitLeClic(page, classe) {
  const bouton = page.locator(`.${classe}`)
  await bouton.scrollIntoViewIfNeeded()
  return bouton.evaluate((el) => {
    const r = el.getBoundingClientRect()
    const sous = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2)
    return { recu: Boolean(sous && (sous === el || el.contains(sous))), sous: sous ? `${sous.tagName}#${sous.id}` : null }
  })
}

// Plein écran : l'enveloppe remplit la fenêtre (T1-T1-008 : 0 px sur iOS), puis revient.
async function gestePleinEcran(page, appareil, cliquer) {
  const puce = page.getByTestId('rp9-plein-ecran-toggle')
  await puce.scrollIntoViewIfNeeded()
  await cliquer(puce)
  const enveloppe = page.getByTestId('rp9-map-wrap')
  await expect(enveloppe, `geste « plein écran » (${appareil}) : l'enveloppe passe en plein écran`).toHaveAttribute('data-plein-ecran', '1')
  await expect.poll(async () => enveloppe.evaluate((el) => {
    const r = el.getBoundingClientRect()
    return [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)].join(',') === `0,0,${window.innerWidth},${window.innerHeight}`
  }), { message: `geste « plein écran » (${appareil}) : l'enveloppe remplit la fenêtre` }).toBe(true)
  await cliquer(puce)
  await expect(enveloppe, `geste « plein écran » (${appareil}) : retour`).toHaveAttribute('data-plein-ecran', '0')
}

// Une ligne de la matrice : `test.step` nommé par le geste, avec sa durée (pour trouver le geste qui traîne).
const etape = (nom, corps) => test.step(nom, async () => {
  const debut = Date.now()
  try { await corps() } finally { console.log(`[ACAL988] ${nom} : ${Math.round((Date.now() - debut) / 1000)} s`) }
})

const SOURIS = 'souris 1440×900'
const IPHONE = 'iPhone 390×844'

// Doigts : chaque trajet {de, vers} ; `pas` étapes de touchMove entre le toucher et le relâchement (protocole
// DevTools : seul moyen de jouer deux doigts ; Chromium seulement).
async function doigts(page, trajets, pas = 10) {
  const cdp = await page.context().newCDPSession(page)
  const points = (t) => trajets.map((d, i) => ({ id: i, x: d.de.x + (d.vers.x - d.de.x) * t, y: d.de.y + (d.vers.y - d.de.y) * t }))
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: points(0) })
  for (let i = 1; i <= pas; i += 1) await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: points(i / pas) })
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
  await cdp.detach()
}

test.describe('ACAL988 — gestes de carte à la souris (bureau)', () => {
  test.use({ viewport: { width: 1440, height: 900 }, hasTouch: false })

  test('la matrice des gestes à la souris', async ({ page }) => {
    test.setTimeout(900_000)
    await carteRefusee(page.context())
    const clic = (x, y) => page.mouse.click(x, y)
    const sansErreur = (erreurs, geste) => expect(erreurs, `geste « ${geste} » (${SOURIS}) : aucun pageerror`).toEqual([])

    // Carte de référence : clic coin ×3 puis double-clic de fermeture (le contour se ferme, « Terminer » se grise).
    let base = null
    await etape('geste « clic coin » + « double-clic de fermeture »', async () => {
      base = await mesurerApres(page, clic, null, { doubleClic: true })
      expect(base.echelle, `geste « clic coin » (${SOURIS}) : trois coins posés où l'on clique`).toBeGreaterThan(0)
      sansErreur(base.erreurs, 'clic coin / double-clic de fermeture')
    })

    await etape('geste « glisser un coin »', async () => {
      const [a] = base.coins
      await page.mouse.move(a.x, a.y)
      await page.mouse.down()
      await page.mouse.move(a.x + 20, a.y + 15, { steps: 6 })
      await page.mouse.move(a.x + 45, a.y + 30, { steps: 6 })
      await page.mouse.up()
      const contour = await contourEnregistre(page, base.id)
      expect(contour[0], `geste « glisser un coin » (${SOURIS}) : le premier coin a bougé`).not.toEqual(base.coinA)
      expect(contour.slice(1), `geste « glisser un coin » (${SOURIS}) : les autres coins n'ont pas bougé`).toEqual(base.contour.slice(1))
      sansErreur(base.erreurs, 'glisser un coin')
    })

    await etape('geste « plein écran »', async () => {
      await gestePleinEcran(page, SOURIS, (b) => b.click())
      sansErreur(base.erreurs, 'plein écran')
    })

    let vMolette = null
    await etape('geste « molette » (la carte zoome, la page ne défile pas)', async () => {
      let depart = null
      const v = vMolette = await mesurerApres(page, clic, async () => {
        const c = await centreCarte(page)
        depart = await defilement(page)
        const avantGeste = await page.locator('#rp9-map canvas').first().screenshot({ animations: 'disabled' })
        await page.mouse.move(c.x, c.y)
        await page.mouse.wheel(0, -500)
        await attendreCarteImmobile(page, avantGeste.toString('base64')) // fin de l'animation de zoom
        expect(await defilement(page), `geste « molette » (${SOURIS}) : la page ne défile pas`).toBe(depart)
      })
      expect(v.echelle, `geste « molette » (${SOURIS}) : la molette zoome (degrés par pixel ${base.echelle} -> ${v.echelle})`)
        .toBeLessThan(base.echelle * 0.9)
      sansErreur(v.erreurs, 'molette')
    })

    // Molette + Alt (rotation du fond hors mode calage : sans effet, jamais une exception — T1-F1-001) : jouée sur la
    // carte déjà mesurée, sans ouvrir une page de plus.
    await etape('geste « molette + Alt »', async () => {
      const c = await centreCarte(page)
      await page.keyboard.down('Alt')
      await page.mouse.move(c.x, c.y)
      await page.mouse.wheel(0, 300)
      await page.keyboard.up('Alt')
      await attendreCarteImmobile(page)
      await expect(page.locator('#rp9-map canvas').first(), `geste « molette + Alt » (${SOURIS}) : la carte reste affichée`).toBeVisible()
      sansErreur(vMolette.erreurs, 'molette + Alt')
    })

    for (const [sens, classe, plusPetit] of [['+', 'maplibregl-ctrl-zoom-in', true], ['−', 'maplibregl-ctrl-zoom-out', false]]) {
      await etape(`geste « ${sens} »`, async () => {
        const v = await mesurerApres(page, clic, async () => {
          const cible = await centreRecoitLeClic(page, classe)
          expect(cible.recu, `geste « ${sens} » (${SOURIS}) : le centre du bouton reçoit le clic (reçu par ${cible.sous})`).toBe(true)
          const avantGeste = (await page.locator('#rp9-map canvas').first().screenshot({ animations: 'disabled' })).toString('base64')
          await page.locator(`.${classe}`).click()
          await attendreCarteImmobile(page, avantGeste)
        })
        const ok = plusPetit ? v.echelle < base.echelle * 0.9 : v.echelle > base.echelle * 1.1
        expect(ok, `geste « ${sens} » (${SOURIS}) : le zoom change dans le bon sens (${base.echelle} -> ${v.echelle})`).toBe(true)
        sansErreur(v.erreurs, sens)
      })
    }
  })
})

test.describe('ACAL988 — gestes de carte au doigt (iPhone)', () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, deviceScaleFactor: 2 })

  test('la matrice des gestes au doigt', async ({ page, browserName }) => {
    test.skip(browserName !== 'chromium', 'les gestes à deux doigts passent par le protocole DevTools (Chromium seulement)')
    test.setTimeout(900_000)
    await carteRefusee(page.context())
    const taper = (x, y) => page.touchscreen.tap(x, y)
    const sansErreur = (erreurs, geste) => expect(erreurs, `geste « ${geste} » (${IPHONE}) : aucun pageerror`).toEqual([])

    let base = null
    await etape('geste « clic coin » (tap)', async () => {
      base = await mesurerApres(page, taper)
      expect(base.echelle, `geste « clic coin » (${IPHONE}) : trois taps posent trois coins`).toBeGreaterThan(0)
      sansErreur(base.erreurs, 'clic coin')
    })

    await etape('geste « plein écran » (tap)', async () => {
      await gestePleinEcran(page, IPHONE, (b) => b.tap())
      sansErreur(base.erreurs, 'plein écran')
    })

    await etape('geste « un doigt : la page défile »', async () => {
      await page.locator('#rp9-map canvas').first().scrollIntoViewIfNeeded()
      const c = await centreCarte(page)
      const avant = await defilement(page)
      await doigts(page, [{ de: { x: c.x, y: c.y + 120 }, vers: { x: c.x, y: c.y - 120 } }])
      await expect.poll(() => defilement(page), { message: `geste « un doigt » (${IPHONE}) : la page défile` }).toBeGreaterThan(avant + 20)
      sansErreur(base.erreurs, 'un doigt')
    })

    await etape('geste « deux doigts : la carte bouge »', async () => {
      let haut = null
      const v = await mesurerApres(page, taper, async () => {
        const c = await centreCarte(page)
        haut = await defilement(page)
        const avantGeste = (await page.locator('#rp9-map canvas').first().screenshot({ animations: 'disabled' })).toString('base64')
        await doigts(page, [
          { de: { x: c.x - 40, y: c.y }, vers: { x: c.x - 40, y: c.y + 80 } },
          { de: { x: c.x + 40, y: c.y }, vers: { x: c.x + 40, y: c.y + 80 } },
        ])
        await attendreCarteImmobile(page, avantGeste)
        expect(await defilement(page), `geste « deux doigts » (${IPHONE}) : la page ne défile pas`).toBe(haut)
      })
      expect(v.coinA, `geste « deux doigts » (${IPHONE}) : la carte a bougé sous les mêmes pixels`).not.toEqual(base.coinA)
      expect(Math.abs(v.echelle / base.echelle - 1), `geste « deux doigts » (${IPHONE}) : le zoom ne change pas`).toBeLessThan(0.05)
      sansErreur(v.erreurs, 'deux doigts')
    })

    await etape('geste « pincer »', async () => {
      const v = await mesurerApres(page, taper, async () => {
        const c = await centreCarte(page)
        const avantGeste = (await page.locator('#rp9-map canvas').first().screenshot({ animations: 'disabled' })).toString('base64')
        await doigts(page, [
          { de: { x: c.x - 20, y: c.y }, vers: { x: c.x - 100, y: c.y } },
          { de: { x: c.x + 20, y: c.y }, vers: { x: c.x + 100, y: c.y } },
        ])
        await attendreCarteImmobile(page, avantGeste)
      })
      expect(v.echelle, `geste « pincer » (${IPHONE}) : écarter deux doigts zoome (${base.echelle} -> ${v.echelle})`)
        .toBeLessThan(base.echelle * 0.9)
      sansErreur(v.erreurs, 'pincer')
    })

    for (const [sens, classe, plusPetit] of [['+', 'maplibregl-ctrl-zoom-in', true], ['−', 'maplibregl-ctrl-zoom-out', false]]) {
      await etape(`geste « ${sens} » (tap)`, async () => {
        const v = await mesurerApres(page, taper, async () => {
          const cible = await centreRecoitLeClic(page, classe)
          expect(cible.recu, `geste « ${sens} » (${IPHONE}) : le centre du bouton reçoit le tap (reçu par ${cible.sous})`).toBe(true)
          const avantGeste = (await page.locator('#rp9-map canvas').first().screenshot({ animations: 'disabled' })).toString('base64')
          await page.locator(`.${classe}`).tap()
          await attendreCarteImmobile(page, avantGeste)
        })
        const ok = plusPetit ? v.echelle < base.echelle * 0.9 : v.echelle > base.echelle * 1.1
        expect(ok, `geste « ${sens} » (${IPHONE}) : le zoom change dans le bon sens (${base.echelle} -> ${v.echelle})`).toBe(true)
        sansErreur(v.erreurs, sens)
      })
    }
  })
})

// ACAL1272 — « Terminer le tracé » et « Annuler le dernier point » pendant le tracé : chacun sur UNE ligne, entier
// dans la fenêtre, au moins 44 × 44 px (téléphone 390 × 664 et tablette portrait 820 × 1180). Avant : un bandeau
// absolu ancré à 50 % sans largeur rendait des colonnes de 56-67 px de large, « Terminer » à x = −25 px.
for (const [nom, viewport] of [['téléphone 390×664', { width: 390, height: 664 }], ['tablette 820×1180', { width: 820, height: 1180 }]]) {
  test.describe(`ACAL1272 — boutons du tracé (${nom})`, () => {
    test.use({ viewport, hasTouch: true, isMobile: true })

    test('Terminer et Annuler : une ligne, entiers, ≥ 44 px', async ({ page }) => {
      test.setTimeout(600_000)
      await carteRefusee(page.context())
      const id = await calepinageVide(page.request)
      await ouvrirAtelierGestes(page, id)
      const coins = await coinsLibres(page)
      for (const { x, y } of coins) {
        await page.touchscreen.tap(x, y)
        await expect(page.locator('#rp9-undo-point')).toBeVisible()
        await page.waitForFunction((depuis) => Date.now() - depuis >= 300, Date.now(), { polling: 50 }) // anti-double-clic (W77)
      }
      await expect(page.locator('#rp9-finish')).toBeEnabled()
      for (const sel of ['#rp9-finish', '#rp9-undo-point']) {
        const m = await page.locator(sel).evaluate((el) => {
          const r = el.getBoundingClientRect()
          const plage = document.createRange()
          plage.selectNodeContents(el)
          const lignes = new Set([...plage.getClientRects()].map((l) => Math.round(l.top))).size
          return { x: r.left, droite: r.right, l: r.width, h: r.height, lignes, largeur: window.innerWidth }
        })
        expect(m.lignes, `${sel} (${nom}) : le libellé tient sur une ligne`).toBe(1)
        expect(m.x, `${sel} (${nom}) : entier à gauche`).toBeGreaterThanOrEqual(0)
        expect(m.droite, `${sel} (${nom}) : entier à droite`).toBeLessThanOrEqual(m.largeur)
        expect(Math.min(m.l, m.h), `${sel} (${nom}) : cible d'au moins 44 × 44 px`).toBeGreaterThanOrEqual(44)
      }
    })
  })
}

// ACAL1813 — le voile « Utilisez deux doigts pour déplacer la carte » (MapLibre) n'apparaît qu'après un glisser d'UN
// doigt sur la carte, jamais au chargement sans geste, et reste BORNÉ à la carte : son z-index (99999) ne doit plus
// passer par-dessus le tiroir ni le bandeau (conteneur du canvas isolé, `roofbuilder.css`).
test.describe('ACAL1813 — voile des deux doigts (téléphone 390×664)', () => {
  test.use({ viewport: { width: 390, height: 664 }, hasTouch: true, isMobile: true })

  test('invisible à 3 s sans geste ; visible au glisser d’un doigt ; borné à la carte', async ({ page, browserName }) => {
    test.skip(browserName !== 'chromium', 'le glissé d’un doigt passe par le protocole DevTools (Chromium seulement)')
    test.setTimeout(600_000)
    await carteRefusee(page.context())
    const id = await calepinageVide(page.request)
    await ouvrirAtelierGestes(page, id)
    const voile = page.locator('#rp9-map .maplibregl-cooperative-gesture-screen')
    await expect(voile, 'la carte tactile porte le voile des deux doigts').toHaveCount(1)
    await expect(voile, 'chargement sans geste : voile invisible').toHaveCSS('opacity', '0', { timeout: 10_000 })
    const bornes = await voile.evaluate((el) => {
      const r = el.getBoundingClientRect()
      const carte = document.querySelector('#rp9-map').getBoundingClientRect()
      return {
        dansLaCarte: r.top >= carte.top - 1 && r.bottom <= carte.bottom + 1 && r.left >= carte.left - 1 && r.right <= carte.right + 1,
        isole: getComputedStyle(el.parentElement).isolation,
      }
    })
    expect(bornes.dansLaCarte, 'le voile ne dépasse pas la carte').toBe(true)
    expect(bornes.isole, 'le voile est borné à la carte (conteneur du canvas isolé : sous le tiroir et le bandeau)').toBe('isolate')
    const c = await centreCarte(page)
    await doigts(page, [{ de: { x: c.x, y: c.y + 40 }, vers: { x: c.x, y: c.y - 40 } }], 4)
    await expect.poll(() => voile.evaluate((el) => getComputedStyle(el).opacity), { message: 'un doigt qui glisse sur la carte montre le voile' }).toBe('1')
  })
})

// WebKit réel (iPhone 13) : les gestes à un point (tap, « + » / « − », plein écran). Ignoré, en le disant, quand
// le navigateur WebKit n'est pas installé (aucune installation n'est tentée) ; les gestes à deux doigts restent
// jouables seulement sous Chromium (protocole DevTools).
test('ACAL988 — WebKit iPhone 13 : tap coin, « + » / « − », plein écran', async ({ playwright, browserName }, testInfo) => {
  test.skip(browserName !== 'chromium', 'la ligne Chromium lance WebKit elle-même')
  test.setTimeout(900_000)
  let navigateur = null
  try { navigateur = await playwright.webkit.launch() } catch { navigateur = null }
  test.skip(!navigateur, 'navigateur WebKit non installé pour Playwright : gestes WebKit non jouables ici')
  const WEBKIT = 'WebKit iPhone 13'
  const contexte = await navigateur.newContext({
    ...playwright.devices['iPhone 13'], baseURL: testInfo.project.use.baseURL, storageState: testInfo.project.use.storageState,
  })
  try {
    const page = await contexte.newPage()
    await carteRefusee(contexte)
    const taper = (x, y) => page.touchscreen.tap(x, y)
    const base = await mesurerApres(page, taper)
    expect(base.echelle, `geste « clic coin » (${WEBKIT}) : trois taps posent trois coins`).toBeGreaterThan(0)
    expect(base.erreurs, `geste « clic coin » (${WEBKIT}) : aucun pageerror`).toEqual([])
    await gestePleinEcran(page, WEBKIT, (b) => b.tap())
    for (const [sens, classe, plusPetit] of [['+', 'maplibregl-ctrl-zoom-in', true], ['−', 'maplibregl-ctrl-zoom-out', false]]) {
      const v = await mesurerApres(page, taper, async () => {
        const cible = await centreRecoitLeClic(page, classe)
        expect(cible.recu, `geste « ${sens} » (${WEBKIT}) : le centre du bouton reçoit le tap (reçu par ${cible.sous})`).toBe(true)
        const avantGeste = (await page.locator('#rp9-map canvas').first().screenshot({ animations: 'disabled' })).toString('base64')
        await page.locator(`.${classe}`).tap()
        await attendreCarteImmobile(page, avantGeste)
      })
      const ok = plusPetit ? v.echelle < base.echelle * 0.9 : v.echelle > base.echelle * 1.1
      expect(ok, `geste « ${sens} » (${WEBKIT}) : le zoom change dans le bon sens (${base.echelle} -> ${v.echelle})`).toBe(true)
      expect(v.erreurs, `geste « ${sens} » (${WEBKIT}) : aucun pageerror`).toEqual([])
    }
  } finally {
    await contexte.close()
    await navigateur.close()
  }
})
