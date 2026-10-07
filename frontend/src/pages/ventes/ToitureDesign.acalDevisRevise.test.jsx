import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { cleanup, waitFor } from '@testing-library/react'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   Lot 2 critique #22 (ACAL92, D-ACAL-3) — la route `/ventes/devis/<V1>/design`
   d'un devis RÉVISÉ ne monte JAMAIS l'atelier éditable : le calepinage résolu
   est lié à la V2 (`devis.id` de la réponse ≠ V1) ⇒ notice « Ce devis a été
   révisé » et redirection vers `/ventes/devis/<V2>/design`, sans écriture.
   ========================================================================== */

vi.mock('../../hooks/useHasPermission', () => ({ useHasPermission: () => false }))
vi.mock('../../lib/toast', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toastInfo: vi.fn() }
})

import '../../test/toitureDesignHarnessCalepinage'
import {
  initRoofToolPro8, rendreDevis, reinitialiserBootMinimal,
} from '../../test/toitureDesignHarness'
import calepinageApi from '../../api/calepinageApi'
import { toastInfo } from '../../lib/toast'

const CTX = exempleContrat('calepinage', 'calepinage_design_context')
const V2 = CTX.calepinage.devis_lie.id
const V1 = V2 + 1000
const REF_V2 = CTX.calepinage.devis_lie.reference

beforeEach(() => {
  vi.clearAllMocks()
  reinitialiserBootMinimal()
  calepinageApi.calepinages.depuisModele.mockImplementation(() => Promise.resolve(
    { data: { id: CTX.calepinage.id, devis: { id: V2, reference: REF_V2, statut: 'brouillon' } } }))
  calepinageApi.calepinages.designContext.mockResolvedValue(
    reponseContrat('calepinage', 'calepinage_design_context'))
  calepinageApi.calepinages.modulesDisponibles.mockResolvedValue({ data: [] })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('ACAL92 — la route d’une version remplacée ouvre la version en vigueur', () => {
  it('redirige vers la V2 avec une notice, sans aucune écriture', async () => {
    rendreDevis(V1)

    await waitFor(() => expect(calepinageApi.calepinages.depuisModele)
      .toHaveBeenCalledWith({ devis_id: V2 }))
    expect(calepinageApi.calepinages.depuisModele.mock.calls[0][0])
      .toEqual({ devis_id: V1 })
    expect(toastInfo).toHaveBeenCalledWith(
      `Ce devis a été révisé — conception de la version en vigueur (${REF_V2})`)
    // L'atelier ne monte qu'APRÈS la redirection (route de la V2).
    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(calepinageApi.calepinages.syncDevis).not.toHaveBeenCalled()
  })

  it('lien direct : aucune redirection, aucune notice', async () => {
    rendreDevis(V2)
    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(calepinageApi.calepinages.depuisModele).toHaveBeenCalledTimes(1)
    expect(toastInfo).not.toHaveBeenCalled()
  })
})
