import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* PACT54 — l'historique de la file de transmission DGI (NTMAR7) était complet
   côté serveur et totalement invisible. Le test verrouille : la liste est
   chargée, chaque transmission montre son statut, et la réponse brute de la
   DGI est rendue en texte lisible, jamais en objet JSON nu. */

vi.mock('../../api/einvoiceApi', () => ({
  default: { transmissions: vi.fn() },
}))

import einvoiceApi from '../../api/einvoiceApi'
import TransmissionsDGIPage from './TransmissionsDGIPage'

const ROWS = [
  {
    id: 1, einvoice: 12, statut: 'en_attente', tentatives: 0,
    prochaine_tentative: null, date_creation: '2026-08-10T09:00:00Z',
    reponse_json: {},
  },
  {
    id: 2, einvoice: 13, statut: 'rejete', tentatives: 3,
    prochaine_tentative: '2026-08-12T09:00:00Z',
    date_creation: '2026-08-09T09:00:00Z',
    reponse_json: { detail: 'ICE destinataire invalide.' },
  },
]

beforeEach(() => { einvoiceApi.transmissions.mockResolvedValue({ data: ROWS }) })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('TransmissionsDGIPage (PACT54)', () => {
  it('liste les transmissions avec leur statut', async () => {
    render(<TransmissionsDGIPage />)
    await waitFor(() => expect(einvoiceApi.transmissions).toHaveBeenCalled())
    // « En attente » est aussi le libellé du filtre Segmented au-dessus du
    // tableau : on scope l'assertion de statut à la ligne concernée (repérée
    // par son numéro d'e-facture, unique) plutôt que sur le texte brut.
    const ligne12 = (await screen.findByText('#12')).closest('tr')
    const ligne13 = screen.getByText('#13').closest('tr')
    expect(within(ligne12).getByText('En attente')).toBeInTheDocument()
    expect(within(ligne13).getByText('Rejeté')).toBeInTheDocument()
  })

  it('rend la réponse DGI en texte lisible, jamais un objet brut', async () => {
    render(<TransmissionsDGIPage />)
    expect(await screen.findByText('ICE destinataire invalide.')).toBeInTheDocument()
    expect(screen.queryByText(/\[object Object\]/)).not.toBeInTheDocument()
  })

  it('filtre sur les transmissions rejetées', async () => {
    const user = userEvent.setup()
    render(<TransmissionsDGIPage />)
    await screen.findByText('#12')

    await user.click(screen.getByRole('radio', { name: 'Rejetées' }))
    expect(screen.queryByText('#12')).not.toBeInTheDocument()
    expect(screen.getByText('#13')).toBeInTheDocument()
  })
})
