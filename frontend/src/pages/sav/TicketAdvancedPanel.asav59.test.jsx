import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

// ASAV59 — après « Fusionner un ticket doublon », la fiche du principal se
// recharge (pièces du doublon visibles) et la liste est prévenue (onSaved).
// Faux serveur qui applique la fusion : les pièces du doublon passent au
// principal, le doublon est annulé.

const serveur = vi.hoisted(() => ({
  pieces: [{ id: 1, produit_nom: 'Fusible 10A', quantite: '1' }],
  doublonAnnule: false,
}))

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
    getTicket: vi.fn(() => Promise.resolve({ data: {
      id: 1, reference: 'SAV-1', statut: 'en_cours', type: 'correctif', priorite: 'normale',
      sous_garantie: 'non', sous_garantie_effectif: 'non', couverture: 'a_determiner',
      devis_id_ext: null, facture_id_ext: null, instructions: '' } })),
    fusionnerTicket: vi.fn(() => {
      serveur.pieces = [...serveur.pieces, { id: 2, produit_nom: 'Câble MC4 (du doublon)', quantite: '2' }]
      serveur.doublonAnnule = true
      return Promise.resolve({ data: {} })
    }),
    getTicketPieces: vi.fn(() => Promise.resolve({ data: serveur.pieces.map((p) => ({ ...p })) })),
    getTicketHistorique: vi.fn(() => Promise.resolve({ data: [] })),
    getEquipements: vi.fn(() => Promise.resolve({ data: [] })),
    getTicketsSimilaires: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    getTriageIa: vi.fn(() => Promise.resolve({ data: { disponible: false } })),
    getPretsEquipement: vi.fn(() => Promise.resolve({ data: [] })),
    getReponsesType: vi.fn(() => Promise.resolve({ data: [] })),
    getTicketChecklist: vi.fn(() => Promise.resolve({ data: [] })),
    getChecklistTemplates: vi.fn(() => Promise.resolve({ data: [] })),
    getTicketPiecesUnifiees: vi.fn(() => Promise.resolve({
      data: { lignes: [], sous_totaux: { ajout: 0, retrait: 0, recyclage: 0 } } })),
  },
}))
vi.mock('../../api/axios', () => ({ default: { get: vi.fn(() => Promise.resolve({ data: [] })) } }))
vi.mock('../../api/installationsApi', () => ({
  default: { getInterventions: vi.fn(() => Promise.resolve({ data: [] })) },
}))

import { TicketDetail } from './TicketsPage'

describe('TicketDetail — ASAV59 rechargement après fusion', () => {
  it('les pièces du doublon apparaissent et la liste est prévenue', async () => {
    const onSaved = vi.fn()
    const store = configureStore({ reducer: {
      tickets: (state = { items: [] }) => state,
      auth: (state = { role: 'responsable', permissions: [] }) => state,
    } })
    render(<Provider store={store}><MemoryRouter>
      <TicketDetail ticket={{ id: 1, reference: 'SAV-1', statut: 'en_cours', type: 'correctif',
        priorite: 'normale', sous_garantie: 'non', sous_garantie_effectif: 'non',
        couverture: 'a_determiner', devis_id_ext: null, facture_id_ext: null, instructions: '' }}
        onClose={() => {}} onSaved={onSaved} />
    </MemoryRouter></Provider>)
    expect(await screen.findByText(/Fusible 10A/)).toBeInTheDocument()
    fireEvent.change(screen.getByPlaceholderText('ID du ticket doublon'), { target: { value: '2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Fusionner' }))
    expect(await screen.findByText(/Câble MC4 \(du doublon\)/)).toBeInTheDocument()
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
    expect(serveur.doublonAnnule).toBe(true)
  }, 60000)
})
