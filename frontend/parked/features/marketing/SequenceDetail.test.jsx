import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  inscriptionsList: vi.fn(),
}))

vi.mock('../../api/marketingApi', () => ({
  default: {
    unwrapList: (res) => {
      const data = res?.data
      return Array.isArray(data) ? data : (data?.results || [])
    },
    sequences: { get: mocks.get },
    inscriptionsSequence: { list: mocks.inscriptionsList },
  },
}))

import SequenceDetail from './SequenceDetail'

const renderScreen = () => render(
  <MemoryRouter initialEntries={['/marketing/sequences/3']}>
    <Routes>
      <Route path="/marketing/sequences/:id" element={<SequenceDetail />} />
    </Routes>
  </MemoryRouter>,
)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.get.mockResolvedValue({
    data: {
      id: 3, nom: 'Onboarding partenaire', actif: true,
      etapes: [
        { id: 1, ordre: 1, delai_jours: 0, canal: 'whatsapp', canal_display: 'WhatsApp', modele_message: 'Bienvenue' },
        { id: 2, ordre: 2, delai_jours: 3, canal: 'email', canal_display: 'Email', modele_message: 'Suivi' },
      ],
    },
  })
  mocks.inscriptionsList.mockResolvedValue({
    data: [
      {
        id: 10, lead_id: 5, lead_reference: 'Lead Ahmed', statut: 'actif',
        executions: [
          { id: 100, etape: 1, execute_le: '2026-07-01T00:00:00Z', resultat: 'envoye', erreur: '' },
        ],
      },
    ],
  })
})

describe('SequenceDetail', () => {
  it('affiche les étapes ordonnées par défaut', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith('3'))
    expect(await screen.findByText('Onboarding partenaire')).toBeInTheDocument()
    const rows = screen.getAllByTestId('etape-row')
    expect(rows).toHaveLength(2)
    expect(rows[0]).toHaveTextContent('J+0')
    expect(rows[1]).toHaveTextContent('J+3')
  })

  it('l\'onglet Participants charge les inscriptions et se déplie sur la trace', async () => {
    renderScreen()
    await screen.findByText('Onboarding partenaire')
    fireEvent.click(screen.getByTestId('sequence-onglet-participants'))
    await waitFor(() => expect(mocks.inscriptionsList).toHaveBeenCalledWith({ sequence: '3' }))
    const participantRow = await screen.findByText('Lead Ahmed')
    expect(screen.queryByTestId('participant-executions')).toBeNull()
    fireEvent.click(participantRow.closest('tr'))
    expect(await screen.findByTestId('participant-executions')).toHaveTextContent('envoye')
  })
})
