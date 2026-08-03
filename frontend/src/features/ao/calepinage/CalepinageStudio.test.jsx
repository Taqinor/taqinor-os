import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
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
