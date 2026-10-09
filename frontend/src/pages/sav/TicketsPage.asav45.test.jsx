import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import CONTRAT from '../../../../backend/django_core/apps/sav/contract_samples/ticket_detail.json'

// ASAV45 — bandeau et sélecteur lisent la garantie EFFECTIVE servie par le
// serveur (contrat ticket_detail.json), sans recalcul local sur la date
// constructeur.

vi.mock('../../features/sav/store/ticketsSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, updateTicket: () => {
    const action = { type: 'sav/updateTicket/noop' }
    action.unwrap = () => Promise.resolve({})
    return action
  } }
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
vi.mock('../../api/axios', () => ({ default: { get: vi.fn(() => Promise.resolve({ data: [] })) } }))
vi.mock('../../api/installationsApi', () => ({
  default: { getInterventions: vi.fn(() => Promise.resolve({ data: [] })) },
}))

import { TicketDetail } from './TicketsPage'

beforeEach(() => { vi.useFakeTimers({ toFake: ['Date'] }); vi.setSystemTime(new Date('2026-10-09T10:00:00')) })
afterEach(() => { cleanup(); vi.useRealTimers() })

function renderDetail(ticket) {
  const store = configureStore({ reducer: {
    tickets: (state = { items: [] }) => state,
    auth: (state = { role: 'responsable', permissions: [] }) => state,
  } })
  return render(<Provider store={store}><MemoryRouter>
    <TicketDetail ticket={{ ...CONTRAT.exemple, type: 'correctif', description: '',
      sous_garantie: 'a_determiner', couverture: 'a_determiner', devis_id_ext: null,
      facture_id_ext: null, instructions: '', ...ticket }}
      onClose={() => {}} onSaved={() => {}} />
  </MemoryRouter></Provider>)
}

describe('TicketDetail — ASAV45 garantie effective servie', () => {
  it('a : constructeur absent, légale servie → sélecteur « Oui » et bandeau légal', async () => {
    renderDetail({ equipement_fin_garantie: null,
      equipement_fin_garantie_effective: '2027-02-10', sous_garantie_effectif: 'oui' })
    expect((await screen.findAllByText(/Garantie jusqu'au 10\/02\/2027 \(légale\)/)).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('combobox').some((c) => c.textContent === 'Oui')).toBe(true)
  })

  it('b : constructeur expiré mais légale en cours → pas de « Garantie expirée »', async () => {
    renderDetail({ equipement_fin_garantie: '2026-08-09',
      equipement_fin_garantie_effective: '2026-12-12', sous_garantie_effectif: 'oui' })
    expect((await screen.findAllByText(/Garantie jusqu'au 12\/12\/2026 \(légale\)/)).length).toBeGreaterThan(0)
    expect(screen.queryByText(/Garantie expirée/)).toBeNull()
    expect(screen.getAllByRole('combobox').some((c) => c.textContent === 'Oui')).toBe(true)
  })
})
