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

vi.mock('../../../api/calepinageApi', async () => (await import('../../../test/fixtures/proxyPermissif')).moduleApiPermissif({
  calepinages: new Proxy({}, { get: (_c, prop) => (prop === 'parcours' ? (...a) => mocks.parcours(...a) : () => Promise.resolve({ data: {} })) }),
}))
vi.mock('../../../api/ventesApi', () => ({ default: { reviserDevis: vi.fn() } }))

/* CALX349 — l'onglet « Approbation » lit `useHasPermission`, qui va chercher
   le store redux : aucun rendu de ce fichier n'en monte un (même double que
   `AtelierPanneaux.test.jsx`). Sans lui, le panneau lève et le rail affiche
   son bandeau d'échec au lieu du contenu. */
const mocks = vi.hoisted(() => ({ hasPermission: vi.fn(() => false), parcours: vi.fn() }))
vi.mock('../../../hooks/useHasPermission', () => ({
  useHasPermission: (code) => mocks.hasPermission(code),
}))

import AtelierPanneaux from '../AtelierPanneaux'
import config from '../module.config.jsx'
import Rail from './Rail'
import { reponseContrat } from '../../../test/fixtures/contractSamples'
import { ETAPES, ESSENTIELS, ecranGuideDeOnglet } from './parcoursGuide'
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

  /* CALX18/CALX25 — un onglet NEUF n'a pas forcément de route profonde
     héritée : le rail est désormais le chemin normal pour l'ouvrir, et
     `module.config.jsx` n'est plus rouvert pour chaque panneau (D-CALX 13).
     L'ancien test symétrique (chaque onglet ⇔ une route de même clé) tenait
     par coïncidence pour les treize onglets fondateurs, mais AUCUNE des deux
     directions n'est une vraie invariante du module : `variantes` a une route
     profonde sans être un onglet du rail (c'est un écran à part), et un
     onglet neuf peut n'avoir aucune route héritée. La protection qui reste
     réellement utile — une route déjà servie ne devient jamais introuvable —
     est celle du test « aucune route du module ne reste orpheline » plus bas,
     qui accepte plusieurs chemins d'accès (nav, onglet, lien rendu). */
})

describe('CALX1 — le rail monte le panneau de l’onglet demandé', () => {
  it('sans `?onglet=`, le rail guidé montre 5 étapes et les seuls essentiels de l’étape active', () => {
    rendreRail()

    expect(screen.getByTestId('cal-rail-onglets')).toBeTruthy()
    for (const cle of ['toit', 'panneaux', 'electrique', 'resultats', 'documents']) {
      expect(screen.getByTestId(`cal-etape-${cle}`), `étape absente : ${cle}`).toBeTruthy()
    }
    // ACAL393 — étape active par défaut = toit : ses seuls essentiels.
    expect(screen.getByTestId('cal-etape-toit')).toHaveAttribute('aria-current', 'step')
    expect(screen.getAllByRole('tab').map((t) => t.getAttribute('data-testid')))
      .toEqual(['cal-onglet-pente', 'cal-onglet-terrain', 'cal-onglet-ombriere'])
    expect(screen.queryByTestId('cal-onglet-panneau')).toBeNull()
  })

  it('chaque clé de ONGLETS est dans la table du parcours, une seule fois', () => {
    const dans = ETAPES.flatMap((e) => e.onglets)
    expect([...dans].sort()).toEqual(ONGLETS.map((o) => o.cle).sort())
    for (const cle of ESSENTIELS) expect(dans, `essentiel inconnu : ${cle}`).toContain(cle)
    expect(ESSENTIELS).toHaveLength(13)
  })

  it('la pastille d’état vient du parcours (contrat) et l’étape active est la première non faite', async () => {
    mocks.parcours.mockResolvedValueOnce(reponseContrat('calepinage', 'calepinage_parcours_guide'))
    rendreRail()
    // contrat : toit fait, panneaux en_cours => étape active « panneaux ».
    await waitFor(() => expect(screen.getByTestId('cal-etape-panneaux'))
      .toHaveAttribute('aria-current', 'step'))
    expect(screen.getByTestId('cal-etape-toit')).toHaveAttribute('data-etat', 'fait')
    expect(screen.getByTestId('cal-etape-resultats-etat')).toHaveTextContent('bloqué')
    expect(screen.getByTestId('cal-onglet-fiches')).toBeTruthy()
  })

  it('un `?onglet=` expert l’ouvre quand même, dans son étape', async () => {
    rendreRail(`?${PARAM_ONGLET}=releve`)
    expect(screen.getByTestId('cal-etape-toit')).toHaveAttribute('aria-current', 'step')
    expect(screen.getByTestId('cal-onglet-releve')).toHaveAttribute('aria-selected', 'true')
    await panneauOuvert()
  }, 30_000)

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
      // ACAL395 : en guidé, les 7 onglets électriques sont des sections d'UNE
      // page portée par l'onglet `ouverture` ; la section demandée est dépliée.
      const ecran = ecranGuideDeOnglet(onglet.cle)
      expect(screen.getByTestId(`cal-onglet-${ecran ? ecran.ouverture : onglet.cle}`))
        .toHaveAttribute('aria-selected', 'true')
      if (ecran?.ouverture === 'verdict-electrique') {
        expect(screen.getByTestId(`cal-electrique-section-${onglet.cle}`))
          .toHaveAttribute('data-state', 'open')
      }
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

    // production est le premier essentiel de l'étape Résultats.
    await utilisateur.click(screen.getByTestId('cal-etape-resultats'))

    await waitFor(() => expect(screen.getByTestId('temoin-url'))
      .toHaveTextContent(`onglet=${cible.cle}`))
    expect(await panneauOuvert()).toBeTruthy()
  })
})

