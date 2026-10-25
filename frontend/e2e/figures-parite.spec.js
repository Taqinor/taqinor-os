// QA-FIGURES — un même chiffre est IDENTIQUE à l'écran, dans l'API et dans la
// charge utile de la page publique (le PDF et ses marqueurs sont couverts côté
// backend par apps/ventes/tests/test_figures_parite.py, sur le même vocabulaire).
//
// 12 des 30 bugs « chiffre faux » de l'audit QA (docs/decisions/COUV-HOR/
// audit-qa-complet.md) étaient le MÊME chiffre différent d'une surface à
// l'autre, presque tous trouvés par le fondateur. Cette spec crée un devis
// résidentiel AVEC facture par la vraie interface (le chemin factures ÷ barème
// de DEV-202609-0113), lit TOUS les chiffres marqués `data-figure` à l'écran,
// relit le même devis par l'API interne et par la charge utile publique (jeton
// INTERNE : aucune notification, aucun changement de statut), et compare avec
// les tolérances de figures.py. Tout chiffre marqué demain est couvert ici sans
// une ligne de plus.
//
// Pas de `sleep` : l'écran du générateur converge (aperçu local → étude horaire
// serveur) ; `expect.poll` relit l'écran jusqu'à ce qu'il n'y ait plus d'écart
// ou que le délai expire — seul un écart PERSISTANT fait échouer.
import { test, expect } from '@playwright/test'
import {
  gotoLeads, createLead, openLead, generateAutoDevis, uniq,
} from './helpers'
import {
  FIGURE_KEYS, clesDuVocabulairePython, clesInconnues, comparer,
  figuresDepuisDevisApi, figuresDepuisProposition, identitesComparees,
  lireFiguresPage,
} from './figures'

const CREATION_DEVIS = /\/api\/django\/ventes\/devis\/(auto\/)?$/

// Écarts RÉELS connus sur CE parcours (lead + facture → Devis automatique →
// Édition complète), chacun avec sa tâche ERR ouverte dans docs/ERROR_PLAN.md.
// ECARTS_CONNUS NE PEUT QUE RÉTRÉCIR : une identité listée qui ne diverge plus
// fait échouer la spec (« retirez-la ») ; on n'en ajoute une qu'avec un repro
// et une tâche ERR-*. Toute AUTRE identité reste comparée strictement — ne
// jamais élargir une tolérance pour faire passer un écart.
// Vide depuis CI #752 : payback_ans@sans/avec (formule moteur à l'écran +
// aperçu à la même occupation que le bloc du devis) et total_ttc@sans/avec
// (prix rouverts au centime) ne divergent plus.
// ERR-QAH-FIG-EDITION-ETUDE-LIVE-VS-DOCUMENT — plus AUCUNE tolérance sur la
// production ni sur les économies : l'écart « intermittent » comparait deux
// options DIFFÉRENTES. Sur un devis « Les deux » aux champs PV divergents
// (panneaux ajoutés pour remplir la batterie), la carte unique de l'écran
// décrivait l'option SANS et l'API sa production de tête, celle de l'option
// AVEC (CI : api 6 813 / écran 4 542 = 6 / 4 panneaux). Les trois surfaces
// portent désormais la production PAR OPTION sur un tel devis
// (`production_annuelle_kwh@sans|@avec`), comparée strictement.
const ECARTS_CONNUS = new Set([])
const identiteEcart = (msg) => msg.split(' : ')[0]

/** Écarts NOUVEAUX (hors liste) + identités connues (stables) qui ne divergent PLUS. */
function ecartsHorsConnus(surfaces) {
  const ecarts = comparer(surfaces)
  const vus = new Set(ecarts.map(identiteEcart))
  const nouveaux = ecarts.filter((e) => !ECARTS_CONNUS.has(identiteEcart(e)))
  const perimes = [...ECARTS_CONNUS].filter((id) => !vus.has(id)).map((id) => `${id} : écart `
    + 'connu qui ne se reproduit plus — retirez-le de ECARTS_CONNUS (la liste ne fait que rétrécir)')
  return [...nouveaux, ...perimes]
}

test('QA-FIGURES : le jumeau JS suit le vocabulaire de figures.py', () => {
  expect(Object.keys(FIGURE_KEYS).sort()).toEqual(clesDuVocabulairePython())
})

