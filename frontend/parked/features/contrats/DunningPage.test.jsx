import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* PACT139 — Relance d'impayé : séquences et étapes. NTSUB8 (`apps/contrats`)
   livrait déjà les modèles/endpoints SANS AUCUN écran. Le journal d'exécution
   par contrat réutilise le chatter CONTRAT15 EXISTANT
   (`contratsApi.getHistorique`, déjà exposé et déjà mocké ailleurs dans ce
   module) plutôt qu'un nouvel endpoint — vérifié en filtrant sur
   `field === 'dunning'`. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

const { apiGet, apiPost } = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(() => Promise.resolve({ data: { id: 99 } })),
}))

vi.mock('../../api/axios', () => ({
  default: { get: (...args) => apiGet(...args), post: (...args) => apiPost(...args) },
}))

const { getHistorique } = vi.hoisted(() => ({
  getHistorique: vi.fn(() => Promise.resolve({ data: [] })),
}))

vi.mock('../../api/contratsApi', () => ({
  default: {
    getContrats: () => Promise.resolve({
      data: [{ id: 7, reference: 'CT-2026-07-0001', objet: 'Maintenance PV' }],
    }),
    getHistorique,
  },
}))

import DunningPage from './DunningPage'

const SEQUENCE = {
  id: 1, nom: 'Relance standard', actif: true,
  etapes: [
    {
      id: 11, sequence: 1, jour_offset: 7, canal: 'email', canal_display: 'E-mail',
      template_ref: '', ordre: 1, declenche_suspension: false,
    },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
  apiPost.mockResolvedValue({ data: { id: 99 } })
  apiGet.mockImplementation((url) => {
    if (url === '/contrats/sequences-dunning/') return Promise.resolve({ data: [SEQUENCE] })
    return Promise.resolve({ data: [] })
  })
  getHistorique.mockResolvedValue({ data: [] })
})

function renderPage() {
  return render(<MemoryRouter><ThemeProvider><DunningPage /></ThemeProvider></MemoryRouter>)
}

describe('DunningPage (PACT139)', () => {
  it('liste les séquences avec leurs étapes déjà imbriquées', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Relance standard')).toBeInTheDocument())
    expect(screen.getByText('J+7')).toBeInTheDocument()
    expect(screen.getByText('E-mail')).toBeInTheDocument()
  })

  it('crée une séquence de relance', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Relance standard')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /Nouvelle séquence/ }))
    fireEvent.change(await screen.findByLabelText(/^Nom/), { target: { value: 'Relance agressive' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer la séquence' }))

    await waitFor(() => expect(apiPost).toHaveBeenCalledWith('/contrats/sequences-dunning/', {
      nom: 'Relance agressive',
    }))
  })

  it('ajoute une étape à une séquence existante', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Relance standard')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /Ajouter une étape/ }))
    fireEvent.change(await screen.findByLabelText(/Jours après l’échéance/), { target: { value: '14' } })
    fireEvent.click(screen.getByRole('button', { name: "Créer l'étape" }))

    await waitFor(() => expect(apiPost).toHaveBeenCalledWith('/contrats/etapes-dunning/', {
      sequence: 1, jour_offset: 14, canal: 'notification_interne', ordre: 0,
      declenche_suspension: false,
    }))
  })

  it('affiche le journal d’exécution du contrat sélectionné (chatter field=dunning)', async () => {
    getHistorique.mockResolvedValue({
      data: [
        {
          id: 1, contrat: 7, type: 'log', field: 'dunning', old_value: '',
          new_value: 'Étape J+7 (E-mail)', message: 'Relance de dunning envoyée.',
          auteur: null, auteur_nom: null, date_creation: '2026-08-10T09:00:00Z',
        },
        {
          id: 2, contrat: 7, type: 'log', field: 'statut', old_value: 'brouillon',
          new_value: 'actif', message: '', auteur: null, auteur_nom: null,
          date_creation: '2026-08-01T09:00:00Z',
        },
      ],
    })
    renderPage()
    await waitFor(() => expect(screen.getByText('Relance standard')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('tab', { name: /Journal par contrat/ }))
    fireEvent.change(await screen.findByLabelText(/^Contrat/), { target: { value: '7' } })

    await waitFor(() => expect(getHistorique).toHaveBeenCalledWith('7'))
    expect(await screen.findByText('Étape J+7 (E-mail)')).toBeInTheDocument()
    // L'entrée de transition de statut (field !== 'dunning') n'apparaît PAS.
    expect(screen.queryByText('brouillon')).not.toBeInTheDocument()
  })
})
