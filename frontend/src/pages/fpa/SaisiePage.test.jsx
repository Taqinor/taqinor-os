import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import authReducer from '../../features/auth/store/authSlice'

/* WIR198 — le workflow de validation de budget (en_saisie → soumis →
   validé/rejeté, NTFPA5) existait côté API sans aucun déclencheur UI. On
   vérifie ici les 3 appels (soumettre/valider/rejeter) avec les query params
   `cycle`/`departement`, le gating par permission `fpa_*` (WIR173) et
   qu'une transition refusée (400) s'affiche en toast plutôt que de planter. */

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
    updateLigneBudget: vi.fn(),
    createLigneBudget: vi.fn(),
    soumettreBudget: (...a) => soumettreBudget(...a),
    validerBudget: (...a) => validerBudget(...a),
    rejeterBudget: (...a) => rejeterBudget(...a),
  },
}))

const toastSuccess = vi.fn()
const toastError = vi.fn()
vi.mock('../../ui', async (orig) => ({
  ...(await orig()),
  toast: { success: (...a) => toastSuccess(...a), error: (...a) => toastError(...a) },
}))

import SaisiePage from './SaisiePage'

function monter({ permissions = [] } = {}) {
  const store = configureStore({
    reducer: { auth: authReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role: 'admin', role_nom: 'Administrateur',
        permissions, isAuthenticated: true, loading: false,
      },
    },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <ThemeProvider><SaisiePage /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  getCycles.mockResolvedValue({ data: [{ id: 1, nom: 'Budget 2027' }] })
  getDepartements.mockResolvedValue({ data: [{ id: 2, nom: 'Commercial' }] })
  getLignesBudget.mockResolvedValue({ data: [] })
  soumettreBudget.mockResolvedValue({ data: { id: 9, statut: 'soumis' } })
  validerBudget.mockResolvedValue({ data: { id: 9, statut: 'valide' } })
  rejeterBudget.mockResolvedValue({ data: { id: 9, statut: 'rejete' } })
})

async function selectionnerCycleEtDepartement(user) {
  await user.selectOptions(screen.getByLabelText('Cycle budgétaire'), '1')
  await user.selectOptions(screen.getByLabelText('Département'), '2')
  await waitFor(() => expect(getLignesBudget).toHaveBeenCalled())
}

describe('SaisiePage — workflow soumettre/valider/rejeter (WIR198)', () => {
  it('masque les 3 boutons sans permission fpa_*', async () => {
    monter({ permissions: [] })
    await waitFor(() => expect(getCycles).toHaveBeenCalled())
    expect(screen.queryByRole('button', { name: 'Soumettre' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Valider' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Rejeter' })).not.toBeInTheDocument()
  })

  it('affiche les 3 boutons avec fpa_saisir et soumet avec cycle+departement', async () => {
    const user = userEvent.setup()
    monter({ permissions: ['fpa_saisir'] })
    await waitFor(() => expect(getCycles).toHaveBeenCalled())
    await selectionnerCycleEtDepartement(user)

    await user.click(screen.getByRole('button', { name: 'Soumettre' }))

    await waitFor(() => expect(soumettreBudget).toHaveBeenCalledWith(
      { cycle: '1', departement: '2' },
    ))
    expect(toastSuccess).toHaveBeenCalledWith('Budget soumis pour validation.')
  })

  it('valide avec fpa_valider', async () => {
    const user = userEvent.setup()
    monter({ permissions: ['fpa_valider'] })
    await waitFor(() => expect(getCycles).toHaveBeenCalled())
    await selectionnerCycleEtDepartement(user)

    await user.click(screen.getByRole('button', { name: 'Valider' }))

    await waitFor(() => expect(validerBudget).toHaveBeenCalledWith(
      { cycle: '1', departement: '2' },
    ))
    expect(toastSuccess).toHaveBeenCalledWith('Budget validé.')
  })

  it('rejette avec un motif saisi au prompt', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'prompt').mockReturnValue('Masse salariale hors cadrage')
    monter({ permissions: ['fpa_administrer'] })
    await waitFor(() => expect(getCycles).toHaveBeenCalled())
    await selectionnerCycleEtDepartement(user)

    await user.click(screen.getByRole('button', { name: 'Rejeter' }))

    await waitFor(() => expect(rejeterBudget).toHaveBeenCalledWith(
      { cycle: '1', departement: '2' }, 'Masse salariale hors cadrage',
    ))
    expect(toastSuccess).toHaveBeenCalledWith('Budget rejeté.')
  })

  it('annule le rejet si le prompt est annulé (aucun appel)', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'prompt').mockReturnValue(null)
    monter({ permissions: ['fpa_administrer'] })
    await waitFor(() => expect(getCycles).toHaveBeenCalled())
    await selectionnerCycleEtDepartement(user)

    await user.click(screen.getByRole('button', { name: 'Rejeter' }))

    expect(rejeterBudget).not.toHaveBeenCalled()
  })

  it('affiche le détail 400 en toast plutôt que de planter', async () => {
    const user = userEvent.setup()
    soumettreBudget.mockRejectedValue({
      response: { data: { detail: 'Ce budget de département est déjà soumis ou validé.' } },
    })
    monter({ permissions: ['fpa_saisir'] })
    await waitFor(() => expect(getCycles).toHaveBeenCalled())
    await selectionnerCycleEtDepartement(user)

    await user.click(screen.getByRole('button', { name: 'Soumettre' }))

    await waitFor(() => expect(toastError).toHaveBeenCalledWith(
      'Ce budget de département est déjà soumis ou validé.',
    ))
  })
})
