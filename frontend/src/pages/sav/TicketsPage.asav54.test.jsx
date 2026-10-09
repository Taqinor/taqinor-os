import { describe, it, expect, vi } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'

// ASAV54 — l'assistant de résolution/clôture s'ouvre au passage à « Résolu »
// sans cause/remède ; la cause se saisit aussi à la fiche ; trois tickets de
// même cause sur le même équipement donnent un regroupement suggéré
// (calcul serveur simulé : produit/équipement + cause, seuil 3).

const serveur = vi.hoisted(() => ({
  tickets: {
    1: { id: 1, reference: 'SAV-1', statut: 'en_cours', equipement: 977, cause: null, remede: null },
    2: { id: 2, reference: 'SAV-2', statut: 'nouveau', equipement: 977, cause: null, remede: null },
    3: { id: 3, reference: 'SAV-3', statut: 'nouveau', equipement: 977, cause: null, remede: null },
  },
  journal: [],
}))
const regroupements = () => {
  const par = {}
  for (const t of Object.values(serveur.tickets)) {
    if (!t.cause) continue
    const k = `${t.equipement}:${t.cause}`
    par[k] = (par[k] ?? 0) + 1
  }
  return Object.values(par).filter((n) => n >= 3)
}

vi.mock('../../features/sav/store/ticketsSlice', async (io) => (await import('./__testutils__/ticketDetailMocks.js')).ticketsSliceMock(await io(), ({ id, data }) => {
  serveur.journal.push(`PATCH ${id}`)
  serveur.tickets[id] = { ...serveur.tickets[id], ...data }
  return serveur.tickets[id]
}))
vi.mock('../../api/savApi', async () => (await import('./__testutils__/ticketDetailMocks.js')).savApiMock({
  getTicket: vi.fn((id) => Promise.resolve({ data: serveur.tickets[id] })),
  getCausesDefaillance: vi.fn(() => Promise.resolve({ data: [{ id: 11, nom: 'Surchauffe' }] })),
  getRemedesDefaillance: vi.fn(() => Promise.resolve({ data: [{ id: 21, nom: 'Remplacement ventilateur' }] })),
  resoudreTicket: vi.fn((id) => {
    serveur.journal.push(`POST resoudre ${id}`)
    serveur.tickets[id] = { ...serveur.tickets[id], statut: 'resolu' }
    return Promise.resolve({ data: serveur.tickets[id] })
  }),
  updateTicket: vi.fn((id, data) => {
    serveur.journal.push(`PATCH-wizard ${id}`)
    serveur.tickets[id] = { ...serveur.tickets[id], ...data }
    return Promise.resolve({ data: serveur.tickets[id] })
  }),
  lienClientTicket: vi.fn(() => Promise.resolve({ data: { url: 'https://x.test/s' } })),
}))
vi.mock('../../api/axios', async () => (await import('./__testutils__/ticketDetailMocks.js')).axiosMock())
vi.mock('../../api/installationsApi', async () => (await import('./__testutils__/ticketDetailMocks.js')).installationsApiMock())

import { TicketDetail } from './TicketsPage'
import { ticketStore } from './__testutils__/ticketDetailMocks.js'

function rendre(id) {
  return render(<Provider store={ticketStore('responsable')}><MemoryRouter>
    <TicketDetail ticket={{ ...serveur.tickets[id], type: 'correctif', priorite: 'normale',
      sous_garantie: 'non', sous_garantie_effectif: 'non', couverture: 'a_determiner',
      devis_id_ext: null, facture_id_ext: null, instructions: '' }}
      onClose={() => {}} onSaved={() => {}} />
  </MemoryRouter></Provider>)
}

describe('TicketDetail — ASAV54 assistant de résolution + cause à la fiche', () => {
  it('résolution par l\'assistant, puis cause saisie sur deux fiches : un regroupement apparaît', async () => {
    const user = userEvent.setup()

    // Ticket 1 : « Résolu » ouvre l'assistant, qui enregistre cause + remède.
    rendre(1)
    await screen.findByText('Ticket SAV — SAV-1', { exact: false })
    const statut = screen.getAllByRole('combobox').find((c) => c.textContent === 'En cours')
    await user.click(statut)
    await user.click(await screen.findByRole('option', { name: 'Résolu' }))
    await user.click(screen.getByRole('button', { name: /Mettre à jour/ }))
    expect(await screen.findByText(/étape 1 sur 2/)).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('option', { name: 'Surchauffe' })).toBeInTheDocument())
    fireEvent.change(screen.getByLabelText(/Cause de la panne/), { target: { value: '11' } })
    fireEvent.change(screen.getByLabelText(/Remède appliqué/), { target: { value: '21' } })
    fireEvent.click(screen.getByRole('button', { name: 'Suivant' }))
    fireEvent.click(screen.getByRole('button', { name: 'Résoudre le ticket' }))
    await waitFor(() => expect(serveur.tickets[1].cause).toBe(11))
    expect(serveur.journal.slice(0, 2)).toEqual(['POST resoudre 1', 'PATCH-wizard 1'])
    expect(serveur.tickets[1].remede).toBe(21)
    cleanup()

    // Tickets 2 et 3 : la cause se renseigne sur la fiche.
    for (const id of [2, 3]) {
      rendre(id)
      await screen.findByText(`Ticket SAV — SAV-${id}`, { exact: false })
      await waitFor(() => expect(screen.getByRole('combobox', { name: 'Cause (fiche)' })).toBeInTheDocument())
      await user.click(screen.getByRole('combobox', { name: 'Cause (fiche)' }))
      await user.click(await screen.findByRole('option', { name: 'Surchauffe' }))
      await user.click(screen.getByRole('button', { name: /Mettre à jour/ }))
      await waitFor(() => expect(serveur.tickets[id].cause).toBe(11))
      cleanup()
    }
    expect(regroupements()).toHaveLength(1)
  }, 180000)
})
