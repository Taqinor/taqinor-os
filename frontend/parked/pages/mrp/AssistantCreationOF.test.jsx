// NTMFG26 — Assistant de création d'Ordre de Fabrication en 3 étapes.
// Test e2e léger (vitest + Testing Library) : le wizard crée un OF sans
// passer par le formulaire technique brut, avertit sans bloquer si la
// charge atelier est saturée, et reste annulable à toute étape (aucun
// appel d'écriture avant le clic final « Créer l'OF »).
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const {
  getGammes, simulerCharge, mrpRun, createOrdreFabrication,
} = vi.hoisted(() => ({
  getGammes: vi.fn(() => Promise.resolve({ data: [] })),
  simulerCharge: vi.fn(() => Promise.resolve({ data: { tenable: 'tenable', poste_goulot: null, retard_jours: 0 } })),
  mrpRun: vi.fn(() => Promise.resolve({ data: [] })),
  createOrdreFabrication: vi.fn(() => Promise.resolve({ data: { id: 42, statut: 'brouillon' } })),
}))

vi.mock('../../api/mrpApi', () => ({
  default: { getGammes, simulerCharge, mrpRun, createOrdreFabrication },
}))

const { getProduits } = vi.hoisted(() => ({
  getProduits: vi.fn(() => Promise.resolve({
    data: { results: [{ id: 7, nom: 'Sous-ensemble électrique' }] },
  })),
}))

vi.mock('../../api/stockApi', () => ({
  default: { getProduits },
}))

import AssistantCreationOF from './AssistantCreationOF'

function renderWizard() {
  return render(
    <MemoryRouter>
      <AssistantCreationOF />
    </MemoryRouter>,
  )
}

beforeEach(() => { vi.clearAllMocks() })

describe('AssistantCreationOF (NTMFG26)', () => {
  it('affiche les 3 étapes et bloque « Suivant » tant qu’aucun produit n’est choisi', () => {
    renderWizard()
    expect(screen.getByText('1. Produit')).toBeInTheDocument()
    expect(screen.getByText('2. Gamme & quantité')).toBeInTheDocument()
    expect(screen.getByText('3. Confirmation')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Suivant/ })).toBeDisabled()
  })

  it('crée un OF en 3 étapes sans passer par le formulaire brut, sans écriture avant la validation finale', async () => {
    const user = userEvent.setup()
    renderWizard()

    // Étape 1 — recherche + choix du produit.
    await user.click(screen.getByRole('combobox'))
    await user.type(screen.getByRole('searchbox'), 'sous')
    const option = await screen.findByRole('option', { name: /Sous-ensemble électrique/ })
    await user.click(option)
    expect(createOrdreFabrication).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: /Suivant/ }))

    // Étape 2 — quantité par défaut (1) suffit ; passe à l'étape 3.
    await user.click(screen.getByRole('button', { name: /Suivant/ }))
    await waitFor(() => expect(simulerCharge).toHaveBeenCalled())
    await waitFor(() => expect(mrpRun).toHaveBeenCalled())
    // Aucune écriture avant le clic final.
    expect(createOrdreFabrication).not.toHaveBeenCalled()

    // Étape 3 — validation finale : seul ce clic appelle la création (NTMFG3).
    await user.click(await screen.findByRole('button', { name: /Créer l'OF/ }))
    await waitFor(() => expect(createOrdreFabrication).toHaveBeenCalledWith(
      expect.objectContaining({ produit: '7', quantite: '1' }),
    ))
    expect(await screen.findByText(/OF-42 créé \(brouillon\)/)).toBeInTheDocument()
  })

  it('affiche un avertissement non bloquant si le poste est saturé, sans empêcher la création', async () => {
    simulerCharge.mockResolvedValue({
      data: { tenable: 'tenable_avec_retard', poste_goulot: 'Poste X', retard_jours: 2 },
    })
    const user = userEvent.setup()
    renderWizard()

    await user.click(screen.getByRole('combobox'))
    await user.type(screen.getByRole('searchbox'), 'sous')
    await user.click(await screen.findByRole('option', { name: /Sous-ensemble électrique/ }))
    await user.click(screen.getByRole('button', { name: /Suivant/ }))
    await user.click(screen.getByRole('button', { name: /Suivant/ }))

    expect(await screen.findByText(/tenable avec un retard estimé de 2/)).toBeInTheDocument()
    // Non bloquant : le bouton de création reste actif.
    expect(screen.getByRole('button', { name: /Créer l'OF/ })).not.toBeDisabled()
  })
})
