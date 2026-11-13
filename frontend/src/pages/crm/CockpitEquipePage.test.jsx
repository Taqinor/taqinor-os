import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { reponseContrat } from '../../test/fixtures/contractSamples'

/* AERR118 — « Effacer l'objectif » demande une confirmation qui nomme
   l'indicateur, le membre et la période ; `deleteObjectif` ne part qu'après
   « Effacer ». Réponse = l'exemple COMMITTÉ du contrat cockpit_equipe. */

const { getCockpitEquipe, saveObjectif, deleteObjectif } = vi.hoisted(() => ({
  getCockpitEquipe: vi.fn(),
  saveObjectif: vi.fn(() => Promise.resolve({ data: {} })),
  deleteObjectif: vi.fn(() => Promise.resolve({ data: {} })),
}))
vi.mock('../../api/crmApi', () => ({
  default: { getCockpitEquipe, saveObjectif, deleteObjectif },
}))

import CockpitEquipePage from './CockpitEquipePage'
import { ConfirmProvider } from '../../providers/ConfirmProvider'

beforeEach(() => {
  getCockpitEquipe.mockResolvedValue(reponseContrat('crm', 'cockpit_equipe', 'exemple'))
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('CockpitEquipePage — AERR118', () => {
  it('Effacer l’objectif : rien sans confirmation nommée', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><ConfirmProvider><CockpitEquipePage /></ConfirmProvider></MemoryRouter>)
    await screen.findByText('Octobre 2026')
    const ligne = screen.getAllByRole('row').find((r) => within(r).queryByText('Sara'))
    await user.click(within(ligne).getByText(/\/ 40/))
    await user.click(await screen.findByRole('button', { name: 'Effacer l’objectif' }))

    const boite = await screen.findByRole('alertdialog')
    expect(boite).toHaveTextContent('Sara')
    expect(boite).toHaveTextContent('Octobre 2026')
    await user.click(within(boite).getByRole('button', { name: 'Annuler' }))
    expect(deleteObjectif).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Effacer l’objectif' }))
    await user.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Effacer' }))
    await waitFor(() => expect(deleteObjectif).toHaveBeenCalledWith(31))
    expect(deleteObjectif).toHaveBeenCalledTimes(1)
  })
})
