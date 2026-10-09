import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

// ASAV52 — les listes SAV lisent TOUTES les pages. Faux serveur paginé à 50
// (comme DRF) : count = total réel, results = 50 au plus.

const paginer = (total, fabrique) => (params = {}) => {
  const page = Number(params.page ?? 1)
  const debut = (page - 1) * 50
  const results = []
  for (let i = debut + 1; i <= Math.min(total, debut + 50); i += 1) results.push(fabrique(i))
  return Promise.resolve({ data: { count: total, next: null, results } })
}

const surcharges = vi.hoisted(() => ({}))

vi.mock('../../api/savApi', () => ({
  default: new Proxy({}, {
    get: (_t, nom) => surcharges[nom] ?? (() => Promise.resolve({ data: [] })),
  }),
}))
vi.mock('../../api/stockApi', () => ({
  default: { getFournisseurs: () => Promise.resolve({ data: [] }) },
}))
vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(() => Promise.resolve({ data: [] })), post: vi.fn() },
}))

import SavAlarmesPage from './SavAlarmesPage'
import WarrantyClaimsPage from './WarrantyClaimsPage'
import SavActionBoardPage from './SavActionBoardPage'
import KbArticlesPage from './KbArticlesPage'
import SavParametresPage from './SavParametresPage'

afterEach(() => {
  cleanup()
  for (const k of Object.keys(surcharges)) delete surcharges[k]
})

const enveloppe = (ui) => render(
  <Provider store={configureStore({ reducer: { auth: (s = { role: 'responsable', permissions: [] }) => s } })}>
    <MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>
  </Provider>)

describe('ASAV52 — listes SAV lues en entier', () => {
  it('Alarmes : « 56 alarmes » et la dernière alarme est visible', async () => {
    surcharges.getAlarmes = paginer(56, (i) => ({
      id: i, code: `E${i}`, gravite: 'warning', statut: 'active', date_detection: '2026-10-01T10:00:00Z' }))
    enveloppe(<SavAlarmesPage />)
    expect(await screen.findByText('56 alarmes')).toBeInTheDocument()
    expect(screen.getByText('E56')).toBeInTheDocument()
  })

  it('Réclamations garantie : 55 réclamations', async () => {
    surcharges.getWarrantyClaims = paginer(55, (i) => ({
      id: i, equipement_produit: 'Onduleur', equipement_serie: `SN-${i}`, statut: 'ouvert',
      rma_ref: '', date_signalement: '2026-10-01', date_resolution: null }))
    enveloppe(<WarrantyClaimsPage />)
    expect(await screen.findByText('55 réclamations')).toBeInTheDocument()
  })

  it('Action requise : les références de seau au-delà de la page 1 sont résolues', async () => {
    const ids = Array.from({ length: 60 }, (_, i) => 60 - i) // 60..1 : les 20 premiers sont en page 2
    surcharges.getSavFileAction = () => Promise.resolve({ data: { buckets: {
      a_repondre: { count: 60, ids },
    } } })
    surcharges.getTickets = paginer(60, (i) => ({ id: i, reference: `SAV-${i}`, client_nom: 'C' }))
    enveloppe(<SavActionBoardPage />)
    expect(await screen.findByText(/SAV-60/)).toBeInTheDocument()
    expect(screen.queryByText(/#60\b/)).toBeNull()
  })

  it('Base de connaissances : 55 articles lus', async () => {
    surcharges.getKbArticles = paginer(55, (i) => ({
      id: i, titre: `Article ${i}`, corps: 'x', categorie: '', tags: [] }))
    enveloppe(<KbArticlesPage />)
    expect(await screen.findByText('Article 55')).toBeInTheDocument()
  })

  it('Paramètres SAV : une liste de 55 réponses types est lue en entier', async () => {
    const user = userEvent.setup()
    surcharges.getReponsesType = paginer(55, (i) => ({
      id: i, titre: `Réponse ${i}`, corps: 'x', nouveau_statut: '' }))
    enveloppe(<SavParametresPage />)
    await user.click(screen.getByRole('tab', { name: 'Réponses types' }))
    await waitFor(() => expect(screen.getByText('Réponse 55')).toBeInTheDocument())
  }, 60000)
})
