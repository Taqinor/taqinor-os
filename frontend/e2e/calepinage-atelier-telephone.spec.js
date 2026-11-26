// ACAL423 — l'atelier de calepinage (`.rp9-host`) doit rester utilisable au téléphone
// (390 × 844) : aucun défilement horizontal de la page, aucune cible tactile (bouton ou
// puce visible) sous 44 px de haut. Même méthode que `mobile.spec.js` (VNT81) :
// `scrollWidth - innerWidth`. La carte peut être absente (ERR121, aucune clé MapTiler) :
// `#rp9-map` reste un conteneur, la mesure porte sur le DOM du builder.
import { test, expect, devices } from '@playwright/test'
import { gotoLeads, createLead, uniq } from './helpers'

// ACAL482 — appareil WebKit réel (iPhone 13) pour TOUT le fichier : la surcharge `test.use`
// fait lancer WebKit même sous le projet `chromium` (qui garde son `storageState`).
test.use({ ...devices['iPhone 13'], viewport: { width: 390, height: 844 } })

// Rend l'écart de largeur ET les éléments qui dépassent (diagnostic lisible dans l'échec).
const sansDebordement = (page) =>
  page.evaluate(() => {
    const de = document.documentElement
    const ecart = de.scrollWidth - window.innerWidth
    if (ecart > 0) {
      const noms = [...document.querySelectorAll('body *')]
        .filter((n) => n.getBoundingClientRect().right > window.innerWidth + 0.5)
        .slice(0, 6).map((n) => `${n.tagName}#${n.id}.${String(n.className).slice(0, 50)} r=${n.getBoundingClientRect().right}`)
      console.log(`DEBORDEMENT sw=${de.scrollWidth} iw=${window.innerWidth} bodysw=${document.body.scrollWidth} ${noms.join(' | ')}`)
    }
    return ecart
  })

test('ACAL482 : le navigateur joué est bien WebKit', async ({ browserName }) => {
  expect(browserName, 'la surcharge d’appareil n’a pas lancé WebKit').toBe('webkit')
})

test.beforeEach(({ page }) => { page.on('console', (m) => { if (m.text().startsWith('DEBORDEMENT')) console.log(m.text()) }) })

test('ACAL482 : liste, fiche et onglet releve à 390 px — sans défilement horizontal', async ({ page }) => {
  const erreurs = []
  page.on('pageerror', (err) => erreurs.push(err))
  await gotoLeads(page)
  const nomLead = await createLead(page, { nom: uniq('Tel ACAL482'), facture: 700, ville: 'Casablanca' })

  await page.goto('/calepinage')
  await expect(page.getByRole('heading', { name: 'Calepinages' })).toBeVisible()
  expect(await sansDebordement(page), 'liste : défilement horizontal (px)').toBeLessThanOrEqual(0)

  await page.goto('/calepinage/nouveau')
  await expect(page.getByRole('heading', { name: 'Nouveau calepinage' })).toBeVisible()
  await page.getByRole('tab', { name: 'Lead' }).click()
  await page.locator('#cal-nouveau-lead').getByRole('combobox').click()
  await page.getByRole('searchbox').fill(nomLead)
  await page.getByRole('option', { name: new RegExp(nomLead) }).first().click()
  await page.locator('#cal-nouveau-nom').fill(uniq('Tel ACAL482 Toiture'))
  await page.getByRole('button', { name: 'Créer le calepinage' }).click()
  await expect(page).toHaveURL(/\/calepinage\/\d+/)
  await expect(page.getByTestId('cal-rail-etapes')).toBeVisible()
  expect(await sansDebordement(page), 'fiche : défilement horizontal (px)').toBeLessThanOrEqual(0)

  const url = new URL(page.url())
  url.searchParams.set('onglet', 'releve')
  url.searchParams.set('mode', 'expert') // Coque (22/11) : le rail d'onglets est celui du mode expert
  await page.goto(url.toString())
  await page.getByTestId('cal-onglet-releve').click()
  const panneau = page.getByTestId('cal-onglet-panneau')
  await expect(panneau).toBeVisible()
  expect(await sansDebordement(page), 'releve : défilement horizontal (px)').toBeLessThanOrEqual(0)
  const larges = await panneau.evaluate((el) =>
    [...el.querySelectorAll('*')]
      .filter((n) => n.getBoundingClientRect().right > window.innerWidth + 1)
      .map((n) => `${n.tagName}.${n.className}`.slice(0, 80)))
  expect(larges, 'contrôles du panneau dépassant 390 px').toEqual([])
  expect(erreurs, 'erreurs de page').toEqual([])
})

