import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import userEvent from '@testing-library/user-event'
import { exempleContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   CAL37/CAL242 — l'emplacement des panneaux de l'atelier en mode calepinage.

   Ce que ce fichier prouve :
   1. le panneau affiche la CIBLE servie par le serveur, et « non renseignée »
      quand elle vaut `null` — jamais une puissance inventée ;
   2. le bouton « Reprendre le contour de l'affaire » (CAL242, sens CAL240) est
      RÉELLEMENT MONTÉ ici : écrit et testé, il n'était accroché à aucun écran,
      c'est-à-dire l'oubli du 03/08/2026 (61 écrans livrés, inatteignables) ;
   3. une conception en LECTURE SEULE ne propose aucune écriture.
   ========================================================================== */

vi.mock('../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      get: vi.fn(),
      genererDevis: vi.fn(),
      syncDevis: vi.fn(),
      importerContourAo: vi.fn(),
    },
  },
}))
vi.mock('../../api/aoApi', () => ({
  default: { toitures: { reprendreContour3d: vi.fn() } },
}))
vi.mock('../../api/ventesApi', () => ({ default: { reviserDevis: vi.fn() } }))

import calepinageApi from '../../api/calepinageApi'
import AtelierPanneaux from './AtelierPanneaux'

const CTX = exempleContrat('calepinage', 'calepinage_design_context')
const CTX_VIDE = exempleContrat('calepinage', 'calepinage_design_context',
  'exemple_vide')
const DETAIL = exempleContrat('calepinage', 'calepinage_detail')

const rendre = (props = {}) => render(
  <MemoryRouter>
    <AtelierPanneaux calepinageId={CTX.calepinage.id} contexte={CTX} {...props} />
  </MemoryRouter>,
)

beforeEach(() => {
  vi.clearAllMocks()
  calepinageApi.calepinages.get.mockResolvedValue({ data: DETAIL })
  calepinageApi.calepinages.importerContourAo.mockResolvedValue({ data: {} })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('AtelierPanneaux (CAL37)', () => {
  it('affiche la cible SERVIE et le lien contextuel vers le comparatif', async () => {
    rendre()

    expect(screen.getByTestId('cal-cible-panneaux'))
      .toHaveTextContent(String(CTX.cible.panneaux))
    expect(screen.getByTestId('cal-lien-variantes'))
      .toHaveAttribute('href', `/calepinage/${CTX.calepinage.id}/variantes`)
  })

  it('cible nulle : « non renseignée », et l’écran le DIT', async () => {
    rendre({ contexte: CTX_VIDE, calepinageId: CTX_VIDE.calepinage.id })

    expect(screen.getByTestId('cal-cible-panneaux'))
      .toHaveTextContent('non renseignée')
    expect(screen.getByRole('status'))
      .toHaveTextContent('Aucune cible de puissance connue')
  })

  it('CAL242 — « Reprendre le contour de l’affaire » est MONTÉ et appelle CAL240', async () => {
    const recharger = vi.fn()
    rendre({ onRecharger: recharger })

    const bouton = await screen.findByRole('button',
      { name: /Reprendre le contour de l’affaire/ })
    await userEvent.click(bouton)

    // Aucune source AO n'est INVENTÉE : l'atelier ne connaît ni l'affaire ni la
    // toiture, donc le corps est vide et le serveur résout depuis le calepinage.
    await waitFor(() => expect(calepinageApi.calepinages.importerContourAo)
      .toHaveBeenCalledWith(CTX.calepinage.id, {}))
    await waitFor(() => expect(recharger).toHaveBeenCalled())
  })

  it('le refus SERVEUR de l’import s’affiche sous le bouton, mot pour mot', async () => {
    calepinageApi.calepinages.importerContourAo.mockRejectedValue({
      response: {
        status: 409,
        data: { detail: 'Cette affaire est déposée : son contour ne bouge plus.' },
      },
    })

    rendre()
    await userEvent.click(await screen.findByRole('button',
      { name: /Reprendre le contour de l’affaire/ }))

    expect(await screen.findByTestId('cal-bouton-contour-affaire-refus'))
      .toHaveTextContent('Cette affaire est déposée : son contour ne bouge plus.')
  })

  it('lecture seule : aucune écriture proposée (ni devis, ni import de contour)', async () => {
    rendre({ lectureSeule: true })

    await waitFor(() => expect(screen.getByTestId('cal-atelier-panneaux')).toBeTruthy())
    expect(screen.queryByTestId('cal-bouton-devis')).toBeNull()
    expect(screen.queryByTestId('cal-bouton-contour-affaire')).toBeNull()
    // Le panneau LUI-MÊME reste : consulter une conception figée est le but.
    expect(screen.getByTestId('cal-lien-variantes')).toBeTruthy()
  })
})
