import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
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

vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))
vi.mock('../../api/ventesApi', () => ({
  default: {
    getDevisDesignContext: vi.fn(),
    getDevisById: vi.fn(() => Promise.resolve({ data: {} })),
    syncDevisLayout: vi.fn(),
    shareLinkDevis: vi.fn(),
    whatsappPreviewDevis: vi.fn(),
    reviserDevis: vi.fn(),
  },
}))
// Le double SUIT la surface RÉELLE de `calepinageApi` (même patron que
// `ToitureDesign.cablageHooks2.test.jsx`) : une liste écrite à la main laisserait des
// groupes indéfinis et ferait planter l'écran au lieu de montrer l'assertion.
vi.mock('../../api/calepinageApi', async (importOriginal) => {
  const actual = await importOriginal()
  const espionner = (groupe) => Object.fromEntries(
    Object.entries(groupe).map(([cle, valeur]) => [
      cle,
      typeof valeur === 'function'
        ? vi.fn(() => Promise.resolve({ data: null }))
        : valeur,
    ]),
  )
  return {
    default: Object.fromEntries(
      Object.entries(actual.default).map(([nom, groupe]) => [
        nom,
        (groupe && typeof groupe === 'object') ? espionner(groupe) : groupe,
      ]),
    ),
  }
})
vi.mock('../../api/crmApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: {
      ...actual.default,
      getLeadPhotoToit: vi.fn(() => Promise.resolve({
        data: { visite_id: null, url: null, texture_calage: null },
      })),
      getRoofFootprint: vi.fn(() => Promise.resolve({ data: {} })),
    },
  }
})
vi.mock('../../lib/toast', () => ({ toastInfo: vi.fn() }))
vi.mock('../../hooks/useHasPermission', () => ({ useHasPermission: () => false }))

const initRoofToolPro8 = vi.fn()
vi.mock('@roofbuilder', () => ({ initRoofToolPro8: (...a) => initRoofToolPro8(...a) }))

import calepinageApi from '../../api/calepinageApi'
import ventesApi from '../../api/ventesApi'
import ToitureDesign from './ToitureDesign'

const CTX = exempleContrat('calepinage', 'calepinage_design_context')
const MODULES = exempleContrat('calepinage', 'calepinage_modules_disponibles')

function rendreCalepinage(id) {
  return render(
    <MemoryRouter initialEntries={[`/calepinage/${id}`]}>
      <Routes>
        <Route path="/calepinage/:id" element={<ToitureDesign mode="calepinage" />} />
      </Routes>
    </MemoryRouter>,
  )
}

function rendreDevis(id) {
  return render(
    <MemoryRouter initialEntries={[`/devis/${id}/toiture`]}>
      <Routes>
        <Route path="/devis/:id/toiture" element={<ToitureDesign mode="devis" />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  delete window.__taqinorRoofBooted
  initRoofToolPro8.mockImplementation((options) => {
    options?.onApiReady?.({
      serializeLayout: vi.fn(() => ({ version: 2, zones: [] })),
      snapshot: vi.fn(() => null),
    })
  })
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

    rendreDevis(9)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(calepinageApi.calepinages.modulesDisponibles).not.toHaveBeenCalled()
    expect(initRoofToolPro8.mock.calls[0][0].modulesDisponibles).toBeUndefined()
  })
})