test('QA-FIGURES : écran, API et proposition publique affichent les mêmes chiffres', async ({ page }) => {
  test.setTimeout(150_000)
  await gotoLeads(page)
  const name = await createLead(page, { nom: uniq('Figures'), facture: 900 })
  await openLead(page, name)

  // L'identifiant du devis créé, lu sur la RÉPONSE de création (jamais deviné
  // dans une liste partagée par les autres specs).
  // Délai ALIGNÉ sur `generateAutoDevis` (45 s jusqu'au canvas du PDF) : la
  // création auto (dimensionnement + rendu) dépasse parfois les 15 s par
  // défaut de `actionTimeout` sur un runner chargé (E4 mesuré 17 à 44 s).
  const creation = page.waitForResponse((r) => r.request().method() === 'POST'
    && CREATION_DEVIS.test(new URL(r.url()).pathname) && r.status() < 300,
  { timeout: 45_000 })
  await generateAutoDevis(page)
  const devisId = (await (await creation).json()).id
  expect(devisId, 'identifiant du devis créé').toBeTruthy()

  // ── Surfaces JSON ─────────────────────────────────────────────────────────
  const detail = await page.request.get(`/api/django/ventes/devis/${devisId}/`)
  expect(detail.ok()).toBeTruthy()
  const detailJson = await detail.json()
  const apiDevis = figuresDepuisDevisApi(detailJson)
  // ERR-QAH-FIG-EDITION-ETUDE-LIVE-VS-DOCUMENT — le repli intermittent du
  // document (6 543 kWh = kWc × productible de repli) n'a pas de cause
  // reproduite sans pile : le journal CI dit, juste après la création, si le
  // bloc horaire est rangé et pour quelle puissance (une ligne, jamais un échec).
  const etudeRangee = detailJson.etude_params || {}
  const bloc = etudeRangee.etude_horaire
  console.log('[ERR-QAH-FIG-EDITION] bloc horaire après création : '
    + (bloc ? `présent, kWc ${bloc.kwc}, production ${bloc.annuel?.production_kwh}, `
      + `source ${bloc.source_production}` : 'ABSENT')
    + ` ; puissance du devis ${etudeRangee.puissance_kwc}`
    + ` ; production API ${apiDevis.production_annuelle_kwh?.[0]?.texte}`)

  // Jeton INTERNE (L-INTPREV) : même charge utile que le client, sans trace
  // d'ouverture, sans notification ; `envoi` absent → aucun changement de statut.
  const lien = await page.request.post(`/api/django/ventes/devis/${devisId}/share-link/`, { data: {} })
  expect(lien.ok()).toBeTruthy()
  const { token_interne: jeton } = await lien.json()
  expect(jeton, 'jeton interne de la proposition').toBeTruthy()
  const data = await page.request.get(`/api/django/public/proposal/${jeton}/data/`)
  expect(data.ok()).toBeTruthy()
  const proposition = figuresDepuisProposition(await data.json())
  // Champs PV divergents : le document chiffre la production de CHAQUE
  // option ; l'écran doit alors montrer ces mêmes identités, une par option.
  const productionsParOption = Object.keys(proposition)
    .filter((id) => id.startsWith('production_annuelle_kwh@')).sort()
  const blocSans = etudeRangee.etude_horaire_sans
  console.log('[ERR-QAH-FIG-EDITION] production par option : '
    + (productionsParOption.length
      ? productionsParOption.map((id) => `${id} proposition ${proposition[id][0].texte}, `
        + `API ${apiDevis[id]?.[0]?.texte}`).join(' ; ')
      : 'options non divergentes')
    + ` ; bloc horaire sans : ${blocSans ? `kWc ${blocSans.kwc}, `
      + `production ${blocSans.annuel?.production_kwh}` : 'ABSENT'}`)

  // ── Écran : l'éditeur complet du MÊME devis ──────────────────────────────
  await page.getByRole('button', { name: /Édition complète/ }).click()
  await expect(page.locator('[data-figure="total_ttc"]').first()).toBeVisible({ timeout: 45_000 })

  // L'écran se remplit en deux temps (lignes, puis l'étude horaire servie par
  // l'aperçu) : tant que ses chiffres d'étude ne sont pas lus, AUCUN écart ne
  // peut apparaître — sans cette attente, une ECARTS_CONNUS vide laissait le
  // poll conclure sur un écran à moitié rendu (CI #752).
  const ETUDE_ECRAN = ['production_annuelle_kwh', 'payback_ans', 'couverture_pct']
  let surfaces = null
  await expect.poll(async () => {
    const ecran = await lireFiguresPage(page)
    surfaces = { ecran, api_devis: apiDevis, proposition }
    const cles = Object.keys(ecran)
    const manquantes = ETUDE_ECRAN.filter((p) => !cles.some((id) => id.startsWith(p)))
    return [...ecartsHorsConnus(surfaces),
      ...manquantes.map((p) => `${p} : pas encore affiché à l'écran (étude non lue)`),
      ...productionsParOption.filter((id) => !(id in ecran))
        .map((id) => `${id} : production de cette option absente de l'écran`),
      ...cles.filter((id) => id.startsWith('production_annuelle_kwh@') && !productionsParOption.includes(id))
        .map((id) => `${id} : production par option à l'écran, unique dans le document`)]
  }, {
    message: 'le même chiffre diffère entre l\'écran, l\'API et la proposition publique '
      + '(hors ECARTS_CONNUS), ou un écart connu ne se reproduit plus',
    timeout: 30_000,
  }).toEqual([])

  expect(clesInconnues(surfaces.ecran), 'clés data-figure hors vocabulaire').toEqual([])
  // Le test ne prouve rien s'il ne confronte rien : les totaux par option et
  // la production doivent être lus sur au moins deux surfaces.
  const comparees = [...identitesComparees(surfaces)]
  expect(comparees.some((id) => id.startsWith('total_ttc@')), comparees.join(', ')).toBe(true)
  expect(comparees.some((id) => id.startsWith('production_annuelle_kwh')), comparees.join(', ')).toBe(true)
  for (const id of productionsParOption) expect(comparees.includes(id), comparees.join(', ')).toBe(true)
})