test('ACAL423 : atelier à 390 px — pas de défilement horizontal, cibles ≥ 44 px', async ({ page }) => {
  await gotoLeads(page)
  const name = await createLead(page, { nom: uniq('Atelier tel ACAL423'), facture: 650, ville: 'Casablanca' })
  const res = await page.request.get(`/api/django/crm/leads/?search=${encodeURIComponent(name)}&page_size=1`)
  expect(res.ok(), `GET /crm/leads/?search= (${res.status()})`).toBeTruthy()
  const body = await res.json()
  const rows = Array.isArray(body) ? body : body.results
  expect(rows?.length, `lead "${name}" introuvable via l'API`).toBeGreaterThan(0)

  await page.goto(`/devis-design/${rows[0].id}`)
  await expect(page.locator('.rp9-host').first()).toBeVisible({ timeout: 20_000 })

  const debordement = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(debordement, 'défilement horizontal de la page (px)').toBeLessThanOrEqual(0)

  const petites = await page.evaluate(() => {
    const out = []
    for (const el of document.querySelectorAll('.rp9-host button, .rp9-host .rp9-chip')) {
      const r = el.getBoundingClientRect()
      if (r.width === 0 || r.height === 0) continue // non visible
      if (r.height < 44) out.push(`${el.id || el.className || el.tagName} (${Math.round(r.height)} px)`)
    }
    return out
  })
  expect(petites, 'boutons et puces de moins de 44 px de haut').toEqual([])
})

// ACAL1745 — le bandeau « GPS du lead corrigé » tient à 390 px : le texte passe à la ligne, les boutons s'empilent
// (≥ 44 px de haut), aucun ne se chevauche ni ne sort de l'écran. La dérive est posée sur la réponse de
// `design-context` (le cas réel demande un GPS corrigé après le tracé) ; la mise en page, elle, est la vraie.
test('ACAL1745 : le bandeau « GPS du lead corrigé » tient en 390 px, boutons empilés et ≥ 44 px', async ({ page }) => {
  await gotoLeads(page)
  const name = await createLead(page, { nom: uniq('Atelier tel ACAL1745'), facture: 650, ville: 'Casablanca' })
  const res = await page.request.get(`/api/django/crm/leads/?search=${encodeURIComponent(name)}&page_size=1`)
  expect(res.ok(), `GET /crm/leads/?search= (${res.status()})`).toBeTruthy()
  const body = await res.json()
  const lead = (Array.isArray(body) ? body : body.results)[0]
  const cree = await page.request.post('/api/django/calepinage/calepinages/', { data: { lead: lead.id, titre: uniq('Tel ACAL1745') } })
  expect(cree.ok(), `POST calepinages (${cree.status()})`).toBeTruthy()
  const cal = await cree.json()

  await page.route(/\/calepinage\/calepinages\/\d+\/design-context\//, async (route) => {
    const reelle = await route.fetch()
    const corps = await reelle.json()
    corps.geometrie = { ...(corps.geometrie || {}), derive: { etat: 'a_decider' } }
    await route.fulfill({ response: reelle, json: corps })
  })
  await page.goto(`/calepinage/${cal.id}`)
  const recentrer = page.getByTestId('acal-derive-recentrer')
  const garder = page.getByTestId('acal-derive-garder')
  await expect(recentrer).toBeVisible({ timeout: 20_000 })
  await expect(garder).toBeVisible()

  const boites = await Promise.all([recentrer, garder, page.locator('.cal-coque-alertes-plus')].map((l) => l.boundingBox()))
  for (const b of boites) {
    expect(b, 'un bouton du bandeau est introuvable').not.toBeNull()
    expect(b.height, 'bouton du bandeau de moins de 44 px').toBeGreaterThanOrEqual(43.5)
    expect(b.x, 'bouton hors de l’écran (gauche)').toBeGreaterThanOrEqual(-0.5)
    expect(b.x + b.width, 'bouton hors de l’écran (droite)').toBeLessThanOrEqual(390.5)
  }
  const [r, g, plus] = boites
  const chevauche = (a, b) => a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height
  expect(chevauche(r, g), '« Recentrer » et « Garder » se chevauchent').toBe(false)
  expect(chevauche(r, plus), '« Recentrer » et « En savoir plus » se chevauchent').toBe(false)
  expect(chevauche(g, plus), '« Garder » et « En savoir plus » se chevauchent').toBe(false)
  expect(await sansDebordement(page), 'défilement horizontal (px)').toBeLessThanOrEqual(0)
})

