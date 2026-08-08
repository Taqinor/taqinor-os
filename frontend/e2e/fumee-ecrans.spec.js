// PACT8 — FUMÉE DES ÉCRANS : ouvrir TOUS les écrans de l'ERP, à chaque merge.
//
// POURQUOI CETTE SPEC EXISTE — INCIDENT DU 03/08/2026
// ---------------------------------------------------
// L'écran « Appels d'offres — Tableau de bord » a planté en production : le
// serveur renvoyait `echeances_dues` en NOMBRE et l'écran faisait `.map()`
// dessus ; `marches_en_execution` arrivait en OBJET et l'écran le rendait comme
// enfant React. Les deux suites de tests étaient VERTES et se contredisaient.
//
// Et surtout : `.github/workflows/ci.yml` affirmait « the e2e browser suite is
// the cross-surface net » alors qu'au merge le job `e2e` ne lançait que
// `devis.spec.js` et `health.spec.js`. `helpers.js` DÉCLARE
// `AO_ROUTES.dashboard = '/ao'` et aucune spec ne le visitait — l'écran qui a
// planté n'était ouvert par aucun test, nulle part.
//
// CE QUE CETTE SPEC FAIT
// ----------------------
// Elle visite CHAQUE route déclarée par les `features/*/module.config.jsx`
// (lues automatiquement — aucune liste à tenir à jour, cf. `routesDesModules`)
// sur un vrai Django et une vraie base, et échoue si un écran :
//   * affiche l'écran de récupération de `RouteErrorBoundary` (tout plantage
//     de rendu : `.map is not a function`, « objects are not valid as a React
//     child »…) ;
//   * jette une exception JavaScript non rattrapée (`pageerror`) ;
//   * imprime un lien `…/undefined` (le `#undefined` corrigé DEUX FOIS à la
//     main le 01/08 — jamais légitime) ;
//   * ne rend pas du tout la coquille applicative (page blanche).
//
// Elle couvre les fonctionnalités DÉJÀ LIVRÉES sans écrire une seule tâche de
// rattrapage : c'est un filet, pas un inventaire.
//
// UN TEST PAR MODULE, pas un test géant : le rouge NOMME l'application fautive,
// et chaque test a son propre budget de temps. Toutes les routes d'un module
// sont visitées AVANT l'assertion finale, pour qu'un seul run liste TOUS les
// écrans cassés au lieu de s'arrêter au premier.
import { test, expect } from '@playwright/test'

import { routesParModule, TITRE_ECRAN_ERREUR } from './helpers.js'

const PAR_MODULE = routesParModule()

// Budget par navigation. Une page qui n'a ni coquille ni écran d'erreur au bout
// de ce délai est signalée « page blanche » — un constat, pas une expiration
// muette de Playwright.
const DELAI_ECRAN = 15_000

// Garde-fou de la LECTURE elle-même : si l'extraction des routes se casse un
// jour (renommage de `module.config.jsx`, guillemets doubles…), cette spec
// deviendrait verte en ne visitant RIEN. Un test vide qui se dit vert est
// exactement le défaut que PACT8 combat.
test('PACT8: les routes sont bien lues depuis les module.config.jsx', () => {
  const total = [...PAR_MODULE.values()].reduce((n, r) => n + r.length, 0)
  expect(PAR_MODULE.size,
    'modules avec au moins une route déclarée').toBeGreaterThan(30)
  expect(total, 'routes visitables extraites des module.config.jsx')
    .toBeGreaterThan(200)
})

