import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import authReducer from '../../features/auth/store/authSlice'

/* ============================================================================
   FG310 — écran « Demandes d'achat » (réquisitions chantier → approbation).
   Vérifie : (1) la liste se charge ; (2) un utilisateur crée + soumet une
   demande (createDemandeAchat + soumettre appelés) ; (3) une demande soumise
   montre Approuver/Refuser au palier responsable/admin, et l'action appelle
   l'endpoint ; (4) un utilisateur `normal` ne voit PAS Approuver.
   ========================================================================== */

vi.mock('../../api/installationsApi', () => ({
  default: {
    getDemandesAchat: vi.fn(),
    getInstallations: vi.fn(),
    createDemandeAchat: vi.fn(),
    createDemandeAchatLigne: vi.fn(),
    soumettreDemandeAchat: vi.fn(),
    approuverDemandeAchat: vi.fn(),
    refuserDemandeAchat: vi.fn(),
  },
}))

vi.mock('../../api/stockApi', () => ({
  default: { getProduits: vi.fn() },
}))

import installationsApi from '../../api/installationsApi'
import stockApi from '../../api/stockApi'
import DemandesAchatList from './DemandesAchatList.jsx'

function makeWrapper({ role = 'responsable', initialEntries = ['/chantiers/demandes-achat'] } = {}) {
  const store = configureStore({
    reducer: { auth: authReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role, role_nom: 'Directeur', permissions: [],
        isAuthenticated: true, loading: false,
      },
    },
  })
  return function wrapper({ children }) {
    return (
      <Provider store={store}>
        <MemoryRouter initialEntries={initialEntries}>
          <ThemeProvider>{children}</ThemeProvider>
        </MemoryRouter>
      </Provider>
    )
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {}
  if (!window.matchMedia) {
    window.matchMedia = () => ({
      matches: false, addListener: () => {}, removeListener: () => {},
      addEventListener: () => {}, removeEventListener: () => {},
    })
  }
  stockApi.getProduits.mockResolvedValue({ data: [] })
  installationsApi.getInstallations.mockResolvedValue({ data: [] })
  installationsApi.getDemandesAchat.mockResolvedValue({
    data: [
      {
        id: 7, reference: 'DA-202607-0007', objet: 'Fixations chantier Anfa',
        statut: 'soumise', priorite: 'haute', montant_estime: '1200.00',
        chantier: null, date_besoin: '2026-07-20', lignes: [], note: '',
      },
    ],
  })
})

describe('DemandesAchatList (FG310)', () => {
  it('charge et affiche les demandes existantes', async () => {
    render(<DemandesAchatList />, { wrapper: makeWrapper() })
    expect((await screen.findAllByText('DA-202607-0007'))[0]).toBeInTheDocument()
    expect(screen.getAllByText('Fixations chantier Anfa')[0]).toBeInTheDocument()
  })

  it('crée puis soumet une nouvelle demande', async () => {
    installationsApi.createDemandeAchat.mockResolvedValue({ data: { id: 42 } })
    installationsApi.soumettreDemandeAchat.mockResolvedValue({ data: { id: 42, statut: 'soumise' } })

    render(<DemandesAchatList />, { wrapper: makeWrapper() })
    await screen.findAllByText('DA-202607-0007')

    fireEvent.click(screen.getByRole('button', { name: /Nouvelle demande/i }))
    fireEvent.change(await screen.findByLabelText('Objet'), {
      target: { value: 'Câbles solaires' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Créer et soumettre/i }))

    await waitFor(() =>
      expect(installationsApi.createDemandeAchat).toHaveBeenCalledWith(
        expect.objectContaining({ objet: 'Câbles solaires', priorite: 'normale' }),
      ),
    )
    await waitFor(() =>
      expect(installationsApi.soumettreDemandeAchat).toHaveBeenCalledWith(42),
    )
  })

  it('un responsable peut approuver une demande soumise', async () => {
    installationsApi.approuverDemandeAchat.mockResolvedValue({
      data: { id: 7, statut: 'approuvee', reference: 'DA-202607-0007', objet: 'Fixations chantier Anfa', lignes: [] },
    })

    render(<DemandesAchatList />, { wrapper: makeWrapper({ role: 'responsable' }) })
    fireEvent.click((await screen.findAllByText('DA-202607-0007'))[0])

    fireEvent.click(await screen.findByRole('button', { name: /Approuver/i }))
    await waitFor(() =>
      expect(installationsApi.approuverDemandeAchat).toHaveBeenCalledWith(7),
    )
  })

  it("cache Approuver pour un rôle normal", async () => {
    render(<DemandesAchatList />, { wrapper: makeWrapper({ role: 'normal' }) })
    fireEvent.click((await screen.findAllByText('DA-202607-0007'))[0])

    // Le détail s'ouvre (objet visible dans le dialogue) mais sans action manager.
    await screen.findAllByText('Fixations chantier Anfa')
    expect(screen.queryByRole('button', { name: /Approuver/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Refuser/i })).not.toBeInTheDocument()
  })

  // VX227 — pré-remplissage depuis une intervention : arriver sur
  // /chantiers/demandes-achat?chantier=5&intervention=9 ouvre le formulaire de
  // création avec le chantier pré-sélectionné et un objet rappelant
  // l'intervention d'origine.
  it('pré-remplit le formulaire depuis les query params chantier/intervention', async () => {
    installationsApi.getInstallations.mockResolvedValue({
      data: [{ id: 5, nom: 'Villa Anfa', reference: 'CH-5' }],
    })
    render(<DemandesAchatList />, {
      wrapper: makeWrapper({
        initialEntries: ['/chantiers/demandes-achat?chantier=5&intervention=9'],
      }),
    })
    // Le dialogue de création s'ouvre automatiquement, objet pré-rempli.
    const objet = await screen.findByLabelText('Objet')
    await waitFor(() =>
      expect(objet).toHaveValue('Besoin non prévu — intervention #9'),
    )
    // Le chantier ciblé est pré-sélectionné dans le formulaire.
    expect(screen.getByText('Villa Anfa')).toBeInTheDocument()
  })
})
