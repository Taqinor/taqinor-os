import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* AUD132 (PAY-10) — « chèque impayé » était INGÉRABLE depuis le produit.
   L'action serveur `POST /ventes/paiements/{id}/rejeter/` (YLEDG5) existait
   sans aucun appelant (grep `rejeter` dans `ventesApi.js` : seulement
   `rejeterEtapeDevis`), et l'écran Encaissements listait montant/date/mode/
   auteur/écriture SANS colonne statut — un paiement rejeté s'y lisait donc
   comme un encaissement valide, compté dans le total. */

vi.mock('../../api/ventesApi', () => ({
  default: {
    getPaiements: vi.fn(() => Promise.resolve({ data: [] })),
    importReleveDryRun: vi.fn(),
    importReleveCommit: vi.fn(),
    rejeterPaiement: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))
// Palier responsable/admin — même garde que le serveur (IsResponsableOrAdmin).
vi.mock('../../hooks/useHasPermission', () => ({
  useHasPermission: () => true,
  useHasRole: () => true,
  useIsAdmin: () => true,
  useIsAdminOrResponsable: () => true,
}))
// EcritureSourceLink interroge la compta : hors sujet ici.
vi.mock('../../features/compta/components/EcritureSourceLink.jsx', () => ({
  default: () => null,
}))

import ventesApi from '../../api/ventesApi'
import PaiementsPage from './PaiementsPage'

const VALIDE = {
  id: 11, facture: 7, facture_reference: 'FAC-2026-0007',
  client: 3, client_nom: 'ACME SARL', montant: '3000.00',
  date_paiement: '2026-08-01', mode: 'virement', mode_display: 'Virement',
  statut: 'valide', statut_display: 'Valide', created_by_username: 'meryem',
}
const REJETE = {
  id: 12, facture: 8, facture_reference: 'FAC-2026-0008',
  client: 3, client_nom: 'ACME SARL', montant: '30000.00',
  date_paiement: '2026-08-02', mode: 'cheque', mode_display: 'Chèque',
  statut: 'rejete', statut_display: 'Rejeté',
  motif_rejet: 'Chèque sans provision', created_by_username: 'meryem',
}

beforeEach(() => {
  ventesApi.getPaiements.mockResolvedValue({ data: [VALIDE, REJETE] })
  ventesApi.rejeterPaiement.mockResolvedValue({ data: {} })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

const renderPage = () => render(
  <MemoryRouter initialEntries={['/ventes/paiements']}>
    <PaiementsPage />
  </MemoryRouter>,
)

describe('PaiementsPage (AUD132 — chèque impayé)', () => {
  it('badge « Rejeté » sur la ligne rejetée, « Encaissé » sur la valide', async () => {
    renderPage()
    expect(await screen.findByText('FAC-2026-0008')).toBeInTheDocument()
    expect(screen.getAllByText('Rejeté').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Encaissé').length).toBeGreaterThan(0)
  })

  it('un paiement rejeté SORT du total affiché', async () => {
    renderPage()
    await screen.findByText('FAC-2026-0008')
    // 3 000 seul — jamais 33 000 (le rejeté ne compte pas).
    expect(screen.getByText('Total encaissé (1)')).toBeInTheDocument()
  })

  it('le bouton « Rejeter » n\'existe que sur un paiement non rejeté', async () => {
    renderPage()
    await screen.findByText('FAC-2026-0008')
    expect(screen.getAllByRole('button', { name: /Rejeter/ })).toHaveLength(1)
  })

  it('l\'appel de rejet part avec le motif saisi', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('FAC-2026-0008')

    await user.click(screen.getByRole('button', { name: /Rejeter/ }))
    const motif = await screen.findByLabelText('Motif du rejet')
    await user.type(motif, 'Chèque sans provision')
    await user.click(
      screen.getByRole('button', { name: 'Confirmer le rejet' }))

    await waitFor(() => expect(ventesApi.rejeterPaiement).toHaveBeenCalled())
    const [id, body] = ventesApi.rejeterPaiement.mock.calls[0]
    expect(id).toBe(11)
    expect(body.motif).toBe('Chèque sans provision')
  })

  it('sans motif, la confirmation reste désactivée (le serveur refuse en 400)', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('FAC-2026-0008')

    await user.click(screen.getByRole('button', { name: /Rejeter/ }))
    await screen.findByLabelText('Motif du rejet')
    expect(
      screen.getByRole('button', { name: 'Confirmer le rejet' }),
    ).toBeDisabled()
  })
})
