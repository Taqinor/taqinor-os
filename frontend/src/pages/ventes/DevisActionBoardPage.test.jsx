import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* QX29 — « Relances du jour » : tableau d'action des devis, miroir de
   SavActionBoardPage.test.jsx (ZSAV6). ventesApi mocké. */

vi.mock('../../api/ventesApi', () => ({
  default: { getDevisActionBoard: vi.fn(), getDevis: vi.fn() },
}))

import ventesApi from '../../api/ventesApi'
import DevisActionBoardPage from './DevisActionBoardPage'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('DevisActionBoardPage', () => {
  it('affiche les buckets avec leurs comptes et les devis référencés', async () => {
    ventesApi.getDevisActionBoard.mockResolvedValue({
      data: {
        buckets: {
          envoyes_sans_reponse: { count: 1, ids: [1] },
          acceptes_non_factures: { count: 0, ids: [] },
          refuses_sans_motif: { count: 0, ids: [] },
          expirant_bientot: { count: 0, ids: [] },
        },
      },
    })
    ventesApi.getDevis.mockResolvedValue({
      data: [{ id: 1, reference: 'DEV-001', client_nom: 'ACME', client_telephone: '0612345678' }],
    })
    render(<MemoryRouter><DevisActionBoardPage /></MemoryRouter>)
    expect(await screen.findByText('Envoyés sans réponse')).toBeInTheDocument()
    expect(await screen.findByText(/DEV-001/)).toBeInTheDocument()
    // Raccourci tel: présent quand un téléphone existe sur le devis.
    expect(screen.getByRole('link', { name: /Appeler/ })).toHaveAttribute('href', 'tel:0612345678')
  })

  it('affiche "Aucun devis." pour un bucket vide (5 buckets, dont la file QX30)', async () => {
    ventesApi.getDevisActionBoard.mockResolvedValue({
      data: {
        buckets: {
          envoyes_sans_reponse: { count: 0, ids: [] },
          acceptes_non_factures: { count: 0, ids: [] },
          refuses_sans_motif: { count: 0, ids: [] },
          expirant_bientot: { count: 0, ids: [] },
          engagement_relance: { count: 0, ids: [] },
        },
      },
    })
    render(<MemoryRouter><DevisActionBoardPage /></MemoryRouter>)
    expect((await screen.findAllByText('Aucun devis.')).length).toBe(5)
  })
})

describe('DevisActionBoardPage — QX30 : file déclenchée par l\'engagement + wa.me pré-rempli', () => {
  it('rend la file "Relance engagement" et pré-remplit wa.me depuis board.wa_drafts', async () => {
    ventesApi.getDevisActionBoard.mockResolvedValue({
      data: {
        buckets: {
          envoyes_sans_reponse: { count: 0, ids: [] },
          acceptes_non_factures: { count: 0, ids: [] },
          refuses_sans_motif: { count: 0, ids: [] },
          expirant_bientot: { count: 0, ids: [] },
          engagement_relance: { count: 1, ids: [9] },
        },
        wa_drafts: { 9: 'Bonjour, votre proposition solaire vous attend toujours !' },
      },
    })
    ventesApi.getDevis.mockResolvedValue({
      data: [{ id: 9, reference: 'DEV-009', client_nom: 'Amine', client_whatsapp: '0612345678' }],
    })
    render(<MemoryRouter><DevisActionBoardPage /></MemoryRouter>)
    expect(await screen.findByText('Relance engagement')).toBeInTheDocument()
    const waLink = await screen.findByRole('link', { name: /WhatsApp/ })
    expect(waLink).toHaveAttribute('href', expect.stringContaining('text=Bonjour%2C%20votre%20proposition'))
  })
})
