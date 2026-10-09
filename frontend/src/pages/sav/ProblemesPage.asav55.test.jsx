import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

// ASAV55 — gestes de la page Problèmes branchés : tickets liés, lier, délier,
// résoudre avec cause racine, supprimer un problème vide (confirmé). Faux
// serveur en mémoire.

const serveur = vi.hoisted(() => ({
  problemes: [
    { id: 5, reference: 'PRB-1', titre: 'Onduleur Y — Usure', statut: 'identifie',
      cause_racine: '', nb_tickets: 1, impact: 3 },
    { id: 6, reference: 'PRB-2', titre: 'Problème vide', statut: 'identifie',
      cause_racine: '', nb_tickets: 0, impact: 0 },
  ],
  liens: { 5: [{ id: 11, reference: 'SAV-0011', client: 'Bennani' }], 6: [] },
}))

vi.mock('../../api/savApi', () => ({
  default: {
    getProblemes: vi.fn(() => Promise.resolve({ data: { results: serveur.problemes.map((p) => ({
      ...p, nb_tickets: (serveur.liens[p.id] ?? []).length })) } })),
    getRegroupementsSuggeres: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    getProblemeTickets: vi.fn((id) => Promise.resolve({ data: { results: [...(serveur.liens[id] ?? [])] } })),
    lierTicketProbleme: vi.fn((id, ticket) => {
      serveur.liens[id] = [...(serveur.liens[id] ?? []), { id: ticket, reference: `SAV-00${ticket}`, client: 'X' }]
      return Promise.resolve({ data: {} })
    }),
    delierTicketProbleme: vi.fn((id, ticket) => {
      serveur.liens[id] = serveur.liens[id].filter((t) => t.id !== ticket)
      return Promise.resolve({ data: {} })
    }),
    saveProbleme: vi.fn((id, data) => {
      serveur.problemes = serveur.problemes.map((p) => (p.id === id ? { ...p, ...data } : p))
      return Promise.resolve({ data: serveur.problemes.find((p) => p.id === id) })
    }),
    deleteProbleme: vi.fn((id) => {
      serveur.problemes = serveur.problemes.filter((p) => p.id !== id)
      return Promise.resolve({ data: {} })
    }),
  },
}))

import ProblemesPage from './ProblemesPage'

afterEach(cleanup)

const monter = () => render(
  <Provider store={configureStore({ reducer: {
    auth: (s = { role: 'responsable', permissions: ['sav_probleme_gerer'] }) => s,
  } })}><ProblemesPage /></Provider>)

describe('ProblemesPage — ASAV55 gestes d\'un problème', () => {
  it('consulter, lier, délier, résoudre avec cause racine', async () => {
    monter()
    fireEvent.click((await screen.findAllByRole('button', { name: 'Gérer' }))[0])
    expect(await screen.findByText('SAV-0011 — Bennani')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('N° du ticket à lier'), { target: { value: '12' } })
    fireEvent.click(screen.getByRole('button', { name: 'Lier un ticket' }))
    expect(await screen.findByText('SAV-0012 — X')).toBeInTheDocument()
    expect(serveur.liens[5]).toHaveLength(2)

    fireEvent.click(screen.getByRole('button', { name: 'Délier SAV-0011' }))
    await waitFor(() => expect(serveur.liens[5]).toHaveLength(1))

    fireEvent.change(screen.getByLabelText('Statut du problème'), { target: { value: 'resolu' } })
    fireEvent.change(screen.getByLabelText('Cause racine'), { target: { value: 'Ventilateur HS' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le problème' }))
    await waitFor(() => expect(serveur.problemes[0].statut).toBe('resolu'))
    expect(serveur.problemes[0].cause_racine).toBe('Ventilateur HS')
  })

  it('supprime un problème vide après confirmation', async () => {
    monter()
    fireEvent.click((await screen.findAllByRole('button', { name: 'Gérer' }))[1])
    fireEvent.click(await screen.findByRole('button', { name: 'Supprimer ce problème' }))
    expect(serveur.problemes).toHaveLength(2) // pas de suppression sans confirmation
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer la suppression' }))
    await waitFor(() => expect(serveur.problemes).toHaveLength(1))
  })
})
