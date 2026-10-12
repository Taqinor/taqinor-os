import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR19 — un commercial SANS la permission globale `journal_activite_voir`
   ouvre l'historique (AuditLog) d'un objet qu'il possède, via l'endpoint
   record-scopé /audit/objets/<content_type>/<id>/history/. On teste ici le
   composant réutilisable posé sur les fiches lead/devis/ticket. Réseau mocké. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const { getObjectHistory } = vi.hoisted(() => ({ getObjectHistory: vi.fn() }))

vi.mock('../../api/auditApi', () => ({
  default: { getObjectHistory: (...a) => getObjectHistory(...a) },
}))

import ObjectHistoryButton from './ObjectHistoryButton'

function withProviders(ui) {
  return render(<ThemeProvider>{ui}</ThemeProvider>)
}

beforeEach(() => { vi.clearAllMocks() })

describe('ObjectHistoryButton (WIR19)', () => {
  it("le propriétaire ouvre l'historique record-scopé de son lead", async () => {
    getObjectHistory.mockResolvedValue({
      data: {
        count: 1,
        results: [
          {
            id: 1, action: 'update', action_label: 'Modification',
            utilisateur: 'reda', detail: 'stage: NEW → CONTACTED',
            timestamp_local: '2026-07-19T10:00:00+01:00',
          },
        ],
      },
    })

    withProviders(<ObjectHistoryButton contentType="crm.lead" objectId={42} label="Historique des modifications" />)

    fireEvent.click(screen.getByRole('button', { name: /Historique des modifications/ }))

    await waitFor(() => expect(getObjectHistory).toHaveBeenCalledWith('crm.lead', 42))
    await waitFor(() => expect(screen.getByTestId('object-history-list')).toBeTruthy())
    expect(screen.getByText('Modification')).toBeTruthy()
    expect(screen.getByText(/stage: NEW → CONTACTED/)).toBeTruthy()
  })

  it('affiche un message clair si le backend refuse (403 non-propriétaire)', async () => {
    getObjectHistory.mockRejectedValue({ response: { status: 403 } })

    withProviders(<ObjectHistoryButton contentType="ventes.devis" objectId={7} />)

    fireEvent.click(screen.getByRole('button', { name: /Historique/ }))

    await waitFor(() => expect(screen.getByText("Vous n'avez pas accès à l'historique de cet objet.")).toBeTruthy())
  })

  it('ne rend rien sans objectId (création non encore persistée)', () => {
    const { container } = withProviders(<ObjectHistoryButton contentType="sav.ticket" objectId={null} />)
    expect(container.querySelector('button')).toBeNull()
  })
})
