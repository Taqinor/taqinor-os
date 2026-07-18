import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import authReducer from '../auth/store/authSlice'
import rhApi from '../../api/rhApi'
import EmployeDetail from './EmployeDetail.jsx'

/* YHIRE2 / ZRH12 + XRH6 — Détail employé : l'en-tête expose l'action Sortie
   pour un actif (et le certificat de travail pour un sorti) ; l'onglet Activité
   (chatter XRH6) est présent. Smoke : le dossier ne plante jamais au montage.
   WIR33 — le bouton « Modifier » ouvre le dialogue d'édition câblé sur
   `rhApi.updateEmploye` (jusqu'ici défini sans appelant). */

vi.mock('react-router-dom', async (orig) => ({
  ...(await orig()),
  useParams: () => ({ id: '7' }),
}))

vi.mock('../../api/rhApi', () => {
  const empty = () => Promise.resolve({ data: [] })
  return {
    default: {
      getEmploye: vi.fn(),
      getDocuments: vi.fn(empty),
      getHabilitations: vi.fn(empty),
      getRegistreFormation: vi.fn(() => Promise.resolve({ data: { lignes: [] } })),
      getIntegration: vi.fn(() => Promise.resolve({ data: { lignes: [], total: 0, faits: 0, progression_pct: 0 } })),
      getHistoriqueEmploye: vi.fn(empty),
      getRemunerations: vi.fn(empty),
      getCompaRatio: vi.fn(() => Promise.resolve({ data: null })),
      getDepartements: vi.fn(empty),
      sortirEmploye: vi.fn(() => Promise.resolve({ data: {} })),
      updateEmploye: vi.fn(),
      getCertificatTravail: vi.fn(),
      confirmerEssai: vi.fn(),
      marquerDeclare: vi.fn(),
    },
  }
})

function renderDetail({ permissions = [] } = {}) {
  const store = configureStore({
    reducer: { auth: authReducer },
    preloadedState: {
      auth: { user: { id: 1 }, role: 'admin', role_nom: 'Administrateur', permissions, isAuthenticated: true, loading: false },
    },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <ThemeProvider>
          <EmployeDetail />
        </ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('EmployeDetail — offboarding (YHIRE2/ZRH12)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('affiche l’action Sortie pour un employé actif', async () => {
    rhApi.getEmploye.mockResolvedValueOnce({
      data: { id: 7, nom: 'Bennani', prenom: 'Youssef', matricule: 'M007', statut: 'actif' },
    })
    renderDetail()
    expect(await screen.findByRole('button', { name: /Sortie/ })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Bennani Youssef' })).toBeInTheDocument()
  })

  it('affiche le certificat de travail pour un employé sorti', async () => {
    rhApi.getEmploye.mockResolvedValueOnce({
      data: { id: 7, nom: 'Bennani', prenom: 'Youssef', matricule: 'M007', statut: 'sorti', date_sortie: '2026-01-15' },
    })
    renderDetail()
    expect(await screen.findByRole('button', { name: /Certificat de travail/ })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Bennani Youssef' })).toBeInTheDocument()
  })

  it('modifie le dossier via rhApi.updateEmploye (WIR33)', async () => {
    rhApi.getEmploye.mockResolvedValueOnce({
      data: { id: 7, nom: 'Bennani', prenom: 'Youssef', matricule: 'M007', statut: 'actif', poste: 'Technicien', type_contrat: 'cdi' },
    })
    rhApi.updateEmploye.mockResolvedValueOnce({ data: {} })
    renderDetail()

    fireEvent.click(await screen.findByRole('button', { name: /Modifier/ }))
    expect(screen.getByText(/Modifier le dossier/)).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Poste'), { target: { value: 'Chef de chantier' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(rhApi.updateEmploye).toHaveBeenCalledWith(
      7, expect.objectContaining({ poste: 'Chef de chantier' }),
    ))
  })
})
