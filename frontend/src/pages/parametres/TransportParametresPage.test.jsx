import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* NTLOG35 — Paramètres > Transport (`transport.ParametresTransport`,
   singleton par société). Le PATCH cible `1/` (motif
   `DouaneParametresPage` — le GET précédent crée le singleton à la volée,
   son id réel n'a pas besoin d'être lu côté client puisqu'il n'existe
   qu'une ligne par société). */

const { get, patch } = vi.hoisted(() => ({ get: vi.fn(), patch: vi.fn() }))
vi.mock('../../api/axios', () => ({ default: { get, patch } }))

const { toastError, toastSuccess } = vi.hoisted(() => ({
  toastError: vi.fn(), toastSuccess: vi.fn(),
}))
vi.mock('../../ui/confirm', () => ({
  toast: { error: toastError, success: toastSuccess },
}))

import TransportParametresPage from './TransportParametresPage'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const DEFAUTS = {
  delai_alerte_retard_heures: 24, pod_obligatoire: true,
  seuil_anomalie_affretement_pct: '15.00',
}

describe('TransportParametresPage', () => {
  it('charge les réglages existants', async () => {
    get.mockResolvedValueOnce({ data: DEFAUTS })
    render(<TransportParametresPage />)
    await waitFor(() => expect(get).toHaveBeenCalledWith('/transport/parametres-transport/'))
    await screen.findByText('Transport')
  })

  it('désactive pod_obligatoire et enregistre', async () => {
    get.mockResolvedValueOnce({ data: DEFAUTS })
    patch.mockResolvedValueOnce({ data: { ...DEFAUTS, pod_obligatoire: false } })
    const user = userEvent.setup()
    render(<TransportParametresPage />)
    await screen.findByLabelText('Preuve de livraison obligatoire')

    await user.click(screen.getByLabelText('Preuve de livraison obligatoire'))
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(patch).toHaveBeenCalledWith(
      '/transport/parametres-transport/1/',
      expect.objectContaining({ pod_obligatoire: false }),
    ))
    await waitFor(() => expect(toastSuccess).toHaveBeenCalled())
  })
})
