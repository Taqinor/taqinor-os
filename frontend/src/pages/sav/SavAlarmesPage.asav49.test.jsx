import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

// ASAV49 — alarme créée à l'écran escaladable : équipement choisi à la
// création (recherche serveur), escalade avec ticket existant ou ouverture
// d'un ticket, refus serveur affiché. Faux serveur appliquant la règle
// d'`escalader` : un ticket ou un équipement à client est requis.

const serveur = vi.hoisted(() => ({ alarmes: [], posts: [], escalades: [] }))

vi.mock('../../api/savApi', () => ({
  default: {
    getAlarmes: vi.fn(() => Promise.resolve({ data: serveur.alarmes.map((a) => ({ ...a })) })),
    getEquipements: vi.fn(() => Promise.resolve({ data: { results: [
      { id: 977, produit_nom: 'Onduleur Deye', numero_serie: 'SN-977' },
    ] } })),
    getTickets: vi.fn(() => Promise.resolve({ data: { results: [
      { id: 55, reference: 'SAV-55', description: 'Panne' },
    ] } })),
    acquitterAlarme: vi.fn((id) => {
      const a = serveur.alarmes.find((x) => x.id === id)
      a.statut = 'acquittee'
      return Promise.resolve({ data: a })
    }),
    escaladerAlarme: vi.fn((id, ticketId) => {
      serveur.escalades.push({ id, ticketId })
      const a = serveur.alarmes.find((x) => x.id === id)
      if (!ticketId && !a.equipement) {
        return Promise.reject({ response: { status: 400, data: {
          ticket: ["Aucun ticket fourni et l'alarme n'a pas d'équipement rattaché à un client."] } } })
      }
      a.statut = 'escaladee'
      a.ticket_reference = 'SAV-NEW'
      return Promise.resolve({ data: a })
    }),
  },
}))
vi.mock('../../api/axios', () => ({
  default: { post: vi.fn((url, body) => {
    serveur.posts.push(body)
    serveur.alarmes.push({
      id: serveur.alarmes.length + 1, code: body.code, gravite: 'warning', statut: 'active',
      equipement: body.equipement ?? null,
      equipement_produit: body.equipement ? 'Onduleur Deye' : null,
      date_detection: '2026-10-09T10:00:00Z',
    })
    return Promise.resolve({ data: {} })
  }) },
}))

import SavAlarmesPage from './SavAlarmesPage'

const rendre = () => render(
  <Provider store={configureStore({ reducer: { auth: (s = { role: 'responsable', permissions: [] }) => s } })}>
    <SavAlarmesPage />
  </Provider>)

afterEach(() => { cleanup(); serveur.alarmes.length = 0; serveur.posts.length = 0; serveur.escalades.length = 0 })

describe('SavAlarmesPage — ASAV49 alarme escaladable', () => {
  it('alarme avec équipement : créer → acquitter → escalader', async () => {
    const user = userEvent.setup()
    rendre()
    await user.click(await screen.findByRole('button', { name: /Créer une alarme/ }))
    await user.type(screen.getByPlaceholderText('ex. E07'), 'E07', { delay: null })
    await user.click(screen.getByRole('combobox', { name: "Équipement de l'alarme" }))
    await user.click(await screen.findByRole('option', { name: /Onduleur Deye — SN-977/ }))
    await user.click(screen.getByRole('button', { name: 'Créer' }))
    await waitFor(() => expect(serveur.posts).toHaveLength(1))
    expect(serveur.posts[0].equipement).toBe(977)

    await user.click(await screen.findByRole('button', { name: 'Acquitter' }))
    await waitFor(() => expect(serveur.alarmes[0].statut).toBe('acquittee'))
    await user.click(await screen.findByRole('button', { name: /Escalader/ }))
    await waitFor(() => expect(serveur.alarmes[0].statut).toBe('escaladee'))
    expect(serveur.escalades[0].ticketId).toBeUndefined()
  }, 60000)

  it('alarme sans équipement : Escalader désactivé, puis escalade avec un ticket existant', async () => {
    const user = userEvent.setup()
    serveur.alarmes.push({ id: 1, code: 'F12', gravite: 'warning', statut: 'active',
      equipement: null, date_detection: '2026-10-09T10:00:00Z' })
    rendre()
    const bouton = await screen.findByRole('button', { name: /Escalader/ })
    expect(bouton).toBeDisabled()
    expect(screen.getByText(/Aucun équipement rattaché/)).toBeInTheDocument()

    await user.click(screen.getByRole('combobox', { name: 'Ticket à relier (F12)' }))
    await user.click(await screen.findByRole('option', { name: /SAV-55/ }))
    expect(screen.getByRole('button', { name: /Escalader/ })).toBeEnabled()
    await user.click(screen.getByRole('button', { name: /Escalader/ }))
    await waitFor(() => expect(serveur.escalades).toHaveLength(1))
    expect(serveur.escalades[0].ticketId).toBe('55')
    await waitFor(() => expect(serveur.alarmes[0].statut).toBe('escaladee'))
  }, 60000)
})
