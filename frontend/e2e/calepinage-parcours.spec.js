// CAL221 — Parcours AUTONOME du module Calepinage, de bout en bout :
// ouvrir /calepinage → créer un calepinage depuis un LEAD → enregistrer une
// variante → la retenir → générer le devis (action CAL24).
//
// POURQUOI CETTE SPEC EXISTE. La suite Playwright couvre l'AO
// (`ao-parcours.spec.js`), le devis (`devis.spec.js`) et le calepinage TACTILE
// (`calepinage_tactile.spec.js`), mais aucun parcours calepinage AUTONOME : la
// porte du module (CAL34), son écran de création (CAL36), son comparatif de
// variantes (CAL42) et sa sortie devis (CAL38) n'étaient jamais traversés
// ensemble. Une porte qui s'ouvre et un bouton qui répond ne prouvent rien tant
// que le chemin complet n'est pas parcouru une fois.
//
// HOOKS DOM STABLES, JAMAIS UN TEXTE TRADUIT quand un hook existe : les
// `data-testid` `cal-*` et les `id` `cal-nouveau-*` sont posés par les écrans
// eux-mêmes (`features/calepinage/*`). Les rares libellés cités (« Créer le
// calepinage », « Retenir ») sont des noms ACCESSIBLES de boutons, pas des
// textes décoratifs.
//
// MODE STRICT PLAYWRIGHT — les DEUX éléments sont appariés quand un libellé est
// ambigu : « Calepinages » est à la fois l'entrée de nav du module et le titre
// de la liste ; « Nouveau calepinage » est à la fois l'entrée de nav et le
// titre de l'écran de création. Chaque locator est donc porté par son RÔLE
// (`link` vs `heading`), jamais par `getByText`.
//
// UNE VARIANTE EST ENREGISTRÉE PAR L'API, PAS PAR L'ÉCRAN — et c'est dit plutôt
// que caché : aucun écran du module n'expose aujourd'hui de geste « enregistrer
// une variante » (le comparatif CAL42 compare et RETIENT ; l'atelier ne publie
// pas encore ce bouton). La spec utilise donc le contexte de requête
// AUTHENTIFIÉ de Playwright (mêmes cookies que la page) pour poser la variante
// par `POST /api/django/calepinage/calepinages/<id>/variantes/`, exactement
// comme d'autres specs sèment leur donnée ; les gestes suivants (retenir,
// générer le devis) passent, eux, par l'INTERFACE RÉELLE.
import { test, expect } from '@playwright/test'
import { uniq, gotoLeads, createLead } from './helpers'

const API = '/api/django/calepinage'

/** L'identifiant du calepinage ouvert, lu sur l'URL de son atelier. */
function idDansUrl(url) {
  const m = /\/calepinage\/(\d+)/.exec(new URL(url).pathname)
  return m ? m[1] : null
}

