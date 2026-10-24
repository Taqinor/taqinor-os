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
// ERR-QAH-FIG-EDITION-ETUDE-LIVE-VS-DOCUMENT — plus aucune tolérance sur
// production / économies : l'aperçu de l'éditeur sert le bloc horaire RANGÉ du
// devis tant que l'écran n'explore rien (`etudes.bloc_horaire_enregistre_pour`,
// mêmes conso, GPS et occupation que le document), et la chute du document à
// 6 543 kWh était un devis SANS bloc rangé — désormais exigé juste après la
// création (le journal « bloc horaire après création » l'a dit présent à
// chaque run CI relu jusqu'au 24/10). Un écart revient ⇒ la spec échoue.
// Vide depuis CI #752 : payback_ans@sans/avec (formule moteur à l'écran +
// aperçu à la même occupation que le bloc du devis) et total_ttc@sans/avec
// (prix rouverts au centime) ne divergent plus.
const ECARTS_CONNUS = new Set([])
const identiteEcart = (msg) => msg.split(' : ')[0]

/** Écarts NOUVEAUX (hors listes) + identités connues (stables) qui ne divergent PLUS. */
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
  // ERR-QAH-FIG-EDITION-ETUDE-LIVE-VS-DOCUMENT — le devis automatique porte
  // son bloc horaire DÈS la création : sans lui le document retombe sur le
  // productible de repli (6 543 kWh = kWc × table), que l'écran ne montre pas.
  // La ligne de journal reste (puissance, production, source lues au même instant).
  const etudeRangee = detailJson.etude_params || {}
  const bloc = etudeRangee.etude_horaire
  console.log('[ERR-QAH-FIG-EDITION] bloc horaire après création : '
    + (bloc ? `présent, kWc ${bloc.kwc}, production ${bloc.annuel?.production_kwh}, `
      + `source ${bloc.source_production}` : 'ABSENT')
    + ` ; puissance du devis ${etudeRangee.puissance_kwc}`
    + ` ; production API ${apiDevis.production_annuelle_kwh?.[0]?.texte}`)
  expect(bloc, 'bloc horaire rangé juste après la création du devis automatique '
    + '(absent ⇒ le document chiffre le productible de repli, pas l’étude de l’écran)').toBeTruthy()
  expect(Number(bloc.kwc), 'puissance du bloc horaire rangé').toBeGreaterThan(0)

  // Jeton INTERNE (L-INTPREV) : même charge utile que le client, sans trace
  // d'ouverture, sans notification ; `envoi` absent → aucun changement de statut.
  const lien = await page.request.post(`/api/django/ventes/devis/${devisId}/share-link/`, { data: {} })
  expect(lien.ok()).toBeTruthy()
  const { token_interne: jeton } = await lien.json()
  expect(jeton, 'jeton interne de la proposition').toBeTruthy()
  const data = await page.request.get(`/api/django/public/proposal/${jeton}/data/`)
  expect(data.ok()).toBeTruthy()
  const proposition = figuresDepuisProposition(await data.json())

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
      ...manquantes.map((p) => `${p} : pas encore affiché à l'écran (étude non lue)`)]
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
})
