import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR198 — le workflow de validation d'un budget de département (en_saisie →
   soumis → validé/rejeté) n'avait AUCUN déclencheur UI sur SaisiePage bien que
   les 3 actions serveur existaient déjà (fpaApi.soumettreBudget/validerBudget/
   rejeterBudget). On vérifie que les 3 boutons appellent bien ces actions avec
   `{cycle, departement}`, qu'un 400 de transition remonte en toast (jamais
   avalé), et que le rejet transmet le motif. */

const getCycles = vi.fn()
const getDepartements = vi.fn()
const getLignesBudget = vi.fn()
const soumettreBudget = vi.fn()
const validerBudget = vi.fn()
const rejeterBudget = vi.fn()

vi.mock('../../api/fpaApi', () => ({
  default: {
    getCycles: (...a) => getCycles(...a),
    getDepartements: (...a) => getDepartements(...a),
    getLignesBudget: (...a) => getLignesBudget(...a),
    soumettreBudget: (...a) => soumettreBudget(...a),
    validerBudget: (...a) => validerBudget(...a),
    rejeterBudget: (...a) => rejeterBudget(...a),
  },
}))

const toastError = vi.fn()
const toastSuccess = vi.fn()
vi.mock('../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: (...a) => toastSuccess(...a), error: (...a) => toastError(...a) } }
})

import SaisiePage from './SaisiePage'

beforeEach(() => {
  vi.clearAllMocks()
  getCycles.mockResolvedValue({ data: [{ id: 1, nom: 'Budget 2026' }] })
  getDepartements.mockResolvedValue({ data: [{ id: 2, nom: 'Commercial' }] })
  getLignesBudget.mockResolvedValue({ data: [] })
  soumettreBudget.mockResolvedValue({ data: {} })
  validerBudget.mockResolvedValue({ data: {} })
  rejeterBudget.mockResolvedValue({ data: {} })
})

async function choisirCycleEtDepartement(user) {
  await screen.findByLabelText('Cycle budgétaire')
  await user.selectOptions(screen.getByLabelText('Cycle budgétaire'), '1')
  await user.selectOptions(screen.getByLabelText('Département'), '2')
}

describe('SaisiePage — workflow de validation (WIR198)', () => {
  it('Soumettre appelle soumettreBudget avec {cycle, departement}', async () => {
    const user = userEvent.setup()
    render(<SaisiePage />)
    await choisirCycleEtDepartement(user)

    await user.click(screen.getByRole('button', { name: 'Soumettre' }))

    await waitFor(() => expect(soumettreBudget).toHaveBeenCalledWith({ cycle: '1', departement: '2' }))
  })

  it('Valider appelle validerBudget avec {cycle, departement}', async () => {
    const user = userEvent.setup()
    render(<SaisiePage />)
    await choisirCycleEtDepartement(user)

    await user.click(screen.getByRole('button', { name: 'Valider' }))

    await waitFor(() => expect(validerBudget).toHaveBeenCalledWith({ cycle: '1', departement: '2' }))
  })

  it('Rejeter appelle rejeterBudget avec {cycle, departement} et le motif saisi', async () => {
    const user = userEvent.setup()
    render(<SaisiePage />)
    await choisirCycleEtDepartement(user)

    await user.type(screen.getByLabelText('Motif du rejet'), 'Hors cadrage')
    await user.click(screen.getByRole('button', { name: 'Rejeter' }))

    await waitFor(() => expect(rejeterBudget).toHaveBeenCalledWith(
      { cycle: '1', departement: '2' }, 'Hors cadrage',
    ))
  })

  it('un 400 de transition remonte en toast (jamais silencieusement avalé)', async () => {
    soumettreBudget.mockRejectedValueOnce({
      response: { data: { detail: 'Le budget doit être en saisie pour être soumis.' } },
    })
    const user = userEvent.setup()
    render(<SaisiePage />)
    await choisirCycleEtDepartement(user)

    await user.click(screen.getByRole('button', { name: 'Soumettre' }))

    await waitFor(() => expect(toastError).toHaveBeenCalledWith(
      'Le budget doit être en saisie pour être soumis.',
    ))
  })
})