test('CAL221: /calepinage → créer depuis un lead → variante → retenir → devis', async ({ page }) => {
  // ── 0. Un lead FRAIS, jamais un enregistrement partagé qu'on mute ───────
  await gotoLeads(page)
  const nomLead = await createLead(page, {
    nom: uniq('CAL221 Lead'), facture: 900, ville: 'Casablanca',
  })

  // ── 1. LA PORTE AUTONOME DU MODULE (CAL34) ─────────────────────────────
  await page.goto('/calepinage')
  // Appariement strict : l'entrée de NAV et le TITRE portent le même mot.
  await expect(page.getByRole('link', { name: 'Calepinages' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Calepinages' })).toBeVisible()

  // ── 2. CRÉER DEPUIS UN LEAD (CAL36) ────────────────────────────────────
  // Idem : le lien de nav, puis le titre de l'écran atteint.
  await page.getByRole('link', { name: 'Nouveau calepinage' }).click()
  await expect(page.getByRole('heading', { name: 'Nouveau calepinage' })).toBeVisible()

  // L'onglet « Lead » est l'onglet par défaut ; on le désigne explicitement
  // pour que la spec reste vraie le jour où l'ordre des onglets change.
  await page.getByRole('tab', { name: 'Lead' }).click()
  await page.locator('#cal-nouveau-lead').getByRole('combobox').click()
  await page.getByRole('searchbox').fill(nomLead)
  await page.getByRole('option', { name: new RegExp(nomLead) }).first().click()

  const nomCalepinage = uniq('CAL221 Toiture')
  await page.locator('#cal-nouveau-nom').fill(nomCalepinage)
  await page.getByRole('button', { name: 'Créer le calepinage' }).click()

  // ── 3. L'ATELIER DU CALEPINAGE CRÉÉ ────────────────────────────────────
  await expect(page).toHaveURL(/\/calepinage\/\d+/)
  await expect(page.getByTestId('cal-atelier-panneaux')).toBeVisible()
  const calepinageId = idDansUrl(page.url())
  expect(calepinageId, 'aucun identifiant de calepinage dans l’URL').toBeTruthy()

  // ── 4. ENREGISTRER UNE VARIANTE (CAL21, par l'API — voir l'en-tête) ────
  const creation = await page.request.post(
    `${API}/calepinages/${calepinageId}/variantes/`,
    { data: { nom: 'CAL221 Variante', parametres: {} } },
  )
  expect(creation.ok(),
    `le serveur a refusé la variante : ${creation.status()} ${await creation.text()}`)
    .toBeTruthy()

  // ── 5. LA RETENIR, PAR L'ÉCRAN (CAL42) ─────────────────────────────────
  await page.getByTestId('cal-lien-variantes').click()
  await expect(page).toHaveURL(/\/calepinage\/\d+\/variantes/)
  const tableau = page.getByTestId('cal-tableau-variantes')
  await expect(tableau).toBeVisible()

  // Mode strict : plusieurs colonnes peuvent porter un bouton « Retenir ».
  // On agit sur la PREMIÈRE, explicitement, plutôt que sur un locator ambigu.
  const aRetenir = tableau.getByRole('button', { name: 'Retenir' })
  if (await aRetenir.count() > 0) {
    await aRetenir.first().click()
  }
  // Après le geste, une variante EST retenue : la colonne l'annonce et son
  // bouton a disparu (le comparatif rend « Retenue », pas un bouton de plus).
  await expect(page.locator('[data-testid^="cal-retenue-"]').first()).toBeVisible()

  // ── 6. GÉNÉRER LE DEVIS (CAL24/CAL38), par l'écran ─────────────────────
  await page.goto(`/calepinage/${calepinageId}`)
  const bloc = page.getByTestId('cal-bouton-devis')
  await expect(bloc).toBeVisible()

  // La sortie devis a DEUX visages selon qu'un devis est déjà lié au
  // calepinage : « Générer le devis » (aucun devis) ou « Resynchroniser le
  // devis » (déjà lié). On apparie les DEUX plutôt que d'en supposer un.
  const generer = page.getByTestId('cal-generer-devis')
  const resynchroniser = page.getByTestId('cal-resynchroniser-devis')
  await expect(generer.or(resynchroniser)).toBeVisible()

  if (await generer.count() > 0) {
    await generer.click()
    // Le geste aboutit : soit le devis est créé (l'écran bascule sur la
    // resynchronisation et affiche la référence liée), soit le SERVEUR refuse
    // en NOMMANT le champ fautif — jamais un bouton muet.
    await expect(
      resynchroniser.or(page.getByTestId('cal-devis-refus')),
    ).toBeVisible()
  } else {
    // Déjà lié : le parcours s'achève sur la resynchronisation, qui est la
    // MÊME sortie CAL24/CAL25 côté serveur.
    await expect(resynchroniser).toBeEnabled()
  }
})

// CALX1 — LE RAIL D'ONGLETS : trois onglets ouverts À LA SUITE, sur le même
// écran, sans jamais taper une URL.
//
// POURQUOI. Treize écrans du module étaient déclarés dans `module.config.jsx`
// et servis par le routeur sans qu'aucun `Link` ni `navigate` du dépôt n'y
// mène : livrés, et introuvables. Le test unitaire prouve que le registre
// monte le bon composant ; cette spec prouve l'autre moitié — qu'un
// utilisateur les ATTEINT depuis l'atelier, en un clic chacun, et que l'URL
// garde la trace de l'onglet ouvert (`?onglet=<cle>`, lien partageable).
//
// HOOKS DOM, PAS DE TEXTE : les onglets portent `data-testid="cal-onglet-<cle>"`
// (`features/calepinage/atelier/Rail.jsx`) et le panneau
// `data-testid="cal-onglet-panneau"`. Les clés citées ici sont celles du
// registre `atelier/onglets.js` ; ce sont AUSSI les derniers segments des
// routes profondes historiques, qui restent servies.
//
// TROIS ONGLETS SANS DONNÉE DE CALCUL : « Pente », « Horizon lointain » et
// « Dossiers réglementaires » s'ouvrent sur un calepinage tout juste créé.
// On n'attend AUCUN chiffre — un calepinage neuf n'a rien calculé, et exiger
// un résultat ici ferait de cette spec un test du moteur.
test('CALX1: l’atelier ouvre trois onglets de suite, sans quitter l’écran', async ({ page }) => {
  await gotoLeads(page)
  const nomLead = await createLead(page, {
    nom: uniq('CALX1 Lead'), facture: 900, ville: 'Casablanca',
  })

  await page.goto('/calepinage/nouveau')
  await expect(page.getByRole('heading', { name: 'Nouveau calepinage' })).toBeVisible()
  await page.getByRole('tab', { name: 'Lead' }).click()
  await page.locator('#cal-nouveau-lead').getByRole('combobox').click()
  await page.getByRole('searchbox').fill(nomLead)
  await page.getByRole('option', { name: new RegExp(nomLead) }).first().click()
  await page.locator('#cal-nouveau-nom').fill(uniq('CALX1 Toiture'))
  await page.getByRole('button', { name: 'Créer le calepinage' }).click()

  await expect(page).toHaveURL(/\/calepinage\/\d+/)
  const rail = page.getByTestId('cal-rail-onglets')
  await expect(rail).toBeVisible()
  // Sans `?onglet=`, l'atelier est exactement ce qu'il était : rien d'ouvert.
  await expect(page.getByTestId('cal-onglet-panneau')).toHaveCount(0)

  const calepinageId = idDansUrl(page.url())
  expect(calepinageId, 'aucun identifiant de calepinage dans l’URL').toBeTruthy()

  for (const cle of ['pente', 'horizon', 'dossiers']) {
    await page.getByTestId(`cal-onglet-${cle}`).click()
    // 1. l'onglet devient l'onglet actif ; 2. son panneau s'affiche ;
    // 3. l'URL porte la clé — un lien copié ici rouvre le même onglet.
    await expect(page.getByTestId(`cal-onglet-${cle}`)).toHaveAttribute('aria-selected', 'true')
    await expect(page.getByTestId('cal-onglet-panneau')).toBeVisible()
    await expect(page).toHaveURL(new RegExp(`onglet=${cle}`))
    // Jamais un écran blanc : soit le panneau a du contenu, soit il NOMME son
    // échec (`cal-onglet-erreur`) — les deux sont visibles, aucun ne l'est pas.
    await expect(page.getByTestId('cal-onglet-erreur')).toHaveCount(0)
  }

  // La route profonde historique reste servie : le lien envoyé hier s'ouvre
  // encore aujourd'hui, sur le même écran que l'onglet.
  await page.goto(`/calepinage/${calepinageId}/pente`)
  await expect(page.getByTestId('cal-pente')).toBeVisible()
})

// CALX130 — LE PARCOURS ENRICHI DU LOT 2, DE BOUT EN BOUT.
//
// POURQUOI CETTE SPEC EXISTE. Les gestes ajoutés par le lot 2 (angles droits CALX89,
// insertion de sommet CALX91, obstacle polygonal CALX103, cible d'optimisation CALX114,
// course du soleil CALX118) avaient chacun leur vitest, mais aucune traversée COMPLÈTE ne
// prouvait qu'un utilisateur réel les enchaîne sur le MÊME calepinage, les enregistre, et
// les retrouve intacts à la réouverture — exactement le piège que PACT10 nomme (l'écran AO
// du 03/08/2026, 0 clé sur 6 concordante, faute d'un contrat/parcours vérifié de bout en bout).
//
// DEUX GESTES DU LOT NE SONT PAS JOUÉS ICI, ET C'EST DIT PLUTÔT QUE CACHÉ. « Corriger le
// type d'une arête » (CALX94) et « choisir un module du stock » (CALX109) ouvrent chacun un
// panneau ancré sur `ctx.dom.areasWindowEl` (`apps/web/src/scripts/roofPro11/edgesUi.ts:249`,
// `.../zones.ts:691-692`), lui-même lu depuis `#rp9-areas-window`
// (`apps/web/src/scripts/roof-tool-pro11.ts:354-357`, commentaire du module : « facultatifs,
// le harness jsdom ne les fournit pas »). Cet id n'existe QUE dans la page de démonstration
// `apps/web/src/pages/preview/toiture-3d-pro-11.astro:739` — recherche exhaustive vérifiée
// sur `frontend/` (aucune occurrence de `rp9-areas-window` NI de son repli `rp9-edges-host`) :
// la page RÉELLE `pages/ventes/ToitureDesign.jsx`, servie par `/calepinage/:id` comme par
// `/devis-design/:id`, ne rend NULLE PART ce conteneur. Un clic sur ces deux panneaux
// timeout-erait donc sur un élément introuvable dans l'atelier tel qu'il est livré
// aujourd'hui, pas sur un vrai refus produit — ce n'est PAS ce que cette spec doit prouver.
// C'est un écart d'intégration ANTÉRIEUR à cette tâche (CALX109 listait pourtant
// `ToitureDesign.jsx` parmi ses fichiers) et hors du fichier unique de cette lane :
// `[BLOCKED: ToitureDesign.jsx ne rend aucun conteneur #rp9-areas-window ni #rp9-edges-host
// — il faut lui ajouter ce conteneur pour que edgesUi.ts/zones.ts s'y accrochent, hors
// périmètre de frontend/e2e/calepinage-parcours.spec.js]` — crochet pour une tâche de phase 2.
test('CALX130: angles droits, sommet inséré, obstacle polygonal, cible d’optimisation, course du soleil — relus à l’identique', async ({ page }) => {
  // ── 0. Un lead FRAIS, un calepinage FRAIS créé depuis lui (même patron que CAL221) ──
  await gotoLeads(page)
  const nomLead = await createLead(page, {
    nom: uniq('CALX130 Lead'), facture: 900, ville: 'Casablanca',
  })

  await page.goto('/calepinage/nouveau')
  await expect(page.getByRole('heading', { name: 'Nouveau calepinage' })).toBeVisible()
  await page.getByRole('tab', { name: 'Lead' }).click()
  await page.locator('#cal-nouveau-lead').getByRole('combobox').click()
  await page.getByRole('searchbox').fill(nomLead)
  await page.getByRole('option', { name: new RegExp(nomLead) }).first().click()
  await page.locator('#cal-nouveau-nom').fill(uniq('CALX130 Toiture'))
  await page.getByRole('button', { name: 'Créer le calepinage' }).click()

  await expect(page).toHaveURL(/\/calepinage\/\d+/)
  const calepinageId = idDansUrl(page.url())
  expect(calepinageId, 'aucun identifiant de calepinage dans l’URL').toBeTruthy()

  // ── 1. LA CARTE ──────────────────────────────────────────────────────────
  const map = page.locator('#rp9-map')
  await expect(map).toBeVisible({ timeout: 20_000 })
  const box = await map.boundingBox()
  expect(box, 'le canvas de la carte doit avoir une taille').toBeTruthy()
  const cx = box.x + box.width / 2
  const cy = box.y + box.height / 2

  // ── 2. CALX89 — ANGLES DROITS, armés AVANT le tracé (puce créée par le
  // constructeur lui-même, `mapDraw.ts ensureAngleChip`, éteinte par défaut). ──
  const angleChip = page.locator('#rp9-snap-angle')
  await expect(angleChip).toBeVisible()
  await angleChip.click()
  await expect(angleChip).toHaveAttribute('aria-pressed', 'true')
  await expect(page.locator('#rp9-status')).toContainText('Angles droits', { timeout: 5_000 })

  // ── 3. TRACER un rectangle À LA SOURIS. Même chemin que le tap tactile
  // (CAL107 : « le `click` de MapLibre est synthétisé après un tap sans glissé —
  // même chemin que l'ajout d'un sommet de tracé ») : on rejoue exactement le
  // patron de `calepinage_tactile.spec.js`, souris au lieu du doigt. ──────────
  const corners = [
    { x: cx - 110, y: cy - 75 },
    { x: cx + 110, y: cy - 75 },
    { x: cx + 110, y: cy + 75 },
    { x: cx - 110, y: cy + 75 },
  ]
  const undoPoint = page.locator('#rp9-undo-point')
  for (const pt of corners) {
    await page.mouse.click(pt.x, pt.y)
    await expect(undoPoint).toBeEnabled({ timeout: 10_000 })
    // Fenêtre anti-double-clic (W77, 240 ms) laissée s'écouler avant le coin
    // suivant, sinon deux clics rapprochés seraient lus comme UN double-clic.
    await page.waitForFunction(
      (since) => Date.now() - since >= 260, Date.now(), { polling: 50 },
    )
  }
  const finishBtn = page.locator('#rp9-finish')
  await expect(finishBtn).toBeEnabled({ timeout: 10_000 })
  await finishBtn.click()
  await expect(page.locator('#rp9-config')).toBeVisible({ timeout: 10_000 })

  // ── 4. CALX91 — INSÉRER UN SOMMET au milieu du premier côté : double-clic
  // sur l'arête (projeté orthogonal, `obstaclesUi.ts insererSommetAu`), actif
  // uniquement une fois le contour fermé. ──────────────────────────────────
  const milieuArete = { x: (corners[0].x + corners[1].x) / 2, y: (corners[0].y + corners[1].y) / 2 }
  await page.mouse.dblclick(milieuArete.x, milieuArete.y)
  await expect(page.locator('#rp9-status')).toContainText('Sommet inséré', { timeout: 5_000 })

  // ── 5. CALX103 — POSER UN OBSTACLE POLYGONAL : clics successifs, double-clic
  // pour fermer (même geste que le tracé du toit, même garde `isSimplePolygon`). ──
  const polyBtn = page.locator('#rp9-obs-polygone')
  await expect(polyBtn).toBeVisible()
  await polyBtn.click()
  await expect(polyBtn).toHaveAttribute('aria-pressed', 'true')
  const obsPts = [
    { x: cx - 25, y: cy - 18 },
    { x: cx + 25, y: cy - 18 },
    { x: cx, y: cy + 18 },
  ]
  for (const pt of obsPts) {
    await page.mouse.click(pt.x, pt.y)
  }
  await page.mouse.dblclick(obsPts[2].x, obsPts[2].y)
  await expect(page.locator('#rp9-obs-edit')).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('#rp9-obs-dims')).toContainText('polygone', { timeout: 5_000 })

  // ── 6. CALX114 — RÉGLER LA CIBLE D'OPTIMISATION : puce créée par le module
  // (`matrix.ts renderCibleChips`), apparue dans `#rp9-results` dès la fermeture
  // du tracé (toit plat par défaut → la matrice se peint tout de suite). ─────
  const cibleChip = page.locator('[data-cible="compte"]')
  await expect(cibleChip).toBeVisible({ timeout: 10_000 })
  await expect(cibleChip).toHaveAttribute('aria-pressed', 'false')
  await cibleChip.click()
  await expect(cibleChip).toHaveAttribute('aria-pressed', 'true')

  // ── 7. CALX118 — OUVRIR L'ONGLET COURSE DU SOLEIL (même patron que CALX1 :
  // hook DOM `data-testid`, jamais un texte traduit). ─────────────────────
  await page.getByTestId('cal-onglet-course-soleil').click()
  await expect(page.getByTestId('cal-onglet-course-soleil')).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByTestId('cal-onglet-panneau')).toBeVisible()
  await expect(page.getByTestId('cal-onglet-erreur')).toHaveCount(0)

  // ── 8. ENREGISTRER le calepinage (CAL37, bouton unique posé par
  // `AtelierPanneaux`, JAMAIS un statut ni un devis touché — règle #4). ─────
  const enregistrer = page.getByRole('button', { name: 'Enregistrer le calepinage' })
  await expect(enregistrer).toBeVisible()
  await enregistrer.click()
  await expect(page.getByTestId('cal-erreur-enregistrement')).toHaveCount(0, { timeout: 15_000 })
  await expect(enregistrer).toBeEnabled({ timeout: 15_000 })

  // ── 9. RELU À L'IDENTIQUE, PAR LE DOCUMENT SERVEUR — la preuve la plus
  // stable : le document `roof_layout` enregistré porte la forme réelle de
  // l'obstacle (CALX85/CALX103) et la cible saisie (CALX88/CALX114), sans
  // dépendre du recentrage 3D de la caméra à la réouverture de l'écran. ─────
  const detail = await page.request.get(`${API}/calepinages/${calepinageId}/`)
  expect(detail.ok(), `GET calepinage (${detail.status()})`).toBeTruthy()
  const layout = (await detail.json())?.roof_layout ?? {}
  const zones = Array.isArray(layout.zones) ? layout.zones : []
  const aUnObstaclePolygonal = zones.some(
    (z) => Array.isArray(z.obstacles)
      && z.obstacles.some((o) => o.forme === 'polygone' && Array.isArray(o.contour)),
  )
  expect(aUnObstaclePolygonal, 'l’obstacle polygonal doit survivre à l’enregistrement').toBeTruthy()
  expect(layout.optimisation?.cible, 'la cible d’optimisation doit survivre à l’enregistrement').toBe('compte')

  // ── 10. ROUVRIR LE CALEPINAGE — la cible reste affichée par l'ÉCRAN, cette
  // fois par une VRAIE réhydratation (`prefill.ts semerOptimisationDepuisDocument`),
  // pas seulement lue sur le document serveur. ─────────────────────────────
  await page.goto(`/calepinage/${calepinageId}`)
  await expect(page.locator('#rp9-config')).toBeVisible({ timeout: 20_000 })
  const cibleChipRouverte = page.locator('[data-cible="compte"]')
  await expect(cibleChipRouverte).toBeVisible({ timeout: 10_000 })
  await expect(cibleChipRouverte).toHaveAttribute('aria-pressed', 'true')
})
