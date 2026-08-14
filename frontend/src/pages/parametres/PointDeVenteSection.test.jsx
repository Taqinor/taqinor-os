import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* NTRET8 — onglet Paramètres → Point de vente : taux horaire comptoir
   (charge/enregistre) + boutiques actives (liste + ajout). */

const getMock = vi.fn()
const patchMock = vi.fn()
const postMock = vi.fn()
const deleteMock = vi.fn()

vi.mock('../../api/axios', () => ({
  default: {
    get: (...args) => getMock(...args),
    patch: (...args) => patchMock(...args),
    post: (...args) => postMock(...args),
    delete: (...args) => deleteMock(...args),
  },
}))

import PointDeVenteSection from './PointDeVenteSection.jsx'

function renderSection() {
  return render(
    <MemoryRouter>
      <ThemeProvider><PointDeVenteSection /></ThemeProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  getMock.mockReset()
  patchMock.mockReset()
  postMock.mockReset()
  deleteMock.mockReset()
  window.confirm = vi.fn(() => true)
})

function mockLoads({ taux = null, boutiques = [], emplacements = [] } = {}) {
  getMock.mockImplementation((url) => {
    if (url === '/parametres/pos/') {
      return Promise.resolve({ data: { id: 1, taux_horaire_comptoir: taux } })
    }
    if (url === '/parametres/pos-boutiques/') {
      return Promise.resolve({ data: boutiques })
    }
    if (url === '/stock/emplacements/') {
      return Promise.resolve({ data: emplacements })
    }
    return Promise.resolve({ data: [] })
  })
}

describe('PointDeVenteSection', () => {
  it('charge et affiche le taux horaire comptoir existant', async () => {
    mockLoads({ taux: '120.50' })
    renderSection()
    await waitFor(() => expect(screen.getByLabelText(/Taux horaire/)).toHaveValue(120.5))
  })

  it('enregistre le taux horaire modifié', async () => {
    mockLoads({ taux: null })
    patchMock.mockResolvedValue({ data: { taux_horaire_comptoir: '150' } })
    renderSection()
    await waitFor(() => expect(screen.getByLabelText(/Taux horaire/)).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText(/Taux horaire/), { target: { value: '150' } })
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer/ }))

    await waitFor(() => expect(patchMock).toHaveBeenCalledWith(
      '/parametres/pos/update/', { taux_horaire_comptoir: '150' }))
  })

  it('affiche l’état vide quand aucune boutique n’est active', async () => {
    mockLoads({ boutiques: [] })
    renderSection()
    await waitFor(() => expect(screen.getByTestId('boutiques-empty')).toBeInTheDocument())
  })

  it('affiche les boutiques actives déjà configurées', async () => {
    mockLoads({
      boutiques: [
        { id: 1, emplacement: 5, emplacement_nom: 'Showroom Casa', actif: true,
          adresse: '12 rue X', horaires: 'Lun-Sam', surface_m2: '80' },
      ],
    })
    renderSection()
    await waitFor(() => expect(screen.getByTestId('boutiques-liste')).toBeInTheDocument())
    expect(screen.getByText('Showroom Casa')).toBeInTheDocument()
  })

  it('ajoute une boutique depuis un emplacement disponible', async () => {
    mockLoads({
      boutiques: [],
      emplacements: [{ id: 5, nom: 'Showroom Casa' }],
    })
    postMock.mockResolvedValue({ data: { id: 1 } })
    renderSection()
    await waitFor(() => expect(screen.getByRole('button', { name: /Ajouter/ })).toBeInTheDocument())
  })
})