describe('ACAL394 — l’interrupteur « Mode expert »', () => {
  beforeEach(() => { try { window.localStorage.clear() } catch { /* ignoré */ } })

  it('guidé par défaut ; cocher montre les 36 onglets rangés sous leur étape, et survit à un rechargement', async () => {
    const utilisateur = userEvent.setup()
    const premier = rendreRail()
    expect(screen.getAllByRole('tab')).toHaveLength(3)
    await utilisateur.click(screen.getByTestId('cal-mode-expert'))
    expect(screen.getAllByRole('tab')).toHaveLength(ETAPES[0].onglets.length)
    let total = 0
    for (const etape of ETAPES) {
      await utilisateur.click(screen.getByTestId(`cal-etape-${etape.cle}`))
      total += screen.getAllByRole('tab').length
    }
    expect(total).toBe(ONGLETS.length)
    expect(ONGLETS).toHaveLength(36)
    premier.unmount()
    // rechargement : la mémoire du navigateur garde l’expert.
    rendreRail()
    expect(screen.getByTestId('cal-mode-expert')).toBeChecked()
    expect(screen.getAllByRole('tab')).toHaveLength(ETAPES[0].onglets.length)
  }, 30_000)

  it('`?mode=expert` force le mode expert', () => {
    rendreRail('?mode=expert')
    expect(screen.getByTestId('cal-mode-expert')).toBeChecked()
    expect(screen.getAllByRole('tab')).toHaveLength(ETAPES[0].onglets.length)
  })
})

