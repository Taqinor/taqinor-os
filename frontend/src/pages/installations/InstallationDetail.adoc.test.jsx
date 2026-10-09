import { describe, it, expect, vi, beforeAll, afterEach } from 'vitest'
import { screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderInstallationDetail as rendre } from '../../test/installationDetailHarness'
import { polyfillResizeObserver } from '../../test/selectNatif'

/* ADOC73 — deux attestations distinctes (installation / fin de travaux) qui
   transmettent leur type, soumises à pvReady comme PV/BL/dossier, et le motif
   d'un 409 serveur affiché au lieu d'un aperçu vide. */

beforeAll(polyfillResizeObserver)

const docs = vi.hoisted(() => ({ attestation: vi.fn() }))
vi.mock('../../api/documentsApi', () => ({ default: docs }))
vi.mock('../../api/savApi', async () => (await import('../../test/selectNatif')).savApiMock)
vi.mock('../../api/crmApi', async () => (await import('../../test/selectNatif')).crmApiMock)
vi.mock('../../api/ventesApi', async () => (await import('../../test/selectNatif')).ventesApiMock)
vi.mock('../../api/installationsApi', async () => ({
  default: {
    ...(await import('../../test/selectNatif')).installationsLecturesVides,
  },
}))
vi.mock('./ChantierGateTimeline', async () => (await import('../../test/selectNatif')).composantNul)
vi.mock('./ChantierChecklist', async () => (await import('../../test/selectNatif')).composantNul)
vi.mock('../../features/installations/offline/OfflineSyncIndicator', async () => (await import('../../test/selectNatif')).composantNul)

const ouvrirDocuments = async (user) => {
  await user.click(await screen.findByRole('tab', { name: /Documents/ }))
}

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('InstallationDetail — ADOC73 attestations', () => {
  it('fin de travaux transmet type=fin_travaux', async () => {
    docs.attestation.mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()
    rendre({ id: 7, reference: 'CH-7', statut: 'installe', annule: false })
    await ouvrirDocuments(user)
    await user.click(screen.getByRole('button', { name: 'Attestation de fin de travaux' }))
    await waitFor(() => expect(docs.attestation).toHaveBeenCalledWith(7, 'fin_travaux'))
    await user.click(screen.getByRole('button', { name: 'Fermer' }))
    await user.click(screen.getByRole('button', { name: 'Attestation d’installation' }))
    await waitFor(() => expect(docs.attestation).toHaveBeenLastCalledWith(7, 'installation'))
  })

  it('attestation désactivée tant que pvReady est faux', async () => {
    const user = userEvent.setup()
    rendre({ id: 8, reference: 'CH-8', statut: 'signe', annule: false })
    await ouvrirDocuments(user)
    expect(screen.getByRole('button', { name: 'Attestation de fin de travaux' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Attestation d’installation' })).toBeDisabled()
    expect(docs.attestation).not.toHaveBeenCalled()
  })

  it('un 409 affiche son motif', async () => {
    docs.attestation.mockRejectedValue({
      response: { status: 409, data: { detail: 'Réception non prononcée : attestation refusée.' } },
    })
    const user = userEvent.setup()
    rendre({ id: 9, reference: 'CH-9', statut: 'installe', annule: false })
    await ouvrirDocuments(user)
    await user.click(screen.getByRole('button', { name: 'Attestation de fin de travaux' }))
    expect(await screen.findByText('Réception non prononcée : attestation refusée.'))
      .toBeInTheDocument()
  })
})
