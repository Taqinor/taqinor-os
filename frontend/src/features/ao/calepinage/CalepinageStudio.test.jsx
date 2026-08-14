import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import resultatReel from './resultatReel.fixture'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

/* ============================================================================
   L'ATELIER, DE BOUT EN BOUT — sur les ROUTES RÉELLES (03/08/2026).
   ----------------------------------------------------------------------------
   Le client axios est mocké, pas `aoApi` : c'est le seul niveau où l'URL
   appelée est observable, et l'URL est exactement ce qui était faux.
   ========================================================================== */

const axiosMock = vi.hoisted(() => ({
  get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn(),
}))
vi.mock('../../../api/axios', () => ({ default: axiosMock }))

// PV51 — `sonner` (le vrai `toast`) ne rend RIEN sans `<Toaster/>` monté dans
// l'arbre ; ce test ne le monte pas (même patron que `ToituresPage.test.jsx`).
// Le SEUL point observable est donc l'appel, pas un texte affiché.
const toastMocks = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }))
vi.mock('../../../ui', async () => {
  const actual = await vi.importActual('../../../ui')
  return { ...actual, toast: { success: toastMocks.success, error: toastMocks.error } }
})

import CalepinageStudio from './CalepinageStudio'

const CALCULER = '/ao/calepinage/calculer/'
const LANCER = '/ao/calepinage/lancer/'
const KIT = 'AO-TABLE-PORTRAIT'
// Rangées SEED : la forme À PLAT de `resultatReel.rangees` (voir la fixture).
const SEED = [[0.8003, KIT], [6.9503, KIT]]

beforeEach(() => {
  vi.clearAllMocks()
  axiosMock.post.mockResolvedValue({ status: 200, data: { ...resultatReel, depuis_cache: false } })
})

describe('CalepinageStudio', () => {
  it('calcule sur /ao/calepinage/calculer/ et dessine les tables POSÉES', async () => {
    const { container } = render(<CalepinageStudio toitureId={7} />)

    await waitFor(() => expect(container.querySelector('[data-ao-canvas="calepinage"]')).toBeInTheDocument())
    expect(axiosMock.post).toHaveBeenCalledWith(CALCULER, { toiture: 7 })
    expect(container.querySelectorAll('[data-item="table"]')).toHaveLength(
      resultatReel.plans[0].tables.length,
    )
  })

  it('affiche les comptes du SERVEUR, sans marge recomposée', async () => {
    render(<CalepinageStudio toitureId={7} />)
    await waitFor(() => expect(screen.getByText('16')).toBeInTheDocument())      // total_modules
    expect(screen.getByText('10 kWc')).toBeInTheDocument()                        // kwc
    expect(screen.getByText('20 modules')).toBeInTheDocument()                    // engagement_modules
    expect(screen.getByText('optimum prouvé (16 modules)')).toBeInTheDocument()   // preuve.libelle
  })

  it("n'appelle JAMAIS /ao/calepinages/… (la ressource qui n'existe pas)", async () => {
    const { container } = render(<CalepinageStudio toitureId={7} />)
    await waitFor(() => expect(container.querySelector('[data-ao-canvas="calepinage"]')).toBeInTheDocument())
    const urls = [...axiosMock.post.mock.calls, ...axiosMock.get.mock.calls].map(([url]) => url)
    expect(urls.some((url) => url.includes('/ao/calepinages'))).toBe(false)
  })

  it("une erreur serveur s'affiche TELLE QUELLE — jamais un écran blanc", async () => {
    axiosMock.post.mockRejectedValue({
      response: { status: 404, data: { detail: 'Toiture introuvable dans cette société.' } },
    })
    render(<CalepinageStudio toitureId={7} />)
    await waitFor(() => expect(screen.getByText('Toiture introuvable dans cette société.')).toBeInTheDocument())
    expect(screen.getByText('Calepinage indisponible')).toBeInTheDocument()
  })

  it("un 400 NOMMÉ conserve le champ fautif du serveur", async () => {
    axiosMock.post.mockRejectedValue({
      response: {
        status: 400,
        data: { entree: ["Aucun kit de calepinage actif n'est disponible pour cette toiture : le calcul n'a rien à poser."] },
      },
    })
    render(<CalepinageStudio toitureId={7} />)
    await waitFor(() => expect(screen.getByText(/Aucun kit de calepinage actif/)).toBeInTheDocument())
  })

  it("PV51 — n'affiche plus le bandeau « tiroirs absents » (ils sont publiés)", async () => {
    const { container } = render(<CalepinageStudio toitureId={7} />)
    await waitFor(() => expect(container.querySelector('[data-ao-canvas="calepinage"]')).toBeInTheDocument())
    expect(container.querySelector('[data-tiroirs="absents"]')).toBeNull()
  })
})

