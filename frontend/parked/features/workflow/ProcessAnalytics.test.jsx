import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

const mocks = vi.hoisted(() => ({
  listDefinitions: vi.fn(),
  getAnalyse: vi.fn(),
}))

vi.mock('../../api/coreApi', () => ({
  default: {
    workflowDefinitions: { list: mocks.listDefinitions },
    workflowAnalyse: { get: mocks.getAnalyse },
  },
}))

import ProcessAnalytics from './ProcessAnalytics'

const DEFINITIONS = [
  { id: 1, nom: 'Validation devis' },
  { id: 2, nom: 'Onboarding grand compte' },
]

const ANALYSE = {
  definition_id: 1,
  definition_code: 'validation_devis',
  definition_nom: 'Validation devis',
  periode: null,
  nb_instances: 12,
  goulot_ordre: 2,
  etapes: [
    {
      step_def_id: 10, ordre: 1, nom: 'Vérification technique', nb_decisions: 8,
      duree_moyenne_h: 2.5, duree_mediane_h: 2.0, duree_p90_h: 4.0,
      taux_rejet: 0.125, taux_escalade: 0, goulot: false,
    },
    {
      step_def_id: 11, ordre: 2, nom: 'Validation direction', nb_decisions: 8,
      duree_moyenne_h: 30.0, duree_mediane_h: 28.0, duree_p90_h: 48.0,
      taux_rejet: 0.25, taux_escalade: 0.375, goulot: true,
    },
  ],
}

describe('ProcessAnalytics (NTWFL24)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.listDefinitions.mockResolvedValue({ data: DEFINITIONS })
    mocks.getAnalyse.mockResolvedValue({ data: ANALYSE })
  })

  it('liste les définitions disponibles', async () => {
    render(<ProcessAnalytics />)
    fireEvent.click(await screen.findByLabelText('Définition'))
    expect(await screen.findByRole('option', { name: 'Validation devis' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Onboarding grand compte' })).toBeInTheDocument()
  })

  it('affiche le détail par étape et surligne le goulot', async () => {
    render(<ProcessAnalytics />)
    fireEvent.click(await screen.findByLabelText('Définition'))
    fireEvent.click(await screen.findByRole('option', { name: 'Validation devis' }))

    await waitFor(() => expect(mocks.getAnalyse).toHaveBeenCalledWith('1', undefined))
    expect(await screen.findByText('Vérification technique')).toBeInTheDocument()
    expect(screen.getByText('Validation direction')).toBeInTheDocument()
    expect(screen.getByText('Goulot')).toBeInTheDocument()
    expect(screen.getByText('13 %')).toBeInTheDocument() // taux_rejet étape 1 (0.125 -> arrondi)
    expect(screen.getByText('38 %')).toBeInTheDocument() // taux_escalade étape 2 (0.375 -> arrondi)
  })

  it('transmet la période choisie au format AAAA-MM', async () => {
    render(<ProcessAnalytics />)
    fireEvent.click(await screen.findByLabelText('Définition'))
    fireEvent.click(await screen.findByRole('option', { name: 'Validation devis' }))
    await waitFor(() => expect(mocks.getAnalyse).toHaveBeenCalled())
    mocks.getAnalyse.mockClear()

    fireEvent.change(screen.getByLabelText(/Période/), { target: { value: '2026-08' } })
    await waitFor(() => expect(mocks.getAnalyse).toHaveBeenCalledWith('1', '2026-08'))
  })

  it("affiche un état vide sans définition sélectionnée", () => {
    render(<ProcessAnalytics />)
    expect(screen.getByText('Aucune définition sélectionnée')).toBeInTheDocument()
  })
})
