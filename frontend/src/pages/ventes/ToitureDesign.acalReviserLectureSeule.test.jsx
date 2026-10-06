import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { exempleContrat } from '../../test/fixtures/contractSamples'

/* ACAL93 (C-ACAL-115) — le bandeau « Lecture seule » de l'atelier OFFRE
   « Réviser (v2) » quand le serveur dit `revision_possible` (design-context du
   calepinage, ACAL36). UNE seule fonction de révision : `reviserEtOuvrir`
   (features/ventes/reviserDevis.js) — jamais masquée par rôle, jamais refusée.
   La charge vient de l'exemple COMMITTÉ `exemple_accepte` (PACT13). */

vi.mock('../../hooks/useHasPermission', () => ({ useHasPermission: () => false }))
const reviserMock = vi.hoisted(() => vi.fn())
vi.mock('../../features/ventes/reviserDevis', () => ({
  reviserEtOuvrir: (...a) => reviserMock(...a),
}))

import '../../test/toitureDesignHarnessCalepinage'
import { navigateMock } from '../../test/toitureDesignHarnessNavigation'
import { initRoofToolPro8, rendreCalepinage, reinitialiserBoot }
  from '../../test/toitureDesignHarness'
import calepinageApi from '../../api/calepinageApi'

const CTX = exempleContrat('calepinage', 'calepinage_design_context')
const CTX_ACCEPTE = exempleContrat('calepinage', 'calepinage_design_context',
  'exemple_accepte')

beforeEach(() => {
  vi.clearAllMocks()
  reinitialiserBoot()
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('ToitureDesign — Réviser depuis la lecture seule (ACAL93)', () => {
  it('calepinage lié à un accepté : Réviser visible et appelle reviserEtOuvrir', async () => {
    expect(CTX_ACCEPTE.revision_possible).toBe(true)
    expect(CTX_ACCEPTE.modifiable).toBe(false)
    calepinageApi.calepinages.designContext.mockResolvedValue({
      data: { ...CTX_ACCEPTE, carte: CTX.carte },
    })
    reviserMock.mockImplementation(async ({ onApres, navigate }) => {
      const v2 = { id: 913, reference: 'DEV-202610-0001-V2' }
      onApres?.(v2)
      navigate(`/ventes/devis/nouveau?edit=${v2.id}`)
      return v2
    })

    rendreCalepinage(CTX_ACCEPTE.calepinage.id)
    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(await screen.findByTestId('pv20-lecture-seule'))
      .toHaveTextContent(CTX_ACCEPTE.raison_lecture_seule)

    await userEvent.click(await screen.findByTestId('acal-reviser-lecture-seule'))

    await waitFor(() => expect(reviserMock).toHaveBeenCalledTimes(1))
    const [{ devis }] = reviserMock.mock.calls[0]
    expect(devis.id).toBe(CTX_ACCEPTE.calepinage.devis_lie.id)
    // La V2 s'ouvre sur sa CONCEPTION.
    expect(navigateMock).toHaveBeenCalledWith('/ventes/devis/913/design')
  })

  it('révision impossible : aucun bouton Réviser dans le bandeau', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue({
      data: { ...CTX_ACCEPTE, carte: CTX.carte, revision_possible: false },
    })
    rendreCalepinage(CTX_ACCEPTE.calepinage.id)
    await screen.findByTestId('pv20-lecture-seule')
    expect(screen.queryByTestId('acal-reviser-lecture-seule')).toBeNull()
  })
})