/* ============================================================================
   PV51 — les cinq tiroirs + marges + suggestions S'ALLUMENT sur la charge
   utile RÉELLE publiée par `/ao/calepinage/calculer/` (PV49/PV50/PV44).
   ----------------------------------------------------------------------------
   La charge vient du CONTRAT COMMITTÉ (PACT10/PACT13,
   `apps/ao/contract_samples/calepinage_tiroirs.json` +
   `calepinage_marges.json`), jamais d'une forme inventée à la main — c'est
   exactement la garantie que ces fixtures existent pour donner.
   ========================================================================== */
describe('CalepinageStudio — PV51 tiroirs/marges alimentés (contrat réel)', () => {
  it('les CINQ tiroirs et les marges de robustesse s’allument sur `resultat.tiroirs`/`resultat.marges`', async () => {
    const tiroirs = exempleContrat('ao', 'calepinage_tiroirs')
    const marges = exempleContrat('ao', 'calepinage_marges')
    axiosMock.post.mockResolvedValue({
      status: 200,
      data: { ...resultatReel, tiroirs, marges },
    })
    const { container } = render(<CalepinageStudio toitureId={7} />)

    await waitFor(() => expect(container.querySelector('[data-ao-tiroir="kits"]')).toBeInTheDocument())
    expect(container.querySelector('[data-ao-tiroir="allees"]')).toBeInTheDocument()
    expect(container.querySelector('[data-ao-tiroir="rives"]')).toBeInTheDocument()
    expect(container.querySelector('[data-ao-tiroir="orientation"]')).toBeInTheDocument()
    expect(container.querySelector('[data-ao-tiroir="electrique"]')).toBeInTheDocument()

    // Les marges de robustesse (mode expert) viennent du MÊME résultat.
    await userEvent.click(screen.getByLabelText('Mode expert'))
    expect(document.querySelector('[data-marge-robustesse="Marge tronçon"]')).not.toBeNull()
  })
})

/* ============================================================================
   PACT168 — Mode expert et Suggestions, MONTÉS dans l'atelier.
   ----------------------------------------------------------------------------
   `ModeExpert` (qui révèle `RobustesseBadges`) et `SuggestionsPanel` étaient
   livrés et importés par personne : l'inspecteur s'arrêtait aux 5 tiroirs
   débutant. Ce que ces tests protègent :
     1. les deux panneaux sont RÉELLEMENT montés à côté des tiroirs ;
     2. le mode expert est replié par défaut et mémorisé côté navigateur ;
     3. un réglage expert repart au SERVEUR par la voie normale des paramètres
        — aucun chiffre n'est recalculé côté écran (AOF94) ;
     4. une suggestion « appliquée » passe par ce même chemin, et quitte la
        liste actionnable pour l'historique (jamais appliquée deux fois).
   ========================================================================== */
