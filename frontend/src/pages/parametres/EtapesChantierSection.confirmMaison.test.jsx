import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, act, cleanup, waitFor, fireEvent, within } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* APAR66 — la suppression d'une étape de chantier passe par le dialogue maison
   (ui/confirm), jamais par `window.confirm`. Oracle comportemental : Supprimer →
   dialogue maison rendu ; Annuler → aucune requête ; Confirmer → requête. */

import { reponseContrat } from '../../test/fixtures/contractSamples'

vi.mock('../../api/installationsApi', () => ({
  default: {
    getStagesChantier: vi.fn(),
    saveStageChantier: vi.fn(async () => ({ data: {} })),
    deleteStageChantier: vi.fn(async () => ({ data: {} })),
  },
}))

import installationsApi from '../../api/installationsApi'
import { ThemeProvider } from '../../design/ThemeProvider'
import { ConfirmProvider } from '../../providers/ConfirmProvider'
import EtapesChantierSection from './EtapesChantierSection'

const store = configureStore({
  reducer: {
    auth: (s = { role: 'admin', role_nom: 'Directeur', permissions: [], user: null }) => s,
  },
})

const renderSection = async () => {
  await act(async () => {
    render(
      <Provider store={store}>
        <ThemeProvider>
          <ConfirmProvider>
            <EtapesChantierSection />
          </ConfirmProvider>
        </ThemeProvider>
      </Provider>,
    )
  })
}

beforeEach(() => {
  installationsApi.deleteStageChantier.mockClear()
  // Une étape NON protégée (seules celles-là exposent « Supprimer »).
  const base = reponseContrat('installations', 'etapes_chantier')
  const rows = base.data.results.map((e, i) => ({ ...e, protege: false, id: e.id ?? i + 1 }))
  installationsApi.getStagesChantier.mockResolvedValue(
    { ...base, data: { ...base.data, results: rows } })
})
afterEach(() => cleanup())

describe('APAR66 EtapesChantierSection — dialogue maison', () => {
  it('Supprimer → dialogue maison rendu ; Annuler → aucune requête', async () => {
    await renderSection()
    await screen.findByDisplayValue('Visite technique')
    fireEvent.click(screen.getAllByLabelText('Supprimer')[0])
    const dialog = await screen.findByRole('alertdialog')
    expect(within(dialog).getByText(/Supprimer l'étape/)).toBeInTheDocument()
    fireEvent.click(within(dialog).getByText('Annuler'))
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
    expect(installationsApi.deleteStageChantier).not.toHaveBeenCalled()
  })

  it('Confirmer → la suppression est envoyée', async () => {
    await renderSection()
    await screen.findByDisplayValue('Visite technique')
    fireEvent.click(screen.getAllByLabelText('Supprimer')[0])
    const dialog = await screen.findByRole('alertdialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Supprimer' }))
    await waitFor(() =>
      expect(installationsApi.deleteStageChantier).toHaveBeenCalledTimes(1))
  })
})
