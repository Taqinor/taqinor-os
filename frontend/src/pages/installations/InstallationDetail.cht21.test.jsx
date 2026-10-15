import { describe, it, expect, vi, beforeAll, afterEach } from 'vitest'
import { screen, cleanup } from '@testing-library/react'
import { renderInstallationDetail } from '../../test/installationDetailHarness'
import { polyfillResizeObserver } from '../../test/selectNatif'
import userEvent from '@testing-library/user-event'

/* ============================================================================
   CHT21(c) — Deep-link cassé du parcours commercial : « Voir le client »
   naviguait vers la liste nue `/crm` (générique) ; même patron que « Voir le
   lead » voisin (`?id=` déjà lu par `ClientList.jsx:73`, VX79).
   ========================================================================== */

beforeAll(polyfillResizeObserver)

vi.mock('../../api/installationsApi', async () => ({
  default: {
    ...(await import('../../test/selectNatif')).installationsLecturesVides,
  },
}))

vi.mock('../../api/ventesApi', async () => (await import('../../test/selectNatif')).ventesApiMock)

vi.mock('../../api/crmApi', async () => (await import('../../test/selectNatif')).crmApiMock)

vi.mock('../../api/savApi', async () => (await import('../../test/selectNatif')).savApiMock)

const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => navigateMock }
})

import InstallationDetail from './InstallationDetail'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('InstallationDetail — « Voir le client » cible la fiche réelle (CHT21c)', () => {
  it('navigue vers /crm?id=<client> (jamais la liste nue)', async () => {
    const user = userEvent.setup()
    renderInstallationDetail({
      id: 701, reference: 'CH-CHT21-701', statut: 'signe', annule: false,
      client: 33, client_nom: 'Client CHT21',
    })

    const bouton = await screen.findByRole('button', { name: 'Voir le client' })
    await user.click(bouton)
    expect(navigateMock).toHaveBeenCalledWith('/crm?id=33')
  })

  it("n'affiche rien quand le chantier n'a aucun client", async () => {
    renderInstallationDetail({
      id: 702, reference: 'CH-CHT21-702', statut: 'signe', annule: false,
      client: null,
    })
    expect(screen.queryByRole('button', { name: 'Voir le client' })).toBeNull()
  })
})
