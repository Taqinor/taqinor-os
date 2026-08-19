// PACT8 — logique partagée de la fumée des écrans, découpée en GROUPES.
//
// POURQUOI CE DÉCOUPAGE (mesuré le 19/08/2026, run 32206663106)
// -------------------------------------------------------------
// `fumee-ecrans.spec.js` pesait 183,4 s, soit 84 % de tout le temps chromium du
// palier e2e, dans UN SEUL fichier. Playwright affecte un fichier entier à un
// shard : ce fichier fixait donc à lui seul le plancher du job e2e, et aucune
// répartition en lanes ne pouvait descendre en dessous. Il est ici scindé en
// GROUPES DE MODULES — la spec bouclait déjà sur les modules, donc la coupure
// est naturelle et ne change RIEN à ce qui est visité.
//
// CE QUI NE CHANGE PAS : un test par module, le même budget de temps par module,
// les mêmes constats (ErrorBoundary, exception non rattrapée, lien `…/undefined`,
// page blanche), le même rejeu unique de la page blanche. L'union des groupes
// visite EXACTEMENT les mêmes routes qu'avant — prouvé par la garde d'union
// déclarée dans le groupe 1 (`declarerGardeUnion`), qui échoue si un module
// tombe du découpage. Un module perdu, c'est un écran que plus personne n'ouvre
// pendant que la CI reste verte : exactement le défaut que PACT8 combat.
import { expect } from '@playwright/test'

import { routesParModule, TITRE_ECRAN_ERREUR } from './helpers.js'

export const PAR_MODULE = routesParModule()

// Budget par navigation. Une page qui n'a ni coquille ni écran d'erreur au bout
// de ce délai est signalée « page blanche » — un constat, pas une expiration
// muette de Playwright.
export const DELAI_ECRAN = 15_000

// Nombre de groupes. Doit rester égal au nombre de fichiers
// `fumee-ecrans-<n>.spec.js` — la garde d'union le vérifie.
export const NB_GROUPES = 3

/**
 * Répartit les modules en `total` groupes de POIDS comparable, en plaçant le
 * plus lourd d'abord sur le groupe le plus léger (LPT, comme le découpage des
 * tests backend). Le poids est le nombre de routes du module : c'est le seul
 * indicateur disponible à la lecture, et il suit de près la durée puisque le
 * coût d'un module est dominé par ses navigations.
 *
 * Déterministe : tri par (-routes, nom), et à égalité c'est toujours le groupe
 * d'indice le plus bas qui prend. Deux appels rendent le même découpage, sinon
 * une lane pourrait rejouer autre chose que ce qu'elle annonce.
 */
export function groupesDeModules(total = NB_GROUPES, parModule = PAR_MODULE) {
  const groupes = Array.from({ length: total }, () => [])
  const charges = new Array(total).fill(0)
  const modules = [...parModule.entries()].sort(
    (a, b) => (b[1].length - a[1].length) || a[0].localeCompare(b[0]),
  )
  for (const [module, chemins] of modules) {
    let cible = 0
    for (let i = 1; i < total; i += 1) if (charges[i] < charges[cible]) cible = i
    groupes[cible].push(module)
    charges[cible] += chemins.length
  }
  return groupes.map((g) => g.sort())
}

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

/**
 * Déclare un test par module du groupe `indice`. Corps IDENTIQUE à la spec
 * d'origine — seule la liste des modules change.
 */
export function declarerGroupe(test, indice, total = NB_GROUPES) {
  const modules = groupesDeModules(total)[indice]
  for (const module of modules) {
    const chemins = PAR_MODULE.get(module)
    test(`PACT8: fumée des écrans — ${module} (${chemins.length} route(s))`, async ({ page }) => {
      // Budget proportionnel au nombre d'écrans du module, jamais les 60 s par
      // défaut : un module de 20 écrans expirerait avant d'avoir tout ouvert.
      test.setTimeout(Math.max(60_000, chemins.length * (DELAI_ECRAN + 5_000)))

      const casses = []
      for (const chemin of chemins) {
        let defauts = await visiter(page, chemin)
        // « page blanche » est le SEUL constat sensible à la charge : une même
        // route tombe puis passe d'un run à l'autre (mesuré le 2026-08-07 —
        // 9 routes un run, 4 modules DIFFÉRENTS le suivant), parce que des
        // dizaines d'écrans lazy s'ouvrent à la file dans un seul navigateur.
        // On le REJOUE une fois avant d'accuser : un écran réellement cassé
        // reste blanc, un écran lent finit par rendre. Les autres constats
        // (ErrorBoundary, exception, lien `…/undefined`) sont déterministes et
        // ne sont jamais rejoués.
        if (defauts.some((d) => d.startsWith('page blanche'))) {
          defauts = await visiter(page, chemin)
        }
        for (const defaut of defauts) casses.push(`${chemin} → ${defaut}`)
      }
      expect(casses,
        `écrans cassés dans le module « ${module} » (chaque ligne est un écran `
        + 'ouvert par un utilisateur aujourd’hui)').toEqual([])
    })
  }
}

/**
 * Gardes déclarées UNE fois (groupe 1) : la lecture des routes fonctionne, et
 * le découpage ne perd rien. Purement calculatoires, coût nul.
 */
export function declarerGardeUnion(test) {
  // Garde-fou de la LECTURE elle-même : si l'extraction des routes se casse un
  // jour (renommage de `module.config.jsx`, guillemets doubles…), ces specs
  // deviendraient vertes en ne visitant RIEN. Un test vide qui se dit vert est
  // exactement le défaut que PACT8 combat.
  test('PACT8: les routes sont bien lues depuis les module.config.jsx', () => {
    const total = [...PAR_MODULE.values()].reduce((n, r) => n + r.length, 0)
    expect(PAR_MODULE.size,
      'modules avec au moins une route déclarée').toBeGreaterThan(30)
    expect(total, 'routes visitables extraites des module.config.jsx')
      .toBeGreaterThan(200)
  })

  // LA garde du découpage : l'union des groupes doit être EXACTEMENT l'ensemble
  // des modules, sans doublon ni perte. Sans elle, scinder ce fichier pourrait
  // faire disparaître silencieusement des écrans de la fumée — la CI resterait
  // verte en visitant moins.
  test('PACT8: le découpage en groupes ne perd aucun module ni aucune route', () => {
    const groupes = groupesDeModules(NB_GROUPES)
    const aplati = groupes.flat()
    expect(aplati.length, 'un module ne peut appartenir qu’à UN groupe')
      .toBe(new Set(aplati).size)
    expect([...aplati].sort(), 'union des groupes == tous les modules lus')
      .toEqual([...PAR_MODULE.keys()].sort())

    const routesGroupees = aplati.reduce((n, m) => n + PAR_MODULE.get(m).length, 0)
    const routesTotales = [...PAR_MODULE.values()].reduce((n, r) => n + r.length, 0)
    expect(routesGroupees, 'toutes les routes restent visitées').toBe(routesTotales)

    for (const [i, groupe] of groupes.entries()) {
      expect(groupe.length, `le groupe ${i + 1} est vide — lane gaspillée`)
        .toBeGreaterThan(0)
    }
  })
}
