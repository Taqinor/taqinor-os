import { describe, it, expect, vi, beforeAll, afterEach } from 'vitest'
import { screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderInstallationDetail as rendre } from '../../test/installationDetailHarness'
import { polyfillResizeObserver } from '../../test/selectNatif'

/* ACHT3 — l'écran du chantier masque les gestes que le serveur refuse :
   « Enregistrer la mise en service » seulement depuis « Installé » et hors
   chantier annulé ; sélecteur de statut désactivé sur un chantier annulé. */

beforeAll(polyfillResizeObserver)

vi.mock('../../ui', async (importActual) => (
  (await import('../../test/selectNatif')).avecSelectNatif(await importActual())
))
vi.mock('./ChantierGateTimeline', async () => (await import('../../test/selectNatif')).composantNul)
vi.mock('./ChantierChecklist', async () => (await import('../../test/selectNatif')).composantNul)
vi.mock('../../features/installations/offline/OfflineSyncIndicator', async () => (await import('../../test/selectNatif')).composantNul)
vi.mock('../../api/installationsApi', async () => ({
  default: {
    ...(await import('../../test/selectNatif')).installationsLecturesVides,
  },
}))
vi.mock('../../api/savApi', async () => (await import('../../test/selectNatif')).savApiMock)
vi.mock('../../api/crmApi', async () => (await import('../../test/selectNatif')).crmApiMock)
vi.mock('../../api/ventesApi', async () => (await import('../../test/selectNatif')).ventesApiMock)

const ouvrirJalons = async (user) => {
  await user.click(await screen.findByRole('tab', { name: /Jalons/ }))
}
const BTN = { name: 'Enregistrer la mise en service' }

afterEach(() => cleanup())

describe('InstallationDetail — ACHT3 gestes refusés masqués', () => {
  it('masque mise en service sur signé', async () => {
    const user = userEvent.setup()
    rendre({ id: 1, reference: 'CH-1', statut: 'signe', annule: false })
    await ouvrirJalons(user)
    expect(screen.queryByRole('button', BTN)).toBeNull()
    expect(screen.getByText(/disponible à partir d’Installé/)).toBeInTheDocument()
  })

  it('désactive le statut sur annulé', async () => {
    const user = userEvent.setup()
    rendre({ id: 2, reference: 'CH-2', statut: 'installe', annule: true })
    expect(await screen.findByLabelText('Statut')).toBeDisabled()
    expect(screen.getByText(/Chantier annulé — réactivez-le/)).toBeInTheDocument()
    await ouvrirJalons(user)
    expect(screen.queryByRole('button', BTN)).toBeNull()
    expect(screen.queryByText('Date de mise en service')).toBeNull()
  })

  it('garde actif sur installé', async () => {
    const user = userEvent.setup()
    rendre({ id: 3, reference: 'CH-3', statut: 'installe', annule: false })
    expect(await screen.findByLabelText('Statut')).toBeEnabled()
    await ouvrirJalons(user)
    expect(screen.getByRole('button', BTN)).toBeInTheDocument()
  })
})
