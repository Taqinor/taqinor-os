import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   CÂBLAGES du lot 2 (Groupe CALX) côté PAGE HÔTE. Les lanes du lot ont écrit des
   modules autonomes et testés qui n'avaient AUCUN appelant : ce fichier prouve les
   lignes d'appel qui les branchent, et RIEN d'autre.

   1. CALX104/CALX403 — la page lit `GET /calepinage/parametres/` et transmet les
      sections `zones_types` + `degagements` TELLES QUELLES au builder
      (`reglagesAtelier`). Sans elles, l'atelier ne propose aucun gabarit d'obstacle
      et ne préremplit aucune largeur d'allée : du code sans appelant.
   2. CALX132 — l'empreinte OSM (`roof-footprint`) porte un bloc `batiment`
      (hauteur/niveaux) que la page JETAIT : elle ne lisait que `polygon`. Il est
      désormais PROPOSÉ au panneau Bâtiment, jamais appliqué d'office.

   PACT13 — les charges utiles viennent des exemples COMMITTÉS, jamais d'un objet
   tapé à la main.
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
// `ToitureDesign.calepinage.test.jsx`) : une liste écrite à la main laisserait des
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

const setBatimentOsmPropose = vi.fn()
const initRoofToolPro8 = vi.fn((options) => {
  options?.onApiReady?.({
    serializeLayout: vi.fn(() => ({ version: 2, zones: [] })),
    snapshot: vi.fn(() => null),
    setBatimentOsmPropose,
  })
})
vi.mock('@roofbuilder', () => ({ initRoofToolPro8: (...a) => initRoofToolPro8(...a) }))

import api from '../../api/axios'
import crmApi from '../../api/crmApi'
import calepinageApi from '../../api/calepinageApi'
import ToitureDesign from './ToitureDesign'

const CTX = exempleContrat('calepinage', 'calepinage_design_context')
const PARAMETRES = exempleContrat('calepinage', 'parametres_calepinage')
const EMPREINTE = exempleContrat('calepinage', 'calepinage_empreinte_osm')

function rendreCalepinage(id) {
  return render(
    <MemoryRouter initialEntries={[`/calepinage/${id}`]}>
      <Routes>
        <Route path="/calepinage/:id" element={<ToitureDesign mode="calepinage" />} />
      </Routes>
    </MemoryRouter>,
  )
}

function rendreLead(id) {
  return render(
    <MemoryRouter initialEntries={[`/toiture/${id}`]}>
      <Routes>
        <Route path="/toiture/:id" element={<ToitureDesign />} />
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
      setBatimentOsmPropose,
    })
  })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('CALX104/CALX403 câblage — les réglages société atteignent enfin l’atelier', () => {
  it('transmet `zones_types` et `degagements` TELS QUELS au builder', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.parametres.get.mockResolvedValue(
      reponseContrat('calepinage', 'parametres_calepinage'))

    rendreCalepinage(CTX.calepinage.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    // (l'écran lit déjà cette porte ailleurs — CAL71 : on n'affirme donc pas un
    // compte d'appels, seulement que la section atteint bien le builder)
    expect(calepinageApi.parametres.get).toHaveBeenCalled()
    const options = initRoofToolPro8.mock.calls[0][0]
    expect(options.reglagesAtelier).toEqual({
      zones_types: PARAMETRES.zones_types,
      degagements: PARAMETRES.degagements,
    })
  })

  it('un refus de droits ou une panne réseau ne bloque pas le boot (aucune cote de repli)', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.parametres.get.mockRejectedValue(new Error('403'))

    rendreCalepinage(CTX.calepinage.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(initRoofToolPro8.mock.calls[0][0].reglagesAtelier).toBeNull()
  })
})

describe('CALX132 câblage — la hauteur OSM est PROPOSÉE au panneau Bâtiment', () => {
  /** Le mode LEAD est le seul qui interroge `roof-footprint` (pin sans contour). */
  function leadSansContour() {
    return {
      id: 42,
      full_name: 'Client test',
      ville: 'Casablanca',
      roof_outline: null,
      roof_point: { lat: 33.59, lng: -7.6 },
      latitude: 33.59,
      longitude: -7.6,
    }
  }

  beforeEach(() => {
    api.get.mockImplementation((url) => {
      if (String(url).includes('/crm/leads/')) {
        return Promise.resolve({ data: leadSansContour() })
      }
      if (String(url).includes('roof-config')) {
        return Promise.resolve({ data: { available: true, maptilerKey: 'k' } })
      }
      return Promise.resolve({ data: {} })
    })
  })

  it('le bloc `batiment` de l’empreinte part vers `setBatimentOsmPropose`', async () => {
    crmApi.getRoofFootprint.mockResolvedValue({ data: EMPREINTE })

    rendreLead(42)

    await waitFor(() => expect(setBatimentOsmPropose).toHaveBeenCalled())
    expect(setBatimentOsmPropose).toHaveBeenCalledWith(EMPREINTE.batiment)
  })

  it('sans bloc `batiment`, RIEN n’est proposé (jamais une hauteur inventée)', async () => {
    crmApi.getRoofFootprint.mockResolvedValue({
      data: { polygon: EMPREINTE.polygon },
    })

    rendreLead(42)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(setBatimentOsmPropose).not.toHaveBeenCalled()
  })
})
