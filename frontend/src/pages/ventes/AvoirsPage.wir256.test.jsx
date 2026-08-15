import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* WIR256 — le lien « Voir l'écriture comptable » (WIR24) doit être monté sur
   la liste des avoirs, un par ligne (sourceType='avoir', sourceId=a.id) : la
   même façade que sur facture/paiement, mais scopée à CET avoir précis. Deux
   cas couverts : le réglage auto-écritures actif (lien présent) et inactif
   (absent). Aucun appel réseau réel — ventesApi et comptaApi sont mockés. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const ecrituresListMock = vi.fn()

vi.mock('../../api/ventesApi', () => ({
  default: {
    getAvoirs: () => Promise.resolve({
      data: [{
        id: 501, reference: 'AV-2026-0001', facture_reference: 'FA-2026-0010',
        client_nom: 'Client Test', total_ttc: 1000, motif: 'Erreur de facturation',
        statut: 'emise', statut_display: 'Émis',
      }],
    }),
  },
}))

vi.mock('../../api/comptaApi', () => ({
  default: { ecritures: { list: (params) => ecrituresListMock(params) } },
}))

import AvoirsPage from './AvoirsPage.jsx'

function mount() {
  const store = configureStore({
    reducer: { auth: () => ({ role: 'admin', role_nom: null, permissions: [] }) },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter><AvoirsPage /></MemoryRouter>
    </Provider>,
  )
}

describe('AvoirsPage — lien écriture comptable par avoir (WIR256)', () => {
  it('affiche le lien quand une écriture existe pour cet avoir (auto-écritures actif)', async () => {
    ecrituresListMock.mockResolvedValueOnce({ data: [{ id: 9, numero: 'VE-2026-0009' }] })
    mount()
    await waitFor(() => {
      expect(ecrituresListMock).toHaveBeenCalledWith({ source_type: 'avoir', source_id: 501 })
    })
    const link = await screen.findByTestId('ecriture-source-link')
    expect(link.getAttribute('href')).toContain('source_type=avoir')
    expect(link.getAttribute('href')).toContain('source_id=501')
  })

  it("n'affiche aucun lien quand aucune écriture n'existe (auto-écritures inactif)", async () => {
    ecrituresListMock.mockResolvedValueOnce({ data: [] })
    mount()
    await waitFor(() => expect(ecrituresListMock).toHaveBeenCalled())
    expect(screen.queryByTestId('ecriture-source-link')).toBeNull()
  })
})
