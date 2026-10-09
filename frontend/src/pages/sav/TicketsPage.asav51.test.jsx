import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

// ASAV51 — le catalogue de 102 produits est servi paginé à 50 : le 102e doit
// se choisir dans « Retirer une pièce » de la fiche ticket.

const serveur = vi.hoisted(() => ({ corps: [], pagesLues: [] }))

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
    getTicketPiecesUnifiees: vi.fn(() => Promise.resolve({
      data: { lignes: [], sous_totaux: { ajout: 0, retrait: 0, recyclage: 0 } } })),
    retirerTicketPiece: vi.fn((id, body) => { serveur.corps.push(body); return Promise.resolve({ data: {} }) }),
    getTicketsSimilaires: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    getTriageIa: vi.fn(() => Promise.resolve({ data: { disponible: false } })),
    getPretsEquipement: vi.fn(() => Promise.resolve({ data: [] })),
    getReponsesType: vi.fn(() => Promise.resolve({ data: [] })),
    getTicketChecklist: vi.fn(() => Promise.resolve({ data: [] })),
    getChecklistTemplates: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))
vi.mock('../../api/axios', () => ({
  default: { get: vi.fn((url, cfg) => {
    if (url !== '/stock/produits/') return Promise.resolve({ data: [] })
    const page = Number(cfg?.params?.page ?? 1)
    serveur.pagesLues.push(page)
    const results = []
    for (let i = (page - 1) * 50 + 1; i <= Math.min(102, page * 50); i += 1) {
      results.push({ id: i, nom: `Produit ${i}`, sku: `P${i}` })
    }
    return Promise.resolve({ data: { count: 102, next: null, results } })
  }) },
}))
vi.mock('../../api/installationsApi', () => ({
  default: { getInterventions: vi.fn(() => Promise.resolve({ data: [] })) },
}))

import { TicketDetail } from './TicketsPage'

describe('TicketDetail — ASAV51 catalogue complet', () => {
  it('le 102e produit se choisit dans « Retirer une pièce »', async () => {
    const user = userEvent.setup()
    const store = configureStore({ reducer: {
      tickets: (state = { items: [] }) => state,
      auth: (state = { role: 'admin', permissions: [] }) => state,
    } })
    render(<Provider store={store}><MemoryRouter>
      <TicketDetail ticket={{ id: 1, reference: 'SAV-1', statut: 'en_cours', type: 'correctif',
        priorite: 'normale', sous_garantie: 'non', sous_garantie_effectif: 'non',
        couverture: 'a_determiner', devis_id_ext: null, facture_id_ext: null, instructions: '' }}
        onClose={() => {}} onSaved={() => {}} />
    </MemoryRouter></Provider>)
    await waitFor(() => expect(serveur.pagesLues).toEqual(expect.arrayContaining([1, 2, 3])))
    await user.click(screen.getByRole('combobox', { name: 'Produit à retirer' }))
    await user.click(await screen.findByText('Produit 102 (P102)'))
    await user.click(screen.getByRole('button', { name: /Retirer une pièce/ }))
    await waitFor(() => expect(serveur.corps).toHaveLength(1))
    expect(serveur.corps[0].produit).toBe('102')
  }, 60000)
})