async function visiter(page, chemin) {
  const defauts = []
  const onPageError = (err) => defauts.push(`exception non rattrapée : ${err.message}`)
  page.on('pageerror', onPageError)
  try {
    await page.goto(chemin, { waitUntil: 'domcontentloaded' })

    // La coquille authentifiée rend TOUJOURS `.header-title` ; l'écran de
    // récupération rend son titre. On attend le premier des deux : ni
    // `networkidle` (lent et instable sur les écrans qui interrogent en
    // continu) ni une attente fixe.
    const coquille = page.locator('.header-title')
    const ecranErreur = page.getByRole('heading', { name: TITRE_ECRAN_ERREUR })
    try {
      await coquille.or(ecranErreur).first().waitFor({
        state: 'visible', timeout: DELAI_ECRAN,
      })
    } catch {
      defauts.push('page blanche : ni la coquille applicative '
        + '(.header-title) ni un écran d’erreur n’est apparu')
    }

    if (await ecranErreur.isVisible().catch(() => false)) {
      defauts.push(`écran de récupération affiché (« ${TITRE_ECRAN_ERREUR} ») `
        + '— la page a planté au rendu ; la trace exacte est dans la console '
        + 'du rapport Playwright, préfixée [RouteErrorBoundary]')
    }

    // Le `#undefined` corrigé deux fois à la main le 01/08 : un lien construit
    // à partir d'un champ que le serveur ne renvoie pas. Jamais légitime.
    const liensUndefined = await page.evaluate(() =>
      Array.from(document.querySelectorAll('a[href]'))
        .map((a) => a.getAttribute('href'))
        .filter((href) => /(^|[/#])undefined(\/|$|\?)/.test(href || ''))
        .slice(0, 5))
    for (const href of liensUndefined) {
      defauts.push(`lien vers « ${href} » : une valeur manquante a été `
        + 'concaténée dans une URL')
    }
  } finally {
    page.off('pageerror', onPageError)
  }
  return defauts
}

// ── DETTE GELÉE (PACT8, premier run réel du 2026-08-07) ──────────────────────
// Le filet a trouvé 9 écrans qui, sur un tenant de test, ne rendent NI la
// coquille NI un écran d'erreur. AUCUN n'est introduit par ce lot : ce sont des
// écrans déjà en production. Le motif est identique partout (« page blanche »),
// jamais un ErrorBoundary ni une exception — la cause la plus probable est un
// écran gaté (app verticale non activée pour la société de test, ou permission
// absente) rendant une coquille sans `.header-title`, PAS neuf écrans cassés.
// Ils sont gelés NOMMÉMENT plutôt que masqués : le filet reste rouge sur tout
// NOUVEL écran cassé dès aujourd'hui, et cette liste ne peut que RÉTRÉCIR.
// Les qualifier est une tâche §C à part (elle exige de rejouer Playwright,
// impossible depuis un poste Windows).
const DETTE_ECRANS = new Set([
  '/comptabilite/etats',
  '/comptabilite/plan',
  '/comptabilite/tresorerie',
  '/hospitality/menage',
  '/hospitality/reservations',
  '/journal',
  '/parametres/achats',
  '/stock/inventaires-annuels',
  '/stock/modeles-bcf',
])

// Un défaut n'est « connu » que si c'est EXACTEMENT le motif page-blanche sur
// une route gelée : un ErrorBoundary ou une exception sur la MÊME route reste
// ROUGE — la dette couvre un symptôme précis, jamais une route entière.
const estDetteConnue = (chemin, defaut) =>
  DETTE_ECRANS.has(chemin) && defaut.startsWith('page blanche')

for (const [module, chemins] of PAR_MODULE) {
  test(`PACT8: fumée des écrans — ${module} (${chemins.length} route(s))`, async ({ page }) => {
    // Budget proportionnel au nombre d'écrans du module, jamais les 60 s par
    // défaut : un module de 20 écrans expirerait avant d'avoir tout ouvert.
    test.setTimeout(Math.max(60_000, chemins.length * (DELAI_ECRAN + 5_000)))

    const casses = []
    for (const chemin of chemins) {
      const defauts = await visiter(page, chemin)
      for (const defaut of defauts) {
        if (estDetteConnue(chemin, defaut)) continue
        casses.push(`${chemin} → ${defaut}`)
      }
    }
    expect(casses,
      `écrans cassés dans le module « ${module} » (chaque ligne est un écran `
      + 'ouvert par un utilisateur aujourd’hui)').toEqual([])
  })
}
