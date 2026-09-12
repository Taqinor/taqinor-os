import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, act, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* CH5 — smoke de l'éditeur d'étapes/gates chantier : il se monte, charge les
   étapes, montre les commandes de configuration au Directeur et les cache à un
   non-Directeur (lecture seule). */

/* PACT10 / CHT23 — la charge utile vient de l'exemple COMMITTÉ
   (`apps/installations/contract_samples/etapes_chantier.json`), jamais d'un
   objet retapé à la main. */
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

const ETAPES = exempleContrat('installations', 'etapes_chantier').results

vi.mock('../../api/installationsApi', () => ({
  default: {
    getStagesChantier: vi.fn(),
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
  installationsApi.getStagesChantier.mockResolvedValue(
    reponseContrat('installations', 'etapes_chantier'))
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

  // CHT23 — seuils de comptage configurables (photos_min / checklist_pct_min),
  // affichés pour l'étape bloquante à `exige_photos`/`exige_checklist` du
  // contrat (id 2, « Mise en service »).
  it('affiche les seuils photos/checklist du contrat pour l’étape bloquante', async () => {
    await renderSection()
    await screen.findByDisplayValue('Mise en service')
    const stage = ETAPES.find((s) => s.id === 2)
    expect(screen.getByLabelText('Photos minimum'))
      .toHaveValue(stage.photos_min)
    expect(screen.getByLabelText('% de checklist minimum'))
      .toHaveValue(stage.checklist_pct_min)
  })

  it('enregistre le nombre de photos minimum au blur', async () => {
    await renderSection()
    const input = await screen.findByLabelText('Photos minimum')
    fireEvent.change(input, { target: { value: '5' } })
    fireEvent.blur(input)
    await waitFor(() =>
      expect(installationsApi.saveStageChantier).toHaveBeenCalledWith(
        2, { photos_min: 5 }))
  })

  it('enregistre le pourcentage de checklist minimum au blur', async () => {
    await renderSection()
    const input = await screen.findByLabelText('% de checklist minimum')
    fireEvent.change(input, { target: { value: '60' } })
    fireEvent.blur(input)
    await waitFor(() =>
      expect(installationsApi.saveStageChantier).toHaveBeenCalledWith(
        2, { checklist_pct_min: 60 }))
  })

  it('désactive les seuils en lecture seule', async () => {
    await renderSection({ role: 'normal', role_nom: 'Technicien' })
    await screen.findByLabelText('Photos minimum')
    expect(screen.getByLabelText('Photos minimum')).toBeDisabled()
    expect(screen.getByLabelText('% de checklist minimum')).toBeDisabled()
  })
})
