import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* PUB42 — file « Aujourd'hui » unifiée : écran d'accueil /publicite, déjà
   classée par priorité côté backend (garde-fous > alertes > approbations >
   commentaires > digest) — l'écran affiche l'ordre reçu SANS le retrier. */

const mocks = vi.hoisted(() => ({ today: vi.fn(), syncStatus: vi.fn() }))

vi.mock('./adsengineApi', () => ({
  default: {
    today: { get: mocks.today },
    syncStatus: { get: mocks.syncStatus },
  },
}))

import TodayScreen from './TodayScreen'

const renderScreen = () => render(<MemoryRouter><TodayScreen /></MemoryRouter>)

const ITEMS = [
  { id: 'garde_fou-1', categorie: 'garde_fou', categorie_label: 'Garde-fou',
    titre: 'Violation de garde-fou', detail: 'Plafond quotidien dépassé.',
    lien: '/publicite/tableau-de-bord', quand: '2026-07-19T08:00:00Z' },
  { id: 'approbation-11', categorie: 'approbation', categorie_label: 'Approbation',
    titre: 'Ajustement de budget', detail: 'CPL en baisse.',
    lien: '/publicite/approbations', quand: '2026-07-19T07:30:00Z' },
  { id: 'commentaire-5', categorie: 'commentaire', categorie_label: 'Commentaire',
    titre: 'Karim B.', detail: 'Combien coûte l’installation ?',
    lien: '/publicite/commentaires', quand: '2026-07-19T06:00:00Z' },
  { id: 'digest-3', categorie: 'digest', categorie_label: 'Digest',
    titre: 'Brief hebdomadaire', detail: '90 MAD/signature (cumulé)',
    lien: '/publicite/brief', quand: '2026-07-19T05:00:00Z' },
]

beforeEach(() => {
  vi.clearAllMocks()
  mocks.today.mockResolvedValue({ data: { items: ITEMS, total: ITEMS.length } })
  mocks.syncStatus.mockResolvedValue({ data: { types: [], stale: false, worst: null } })
})

describe('TodayScreen (PUB42)', () => {
  it('affiche la file dans l’ordre reçu (jamais retriée côté front)', async () => {
    renderScreen()
    const rows = await screen.findAllByTestId('ae-today-item')
    expect(rows).toHaveLength(4)
    expect(rows[0]).toHaveAttribute('data-categorie', 'garde_fou')
    expect(rows[1]).toHaveAttribute('data-categorie', 'approbation')
    expect(rows[2]).toHaveAttribute('data-categorie', 'commentaire')
    expect(rows[3]).toHaveAttribute('data-categorie', 'digest')
  })

  it('chaque item est cliquable vers SON écran', async () => {
    renderScreen()
    const rows = await screen.findAllByTestId('ae-today-item')
    expect(rows[0]).toHaveAttribute('href', '/publicite/tableau-de-bord')
    expect(rows[1]).toHaveAttribute('href', '/publicite/approbations')
    expect(rows[2]).toHaveAttribute('href', '/publicite/commentaires')
    expect(rows[3]).toHaveAttribute('href', '/publicite/brief')
  })

  it('montre le titre, le détail et le badge de catégorie de chaque item', async () => {
    renderScreen()
    await screen.findAllByTestId('ae-today-item')
    expect(screen.getByText('Violation de garde-fou')).toBeInTheDocument()
    expect(screen.getByText('Plafond quotidien dépassé.')).toBeInTheDocument()
    const badges = screen.getAllByTestId('ae-today-item-badge')
    expect(badges[0]).toHaveTextContent('Garde-fou')
  })

  it('file vide -> message dédié (pas une erreur, rien à faire)', async () => {
    mocks.today.mockResolvedValue({ data: { items: [], total: 0 } })
    renderScreen()
    expect(await screen.findByTestId('ae-today-empty')).toHaveTextContent('Rien à traiter')
  })

  it('panne réseau -> message d’erreur, PAS le message « rien à traiter »', async () => {
    mocks.today.mockRejectedValue(new Error('network'))
    renderScreen()
    expect(await screen.findByTestId('ae-today-load-error')).toBeInTheDocument()
    expect(screen.queryByTestId('ae-today-empty')).toBeNull()
  })

  it('charge la file au montage', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.today).toHaveBeenCalled())
  })
})
