import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* NTDMO26 — assistant first-run « société réelle ». Aucun nouvel endpoint
   backend : « Passer » et chaque étape complétée réutilisent ignorer/
   marquer-fait (WIR59/NTDMO13, déjà exposés) — voir apps/onboarding/tests/
   test_ntdmo26_demarrage_wizard.py côté serveur. */

const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => navigateMock }
})

const { apiMock } = vi.hoisted(() => ({
  apiMock: { get: vi.fn(), post: vi.fn() },
}))
vi.mock('../../api/axios', () => ({ default: apiMock }))

vi.mock('../../api/parametresApi', () => ({
  default: {
    getProfile: vi.fn(() => Promise.resolve({ data: { nom: '', adresse: '', email: '', telephone: '' } })),
    updateProfile: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))
vi.mock('../../api/stockApi', () => ({
  default: { createProduit: vi.fn(() => Promise.resolve({ data: {} })) },
}))
vi.mock('../../api/rolesApi', () => ({
  default: { getRoles: vi.fn(() => Promise.resolve({ data: [{ id: 1, nom: 'Utilisateur' }] })) },
}))

import DemarrageWizard from './DemarrageWizard'
import parametresApi from '../../api/parametresApi'

const PROGRESS = {
  items: [
    { id: 10, key: 'assistant_demarrage', libelle: 'Assistant', lien: '/onboarding/demarrage', fait: false, event_key: '' },
    { id: 11, key: 'configurer_societe', libelle: 'Configurer votre société', lien: '/parametres', fait: false, event_key: '' },
    { id: 12, key: 'premier_produit', libelle: 'Ajouter votre premier produit', lien: '/stock', fait: false, event_key: '' },
  ],
  faits: 0, total: 3, pourcentage: 0, termine: false, assistant_demarrage_auto: true,
}

function renderWizard() {
  return render(<MemoryRouter><DemarrageWizard /></MemoryRouter>)
}

afterEach(() => {
  cleanup()
  navigateMock.mockReset()
  apiMock.get.mockReset()
  apiMock.post.mockReset()
})

describe('DemarrageWizard (NTDMO26)', () => {
  it('affiche la première étape (bienvenue) puis avance sur « Commencer »', async () => {
    apiMock.get.mockResolvedValueOnce({ data: PROGRESS })
    const user = userEvent.setup()
    renderWizard()
    expect(await screen.findByText('Configurez votre société en 5 minutes')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Commencer' }))
    expect(screen.getByText('1. Coordonnées de la société')).toBeInTheDocument()
  })

  it('« Passer, je configurerai plus tard » ignore l\'item assistant_demarrage et navigue au dashboard', async () => {
    apiMock.get.mockResolvedValueOnce({ data: PROGRESS })
    apiMock.post.mockResolvedValueOnce({ data: {} })
    const user = userEvent.setup()
    renderWizard()
    await screen.findByText('Configurez votre société en 5 minutes')
    await user.click(screen.getByRole('button', { name: 'Passer, je configurerai plus tard' }))
    await waitFor(() => expect(apiMock.post)
      .toHaveBeenCalledWith('/onboarding/progress/10/ignorer/'))
    expect(navigateMock).toHaveBeenCalledWith('/dashboard')
  })

  it('enregistrer la société appelle updateProfile puis marque configurer_societe fait', async () => {
    apiMock.get.mockResolvedValueOnce({ data: PROGRESS })
    apiMock.post.mockResolvedValueOnce({ data: {} })
    const user = userEvent.setup()
    renderWizard()
    await user.click(await screen.findByRole('button', { name: 'Commencer' }))
    await user.type(screen.getByPlaceholderText('Nom de la société'), 'TAQINOR')
    await user.click(screen.getByRole('button', { name: 'Enregistrer et continuer' }))
    await waitFor(() => expect(parametresApi.updateProfile).toHaveBeenCalled())
    await waitFor(() => expect(apiMock.post)
      .toHaveBeenCalledWith('/onboarding/progress/11/marquer-fait/'))
    expect(await screen.findByText('2. Premier produit du catalogue')).toBeInTheDocument()
  })
})