// Un calepinage neuf rattaché à un lead créé pour le cas (les tests de ce fichier partent tous de là).
async function calepinageDeTest(page, prefixe) {
  await gotoLeads(page)
  const name = await createLead(page, { nom: uniq(prefixe), facture: 650, ville: 'Casablanca' })
  const res = await page.request.get(`/api/django/crm/leads/?search=${encodeURIComponent(name)}&page_size=1`)
  expect(res.ok(), `GET /crm/leads/?search= (${res.status()})`).toBeTruthy()
  const body = await res.json()
  const lead = (Array.isArray(body) ? body : body.results)[0]
  const cree = await page.request.post('/api/django/calepinage/calepinages/', { data: { lead: lead.id, titre: uniq(prefixe) } })
  expect(cree.ok(), `POST calepinages (${cree.status()})`).toBeTruthy()
  return cree.json()
}

// ACAL1807 — au téléphone, le toit d'abord : à 390 × 664 le tiroir s'ouvre RÉDUIT et la carte visible (du haut de la
// carte au haut du tiroir) mesure au moins 45 % de la hauteur ; au centre de cette zone, aucune pièce flottante.
test('ACAL1807 : carte visible ≥ 45 % de la hauteur à 390 × 664, tiroir réduit, aucune pièce au centre du toit', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 664 })
  const cal = await calepinageDeTest(page, 'Atelier tel ACAL1807')
  await page.goto(`/calepinage/${cal.id}`)
  const tiroir = page.getByTestId('cal-panneau-etape')
  await expect(tiroir).toHaveAttribute('data-deplie', '0', { timeout: 20_000 })
  for (const etape of ['cal-etape-toit', 'cal-etape-panneaux']) {
    await page.getByTestId(etape).click()
    await expect(tiroir).toHaveAttribute('data-deplie', '0')
    const m = await page.evaluate(() => {
      const carte = document.getElementById('rp9-map').getBoundingClientRect()
      const t = document.querySelector('[data-testid="cal-panneau-etape"]').getBoundingClientRect()
      const el = document.elementFromPoint(carte.x + carte.width / 2, carte.y + (t.top - carte.y) / 2)
      return { visible: t.top - carte.y, hautTiroir: t.height, centreDansCarte: !!el && !!el.closest('#rp9-map, .rp9-map-wrap') }
    })
    expect(m.visible, `${etape} : carte visible (px)`).toBeGreaterThanOrEqual(0.45 * 664 - 1)
    expect(m.hautTiroir, `${etape} : tiroir réduit (px)`).toBeLessThanOrEqual(110)
    expect(m.centreDansCarte, `${etape} : une pièce couvre le centre du toit`).toBe(true)
  }
  await page.getByRole('button', { name: 'Agrandir ou réduire le panneau du bas' }).click()
  await expect(tiroir).toHaveAttribute('data-deplie', '1')
})

// ACAL1809 — « Relevé » est dans le bandeau, visible dans le premier écran (390 × 844), ≥ 44 × 44, et ouvre le relevé.
test('ACAL1809 : « Relevé » dans le bandeau, 44 × 44 dans le premier écran, un toucher ouvre le relevé', async ({ page }) => {
  const cal = await calepinageDeTest(page, 'Atelier tel ACAL1809')
  await page.goto(`/calepinage/${cal.id}`)
  const entree = page.getByTestId('cal-barre-releve')
  await expect(entree).toBeVisible({ timeout: 20_000 })
  const b = await entree.boundingBox()
  expect(b.width, 'largeur de l’entrée Relevé').toBeGreaterThanOrEqual(43.5)
  expect(b.height, 'hauteur de l’entrée Relevé').toBeGreaterThanOrEqual(43.5)
  expect(b.y + b.height, 'dans le premier écran').toBeLessThanOrEqual(844)
  await entree.tap()
  await expect(page).toHaveURL(new RegExp(`/calepinage/${cal.id}/releve$`))
})

