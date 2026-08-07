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
   `rhApi.updateEmploye` (jusqu'ici défini sans appelant).
   WIR131 — l'onglet Badges attribue un badge du catalogue société via
   `rhApi.attribuerBadge` (jusqu'ici défini sans appelant), scopé à ce dossier
   (`beneficiaire`). */

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
      // WIR131 — badges (ZRH14).
      getAttributionsBadge: vi.fn(empty),
      getBadgesReconnaissance: vi.fn(() => Promise.resolve({
        data: [{ id: 3, nom: 'Esprit d’équipe', icone: '🤝', actif: true }],
      })),
      attribuerBadge: vi.fn(() => Promise.resolve({ data: {} })),
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

  it('attribue un badge du catalogue via rhApi.attribuerBadge (WIR131)', async () => {
    const { default: userEvent } = await import('@testing-library/user-event')
    rhApi.getEmploye.mockResolvedValueOnce({
      data: { id: 7, nom: 'Bennani', prenom: 'Youssef', matricule: 'M007', statut: 'actif' },
    })
    renderDetail()
    await waitFor(() => expect(rhApi.getAttributionsBadge).toHaveBeenCalledWith({ beneficiaire: '7' }))

    // Onglet Radix : activation au focus → userEvent (fireEvent.click ne
    // bascule pas l'onglet sous jsdom).
    await userEvent.click(screen.getByRole('tab', { name: /Badges/ }))
    // Le bouton reste désactivé tant que le catalogue société (chargé à part)
    // n'est pas arrivé — attendre qu'il soit cliquable avant de cliquer.
    await waitFor(() => expect(screen.getByRole('button', { name: /Attribuer un badge/ })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: /Attribuer un badge/ }))

    expect(screen.getByText(/Attribuer un badge — Bennani Youssef/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Attribuer le badge' }))

    await waitFor(() => expect(rhApi.attribuerBadge).toHaveBeenCalledWith({
      badge: 3, beneficiaire: 7, message: '',
    }))
  })

  it('le menu de motif de sortie ⊆ DossierEmploye.MotifSortie — chaque option aboutit (PACT156)', async () => {
    // Valeurs réelles du modèle (backend/django_core/apps/rh/models.py:209-215) :
    // rh/views.py:518 refuse (400) tout `motif` hors de cette liste.
    const MOTIF_SORTIE_VALUES = [
      'demission', 'licenciement', 'fin_contrat', 'retraite', 'rupture_essai', 'autre',
    ]
    rhApi.getEmploye.mockResolvedValueOnce({
      data: { id: 7, nom: 'Bennani', prenom: 'Youssef', matricule: 'M007', statut: 'actif' },
    })
    renderDetail()

    fireEvent.click(await screen.findByRole('button', { name: /Sortie/ }))
    const select = screen.getByLabelText('Motif')
    const optionValues = Array.from(select.querySelectorAll('option'))
      .map((o) => o.value)
      .filter((v) => v !== '')
    expect(optionValues.length).toBeGreaterThan(0)
    optionValues.forEach((v) => expect(MOTIF_SORTIE_VALUES).toContain(v))

    fireEvent.change(screen.getByLabelText('Date de sortie'), { target: { value: '2026-08-07' } })
    fireEvent.change(select, { target: { value: 'rupture_essai' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer la sortie' }))

    await waitFor(() => expect(rhApi.sortirEmploye).toHaveBeenCalledWith(
      7, expect.objectContaining({ motif: 'rupture_essai' }),
    ))
  })
})