describe('CalepinageStudio — mode expert et suggestions (PACT168)', () => {
  // L'interrupteur du mode expert est mémorisé (`safeStorage`) : sans purge,
  // le test suivant hériterait de l'état laissé par le précédent.
  beforeEach(() => {
    try { window.localStorage.clear() } catch { /* stockage indisponible */ }
  })

  it('monte le mode expert à côté des cinq tiroirs, REPLIÉ par défaut', async () => {
    const { container } = render(<CalepinageStudio toitureId={7} />)

    await waitFor(() => expect(container.querySelector('[data-ao-tiroir="expert"]')).toBeInTheDocument())
    expect(screen.getByLabelText('Mode expert')).toBeInTheDocument()
    expect(screen.queryByLabelText('Pas de recherche (m)')).toBeNull()
  })

  it('activer le mode expert révèle les réglages fins ET les marges du moteur', async () => {
    axiosMock.post.mockResolvedValue({
      status: 200,
      data: { ...resultatReel, marges: { troncon_min_cm: 1.2, bande_min_cm: 8 } },
    })
    render(<CalepinageStudio toitureId={7} />)
    await waitFor(() => expect(screen.getByLabelText('Mode expert')).toBeInTheDocument())

    await userEvent.click(screen.getByLabelText('Mode expert'))

    expect(screen.getByLabelText('Pas de recherche (m)')).toBeInTheDocument()
    expect(document.querySelector('[data-marge-robustesse="Marge tronçon"]')).not.toBeNull()
    expect(document.querySelector('[data-marge-robustesse="Marge bande"]')).not.toBeNull()
  })

  it('un réglage expert repart au SERVEUR (jamais un recalcul côté écran)', async () => {
    render(<CalepinageStudio toitureId={7} />)
    await waitFor(() => expect(screen.getByLabelText('Mode expert')).toBeInTheDocument())
    await userEvent.click(screen.getByLabelText('Mode expert'))

    await userEvent.type(screen.getByLabelText('Pas de recherche (m)'), '3')

    await waitFor(
      () => expect(axiosMock.post).toHaveBeenCalledWith(
        CALCULER, { toiture: 7, params: { pas_recherche_m: 3 } },
      ),
      { timeout: 5000 },
    )
  })

  it('le panneau de suggestions est monté et DIT qu’il n’y en a aucune', async () => {
    const { container } = render(<CalepinageStudio toitureId={7} />)

    await waitFor(() => expect(container.querySelector('[data-suggestions-panel]')).toBeInTheDocument())
    expect(container.querySelector('[data-suggestions-panel]').dataset.suggestionsPanel).toBe('0')
    expect(screen.getByText('Aucune suggestion en attente')).toBeInTheDocument()
  })

  // PV51 — la forme RÉELLE du contrat (`calepinage_suggestions.json`,
  // `apps/ao/calepinage_io.action_de_patch`) est `action: {type, patch}`,
  // JAMAIS `patch_entree` (ce champ n'a jamais voyagé sur le fil : il vit
  // seulement côté moteur, avant traduction par `suggestion_vers_json`).
  it('une suggestion « parametres » s’applique par la VOIE DES PARAMÈTRES (action.patch) et rejoint l’historique', async () => {
    axiosMock.post.mockResolvedValue({
      status: 200,
      data: {
        ...resultatReel,
        suggestions: [{
          code: 'ALLEE_GRATUITE',
          titre: 'Réduire l’allée à 0,55 m',
          gain_modules: 2,
          confiance: 'HAUTE',
          action: { type: 'parametres', patch: { allee_min_m: 0.55 } },
        }],
      },
    })
    render(<CalepinageStudio toitureId={7} />)
    await screen.findByText('Réduire l’allée à 0,55 m')

    await userEvent.click(screen.getByRole('button', { name: 'Appliquer' }))

    await waitFor(
      () => expect(axiosMock.post).toHaveBeenCalledWith(
        CALCULER, { toiture: 7, params: { allee_min_m: 0.55 } },
      ),
      { timeout: 5000 },
    )
    await waitFor(() => expect(
      document.querySelector('[data-suggestion-appliquee]'),
    ).not.toBeNull())
  })

  // PV51 — une suggestion « obstacle » (`ARBITRER_A`) PATCH la ressource
  // `ObstacleAO` retrouvée par son `repere` parmi les obstacles de la toiture,
  // puis force un recalcul — jamais un paramètre du corps de `/calculer/`.
  it('une suggestion « obstacle » retrouve l’ObstacleAO par son repère, PATCH sa provenance, et recalcule', async () => {
    axiosMock.post.mockResolvedValue({
      status: 200,
      data: {
        ...resultatReel,
        suggestions: [{
          code: 'ARBITRER_A',
          titre: "Écarter l'obstacle A (nature non confirmée)",
          gain_modules: -4,
          action: { type: 'obstacle', obstacle: 'A', provenance: 'ECARTE' },
        }],
      },
    })
    axiosMock.get.mockResolvedValue({
      data: [{ id: 42, repere: 'A', toiture: 7 }, { id: 43, repere: 'B', toiture: 7 }],
    })
    axiosMock.patch.mockResolvedValue({ data: { id: 42, repere: 'A', provenance: 'ECARTE' } })

    render(<CalepinageStudio toitureId={7} />)
    await screen.findByText("Écarter l'obstacle A (nature non confirmée)")

    await userEvent.click(screen.getByRole('button', { name: 'Appliquer' }))

    await waitFor(() => expect(axiosMock.get).toHaveBeenCalledWith(
      '/ao/obstacles/', { params: { toiture: 7 } },
    ))
    await waitFor(() => expect(axiosMock.patch).toHaveBeenCalledWith(
      '/ao/obstacles/42/', { provenance: 'ECARTE' },
    ))
    // Recalcul déclenché APRÈS le PATCH — jamais un chiffre recalculé côté écran.
    await waitFor(() => expect(
      document.querySelector('[data-suggestion-appliquee]'),
    ).not.toBeNull(), { timeout: 5000 })
  })
})

