import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const mocks = vi.hoisted(() => ({ tableauMarches: vi.fn() }))

vi.mock('../../api/aoApi', () => ({
  default: { tableauMarches: mocks.tableauMarches },
}))

import DashboardPage from './DashboardPage'

const renderScreen = () => render(<MemoryRouter><DashboardPage /></MemoryRouter>)

const PAYLOAD = {
  ao_en_cours: 7,
  taux_reussite: 42.5,
  cautions_immobilisees: 250000,
  marches_en_execution: 3,
  capacite_vs_engagement: '12/15 équipes',
  echeances_dues: [
    { id: 1, libelle: 'Remise des plis', date_echeance: '2026-08-10', affaire_id: 5, affaire_reference: 'AO-2026-005' },
    { id: 2, libelle: 'Ouverture des plis', date_echeance: '2026-08-20', affaire_id: 6, affaire_reference: 'AO-2026-006' },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.tableauMarches.mockResolvedValue({ data: PAYLOAD })
})

describe('DashboardPage', () => {
  it('charge le tableau de bord via UN SEUL appel agrégé (aoApi.tableauMarches)', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.tableauMarches).toHaveBeenCalledTimes(1))
    expect(await screen.findByText('AO en cours')).toBeInTheDocument()
  })

  it('affiche les 5 KPI lus TELS QUELS du payload agrégé (aucun calcul côté front)', async () => {
    renderScreen()
    await screen.findByText('AO en cours')
    expect(screen.getByText('7')).toBeInTheDocument()
    expect(screen.getByText('43 %')).toBeInTheDocument() // Math.round(42.5) = 43 (arrondi d'affichage, pas un calcul de KPI)
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('12/15 équipes')).toBeInTheDocument()
  })

  it('le centre d’échéances est alimenté par le MÊME appel agrégé (echeances_dues), aucune seconde requête', async () => {
    renderScreen()
    await screen.findByText('AO en cours')
    expect(screen.getByText('Remise des plis')).toBeInTheDocument()
    expect(screen.getByText('Ouverture des plis')).toBeInTheDocument()
    expect(mocks.tableauMarches).toHaveBeenCalledTimes(1)
  })
})

// ── Garde de source : seuils d'urgence via ui/module/urgency.js, jamais une
//    constante locale (Done AOF172). ────────────────────────────────────────
describe('DashboardPage.jsx — contrat de source', () => {
  const here = dirname(fileURLToPath(import.meta.url))
  const src = readFileSync(join(here, 'DashboardPage.jsx'), 'utf8')

  it('utilise EcheanceCenter (qui porte lui-même urgency.js) — aucun seuil de jours codé en dur ici', () => {
    expect(src).toMatch(/EcheanceCenter/)
    expect(src).not.toMatch(/urgencyLevel|urgencyTone|urgencyLabel|daysUntil/)
    expect(src).not.toMatch(/\bJ-\d/)
  })

  it('un seul appel réseau agrégé (aoApi.tableauMarches), jamais un axios.get direct', () => {
    expect(src).toMatch(/aoApi\.tableauMarches\(\)/)
    expect(src).not.toMatch(/axios\.get/)
  })
})
