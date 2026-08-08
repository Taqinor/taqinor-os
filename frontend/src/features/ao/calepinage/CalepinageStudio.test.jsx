import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import resultatReel from './resultatReel.fixture'

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

import CalepinageStudio from './CalepinageStudio'

const CALCULER = '/ao/calepinage/calculer/'

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

  it("nomme l'absence des tiroirs au lieu de laisser une colonne vide", async () => {
    const { container } = render(<CalepinageStudio toitureId={7} />)
    await waitFor(() => expect(container.querySelector('[data-tiroirs="absents"]')).toBeInTheDocument())
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

  it('une suggestion du moteur s’applique par la VOIE DES PARAMÈTRES et rejoint l’historique', async () => {
    axiosMock.post.mockResolvedValue({
      status: 200,
      data: {
        ...resultatReel,
        suggestions: [{
          code: 'AO-REC-1',
          titre: 'Réduire l’allée à 0,55 m',
          gain_modules: 2,
          confiance: 'HAUTE',
          patch_entree: { allee_m: 0.55 },
        }],
      },
    })
    render(<CalepinageStudio toitureId={7} />)
    await screen.findByText('Réduire l’allée à 0,55 m')

    await userEvent.click(screen.getByRole('button', { name: 'Appliquer' }))

    await waitFor(
      () => expect(axiosMock.post).toHaveBeenCalledWith(
        CALCULER, { toiture: 7, params: { allee_m: 0.55 } },
      ),
      { timeout: 5000 },
    )
    await waitFor(() => expect(
      document.querySelector('[data-suggestion-appliquee]'),
    ).not.toBeNull())
  })
})