/* ============================================================================
   PV51/PV67 — « Générer des variantes » : le studio retrouve la variante
   RETENUE de la toiture avant d'appeler l'action serveur.
   ========================================================================== */
describe('CalepinageStudio — PV51/PV67 « Générer des variantes »', () => {
  it('retrouve la variante RETENUE puis poste sur generer-variantes/', async () => {
    axiosMock.get.mockResolvedValue({ data: [{ id: 9, toiture: 7, est_retenue: true }] })
    render(<CalepinageStudio toitureId={7} />)
    await waitFor(() => expect(screen.getByRole('button', { name: /Générer des variantes/ })).toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: /Générer des variantes/ }))

    await waitFor(() => expect(axiosMock.get).toHaveBeenCalledWith(
      '/ao/variantes-calepinage/', { params: { toiture: 7, est_retenue: true } },
    ))
    await waitFor(() => expect(axiosMock.post).toHaveBeenCalledWith(
      '/ao/calepinage/variantes/9/generer-variantes/',
    ))
    await waitFor(() => expect(toastMocks.success).toHaveBeenCalled())
    expect(toastMocks.success.mock.calls.at(-1)[0]).toMatch(/Variantes d.orientation générées/)
  })

  it('sans variante retenue, le motif s’affiche SANS appeler generer-variantes/', async () => {
    axiosMock.get.mockResolvedValue({ data: [] })
    render(<CalepinageStudio toitureId={7} />)
    await waitFor(() => expect(screen.getByRole('button', { name: /Générer des variantes/ })).toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: /Générer des variantes/ }))

    await waitFor(() => expect(toastMocks.error).toHaveBeenCalled())
    expect(toastMocks.error.mock.calls.at(-1)[0]).toMatch(/aucune variante retenue/i)
    const appelsGenerer = axiosMock.post.mock.calls.filter(([url]) => url.includes('generer-variantes'))
    expect(appelsGenerer).toHaveLength(0)
  })
})

/* ============================================================================
   PV31/PV32 — mode « rangées imposées par l'utilisateur ».
   ----------------------------------------------------------------------------
   Bout en bout, sur les VRAIES routes : un geste sur le plan (glisser une
   bande / cliquer le fond / supprimer / annuler) doit produire un appel
   `POST /ao/calepinage/calculer/` dont `params.mode_pose` et
   `params.rangees_imposees` portent EXACTEMENT ce que le brouillon contient —
   jamais un chiffre recalculé côté écran. `getBoundingClientRect` est simulé
   sur le SVG (même patron que `PlanLayer.test.jsx`/`GanttChart.test.jsx`).
   ========================================================================== */

async function preparerAtelier() {
  const utils = render(<CalepinageStudio toitureId={7} />)
  await waitFor(() => expect(
    utils.container.querySelector('[data-ao-canvas="calepinage"]'),
  ).toBeInTheDocument())
  return utils
}

