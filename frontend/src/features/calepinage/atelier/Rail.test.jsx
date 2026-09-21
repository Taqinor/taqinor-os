import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'

/* ============================================================================
   CALX1 — LE RAIL D'ONGLETS, ET LA PREUVE QU'AUCUNE ROUTE NE RESTE ORPHELINE.
   ----------------------------------------------------------------------------
   Ce que ce fichier empêche de revenir :
     1. les treize écrans servis par le routeur et visés par AUCUN lien — un
        écran qu'on ne peut pas ouvrir n'existe pas (incident du 03/08/2026) ;
     2. un onglet inscrit au registre qui ne monterait pas son composant ;
     3. un `?onglet=` fautif qui rendrait un écran blanc ;
     4. une route AJOUTÉE plus tard à `module.config.jsx` sans être rendue
        atteignable : le test ITÈRE sur `config.routes` et n'en compte JAMAIS
        le nombre — une quatorzième route ne le périme pas, elle le fait
        rougir tant qu'elle n'est ni un item de nav, ni un onglet du rail, ni
        un lien rendu par l'atelier.

   L'API DU MODULE EST DOUBLÉE PAR UN PROXY PERMISSIF : ce fichier juge le RAIL
   (il monte le bon panneau pour la bonne clé), pas le contenu de chacun des
   treize panneaux — chacun a, ou aura, son propre test. Le proxy rend une
   promesse résolue pour n'importe quel appel, donc aucun panneau ne tombe sur
   une méthode absente : un rouge ici désigne le rail, jamais une doublure
   oubliée.
   ========================================================================== */

vi.mock('../../../api/calepinageApi', () => {
  const reponse = () => Promise.resolve({ data: {} })
  const doublure = () => new Proxy(function appel() { return reponse() }, {
    // `then` DOIT rester absent : un proxy « thenable » serait attendu comme
    // une promesse par `await` et bloquerait le test.
    get: (_cible, prop) => (typeof prop === 'symbol' || prop === 'then'
      ? undefined
      : doublure()),
    apply: () => reponse(),
  })
  return { default: doublure() }
})
vi.mock('../../../api/ventesApi', () => ({ default: { reviserDevis: vi.fn() } }))

import AtelierPanneaux from '../AtelierPanneaux'
import config from '../module.config.jsx'
import Rail from './Rail'
import { ONGLETS, PARAM_ONGLET, ongletParCle, ongletsTries, resoudreOnglet } from './onglets'

const ID = '7'

const rendreRail = (recherche = '') => render(
  <MemoryRouter initialEntries={[`/calepinage/${ID}${recherche}`]}>
    <Routes>
      <Route path="/calepinage/:id" element={<Rail />} />
    </Routes>
  </MemoryRouter>,
)

/* Le panneau ouvert, une fois le module paresseux chargé ET son premier rendu
   utile passé. Les deux attentes sont RÉELLES : le composant arrive par
   `import()` (un tick), puis la plupart des panneaux traversent un état de
   chargement muet (une roue sans texte) avant d'écrire quoi que ce soit — d'où
   un délai large, et une attente sur le CONTENU plutôt que sur un simple
   montage. Un écran blanc durable fait donc rougir ce helper. */
const DELAI_PANNEAU = 15_000

