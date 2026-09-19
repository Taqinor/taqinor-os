import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* NTOBS19 — Assistant guidé « Créer une fenêtre de maintenance » (wizard 3
   étapes) au-dessus de core.MaintenanceWindow (NTOBS9) tel quel. Vérifie :
   le parcours 3 étapes, l'aperçu fidèle (étape 3) et que le SEUL POST
   effectué est `coreApi.maintenanceWindows.create` avec le bon payload. */

const create = vi.fn()

vi.mock('../../api/coreApi', () => ({
  default: {
    maintenanceWindows: {
      create: (...a) => create(...a),
    },
  },
}))

const navigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => navigate }
})

import MaintenanceWizard from './MaintenanceWizard'

function renderAvec({ isSuperuser = false } = {}) {
  const store = configureStore({
    reducer: { auth: (state = { user: { is_superuser: isSuperuser } }) => state },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <MaintenanceWizard />
      </MemoryRouter>
    </Provider>,
  )
}

beforeEach(() => {
  create.mockReset()
  navigate.mockReset()
})

describe('MaintenanceWizard (NTOBS19)', () => {
  it("n'écrit rien avant l'étape 3 — avancer/reculer dans le wizard n'appelle jamais l'API", async () => {
    const user = userEvent.setup()
    renderAvec()
    await user.click(screen.getByRole('button', { name: 'Suivant' })) // étape 1 -> 2
    expect(create).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Précédent' })) // 2 -> 1
    expect(create).not.toHaveBeenCalled()
  })

  it("l'option « système entier » n'est proposée qu'au superutilisateur", () => {
    renderAvec({ isSuperuser: false })
    expect(screen.queryByText('Système entier (toutes les sociétés)')).not.toBeInTheDocument()
  })

  it("l'aperçu (étape 3) reflète fidèlement l'impact et la description saisis", async () => {
    const user = userEvent.setup()
    renderAvec()
    await user.click(screen.getByRole('button', { name: 'Suivant' })) // -> étape 2

    const debut = new Date(Date.now() + 3 * 60 * 60 * 1000)
    const debutLocal = debut.toISOString().slice(0, 16)
    const fin = new Date(Date.now() + 5 * 60 * 60 * 1000)
    const finLocal = fin.toISOString().slice(0, 16)

    await user.type(screen.getByLabelText('Débute le'), debutLocal)
    await user.type(screen.getByLabelText('Termine le'), finLocal)
    await user.type(screen.getByLabelText('Description'), 'Bascule infra planifiée.')

    await user.click(screen.getByRole('button', { name: 'Suivant' })) // -> étape 3

    const banniere = screen.getByTestId('maintenance-wizard-banner-preview')
    expect(banniere).toHaveTextContent('planifiée')
    expect(banniere).toHaveTextContent('Dégradé') // impact par défaut

    const email = screen.getByTestId('maintenance-wizard-email-preview')
    expect(email).toHaveTextContent('Bascule infra planifiée.')
  })

  it('confirmer crée UNE fenêtre identique au formulaire saisi, puis redirige', async () => {
    const user = userEvent.setup()
    create.mockResolvedValueOnce({ data: { id: 1 } })
    renderAvec()

    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    const debutLocal = new Date(Date.now() + 3 * 60 * 60 * 1000).toISOString().slice(0, 16)
    const finLocal = new Date(Date.now() + 5 * 60 * 60 * 1000).toISOString().slice(0, 16)
    await user.type(screen.getByLabelText('Débute le'), debutLocal)
    await user.type(screen.getByLabelText('Termine le'), finLocal)
    await user.type(screen.getByLabelText('Description'), 'Bascule infra.')
    await user.click(screen.getByRole('button', { name: 'Suivant' }))

    await user.click(screen.getByRole('button', { name: /Créer la fenêtre/ }))

    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    const payload = create.mock.calls[0][0]
    expect(payload.description).toBe('Bascule infra.')
    expect(payload.impact).toBe('degrade')
    expect(payload.company).toBeUndefined() // jamais posé sans superutilisateur + choix explicite
    expect(navigate).toHaveBeenCalledWith('/parametres')
  })
})
