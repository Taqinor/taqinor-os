import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

// VX216(b) — un ticket résolu automatiquement par YSERV2 (intervention
// terminée) ne montrait jamais QUELLE intervention l'a résolu ; le lien
// « Chantier » pointait vers la page générique /chantiers au lieu d'un
// deep-link vers CE chantier (patron VX79 ?id=).

vi.mock('../../features/sav/store/ticketsSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    updateTicket: () => {
      const action = { type: 'sav/updateTicket/noop' }
      action.unwrap = () => Promise.resolve({})
      return action
    },
  }
})

vi.mock('../../api/savApi', () => ({
  default: {
    getTicketHistorique: vi.fn(() => Promise.resolve({ data: [] })),
    getTicketPieces: vi.fn(() => Promise.resolve({ data: [] })),
    getEquipements: vi.fn(() => Promise.resolve({ data: [] })),
    getTicketsSimilaires: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    getTriageIa: vi.fn(() => Promise.resolve({ data: { disponible: false } })),
    getPretsEquipement: vi.fn(() => Promise.resolve({ data: [] })),
    getReponsesType: vi.fn(() => Promise.resolve({ data: [] })),
    getTicketChecklist: vi.fn(() => Promise.resolve({ data: [] })),
    getChecklistTemplates: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))

vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(() => Promise.resolve({ data: [] })) },
}))

vi.mock('../../api/installationsApi', () => ({
  default: { getInterventions: vi.fn(() => Promise.resolve({ data: [] })) },
}))

import { TicketDetail } from './TicketsPage'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function makeStore() {
  return configureStore({
    reducer: {
      tickets: (state = { items: [] }) => state,
      auth: (state = { role: 'admin', permissions: [] }) => state,
    },
  })
}

function renderDetail(ticket, opts = {}) {
  const store = makeStore()
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <TicketDetail ticket={ticket} onClose={() => {}} onSaved={() => {}} {...opts} />
      </MemoryRouter>
    </Provider>,
  )
}

const baseTicket = {
  id: 1, reference: 'SAV-1', statut: 'resolu', type: 'correctif',
  priorite: 'normale', sous_garantie: 'non', sous_garantie_effectif: 'non',
  couverture: 'a_determiner', devis_id_ext: null, facture_id_ext: null,
  installation: 55, installation_reference: 'CH-2026-07-0009',
}

describe('TicketDetail — VX216(b) : ticket résolu par une intervention', () => {
  it('montre « Résolu par » avec l\'intervention, sa date et son technicien', async () => {
    renderDetail({
      ...baseTicket,
      interventions: [
        {
          id: 101, type_intervention: 'depannage', type_intervention_display: 'Dépannage',
          installation_id: 55, date_prevue: '2026-06-01', date_realisee: '2026-06-02',
          compte_rendu: 'Remplacement fusible', technicien_nom: 'Yassine',
        },
      ],
    })
    await screen.findByText('Résolu par')
    expect(screen.getByDisplayValue('Intervention #101 du 02/06/2026 par Yassine')).toBeInTheDocument()
  })

  it('retient la PLUS RÉCENTE intervention réalisée quand plusieurs existent', async () => {
    renderDetail({
      ...baseTicket,
      interventions: [
        {
          id: 101, type_intervention: 'depannage', type_intervention_display: 'Dépannage',
          installation_id: 55, date_prevue: '2026-06-01', date_realisee: '2026-06-02',
          compte_rendu: '', technicien_nom: 'Yassine',
        },
        {
          id: 202, type_intervention: 'maintenance', type_intervention_display: 'Maintenance',
          installation_id: 55, date_prevue: '2026-06-10', date_realisee: '2026-06-11',
          compte_rendu: '', technicien_nom: 'Nabil',
        },
      ],
    })
    await screen.findByText('Résolu par')
    expect(screen.getByDisplayValue('Intervention #202 du 11/06/2026 par Nabil')).toBeInTheDocument()
  })

  it('n\'affiche aucun champ « Résolu par » sans intervention réalisée', async () => {
    renderDetail({ ...baseTicket, interventions: [] })
    await screen.findByText('Ticket SAV — SAV-1', { exact: false })
    expect(screen.queryByText('Résolu par')).not.toBeInTheDocument()
  })

  it('le lien Chantier pointe vers ce chantier précis (?id=), pas la liste générique', async () => {
    renderDetail({ ...baseTicket, interventions: [] })
    await screen.findByText('Ticket SAV — SAV-1', { exact: false })
    const link = screen.getByTitle('Ouvrir ce chantier')
    expect(link).toHaveAttribute('href', '/chantiers?id=55')
  })
})
