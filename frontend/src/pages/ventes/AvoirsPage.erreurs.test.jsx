import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* AFAC61 — un échec de chargement des avoirs affiche une ERREUR, plus jamais
   « Aucun avoir — Créez-en un ». */

vi.mock('../../hooks/useHasPermission', () => ({ useIsAdmin: () => true }))
vi.mock('../../api/ventesApi', () => ({
  default: {
    getAvoirs: vi.fn(),
    annulerAvoir: vi.fn(),
    telechargerAvoirPdf: vi.fn(),
  },
}))

import ventesApi from '../../api/ventesApi'
import AvoirsPage from './AvoirsPage'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('AvoirsPage — AFAC61 : erreurs affichées', () => {
  it('chargement en échec : erreur serveur affichée, pas « Aucun avoir »', async () => {
    ventesApi.getAvoirs.mockRejectedValue({
      response: { status: 503, data: { detail: 'Service momentanément indisponible.' } },
    })
    render(<MemoryRouter><AvoirsPage /></MemoryRouter>)
    expect(await screen.findByRole('alert')).toHaveTextContent('Service momentanément indisponible.')
    expect(screen.queryByText('Aucun avoir')).toBeNull()
  })

  it('annulation refusée : la raison du serveur s\'affiche', async () => {
    ventesApi.getAvoirs.mockResolvedValue({
      data: { count: 1, next: null, results: [{ id: 4, reference: 'AV-004', statut: 'emise', total_ttc: '100.00' }] },
    })
    ventesApi.annulerAvoir.mockRejectedValue({
      response: { status: 400, data: { detail: 'Annulation refusée : avoir déjà imputé.' } },
    })
    render(<MemoryRouter><AvoirsPage /></MemoryRouter>)
    await screen.findByText('AV-004')
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Annuler' }))
    await user.click(await screen.findByRole('button', { name: "Annuler l'avoir" }))
    expect(await screen.findByText('Annulation refusée : avoir déjà imputé.')).toBeInTheDocument()
  })
})
