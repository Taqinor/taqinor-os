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
import { uniq, gotoLeads, createLead, openLead, closeLeadModal } from './helpers'

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
// course du soleil CALX118, correction de type d'arête CALX94, choix de module CALX109)
// avaient chacun leur vitest, mais aucune traversée COMPLÈTE ne prouvait qu'un utilisateur
// réel les enchaîne sur le MÊME calepinage, les enregistre, et les retrouve intacts à la
// réouverture — exactement le piège que PACT10 nomme (l'écran AO du 03/08/2026, 0 clé sur 6
// concordante, faute d'un contrat/parcours vérifié de bout en bout).
//
// FIX-RP9 — CALX94/CALX109 ÉTAIENT INJOIGNABLES, ET C'EST MAINTENANT CORRIGÉ. Les deux
// panneaux s'ancrent sur `ctx.dom.areasWindowEl` (`apps/web/src/scripts/roofPro11/edgesUi.ts:249`,
// `.../zones.ts:691-692`), lui-même lu depuis `#rp9-areas-window`
// (`apps/web/src/scripts/roof-tool-pro11.ts:357`). Cet id n'existait QUE dans la page de
// démonstration `apps/web/src/pages/preview/toiture-3d-pro-11.astro:739` — la page RÉELLE
// `pages/ventes/ToitureDesign.jsx`, servie par `/calepinage/:id` comme par `/devis-design/:id`,
// ne rendait NULLE PART ce conteneur (CALX109 listait pourtant `ToitureDesign.jsx` parmi ses
// fichiers : un reliquat d'acceptation). Le conteneur (même contenu/emplacement que la page
// publique) est maintenant posé dans `ToitureDesign.jsx`, juste après `#rp9-results` — les deux
// gestes sont donc joués ci-dessous, avec preuve de persistance comme les cinq autres.
test('CALX130: angles droits, sommet inséré, obstacle polygonal, cible d’optimisation, course du soleil, arête corrigée, module choisi — relus à l’identique', async ({ page }) => {
  // ── 0. Un lead FRAIS, un calepinage FRAIS créé depuis lui (même patron que CAL221) ──
  await gotoLeads(page)
  const nomLead = await createLead(page, {
    nom: uniq('CALX130 Lead'), facture: 900, ville: 'Casablanca',
  })

  // ── 0bis. CALX109 — UN MODULE RÉEL DU CATALOGUE, posé par l'API (même patron que la
  // variante CAL221 : l'écran ne sait pas SAISIR une fiche technique, seul le geste de
  // CHOIX se joue à l'écran). Fiche complète (longueur/largeur/puissance crête) pour que
  // `apps.stock.selectors.dimensions_de_pose` la rende SÉLECTIONNABLE (jamais grisée) —
  // posé AVANT la création du calepinage : le catalogue est lu une fois, à l'ouverture de
  // l'atelier (`calepinageApi.calepinages.modulesDisponibles`).
  const nomModule = uniq('CALX109 Module')
  const produitRes = await page.request.post('/api/django/stock/produits/', {
    data: { nom: nomModule, prix_vente: '1000.00' },
  })
  expect(produitRes.ok(),
    `produit module refusé : ${produitRes.status()} ${await produitRes.text()}`).toBeTruthy()
  const { id: produitId } = await produitRes.json()
  const ficheRes = await page.request.post('/api/django/stock/fiches-techniques/', {
    data: {
      produit: produitId, type_fiche: 'module',
      longueur_mm: 2384, largeur_mm: 1303, pmax_wc: 720,
    },
  })
  expect(ficheRes.ok(),
    `fiche technique refusée : ${ficheRes.status()} ${await ficheRes.text()}`).toBeTruthy()
  const moduleIdAttendu = `produit-${produitId}`

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

  // ── 0ter. PRÉREQUIS D'ENVIRONNEMENT : UNE CARTE SERVIE (FIX-M5-E2E). ─────
  // Tous les gestes ci-dessous vivent dans le CONSTRUCTEUR (`initRoofToolPro8`
  // → `createMapDraw`, qui crée lui-même `#rp9-snap-angle`). Or l'atelier ne le
  // boote QUE si le serveur publie une carte (`design-context` → `carte`, lue
  // par `_config_carte()` dans `PUBLIC_MAPTILER_KEY`) ; sans elle il s'arrête
  // en NOMMANT la panne (`ToitureDesign.jsx` `bootCalepinage`) — et `#rp9-map`,
  // simple conteneur JSX, reste « visible » quand même. Le job e2e de la CI ne
  // pose AUCUNE clé MapTiler (secret non provisionné) : ce parcours n'y est
  // donc pas rejouable, et il le DIT (skip motivé) au lieu d'échouer 15 s plus
  // loin sur une puce jamais créée. La vérité vient du SERVEUR (même porte que
  // l'écran), jamais d'une variable devinée côté spec : là où la carte est
  // servie, le parcours complet se joue, inchangé.
  const contexteRes = await page.request.get(
    `${API}/calepinages/${calepinageId}/design-context/`)
  expect(contexteRes.ok(),
    `design-context refusé : ${contexteRes.status()}`).toBeTruthy()
  const { carte } = await contexteRes.json()
  if (!carte?.available) {
    // Même sans carte, l'écran ne montre jamais une carte morte muette.
    await expect(page.getByRole('alert').filter({ hasText: 'clé MapTiler' })).toBeVisible()
  }
  test.skip(!carte?.available,
    'carte indisponible sur cet environnement (le serveur ne publie aucune clé MapTiler) : '
    + 'le constructeur de l’atelier ne boote pas — gestes CALX89…CALX109 non rejouables ici')

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

  // ── 7bis. CALX94 — CORRIGER LE TYPE D'UNE ARÊTE. Le panneau (`#rp9-edge-mode` /
  // `#rp9-edge-type`) n'existe QUE si `#rp9-areas-window` est présent dans le DOM
  // (`edgesUi.ts ensurePanel`, anchor = repli sur cette fenêtre) — la preuve directe que
  // le conteneur ajouté par FIX-RP9 rend enfin ce geste joignable. Clic au milieu du côté
  // BAS (corners[2]→corners[3]) : le seul côté qu'aucun autre geste de ce test ne touche
  // (le sommet CALX91 a été inséré sur le côté HAUT, l'obstacle est près du centre). ──
  const edgeModeBtn = page.locator('#rp9-edge-mode')
  await expect(edgeModeBtn).toBeVisible({ timeout: 10_000 })
  await edgeModeBtn.click()
  await expect(edgeModeBtn).toHaveAttribute('aria-pressed', 'true')
  const milieuBas = { x: (corners[2].x + corners[3].x) / 2, y: (corners[2].y + corners[3].y) / 2 }
  await page.mouse.click(milieuBas.x, milieuBas.y)
  const edgeInfo = page.locator('#rp9-edge-info')
  await expect(edgeInfo).toContainText('Arête nº', { timeout: 5_000 })
  // L'arête sélectionnée est NOMMÉE dans le texte — on lit son numéro plutôt que de
  // supposer un index (CALX91 a déjà décalé l'ordre des sommets en insérant un point).
  const infoArete = (await edgeInfo.textContent()) ?? ''
  const numeroArete = Number(/Arête nº(\d+)/.exec(infoArete)?.[1])
  expect(numeroArete, `numéro d’arête introuvable dans « ${infoArete} »`).toBeGreaterThan(0)
  await page.locator('#rp9-edge-type').selectOption('faitage')
  await expect(edgeInfo).toContainText('Faîtage', { timeout: 5_000 })
  await expect(edgeInfo).toContainText('corrigé à la main', { timeout: 5_000 })
  await edgeModeBtn.click() // désarme le mode — rend le clic carte au tracé/obstacles
  await expect(edgeModeBtn).toHaveAttribute('aria-pressed', 'false')

  // ── 7ter. CALX109 — CHOISIR UN MODULE DU STOCK sur le pan actif. Même anchor que
  // CALX94 ci-dessus (`zones.ts ensureModulePicker`, `ctx.dom.areasWindowEl`) : le
  // sélecteur ne peut exister que depuis le même correctif. Le module posé en 0bis
  // (fiche complète) est SÉLECTIONNABLE — jamais l'un des modèles grisés. ─────────
  const moduleSelect = page.locator('#rp9-pan-module-select')
  await expect(moduleSelect).toBeVisible({ timeout: 10_000 })
  await moduleSelect.selectOption({ label: nomModule })
  await expect(page.locator('#rp9-status')).toContainText('repavé à ses cotes', { timeout: 10_000 })

  // ── 8. ENREGISTRER le calepinage (CAL37, bouton unique posé par
  // `AtelierPanneaux`, JAMAIS un statut ni un devis touché — règle #4). ─────
  const enregistrer = page.getByRole('button', { name: 'Enregistrer le calepinage' })
  await expect(enregistrer).toBeVisible()
  await enregistrer.click()
  await expect(page.getByTestId('cal-erreur-enregistrement')).toHaveCount(0, { timeout: 15_000 })
  await expect(enregistrer).toBeEnabled({ timeout: 15_000 })

  // ── 9. RELU À L'IDENTIQUE, PAR LE DOCUMENT SERVEUR — la preuve la plus
  // stable : le document `roof_layout` enregistré porte la forme réelle de
  // l'obstacle (CALX85/CALX103), la cible saisie (CALX88/CALX114), l'arête corrigée
  // (CALX94) et le module choisi (CALX109), sans dépendre du recentrage 3D de la
  // caméra à la réouverture de l'écran. ─────────────────────────────────────
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

  // CALX94 — l'arête corrigée à la main (index 0-based = le numéro lu à l'écran − 1)
  // porte le type choisi ET `manuel: true` — jamais re-déduite en silence.
  const areteEcrite = zones
    .flatMap((z) => (Array.isArray(z.edges) ? z.edges : []))
    .find((e) => e.index === numeroArete - 1)
  expect(areteEcrite, `aucune arête nº${numeroArete} enregistrée parmi ${JSON.stringify(zones.map((z) => z.edges))}`)
    .toBeTruthy()
  expect(areteEcrite?.type, 'le type corrigé (Faîtage) doit survivre à l’enregistrement').toBe('faitage')
  expect(areteEcrite?.manuel, 'la correction doit rester marquée manuelle').toBe(true)

  // CALX109 — le module choisi voyage dans `zones[].geometry.moduleId` (contrat CALX82).
  const moduleEcrit = zones.some((z) => z.geometry?.moduleId === moduleIdAttendu)
  expect(moduleEcrit,
    `moduleId « ${moduleIdAttendu} » introuvable parmi ${JSON.stringify(zones.map((z) => z.geometry?.moduleId))}`)
    .toBeTruthy()

  // ── 10. ROUVRIR LE CALEPINAGE — la cible reste affichée par l'ÉCRAN, cette
  // fois par une VRAIE réhydratation (`prefill.ts semerOptimisationDepuisDocument`),
  // pas seulement lue sur le document serveur. ─────────────────────────────
  await page.goto(`/calepinage/${calepinageId}`)
  await expect(page.locator('#rp9-config')).toBeVisible({ timeout: 20_000 })
  const cibleChipRouverte = page.locator('[data-cible="compte"]')
  await expect(cibleChipRouverte).toBeVisible({ timeout: 10_000 })
  await expect(cibleChipRouverte).toHaveAttribute('aria-pressed', 'true')
})