// ACAL1812 — « Terminer le relevé » répond EN VUE : le refus (orientation sans précision) pose le focus sur le champ
// fautif et s'écrit dans une bannière entièrement au-dessus de la barre du bas ; le succès idem.
test('ACAL1812 : la réponse de « Terminer le relevé » est visible, au-dessus de la barre fixe du bas', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 664 })
  const cal = await calepinageDeTest(page, 'Atelier tel ACAL1812')
  await page.goto(`/calepinage/${cal.id}/releve`)
  await page.getByTestId('releve-orientation-bouton').tap()
  await page.getByTestId('releve-azimut-main').fill('160')
  await page.getByTestId('releve-terminer').tap()
  const message = page.getByTestId('releve-message')
  await expect(message).toBeVisible()
  await expect(page.locator('#releve-precision')).toBeFocused()
  const dessus = async () => page.evaluate(() => {
    const m = document.querySelector('[data-testid="releve-message"]').getBoundingClientRect()
    const p = document.querySelector('.cal-tel-pied').getBoundingClientRect()
    return { basMessage: m.bottom, hautPied: p.top }
  })
  let m = await dessus()
  expect(m.basMessage, 'le refus est sous la barre du bas').toBeLessThanOrEqual(m.hautPied + 0.5)
  await page.getByTestId('releve-precision').fill('10')
  await page.getByTestId('releve-longueur').fill('12,4')
  await page.getByTestId('releve-largeur').fill('8,6')
  await page.getByTestId('releve-terminer').tap()
  // ACAL1319 / D-ACAL-68 — le succès ne se lit plus sur l'écran : « Terminer » enregistre puis revient à la fiche.
  await expect(page).toHaveURL(new RegExp(`/calepinage/${cal.id}$`))
})

// ACAL1811 — « Voir en 3D » du relevé ouvre « Montrer au client » ; « Retour au relevé » ramène au relevé.
test('ACAL1811 : « Voir en 3D » du relevé mène à la vue client, « Retour au relevé » revient', async ({ page }) => {
  const cal = await calepinageDeTest(page, 'Atelier tel ACAL1811')
  await page.goto(`/calepinage/${cal.id}/releve`)
  await page.getByTestId('releve-voir-3d').tap()
  await expect(page).toHaveURL(new RegExp(`/calepinage/${cal.id}/client$`))
  await page.getByTestId('client-retour-releve').tap()
  await expect(page).toHaveURL(new RegExp(`/calepinage/${cal.id}/releve$`))
})

// ACAL1810 — un relevé terminé HORS LIGNE est gardé sur le téléphone et part SEUL au retour du réseau (même file que
// les photos) : `GET releve/` le rend quelques secondes après, sans aucun geste, et l'écran dit « Relevé envoyé. ».
test('ACAL1810 : relevé terminé hors ligne, envoyé seul au retour du réseau', async ({ page, context }) => {
  const cal = await calepinageDeTest(page, 'Atelier tel ACAL1810')
  await page.goto(`/calepinage/${cal.id}/releve`)
  await page.getByTestId('releve-longueur').fill('12,4')
  await page.getByTestId('releve-largeur').fill('8,6')
  await context.setOffline(true)
  await page.getByTestId('releve-terminer').tap()
  await expect(page.getByTestId('releve-message')).toHaveText('Relevé gardé sur ce téléphone : il partira au retour du réseau.')
  await context.setOffline(false)
  await expect(page.getByTestId('releve-message')).toHaveText('Relevé envoyé.', { timeout: 15_000 })
  await expect(async () => {
    const res = await page.request.get(`/api/django/calepinage/calepinages/${cal.id}/releve/`)
    expect(res.ok()).toBeTruthy()
    expect((await res.json()).releves.length, 'relevés servis').toBe(1)
  }).toPass({ timeout: 15_000 })
})
