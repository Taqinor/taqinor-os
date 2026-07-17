import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* NTAGR12 — écran « Main d'œuvre & Matériel » : onglet pointage (saisie
   rapide) + onglet matériel (heures moteur cumulées). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

vi.mock('../../api/agricultureApi', () => ({
  default: {
    pointages: {
      list: () => Promise.resolve({
        data: [{
          id: 1, date: '2026-06-10', travailleur_nom: 'Fatima Z.',
          tache: 'Récolte', nombre_journees: '5.0', taux_journalier_mad: '90.00',
        }],
      }),
      create: vi.fn(() => Promise.resolve({ data: { id: 2 } })),
    },
    equipesSaisonnieres: { list: () => Promise.resolve({ data: [{ id: 1, nom: 'Équipe A' }] }) },
    campagnes: { list: () => Promise.resolve({ data: [{ id: 7, culture: 'Tomate' }] }) },
    parcelles: { list: () => Promise.resolve({ data: [{ id: 3, nom: 'Parcelle 1' }] }) },
    materiels: {
      list: () => Promise.resolve({
        data: [{
          id: 4, nom: 'Tracteur MF 1', type_materiel: 'tracteur',
          type_materiel_display: 'Tracteur', numero_serie: 'SN-01',
          heures_moteur: '12.5',
        }],
      }),
    },
    utilisationsMateriel: { create: vi.fn(() => Promise.resolve({ data: { id: 5 } })) },
  },
}))

import RessourcesPage from './RessourcesPage'

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('RessourcesPage (NTAGR12)', () => {
  it('affiche le pointage journalier par défaut', async () => {
    withProviders(<RessourcesPage />)
    await waitFor(() => expect(screen.getAllByText('Fatima Z.').length).toBeGreaterThan(0))
    expect(screen.getAllByText('Récolte').length).toBeGreaterThan(0)
  })

  it('bascule sur l’onglet Matériel et affiche les heures moteur', async () => {
    const user = userEvent.setup()
    withProviders(<RessourcesPage />)
    await waitFor(() => expect(screen.getAllByText('Fatima Z.').length).toBeGreaterThan(0))

    await user.click(screen.getByRole('tab', { name: 'Matériel' }))
    await waitFor(() => expect(screen.getAllByText('Tracteur MF 1').length).toBeGreaterThan(0))
    expect(screen.getAllByText('12.5 h').length).toBeGreaterThan(0)
  })

  it('ouvre le formulaire de nouveau pointage', async () => {
    const user = userEvent.setup()
    withProviders(<RessourcesPage />)
    await waitFor(() => expect(screen.getAllByText('Fatima Z.').length).toBeGreaterThan(0))

    await user.click(screen.getByRole('button', { name: /Nouveau pointage/ }))
    expect(await screen.findByText('Nouveau pointage')).toBeInTheDocument()
  })
})
