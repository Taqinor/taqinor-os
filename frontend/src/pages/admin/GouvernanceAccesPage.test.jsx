import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '../../design/ThemeProvider'

/* WIR135 — l'écran Gouvernance des accès lance une campagne, atteste/révoque un
   item, liste les règles SoD + violations, et lit le rapport de certification. */

const H = vi.hoisted(() => ({
  campList: vi.fn(() => Promise.resolve({ data: [
    { id: 1, nom: 'Q3 2026', statut: 'ouverte', items: [
      // Forme serveur : accessreview.services.generate_items fige un objet.
      { id: 10, user: 5, role_snapshot: { role_id: 3, role_nom: 'Commercial' }, decision: 'en_attente' },
    ] },
  ] })),
  campGet: vi.fn(() => Promise.resolve({ data: { id: 1, nom: 'Q3 2026', statut: 'ouverte', items: [
    { id: 10, user: 5, role_snapshot: { role_id: 3, role_nom: 'Commercial' }, decision: 'revoque' },
  ] } })),
  campCreate: vi.fn(() => Promise.resolve({ data: { id: 2 } })),
  attester: vi.fn(() => Promise.resolve({ data: {} })),
  sodList: vi.fn(() => Promise.resolve({ data: [] })),
  sodViolations: vi.fn(() => Promise.resolve({ data: [{ user: 5, libelle: 'Achat ⊗ Paiement' }] })),
  sodCreate: vi.fn(() => Promise.resolve({ data: {} })),
  revueAcces: vi.fn(() => Promise.resolve({ data: [{ username: 'sami', role: 'Commercial', last_login: '2026-07-01T09:00:00Z' }] })),
}))
vi.mock('../../api/accessReviewApi', () => ({
  default: {
    campaigns: { list: H.campList, get: H.campGet, create: H.campCreate, remove: vi.fn(), attester: H.attester },
    sodRules: { list: H.sodList, create: H.sodCreate, remove: vi.fn(), violations: H.sodViolations, seedStandard: vi.fn() },
    revueAcces: H.revueAcces, revueAccesCsv: vi.fn(),
  },
}))

import GouvernanceAccesPage from './GouvernanceAccesPage'

const renderPage = () => render(<ThemeProvider><GouvernanceAccesPage /></ThemeProvider>)

beforeEach(() => Object.values(H).forEach((f) => f.mockClear()))
afterEach(() => cleanup())

describe('WIR135 GouvernanceAccesPage', () => {
  it('monte l’écran et liste les campagnes', async () => {
    renderPage()
    expect(screen.getByText('Gouvernance des accès')).toBeInTheDocument()
    await waitFor(() => expect(H.campList).toHaveBeenCalled())
    expect(await screen.findByText('Q3 2026')).toBeInTheDocument()
  })

  it('révoque un item de campagne (retire le rôle via le serveur)', async () => {
    renderPage()
    fireEvent.click(await screen.findByText('Q3 2026'))
    // Le rôle figé s'affiche par son libellé (jamais l'objet brut : React #31).
    expect(await screen.findByText('Commercial')).toBeInTheDocument()
    fireEvent.click(await screen.findByText('Révoquer'))
    await waitFor(() => expect(H.attester).toHaveBeenCalledWith(1,
      expect.objectContaining({ item: 10, decision: 'revoque' })))
  })

  it('affiche les violations SoD', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(screen.getByRole('tab', { name: /Règles SoD/ }))
    await waitFor(() => expect(H.sodViolations).toHaveBeenCalled())
    expect(await screen.findByText(/Achat ⊗ Paiement/)).toBeInTheDocument()
  })

  it('lit le rapport de certification', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(screen.getByRole('tab', { name: /Rapport/ }))
    await waitFor(() => expect(H.revueAcces).toHaveBeenCalled())
    expect(await screen.findByText('sami')).toBeInTheDocument()
  })
})
