import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, act, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* CH5 — smoke de l'éditeur d'étapes/gates chantier : il se monte, charge les
   étapes, montre les commandes de configuration au Directeur et les cache à un
   non-Directeur (lecture seule). */

vi.mock('../../api/installationsApi', () => ({
  default: {
    getStagesChantier: vi.fn(async () => ({
      data: [
        { id: 1, cle: 'etude_site', libelle: 'Visite technique', ordre: 0,
          bloquant: false, actif: true, protege: true, statut_legacy_display: 'Signé' },
        { id: 2, cle: 'mise_en_service', libelle: 'Mise en service', ordre: 6,
          bloquant: true, actif: true, protege: true, exige_tests: true,
          statut_legacy_display: 'Installé' },
      ],
    })),
    saveStageChantier: vi.fn(async () => ({ data: {} })),
    deleteStageChantier: vi.fn(async () => ({ data: {} })),
  },
}))

import installationsApi from '../../api/installationsApi'
import { ThemeProvider } from '../../design/ThemeProvider'
import EtapesChantierSection from './EtapesChantierSection'

function makeStore({ role = 'admin', role_nom = 'Directeur' } = {}) {
  return configureStore({
    reducer: {
      auth: (s = { role, role_nom, permissions: [], user: null }) => s,
    },
  })
}

const renderSection = async (opts = {}) => {
  await act(async () => {
    render(
      <Provider store={makeStore(opts)}>
        <ThemeProvider>
          <EtapesChantierSection />
        </ThemeProvider>
      </Provider>,
    )
  })
}

beforeEach(() => {
  installationsApi.getStagesChantier.mockClear()
  installationsApi.saveStageChantier.mockClear()
})
afterEach(() => cleanup())

describe('CH5 EtapesChantierSection', () => {
  it('charge et liste les étapes du cycle de vie', async () => {
    await renderSection()
    await waitFor(() =>
      expect(installationsApi.getStagesChantier).toHaveBeenCalled())
    expect(screen.getByDisplayValue('Visite technique')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Mise en service')).toBeInTheDocument()
    // Le badge « Bloquant » apparaît pour l'étape de mise en service.
    expect(screen.getByText('Bloquant')).toBeInTheDocument()
  })

  it('montre les commandes de configuration au Directeur', async () => {
    await renderSection({ role: 'admin', role_nom: 'Directeur' })
    await waitFor(() =>
      expect(screen.getByDisplayValue('Visite technique')).toBeInTheDocument())
    // Le champ d'ajout d'étape est présent.
    expect(screen.getByPlaceholderText('Nouvelle étape…')).toBeInTheDocument()
  })

  it('passe en lecture seule pour un non-Directeur', async () => {
    await renderSection({ role: 'normal', role_nom: 'Technicien' })
    await waitFor(() =>
      expect(screen.getByDisplayValue('Visite technique')).toBeInTheDocument())
    // Message lecture seule + pas de champ d'ajout.
    expect(screen.getByText(/lecture seule/i)).toBeInTheDocument()
    expect(screen.queryByPlaceholderText('Nouvelle étape…')).toBeNull()
  })

  it('enregistre le renommage d’une étape au blur', async () => {
    await renderSection()
    const input = await screen.findByDisplayValue('Visite technique')
    fireEvent.change(input, { target: { value: 'Étude de site' } })
    fireEvent.blur(input)
    await waitFor(() =>
      expect(installationsApi.saveStageChantier).toHaveBeenCalledWith(
        1, { libelle: 'Étude de site' }))
  })
})