describe('ACAL395 — l’étape Électrique en UNE page', () => {
  const SECTIONS = ['equipements-electriques', 'cheminement-cables', 'raccordement', 'verdict-electrique',
    'materiel-electrique', 'saisies-electriques', 'decisions-electriques']
  const parcoursElectrique = (etat) => {
    const base = reponseContrat('calepinage', 'calepinage_parcours_guide')
    const ligne = (code) => ({ code, message: 'm', etape: 'electrique', cible: { onglet: 'verdict-electrique', champ: '' }, gravite: 'a_regler', nombre: 1 })
    return {
      ...base,
      data: {
        ...base.data,
        etapes: base.data.etapes.map((e) => (e.cle === 'electrique' ? { ...e, etat } : e)),
        manque: [...base.data.manque, ligne('a'), ligne('b')],
      },
    }
  }
  beforeEach(() => { try { window.localStorage.clear() } catch { /* ignoré */ } })

  it('guidé : UNE page, « 2 points à régler » et 7 sections ; le Verdict est ouvert quand l’étape est bloquée', async () => {
    mocks.parcours.mockResolvedValue(parcoursElectrique('bloque'))
    const utilisateur = userEvent.setup()
    rendreRail()
    await utilisateur.click(screen.getByTestId('cal-etape-electrique'))
    expect(await screen.findByTestId('cal-etape-electrique-ecran', {}, { timeout: DELAI_PANNEAU })).toBeTruthy()
    await waitFor(() => expect(screen.getByTestId('cal-electrique-synthese')).toHaveTextContent('2 points à régler'))
    for (const cle of SECTIONS) expect(screen.getByTestId(`cal-electrique-section-${cle}`), cle).toBeTruthy()
    expect(screen.getByTestId('cal-electrique-section-verdict-electrique')).toHaveAttribute('data-state', 'open')
    expect(screen.getByTestId('cal-electrique-section-raccordement')).toHaveAttribute('data-state', 'closed')
    // une seule page : pas un onglet par panneau.
    expect(screen.queryByTestId('cal-onglet-raccordement')).toBeNull()
  }, 30_000)

  it('« Conforme » quand l’étape est faite', async () => {
    mocks.parcours.mockResolvedValue(parcoursElectrique('fait'))
    rendreRail(`?${PARAM_ONGLET}=verdict-electrique`)
    await waitFor(() => expect(screen.getByTestId('cal-electrique-synthese')).toHaveTextContent('Conforme'))
  }, 30_000)

  it('un ancien lien `?onglet=verdict-electrique` déplie le Verdict, `?onglet=raccordement` le Raccordement', async () => {
    const premier = rendreRail(`?${PARAM_ONGLET}=verdict-electrique`)
    expect(await screen.findByTestId('cal-electrique-section-verdict-electrique', {}, { timeout: DELAI_PANNEAU }))
      .toHaveAttribute('data-state', 'open')
    premier.unmount()
    rendreRail(`?${PARAM_ONGLET}=raccordement`)
    expect(await screen.findByTestId('cal-electrique-section-raccordement', {}, { timeout: DELAI_PANNEAU }))
      .toHaveAttribute('data-state', 'open')
  }, 30_000)

  it('en mode expert, les 7 onglets restent', () => {
    rendreRail(`?${PARAM_ONGLET}=raccordement&mode=expert`)
    for (const cle of SECTIONS) expect(screen.getByTestId(`cal-onglet-${cle}`), cle).toBeTruthy()
    expect(screen.queryByTestId('cal-etape-electrique-ecran')).toBeNull()
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

/* ============================================================================
   CALX222 — `builderApi` DESCEND JUSQU'AU PANNEAU.
   ----------------------------------------------------------------------------
   Le panneau « Équipements électriques » sait armer une pose dans la scène 3D
   depuis CALX222, mais personne ne lui passait l'API du constructeur : le
   bouton répondait « outil 3D non prêt » même dans l'atelier. Ces deux essais
   figent LE FIL (écran → `AtelierPanneaux` → `Rail` → panneau) et l'aveu
   honnête quand le fil n'existe pas — jamais une pose armée dans le vide.
   ========================================================================== */
describe('CALX222 — l’API du constructeur atteint les panneaux d’onglet', () => {
  const ONGLET = `?${PARAM_ONGLET}=equipements-electriques`

  it('le rail relaie `builderApi` : « Armer la pose » atteint la scène', async () => {
    const armerPose = vi.fn()
    const utilisateur = userEvent.setup()
    render(
      <MemoryRouter initialEntries={[`/calepinage/${ID}${ONGLET}`]}>
        <Routes>
          <Route
            path="/calepinage/:id"
            element={<Rail builderApi={{ electrique: { armerPose } }} />}
          />
        </Routes>
      </MemoryRouter>,
    )

    await panneauOuvert()
    await utilisateur.click(await screen.findByTestId('calx222-armer'))

    expect(armerPose).toHaveBeenCalledTimes(1)
    expect(screen.queryByTestId('calx222-armement-motif')).toBeNull()
  }, 30_000)

  it('sans `builderApi`, le panneau DIT que l’outil 3D n’est pas prêt', async () => {
    const utilisateur = userEvent.setup()
    rendreRail(ONGLET)

    await panneauOuvert()
    await utilisateur.click(await screen.findByTestId('calx222-armer'))

    expect(await screen.findByTestId('calx222-armement-motif'))
      .toHaveTextContent('Outil 3D non prêt')
  }, 30_000)

  it('l’atelier passe SON `builderApi` au rail — le fil complet', async () => {
    const armerPose = vi.fn()
    const utilisateur = userEvent.setup()
    render(
      <MemoryRouter initialEntries={[`/calepinage/${ID}${ONGLET}`]}>
        <Routes>
          <Route
            path="/calepinage/:id"
            element={(
              <AtelierPanneaux
                calepinageId={ID}
                contexte={{ cible: null, calepinage: null }}
                builderApi={{ electrique: { armerPose } }}
              />
            )}
          />
        </Routes>
      </MemoryRouter>,
    )

    await panneauOuvert()
    await utilisateur.click(await screen.findByTestId('calx222-armer'))

    expect(armerPose).toHaveBeenCalledTimes(1)
  }, 30_000)
})

/* ACAL44 — le rail relaie `lectureSeule` à l'onglet ACTIF : le bouton
   d'écriture du panneau monté est désactivé. */
describe('ACAL44 — lecture seule relayée', () => {
  it('lectureSeule est relayée à l’onglet actif', async () => {
    render(
      <MemoryRouter initialEntries={[`/calepinage/${ID}?${PARAM_ONGLET}=postes-pertes`]}>
        <Routes>
          <Route path="/calepinage/:id" element={<Rail lectureSeule />} />
        </Routes>
      </MemoryRouter>,
    )
    const bouton = await screen.findByTestId('cal-pertes-enregistrer', {},
      { timeout: DELAI_PANNEAU })
    expect(bouton).toBeDisabled()
  }, DELAI_PANNEAU + 5_000)
})

/** Témoin minimal : il rend la recherche de l'URL du ROUTEUR (MemoryRouter ne
    touche jamais `window.location`), pour l'assertion sur `?onglet=`. */
function TemoinUrl() {
  return <span data-testid="temoin-url">{useLocation().search}</span>
}