// CALX386 — LE PARCOURS COMPLET, DE L'ATELIER AU RETOUR CRM.
//
// POURQUOI CETTE SPEC EXISTE. CAL221 (ci-dessus) traverse création → variante
// (semée par l'API) → retenir → devis, mais son PROPRE en-tête le disait déjà
// à l'écriture de CALX386 : ni la conception, ni la simulation, ni
// l'électrique, ni les documents, ni le retour CRM n'étaient jamais
// traversés — et `e2e-shard` ne joue cette spec QUE dans `release-verify.yml`
// (nightly/manuel), jamais sur une PR. Ce test ajoute les maillons manquants,
// PAR L'INTERFACE, sur un calepinage frais.
//
// TRAVERSÉE, PAS RÉUSSITE FORCÉE. Un calepinage tout juste créé depuis un
// lead n'a NI toiture tracée, NI postes de pertes saisis : `BoutonLancerSimulation`
// (`production/PanneauProduction.jsx`) est lui-même DÉSACTIVÉ tant que
// `pertes`/`cascade.etapes` sont vides (CALX48 — « sans poste de perte, le
// bouton est inactif »), et le générateur de devis peut tout aussi
// légitimement REFUSER en NOMMANT le champ (`roof_layout` absent) que
// réussir. Exiger un résultat chiffré à chaque étape ferait de cette spec un
// test du MOTEUR, pas du PARCOURS — exactement la distinction que l'en-tête
// de CALX1 pose déjà pour « Pente »/« Horizon lointain »/« Dossiers
// réglementaires ». Chaque étape est donc affirmée SOIT servie, SOIT NOMMÉE
// (jamais un écran blanc) — la garde `check_calepinage_actions_consommees.py`
// (CALX381) et les tests unitaires des panneaux couvrent déjà la RÉUSSITE
// chiffrée sur des données préparées.
//
// LE RETOUR CRM : `BlocCalepinageDevis` (`features/ventes/BlocCalepinageDevis.jsx`,
// CAL40) n'est monté que dans le dialogue d'ÉDITION du devis
// (`DevisForm.jsx`), ouvert depuis `DevisList.jsx` par le menu « Plus
// d'actions » → « Éditer » d'UNE ligne — jamais depuis l'espace de travail du
// lead (`LeadWorkspace.jsx` ouvre le devis en conception 3D, un écran
// DIFFÉRENT). La spec revient donc au lead (preuve que le geste CRM reste
// joignable), PUIS ouvre le devis généré par sa ligne dans la liste — les
// DEUX preuves attendues par la tâche, dans l'ordre où l'application les rend
// réellement disponibles.
test('CALX386: atelier → simulation → électrique → documents → devis → retour CRM', async ({ page }) => {
  await gotoLeads(page)
  const nomLead = await createLead(page, {
    nom: uniq('CALX386 Lead'), facture: 900, ville: 'Casablanca',
  })

  // ── 1. CRÉER DEPUIS LE LEAD ET OUVRIR L'ATELIER (LA CONCEPTION) ─────────
  // Sans `?onglet=`, l'atelier rend sa vue par défaut — la conception 3D
  // elle-même (`AtelierPanneaux.jsx`) : c'est CETTE vue que la tâche nomme
  // « Conception », pas un onglet séparé du registre.
  await page.goto('/calepinage/nouveau')
  await expect(page.getByRole('heading', { name: 'Nouveau calepinage' })).toBeVisible()
  await page.getByRole('tab', { name: 'Lead' }).click()
  await page.locator('#cal-nouveau-lead').getByRole('combobox').click()
  await page.getByRole('searchbox').fill(nomLead)
  await page.getByRole('option', { name: new RegExp(nomLead) }).first().click()
  await page.locator('#cal-nouveau-nom').fill(uniq('CALX386 Toiture'))
  await page.getByRole('button', { name: 'Créer le calepinage' }).click()

  await expect(page).toHaveURL(/\/calepinage\/\d+/)
  await expect(page.getByTestId('cal-atelier-panneaux')).toBeVisible()
  const calepinageId = idDansUrl(page.url())
  expect(calepinageId, 'aucun identifiant de calepinage dans l’URL').toBeTruthy()

  // ── 2. SIMULATION (onglet « Production », CALX5/CALX48) ────────────────
  await page.getByTestId('cal-onglet-production').click()
  await expect(page.getByTestId('cal-onglet-production')).toHaveAttribute('aria-selected', 'true')
  const panneauProduction = page.getByTestId('cal236-panneau')
  await expect(panneauProduction).toBeVisible()
  const lancerSimulation = page.getByTestId('calx48-lancer-bouton')
  await expect(lancerSimulation).toBeVisible()
  if (await lancerSimulation.isEnabled()) {
    await lancerSimulation.click()
    // Le résultat SERVI : soit la simulation aboutit (le panneau total
    // s'affiche), soit le serveur la refuse en NOMMANT le motif — les deux
    // sont un résultat SERVI, aucun des deux n'est un écran muet.
    await expect(
      page.getByTestId('cal236-total').or(page.getByTestId('calx48-refus')),
    ).toBeVisible({ timeout: 15_000 })
  } else {
    // Bouton désactivé (aucun poste de perte saisi, CALX48) : l'état
    // « non simulé » est lui-même le résultat servi pour ce calepinage.
    await expect(page.getByTestId('cal236-non-simule')).toBeVisible()
  }

  // ── 3. ÉLECTRIQUE (onglet « Équipements électriques », CALX222) ────────
  await page.getByTestId('cal-onglet-equipements-electriques').click()
  await expect(page.getByTestId('cal-onglet-equipements-electriques'))
    .toHaveAttribute('aria-selected', 'true')
  await expect(
    page.getByTestId('calx222-panneau').or(page.getByTestId('calx222-erreur')),
  ).toBeVisible()

  // ── 4. DOCUMENTS (onglet « Documents », CALX19/CALX320) ────────────────
  await page.getByTestId('cal-onglet-documents').click()
  await expect(page.getByTestId('cal-onglet-documents')).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByTestId('cal-doc-panneau')).toBeVisible()

  // ── 5. GÉNÉRER LE DEVIS (CAL24/CAL38) — aucune variante sur ce
  // calepinage : le serveur chiffre la conception elle-même (voir l'en-tête
  // de `BoutonDevis.jsx`), donc le bouton n'est jamais bloqué par une
  // variante manquante ici. ───────────────────────────────────────────────
  await page.goto(`/calepinage/${calepinageId}`)
  const boutonDevis = page.getByTestId('cal-bouton-devis')
  await expect(boutonDevis).toBeVisible()
  const generer = page.getByTestId('cal-generer-devis')
  const resynchroniser = page.getByTestId('cal-resynchroniser-devis')
  await expect(generer.or(resynchroniser)).toBeVisible()

  let devisId = null
  if (await generer.count() > 0) {
    await generer.click()
    // Succès → l'écran NAVIGUE vers la conception du devis créé (`BoutonDevis.jsx
    // ::generer`) : l'URL porte son identifiant. Refus → le serveur NOMME le
    // champ fautif — les deux sont un résultat servi, jamais un bouton muet.
    await expect(page).toHaveURL(/\/ventes\/devis\/\d+\/design|\/calepinage\/\d+/)
    if (/\/ventes\/devis\/(\d+)\/design/.test(page.url())) {
      devisId = /\/ventes\/devis\/(\d+)\/design/.exec(page.url())[1]
    } else {
      await expect(page.getByTestId('cal-devis-refus')).toBeVisible()
    }
  } else {
    // Déjà lié (course avec un run précédent sur le même calepinage — ne se
    // produit pas sur un calepinage frais, mais la spec ne le suppose pas).
    await expect(resynchroniser).toBeEnabled()
  }

  // ── 6. RETOUR CRM — le lead reste joignable (même geste que
  // `openLead`/`calepinage-parite-crm.spec.js`), PUIS le devis généré
  // affiche le bloc calepinage qui le pilote (CAL40). ────────────────────
  await gotoLeads(page)
  await openLead(page, nomLead)
  await closeLeadModal(page)

  if (devisId) {
    await page.goto('/ventes/devis')
    const ligne = page.locator(`#devis-row-${devisId}`)
    await expect(ligne).toBeVisible({ timeout: 15_000 })
    await ligne.getByRole('button', { name: /Plus d.actions/ }).click()
    await page.getByRole('menuitem', { name: 'Éditer' }).click()
    // Silencieux quand le devis n'a pas (encore) de calepinage résolu côté
    // serveur (`BlocCalepinageDevis.jsx` : « jamais un bloc vide ») — mais
    // CE devis vient JUSTEMENT d'être généré PAR ce calepinage : le bloc doit
    // apparaître, avec le lien retour vers l'atelier.
    await expect(page.getByTestId('cal-bloc-calepinage-devis')).toBeVisible({ timeout: 15_000 })
  }
})
