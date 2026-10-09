import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

// ASAV53 — plus de garde locale « Stock insuffisant » : le serveur (ERR80)
// décide. Faux serveur qui applique ERR80 sur SON stock : pièce compatible
// 900 (stock 5, absente de la liste produits chargée) acceptée ; pièce 7
// (stock 0) refusée en 400 avec le message du serveur.

const serveur = vi.hoisted(() => ({ stock: { 900: 5, 7: 0 }, pieces: [], appels: 0 }))

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
    getTicketPieces: vi.fn(() => Promise.resolve({ data: serveur.pieces })),
    getEquipements: vi.fn(() => Promise.resolve({ data: [] })),
    getPiecesCompatibles: vi.fn(() => Promise.resolve({
      data: { results: [{ piece_id: 900, nom: 'Ventilateur', sku: 'VENT' }] } })),
    addTicketPiece: vi.fn((id, body) => {
      serveur.appels += 1
      const pid = Number(body.produit)
      const qte = Number(body.quantite)
      if (body.decrement && (serveur.stock[pid] ?? 0) < qte) {
        return Promise.reject({ response: { status: 400, data: {
          detail: `Stock insuffisant (ERR80) : ${serveur.stock[pid] ?? 0} disponible.` } } })
      }
      if (body.decrement) serveur.stock[pid] -= qte
      serveur.pieces.push({ id: serveur.pieces.length + 1, produit_nom: pid === 900 ? 'Ventilateur' : 'Autre', quantite: body.quantite })
      return Promise.resolve({ data: {}, status: 201 })
    }),
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
vi.mock('../../api/axios', () => ({
  default: { get: vi.fn((url) => Promise.resolve({
    // La liste produits chargée ne contient PAS la pièce 900 et donne 0 au 7.
    data: url === '/stock/produits/' ? [{ id: 7, nom: 'Autre', sku: 'AUT', quantite_stock: 0 }] : [] })) },
}))
vi.mock('../../api/installationsApi', () => ({
  default: { getInterventions: vi.fn(() => Promise.resolve({ data: [] })) },
}))

import { TicketDetail } from './TicketsPage'

function rendre() {
  const store = configureStore({ reducer: {
    tickets: (state = { items: [] }) => state,
    auth: (state = { role: 'admin', permissions: [] }) => state,
  } })
  return render(<Provider store={store}><MemoryRouter>
    <TicketDetail ticket={{ id: 1, reference: 'SAV-1', statut: 'en_cours', type: 'correctif',
      priorite: 'normale', sous_garantie: 'non', sous_garantie_effectif: 'non',
      couverture: 'a_determiner', devis_id_ext: null, facture_id_ext: null, instructions: '' }}
      onClose={() => {}} onSaved={() => {}} />
  </MemoryRouter></Provider>)
}

describe('TicketDetail — ASAV53 garde de stock côté serveur', () => {
  it('pièce compatible absente de la liste : appel serveur, acceptée ; pièce à 0 : message ERR80 du serveur', async () => {
    const user = userEvent.setup()
    rendre()
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Produit de la pièce' })).toBeInTheDocument())
    await user.click(screen.getByRole('checkbox'))

    await user.click(screen.getByRole('combobox', { name: 'Produit de la pièce' }))
    await user.click(await screen.findByText(/★ Ventilateur/))
    await user.click(screen.getByRole('button', { name: /Ajouter la pièce/ }))
    await waitFor(() => expect(serveur.pieces).toHaveLength(1))
    expect(serveur.stock[900]).toBe(4)

    await user.click(screen.getByRole('checkbox'))
    await user.click(screen.getByRole('combobox', { name: 'Produit de la pièce' }))
    await user.click(await screen.findByText('Autre (AUT)'))
    await user.click(screen.getByRole('button', { name: /Ajouter la pièce/ }))
    expect(await screen.findByText(/Stock insuffisant \(ERR80\)/)).toBeInTheDocument()
    expect(serveur.appels).toBe(2)
  }, 90000)
})
