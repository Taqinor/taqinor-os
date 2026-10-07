import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, cleanup, waitFor } from '@testing-library/react'
import { reponseContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   Lot 2 critique #27 (ACAL37) — un utilisateur qui n'a que le droit de VOIR :
   `POST depuis-modele/` répond 403 ⇒ le calepinage existant est lu sur la
   fiche devis (`GET ventes/devis/<id>/` → `calepinage.id`) et l'atelier
   s'ouvre en LECTURE SEULE ; sans calepinage, un message le dit. Aucune
   écriture.
   ========================================================================== */

vi.mock('../../hooks/useHasPermission', () => ({ useHasPermission: () => false }))

import {
  CTX_CALEPINAGE_DEVIS as CTX, DEVIS_ID_CALEPINAGE as DEVIS_ID,
} from '../../test/toitureDesignHarnessCalepinage'
import { initRoofToolPro8, rendreDevis, reinitialiserBootMinimal } from '../../test/toitureDesignHarness'
import ventesApi from '../../api/ventesApi'
import calepinageApi from '../../api/calepinageApi'

const INTERDIT = { response: { status: 403, data: { detail: 'Permission refusée.' } } }

beforeEach(() => {
  vi.clearAllMocks()
  reinitialiserBootMinimal()
  calepinageApi.calepinages.depuisModele.mockRejectedValue(INTERDIT)
  calepinageApi.calepinages.designContext.mockResolvedValue(
    reponseContrat('calepinage', 'calepinage_design_context'))
  calepinageApi.calepinages.modulesDisponibles.mockResolvedValue({ data: [] })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('ACAL37 — droit de voir seulement', () => {
  it('403 ⇒ calepinage lu sur la fiche devis, atelier en lecture seule', async () => {
    ventesApi.getDevisById.mockResolvedValue(
      { data: { id: DEVIS_ID, calepinage: { id: CTX.calepinage.id } } })
    rendreDevis(DEVIS_ID)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(ventesApi.getDevisById).toHaveBeenCalledWith(String(DEVIS_ID))
    expect(calepinageApi.calepinages.designContext)
      .toHaveBeenCalledWith(String(CTX.calepinage.id))
    expect(await screen.findByTestId('pv20-lecture-seule'))
      .toHaveTextContent('vous pouvez consulter cette conception, pas la modifier')
    expect(calepinageApi.calepinages.syncDevis).not.toHaveBeenCalled()
  })

  it('403 sans calepinage ⇒ message, aucun atelier', async () => {
    ventesApi.getDevisById.mockResolvedValue({ data: { id: DEVIS_ID, calepinage: null } })
    rendreDevis(DEVIS_ID)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Aucune conception pour ce devis — un utilisateur habilité doit la créer.')
    expect(initRoofToolPro8).not.toHaveBeenCalled()
  })
})
