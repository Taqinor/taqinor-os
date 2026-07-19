import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR124 — les 4 onglets d'Inspections (ITP, Audits, Procédures qualité, Retours
   client) étaient lecture seule alors que le backend est complet. On vérifie que
   chaque onglet expose désormais une action d'écriture, et que le chemin de
   création d'une procédure fonctionne de bout en bout. Réseau mocké. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
  if (typeof Element.prototype.hasPointerCapture === 'undefined') {
    Element.prototype.hasPointerCapture = () => false
  }
  if (typeof Element.prototype.scrollIntoView === 'undefined') {
    Element.prototype.scrollIntoView = () => {}
  }
})

const { empty, procedureCreate } = vi.hoisted(() => ({
  empty: () => Promise.resolve({ data: [] }),
  procedureCreate: vi.fn(() => Promise.resolve({ data: { id: 5 } })),
}))

vi.mock('../../api/qhseApi', () => ({
  default: {
    plansInspection: { list: empty },
    plansChantier: { list: empty, instancier: vi.fn(() => Promise.resolve({ data: {} })) },
    releves: { list: empty },
    grillesAudit: { list: empty, create: vi.fn() },
    audits: { list: empty, create: vi.fn(), calculerScore: vi.fn(), leverNcr: vi.fn() },
    notationsFinChantier: { list: empty },
    proceduresQualite: { list: empty, create: (...a) => procedureCreate(...a), activer: vi.fn() },
    retoursClient: {
      list: empty,
      create: vi.fn(),
      moyenne: () => Promise.resolve({ data: { moyenne: 4.2, total: 3 } }),
    },
  },
}))

import Inspections from './Inspections'

function withProviders(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

beforeEach(() => { vi.clearAllMocks() })

describe('Inspections — actions d\'écriture (WIR124)', () => {
  it('l\'onglet ITP propose d\'instancier un plan', async () => {
    withProviders(<Inspections />)
    await waitFor(() => expect(screen.getByRole('button', { name: /Instancier un plan/ })).toBeTruthy())
  })

  it('l\'onglet Audits propose de créer une grille et démarrer un audit', async () => {
    const user = userEvent.setup()
    withProviders(<Inspections />)
    await user.click(screen.getByRole('tab', { name: 'Audits' }))
    await waitFor(() => expect(screen.getByRole('button', { name: /Nouvelle grille/ })).toBeTruthy())
    expect(screen.getByRole('button', { name: /Démarrer un audit/ })).toBeTruthy()
  })

  it('l\'onglet Fin de chantier affiche la moyenne et permet de créer une procédure', async () => {
    const user = userEvent.setup()
    withProviders(<Inspections />)
    await user.click(screen.getByRole('tab', { name: 'Fin de chantier' }))

    await waitFor(() => expect(screen.getByTestId('retours-moyenne')).toBeTruthy())
    expect(screen.getByText(/4\.2\/5/)).toBeTruthy()

    await user.click(screen.getByRole('button', { name: /Nouvelle procédure/ }))
    await waitFor(() => expect(screen.getByText('Nouvelle procédure qualité')).toBeTruthy())

    fireEvent.change(screen.getByLabelText('Référence'), { target: { value: 'PQ-001' } })
    fireEvent.change(screen.getByLabelText('Titre'), { target: { value: 'Contrôle pose' } })
    await user.click(screen.getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(procedureCreate).toHaveBeenCalledWith(
      expect.objectContaining({ reference: 'PQ-001', titre: 'Contrôle pose', version: 1 }),
    ))
  })

  it('l\'onglet Fin de chantier propose de créer un retour client', async () => {
    const user = userEvent.setup()
    withProviders(<Inspections />)
    await user.click(screen.getByRole('tab', { name: 'Fin de chantier' }))
    await waitFor(() => expect(screen.getByRole('button', { name: /Nouveau retour/ })).toBeTruthy())
  })
})
