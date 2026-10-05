import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { cleanup, waitFor } from '@testing-library/react'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   CALX109 CÂBLAGE — LE CATALOGUE DE MODULES DE LA SOCIÉTÉ ATTEINT L'ATELIER.

   `GET calepinages/<pk>/modules-disponibles/` sert les fiches « module » du stock avec
   leurs VRAIES cotes (contrat `calepinage_modules_disponibles.json`). L'atelier 3D ne parle
   jamais à Django : c'est la PAGE HÔTE qui lit cette porte et transmet la réponse TELLE
   QUELLE au constructeur (`InitOptions.modulesDisponibles`). Sans cette ligne, le sélecteur
   de module de l'atelier n'a rien à proposer et chaque pan reste pavé avec le module par
   défaut, quoi qu'il y ait au stock.

   Même patron, même discipline que `chargerReglagesAtelier` (CALX104/CALX403, éprouvé par
   `ToitureDesign.cablageHooks2.test.jsx`) : porte BEST-EFFORT lancée en parallèle du
   design-context, qui ne bloque JAMAIS le boot et n'invente rien quand elle échoue.

   PACT13 — la charge utile vient de l'exemple COMMITTÉ, jamais d'un objet tapé à la main.
   ========================================================================== */

vi.mock('../../hooks/useHasPermission', () => ({ useHasPermission: () => false }))

import '../../test/toitureDesignHarnessCalepinage'
import {
  initRoofToolPro8, rendreCalepinage, rendreDevis, reinitialiserBootMinimal, stubberEmpreinteOsm,
} from '../../test/toitureDesignHarness'
import calepinageApi from '../../api/calepinageApi'
import ventesApi from '../../api/ventesApi'

stubberEmpreinteOsm()

const CTX = exempleContrat('calepinage', 'calepinage_design_context')
const MODULES = exempleContrat('calepinage', 'calepinage_modules_disponibles')

beforeEach(() => {
  vi.clearAllMocks()
  reinitialiserBootMinimal()
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('CALX109 câblage — le catalogue de modules atteint le constructeur', () => {
  it('le mode CALEPINAGE lit `modules-disponibles` et transmet la réponse TELLE QUELLE', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.calepinages.modulesDisponibles.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_modules_disponibles'))

    rendreCalepinage(CTX.calepinage.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(calepinageApi.calepinages.modulesDisponibles)
      .toHaveBeenCalledWith(String(CTX.calepinage.id))
    expect(initRoofToolPro8.mock.calls[0][0].modulesDisponibles).toEqual(MODULES)
  })

  it('un refus de droits ou une panne réseau ne bloque pas le boot (aucun module inventé)', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.calepinages.modulesDisponibles.mockRejectedValue(new Error('403'))

    rendreCalepinage(CTX.calepinage.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    // `null` = aucun catalogue : l'atelier pose son module par défaut, NOMMÉ.
    expect(initRoofToolPro8.mock.calls[0][0].modulesDisponibles).toBeNull()
  })

  it('le mode DEVIS ne fait AUCUNE requête de catalogue (porte propre au calepinage)', async () => {
    ventesApi.getDevisDesignContext.mockResolvedValue({
      data: {
        devis: { id: 9, reference: 'DV-9' },
        client: {},
        geometrie: { roof_layout: null, roof_outline: null, roof_point: null },
        cible: null,
        carte: { available: true, maptilerKey: 'k', mapboxToken: '' },
        modifiable: true,
        motif_lecture_seule: null,
      },
    })

    rendreDevis(9, '/devis/:id/toiture')

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(calepinageApi.calepinages.modulesDisponibles).not.toHaveBeenCalled()
    expect(initRoofToolPro8.mock.calls[0][0].modulesDisponibles).toBeUndefined()
  })
})
