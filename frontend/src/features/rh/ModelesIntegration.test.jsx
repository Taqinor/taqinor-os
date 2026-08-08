import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import ModelesIntegration from './ModelesIntegration.jsx'

/* PACT85 — Modèles d'intégration (onboarding). Un modèle créé doit être
   immédiatement disponible (aucun champ dérivé/inventé côté client — la
   liste rechargée vient du serveur). */

vi.mock('../../api/rhApi', () => {
  const empty = () => Promise.resolve({ data: [] })
  return {
    default: {
      getModelesIntegration: vi.fn(empty),
      getPostes: vi.fn(empty),
      getDepartements: vi.fn(empty),
      createModeleIntegration: vi.fn(),
      createElementIntegration: vi.fn(),
      deleteElementIntegration: vi.fn(),
    },
  }
})

function renderScreen() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <ModelesIntegration />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('ModelesIntegration (PACT85)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('rend le module', async () => {
    renderScreen()
    expect(await screen.findByText('Modèles d’intégration')).toBeInTheDocument()
  })

  it('crée un modèle via rhApi.createModeleIntegration', async () => {
    rhApi.createModeleIntegration.mockResolvedValueOnce({ data: { id: 1 } })
    renderScreen()
    await screen.findByText('Modèles d’intégration')

    fireEvent.click(await screen.findByRole('button', { name: /Nouveau modèle/ }))
    fireEvent.change(screen.getByLabelText('Nom'), { target: { value: 'Onboarding technicien' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(rhApi.createModeleIntegration).toHaveBeenCalledWith(
      expect.objectContaining({ nom: 'Onboarding technicien' }),
    ))
    expect(rhApi.getModelesIntegration).toHaveBeenCalledTimes(2)
  })

  it('ajoute une étape à un modèle sélectionné via rhApi.createElementIntegration', async () => {
    rhApi.getModelesIntegration.mockResolvedValue({
      data: [{ id: 4, nom: 'Onboarding standard', actif: true, elements: [] }],
    })
    rhApi.createElementIntegration.mockResolvedValueOnce({ data: { id: 1 } })
    renderScreen()
    fireEvent.click(await screen.findByText('Onboarding standard'))

    fireEvent.click(await screen.findByRole('button', { name: 'Étape' }))
    fireEvent.change(screen.getByLabelText('Libellé'), { target: { value: 'Contrat signé' } })
    fireEvent.click(screen.getByRole('button', { name: 'Ajouter' }))

    await waitFor(() => expect(rhApi.createElementIntegration).toHaveBeenCalledWith(
      expect.objectContaining({ modele: 4, libelle: 'Contrat signé' }),
    ))
  })
})