// Glisse la bande d'index `index` : pointerdown dessus (sélectionne + amorce
// le brouillon), pointermove sur le canvas (aperçu), pointerup (valide).
function glisserRangee(container, index, clientY) {
  const svg = container.querySelector('[data-ao-canvas]')
  vi.spyOn(svg, 'getBoundingClientRect').mockReturnValue({ top: 0, height: 100 })
  fireEvent.pointerDown(container.querySelector(`[data-rangee-index="${index}"]`))
  fireEvent.pointerMove(svg, { clientY })
  fireEvent.pointerUp(svg)
}

const dernierAppelCalculer = () => axiosMock.post.mock.calls
  .filter(([url]) => url === CALCULER)
  .at(-1)?.[1]

describe('CalepinageStudio — PV31 brouillon de rangées imposées', () => {
  it('glisser une rangée envoie mode_pose + rangees_imposees, la seconde rangée INTACTE', async () => {
    const { container } = await preparerAtelier()
    glisserRangee(container, 0, 40)

    await waitFor(() => {
      const corps = dernierAppelCalculer()
      expect(corps?.params?.mode_pose).toBe('rangees_imposees_utilisateur')
      expect(corps.params.rangees_imposees).toHaveLength(2)
      expect(corps.params.rangees_imposees[1]).toEqual([6.9503, KIT])
      expect(corps.params.rangees_imposees[0][1]).toBe(KIT)
    }, { timeout: 5000 })

    expect(screen.getByRole('button', { name: 'Revenir au calcul optimal' })).toBeInTheDocument()
  })

  it('un clic SANS déplacement sélectionne mais n’envoie rien', async () => {
    const { container } = await preparerAtelier()
    fireEvent.pointerDown(container.querySelector('[data-rangee-index="0"]'))
    fireEvent.pointerUp(container.querySelector('[data-ao-canvas]'))

    const supprimer = await screen.findByRole('button', { name: 'Supprimer la rangée sélectionnée' })
    expect(supprimer).toBeEnabled()
    // Sélection seule : aucun geste APPLIQUÉ, donc aucun recalcul déclenché.
    expect(dernierAppelCalculer()?.params?.mode_pose).toBeUndefined()
  })

  it('cliquer le fond ajoute une rangée (kit repris de la plus proche)', async () => {
    const { container } = await preparerAtelier()
    const svg = container.querySelector('[data-ao-canvas]')
    vi.spyOn(svg, 'getBoundingClientRect').mockReturnValue({ top: 0, height: 100 })
    fireEvent.pointerDown(svg, { clientY: 20 })

    await waitFor(() => {
      const corps = dernierAppelCalculer()
      expect(corps?.params?.mode_pose).toBe('rangees_imposees_utilisateur')
      expect(corps.params.rangees_imposees).toHaveLength(3)
      expect(corps.params.rangees_imposees.every(([, kit]) => kit === KIT)).toBe(true)
    }, { timeout: 5000 })
  })

  it('sélectionner puis supprimer une rangée l’enlève du brouillon', async () => {
    const { container } = await preparerAtelier()
    fireEvent.pointerDown(container.querySelector('[data-rangee-index="0"]'))
    fireEvent.pointerUp(container.querySelector('[data-ao-canvas]'))
    await userEvent.click(await screen.findByRole('button', { name: 'Supprimer la rangée sélectionnée' }))

    await waitFor(() => {
      expect(dernierAppelCalculer()?.params?.rangees_imposees).toEqual([[6.9503, KIT]])
    }, { timeout: 5000 })
  })

  it('Annuler revient EXACTEMENT au brouillon précédent', async () => {
    const { container } = await preparerAtelier()
    glisserRangee(container, 0, 40)
    await waitFor(() => expect(dernierAppelCalculer()?.params?.rangees_imposees).toHaveLength(2), { timeout: 5000 })

    await userEvent.click(screen.getByRole('button', { name: 'Annuler' }))

    await waitFor(() => {
      expect(dernierAppelCalculer()?.params?.rangees_imposees).toEqual(SEED)
    }, { timeout: 5000 })
  })

  it('un 400 du serveur GARDE le brouillon affiché — jamais un retour silencieux à l’optimum', async () => {
    const { container } = await preparerAtelier()
    axiosMock.post.mockImplementation((url) => (url === CALCULER
      ? Promise.reject({
        response: { status: 400, data: { entree: ["Rangée imposée n°1 : le kit « X » n'est pas autorisé."] } },
      })
      : Promise.resolve({ status: 200, data: { ...resultatReel, depuis_cache: false } })))

    glisserRangee(container, 0, 40)

    await waitFor(
      () => expect(screen.getByText(/n'est pas autorisé/)).toBeInTheDocument(),
      { timeout: 5000 },
    )
    expect(screen.getByRole('button', { name: 'Revenir au calcul optimal' })).toBeInTheDocument()
  })
})

describe('CalepinageStudio — PV32 écart, enregistrement et garde-fou de sortie', () => {
  it('« Revenir au calcul optimal » sur un brouillon divergent demande confirmation', async () => {
    const { container } = await preparerAtelier()
    glisserRangee(container, 0, 40)
    await screen.findByRole('button', { name: 'Revenir au calcul optimal' })
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)

    await userEvent.click(screen.getByRole('button', { name: 'Revenir au calcul optimal' }))
    expect(confirmSpy).toHaveBeenCalledTimes(1)
  })

  it('confirmation ANNULÉE : le brouillon (et ses rangées) restent affichés', async () => {
    const { container } = await preparerAtelier()
    glisserRangee(container, 0, 40)
    await screen.findByRole('button', { name: 'Revenir au calcul optimal' })
    vi.spyOn(window, 'confirm').mockReturnValue(false)

    await userEvent.click(screen.getByRole('button', { name: 'Revenir au calcul optimal' }))

    expect(screen.getByRole('button', { name: 'Revenir au calcul optimal' })).toBeInTheDocument()
    expect(container.querySelectorAll('[data-item="rangee-bande"]')).toHaveLength(2)
  })

  it('confirmation ACCEPTÉE : mode_pose/rangees_imposees disparaissent du prochain appel', async () => {
    const { container } = await preparerAtelier()
    glisserRangee(container, 0, 40)
    await screen.findByRole('button', { name: 'Revenir au calcul optimal' })
    vi.clearAllMocks()
    axiosMock.post.mockResolvedValue({ status: 200, data: { ...resultatReel, depuis_cache: false } })
    vi.spyOn(window, 'confirm').mockReturnValue(true)

    await userEvent.click(screen.getByRole('button', { name: 'Revenir au calcul optimal' }))

    await waitFor(
      () => expect(axiosMock.post).toHaveBeenCalledWith(CALCULER, { toiture: 7 }),
      { timeout: 5000 },
    )
    expect(screen.queryByRole('button', { name: 'Revenir au calcul optimal' })).toBeNull()
  })

  it('« Enregistrer comme variante » appelle lancer(persister, role ALTERNATIVE, nom auto)', async () => {
    const { container } = await preparerAtelier()
    glisserRangee(container, 0, 40)

    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer comme variante/ }))

    await waitFor(() => {
      const appel = axiosMock.post.mock.calls.find(([url]) => url === LANCER)
      expect(appel).toBeTruthy()
      const [, corps] = appel
      expect(corps.toiture).toBe(7)
      expect(corps.persister).toBe(true)
      expect(corps.role).toBe('ALTERNATIVE')
      expect(corps.nom).toMatch(/^Plan imposé du \d{2}\/\d{2}$/)
      expect(corps.params.mode_pose).toBe('rangees_imposees_utilisateur')
      expect(corps.params.rangees_imposees).toHaveLength(2)
    }, { timeout: 5000 })
  })

  it('l’écart à l’optimum d’un plan imposé s’affiche verbatim depuis le moteur', async () => {
    axiosMock.post.mockImplementation(() => Promise.resolve({
      status: 200,
      data: {
        ...resultatReel,
        depuis_cache: false,
        plans: [{ ...resultatReel.plans[0], ecart_a_l_optimum: 6 }],
        preuve: { ...resultatReel.preuve, methode: 'impose_utilisateur', methode_exacte: false, optimal: false },
      },
    }))
    const { container } = await preparerAtelier()
    glisserRangee(container, 0, 40)

    await waitFor(() => expect(screen.getByText('-6 modules vs optimum')).toBeInTheDocument(), { timeout: 5000 })
    expect(screen.getByText('Plan imposé — non optimal')).toBeInTheDocument()
  })
})