async function panneauOuvert() {
  const panneau = await screen.findByTestId('cal-onglet-panneau', {}, { timeout: DELAI_PANNEAU })
  await waitFor(() => {
    const texte = panneau.textContent.trim()
    expect(texte, 'le panneau est resté sur son écran d’attente')
      .not.toMatch(/Ouverture de l’onglet|Ouverture de l'onglet/)
    expect(texte.length, 'le panneau n’a rien affiché — écran blanc').toBeGreaterThan(0)
  }, { timeout: DELAI_PANNEAU })
  return panneau
}

beforeEach(() => vi.clearAllMocks())
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('CALX1 — le registre `atelier/onglets.js`', () => {
  it('chaque entrée porte la forme attendue, avec une clé et un ordre uniques', () => {
    expect(ONGLETS.length, 'registre vide').toBeGreaterThan(0)
    const cles = []
    const ordres = []
    for (const onglet of ONGLETS) {
      expect(typeof onglet.cle, `clé manquante : ${JSON.stringify(onglet)}`).toBe('string')
      expect(onglet.cle.length).toBeGreaterThan(0)
      expect(typeof onglet.libelle, `libellé manquant : ${onglet.cle}`).toBe('string')
      expect(onglet.libelle.trim().length, `libellé vide : ${onglet.cle}`).toBeGreaterThan(0)
      expect(typeof onglet.groupe, `groupe manquant : ${onglet.cle}`).toBe('string')
      expect(Number.isFinite(onglet.ordre), `ordre non numérique : ${onglet.cle}`).toBe(true)
      expect(onglet.composant, `composant manquant : ${onglet.cle}`).toBeTruthy()
      cles.push(onglet.cle)
      ordres.push(onglet.ordre)
    }
    expect(new Set(cles).size, `clés en double : ${cles.join(', ')}`).toBe(cles.length)
    expect(new Set(ordres).size, `ordres en double : ${ordres.join(', ')}`).toBe(ordres.length)
  })

  it('`?onglet=` absent n’ouvre rien, une clé inconnue retombe sur le PREMIER onglet', () => {
    expect(resoudreOnglet(null)).toBeNull()
    expect(resoudreOnglet('')).toBeNull()
    expect(resoudreOnglet('cle-qui-n-existe-pas')).toBe(ongletsTries()[0])
    const premier = ongletsTries()[0]
    expect(resoudreOnglet(premier.cle)).toBe(premier)
  })

  it('la clé d’un onglet est EXACTEMENT le dernier segment de sa route profonde, quand il en hérite une', () => {
    // CALX19 — `module.config.jsx` le dit lui-même (commentaire au-dessus de
    // `/calepinage/:id`) : « aucune [route] n’est à ajouter ici pour un
    // onglet neuf — un panneau de plus, c’est une ligne de plus dans
    // `atelier/onglets.js`, rien d’autre. » Les TREIZE onglets de CALX1
    // héritaient d’un lien profond PRÉEXISTANT (le constat même du lot 1 :
    // des routes servies sans consommateur) ; un onglet POSÉ APRÈS eux n’en a
    // pas besoin et n’en crée pas. Liste EXPLICITE (jamais une exception
    // devinée) : un onglet qui s’y ajoute le fait avec son commentaire
    // `// CALX<id>`, jamais en silence.
    const SANS_ROUTE_PROFONDE = new Set([
      'documents', // CALX19 — panneau tab-only, aucun lien profond dédié.
    ])
    const chemins = new Set(config.routes.map((r) => r.path))
    for (const onglet of ONGLETS) {
      if (SANS_ROUTE_PROFONDE.has(onglet.cle)) continue
      expect(
        chemins.has(`/calepinage/:id/${onglet.cle}`),
        `l’onglet « ${onglet.cle} » n’a pas de route profonde /calepinage/:id/${onglet.cle}`,
      ).toBe(true)
    }
  })
})

describe('CALX1 — le rail monte le panneau de l’onglet demandé', () => {
  it('sans `?onglet=`, le rail est là, tous les onglets aussi, aucun panneau ouvert', () => {
    rendreRail()

    expect(screen.getByTestId('cal-rail-onglets')).toBeTruthy()
    for (const onglet of ONGLETS) {
      expect(
        screen.getByTestId(`cal-onglet-${onglet.cle}`),
        `onglet absent du rail : ${onglet.cle}`,
      ).toHaveTextContent(onglet.libelle)
    }
    expect(screen.queryByTestId('cal-onglet-panneau')).toBeNull()
  })

  /* ITÉRATION sur le registre : chaque entrée, sans exception, rend SON
     composant. Deux garde-fous plutôt qu'un texte attendu par onglet (qui
     figerait le contenu de treize écrans dans un test du rail) :
       - le panneau n'est NI vide NI l'écran d'attente ;
       - il ne rend pas le bandeau d'échec (un panneau qui plante est un rouge,
         pas un « une erreur est survenue » qui passerait inaperçu). */
  for (const onglet of ONGLETS) {
    it(`onglet « ${onglet.libelle} » (?onglet=${onglet.cle}) : son composant est monté`, async () => {
      rendreRail(`?${PARAM_ONGLET}=${onglet.cle}`)

      await panneauOuvert()
      expect(screen.queryByTestId('cal-onglet-erreur'),
        `le panneau « ${onglet.cle} » a échoué au rendu`).toBeNull()
      expect(screen.getByTestId(`cal-onglet-${onglet.cle}`))
        .toHaveAttribute('aria-selected', 'true')
    }, 30_000)
  }

  it('une clé inconnue ouvre le PREMIER onglet — jamais un écran blanc', async () => {
    const premier = ongletsTries()[0]
    rendreRail(`?${PARAM_ONGLET}=onglet-supprime-en-2019`)

    await panneauOuvert()
    expect(screen.queryByTestId('cal-onglet-erreur')).toBeNull()
    expect(screen.getByTestId(`cal-onglet-${premier.cle}`))
      .toHaveAttribute('aria-selected', 'true')
  }, 30_000)

  it('cliquer un onglet écrit `?onglet=` dans l’URL — le lien reste partageable', async () => {
    const utilisateur = userEvent.setup()
    const cible = ongletParCle('production')
    expect(cible, 'l’onglet « production » a disparu du registre').toBeTruthy()

    render(
      <MemoryRouter initialEntries={[`/calepinage/${ID}`]}>
        <Routes>
          <Route
            path="/calepinage/:id"
            element={(
              <>
                <Rail />
                <TemoinUrl />
              </>
            )}
          />
        </Routes>
      </MemoryRouter>,
    )

    await utilisateur.click(screen.getByTestId(`cal-onglet-${cible.cle}`))

    await waitFor(() => expect(screen.getByTestId('temoin-url'))
      .toHaveTextContent(`onglet=${cible.cle}`))
    expect(await panneauOuvert()).toBeTruthy()
  })
})

describe('CALX1 — aucune route du module ne reste orpheline', () => {
  /* On ITÈRE sur `config.routes`. Une route est atteignable en deux clics
     quand elle est : (a) un item de nav du module ; (b) l'atelier lui-même ;
     (c) un onglet du rail — `/calepinage/:id/<cle>` avec `<cle>` au registre ;
     (d) un lien RÉELLEMENT rendu par l'atelier (les hrefs sont relevés sur le
     rendu, pas recopiés dans une liste qui pourrait mentir). */
  it('chaque route déclarée est atteignable depuis l’atelier', async () => {
    const { container } = render(
      <MemoryRouter initialEntries={[`/calepinage/${ID}`]}>
        <Routes>
          <Route
            path="/calepinage/:id"
            element={<AtelierPanneaux calepinageId={ID} contexte={{ cible: null, calepinage: null }} />}
          />
        </Routes>
      </MemoryRouter>,
    )
    await waitFor(() => expect(screen.getByTestId('cal-atelier-panneaux')).toBeTruthy())

    const liensRendus = new Set(
      [...container.querySelectorAll('a[href]')]
        .map((a) => a.getAttribute('href').split('?')[0])
        // Le calepinage rendu porte l'identifiant `ID` : on le re-généralise
        // pour comparer au gabarit `/calepinage/:id/...` du registre de routes.
        .map((href) => href.replace(`/calepinage/${ID}`, '/calepinage/:id')),
    )
    const navItems = new Set(config.nav.items.map((i) => i.to))

    const orphelines = []
    for (const route of config.routes) {
      const segment = route.path.startsWith('/calepinage/:id/')
        ? route.path.slice('/calepinage/:id/'.length)
        : null
      const atteignable = navItems.has(route.path)
        || route.path === '/calepinage/:id'
        || (segment !== null && ongletParCle(segment) !== null)
        || liensRendus.has(route.path)
      if (!atteignable) orphelines.push(route.path)
    }

    expect(
      orphelines,
      `route(s) servie(s) mais introuvable(s) depuis l’atelier : ${orphelines.join(', ')} — `
      + 'inscrivez le panneau au registre `atelier/onglets.js`, ou posez un lien.',
    ).toEqual([])
  })
})

/** Témoin minimal : il rend la recherche de l'URL du ROUTEUR (MemoryRouter ne
    touche jamais `window.location`), pour l'assertion sur `?onglet=`. */
function TemoinUrl() {
  return <span data-testid="temoin-url">{useLocation().search}</span>
}
