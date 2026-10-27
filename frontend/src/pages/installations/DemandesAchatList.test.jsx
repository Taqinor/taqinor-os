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
    genererBcfDemandeAchat: vi.fn(),
    getEtapesApprobationDA: vi.fn(),
    approuverEtapeDA: vi.fn(),
    rejeterEtapeDA: vi.fn(),
  },
}))

vi.mock('../../api/stockApi', () => ({
  // NTP2P3 — l'écran lit le CATALOGUE D'ACHAT (jamais `/stock/produits/`).
  default: {
    getProduits: vi.fn(),
    getCatalogueAchat: vi.fn(),
    // NTP2P22 — favoris (épinglés + 5 derniers demandés).
    getFavorisCatalogueAchat: vi.fn(),
    // NTP2P23 — simulateur d'impact budgétaire (lecture seule).
    simulerBudgetDisponible: vi.fn(),
    getBonCommandeFournisseur: vi.fn(),
  },
}))

import installationsApi from '../../api/installationsApi'
import stockApi from '../../api/stockApi'
import DemandesAchatList from './DemandesAchatList.jsx'
import { erreurLigne } from './demandeAchatLigne'

function makeWrapper({ role = 'responsable', permissions = [], initialEntries = ['/chantiers/demandes-achat'] } = {}) {
  const store = configureStore({
    reducer: { auth: authReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role, role_nom: 'Directeur', permissions,
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
  stockApi.getCatalogueAchat.mockResolvedValue({ data: [] })
  stockApi.getFavorisCatalogueAchat.mockResolvedValue({
    data: { epingles: [], recents: [], produit_ids: [] },
  })
  // Défaut : contrôle budgétaire INACTIF (cas historique) — le bandeau
  // d'impact ne doit alors jamais apparaître.
  stockApi.simulerBudgetDisponible.mockResolvedValue({
    data: { controle_actif: false, suffisant: true },
  })
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

  /* NTP2P23 — simulateur d'impact budgétaire AVANT la soumission. */
  it('avertit quand la demande dépasse le budget restant du département', async () => {
    stockApi.simulerBudgetDisponible.mockResolvedValue({
      data: {
        controle_actif: true, suffisant: false,
        restant: '4000.00', montant_manquant: '1000.00',
        montant_demande: '5000.00',
      },
    })

    render(<DemandesAchatList />, { wrapper: makeWrapper() })
    await screen.findAllByText('DA-202607-0007')

    fireEvent.click(screen.getByRole('button', { name: /Nouvelle demande/i }))
    fireEvent.change(await screen.findByLabelText('Quantité'), {
      target: { value: '1' },
    })
    fireEvent.change(screen.getByLabelText('Prix estimé'), {
      target: { value: '5000' },
    })

    const bandeau = await screen.findByTestId('da-impact-budget', {}, { timeout: 3000 })
    expect(bandeau).toHaveAttribute('role', 'alert')
    expect(bandeau.textContent).toMatch(/dépasse le budget restant/i)
    // Le simulateur est en LECTURE SEULE : rien n'est soumis ni engagé.
    expect(installationsApi.createDemandeAchat).not.toHaveBeenCalled()
    expect(installationsApi.soumettreDemandeAchat).not.toHaveBeenCalled()
  })

  it('n’affiche aucun bandeau budget quand le contrôle est inactif', async () => {
    render(<DemandesAchatList />, { wrapper: makeWrapper() })
    await screen.findAllByText('DA-202607-0007')
    fireEvent.click(screen.getByRole('button', { name: /Nouvelle demande/i }))
    await screen.findByLabelText('Objet')
    await waitFor(() =>
      expect(stockApi.simulerBudgetDisponible).toHaveBeenCalled())
    expect(screen.queryByTestId('da-impact-budget')).toBeNull()
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

  it('ENF15 : le picker lit toutes les pages du catalogue (la page 2 est demandée et listée)', async () => {
    stockApi.getCatalogueAchat.mockImplementation(({ page } = {}) => Promise.resolve({
      data: page === 2
        ? { count: 3, next: null, previous: 'p1', results: [{ id: 3, nom: 'Disjoncteur 32A', sku: 'DJ-32' }] }
        : {
          count: 3, next: 'p2', previous: null,
          results: [{ id: 1, nom: 'Câble 6mm', sku: 'CB-6' }, { id: 2, nom: 'Chevilles', sku: 'CH-1' }],
        },
    }))
    render(<DemandesAchatList />, { wrapper: makeWrapper() })
    await screen.findAllByText('DA-202607-0007')
    fireEvent.click(screen.getByRole('button', { name: /Nouvelle demande/i }))
    fireEvent.click(await screen.findByTestId('catalogue-achat-trigger'))
    expect(await screen.findByRole('option', { name: /Disjoncteur 32A/ })).toBeInTheDocument()
    expect(stockApi.getCatalogueAchat).toHaveBeenCalledWith(expect.objectContaining({ page: 2 }))
  })
})

// ACHT63 — chantier identifié par sa référence (les chantiers n'ont pas de `nom`).
const DA_ACHT63 = {
  id: 7, reference: 'DA-202609-0007', objet: 'Fixations', statut: 'brouillon', priorite: 'normale',
  montant_estime: '0', chantier: 3, date_besoin: null, lignes: [], note: '',
}
async function ouvrirEtRemplir(prix) {
  render(<DemandesAchatList />, { wrapper: makeWrapper() })
  await screen.findAllByText('DA-202609-0007')
  fireEvent.click(screen.getByRole('button', { name: /Nouvelle demande/i }))
  fireEvent.change(await screen.findByLabelText('Objet'), { target: { value: 'Câbles' } })
  fireEvent.change(screen.getByLabelText('Désignation'), { target: { value: 'Câble 6mm' } })
  fireEvent.change(screen.getByLabelText('Quantité'), { target: { value: '2' } })
  fireEvent.change(screen.getByLabelText('Prix estimé'), { target: { value: prix } })
}

describe('DemandesAchatList — ACHT63 (référence chantier, validation, reprise)', () => {
  beforeEach(() => {
    installationsApi.getInstallations.mockResolvedValue({ data: [{ id: 3, reference: 'CHT-202609-0001' }] })
    installationsApi.getDemandesAchat.mockResolvedValue({ data: [DA_ACHT63] })
  })

  it('affiche la référence du chantier dans la colonne', async () => {
    render(<DemandesAchatList />, { wrapper: makeWrapper() })
    expect((await screen.findAllByText('CHT-202609-0001')).length).toBeGreaterThan(0)
  })

  it('un prix à 3 décimales est refusé localement : aucune demande créée, puis une seule après correction', async () => {
    installationsApi.createDemandeAchat.mockResolvedValue({ data: { id: 42 } })
    installationsApi.createDemandeAchatLigne.mockResolvedValue({ data: {} })
    await ouvrirEtRemplir('12.345')
    fireEvent.click(screen.getByRole('button', { name: /brouillon/i }))
    expect(await screen.findByText(/2 décimales au plus/)).toBeInTheDocument()
    expect(installationsApi.createDemandeAchat).not.toHaveBeenCalled()

    fireEvent.change(screen.getByLabelText('Prix estimé'), { target: { value: '12.35' } })
    fireEvent.click(screen.getByRole('button', { name: /brouillon/i }))
    await waitFor(() => expect(installationsApi.createDemandeAchatLigne).toHaveBeenCalledTimes(1))
    expect(installationsApi.createDemandeAchat).toHaveBeenCalledTimes(1)
  })

  it('refus serveur de la 1re ligne : le nouvel essai réutilise la demande créée (aucun doublon)', async () => {
    installationsApi.createDemandeAchat.mockResolvedValue({ data: { id: 42 } })
    installationsApi.createDemandeAchatLigne
      .mockRejectedValueOnce({ response: { status: 400, data: { prix_estime: ['Refusé.'] } } })
      .mockResolvedValue({ data: {} })
    await ouvrirEtRemplir('12.30')
    fireEvent.click(screen.getByRole('button', { name: /brouillon/i }))
    await waitFor(() => expect(installationsApi.createDemandeAchatLigne).toHaveBeenCalledTimes(1))
    await screen.findByText(/Refusé/)
    fireEvent.click(screen.getByRole('button', { name: /brouillon/i }))
    await waitFor(() => expect(installationsApi.createDemandeAchatLigne).toHaveBeenCalledTimes(2))
    expect(installationsApi.createDemandeAchat).toHaveBeenCalledTimes(1)
    expect(installationsApi.createDemandeAchatLigne.mock.calls[1][0].demande).toBe(42)
  })

  it('erreurLigne : quantités et prix', () => {
    expect(erreurLigne({ quantite: '2', prix_estime: '12.5' }, 0)).toBe('')
    expect(erreurLigne({ quantite: '1.234', prix_estime: '' }, 1)).toMatch(/Ligne 2/)
    expect(erreurLigne({ quantite: '-1', prix_estime: '' }, 0)).toMatch(/invalide/)
  })
})

describe('DemandesAchatList — générer le BCF / étapes', () => {
  const approuvee = {
    id: 8, reference: 'DA-202607-0008', objet: 'Câbles', statut: 'approuvee',
    priorite: 'normale', montant_estime: '100.00', chantier: null, bon_commande: null,
    lignes: [], note: '',
  }

  it('« Générer le BCF » appelle l’API et affiche la référence du BCF', async () => {
    installationsApi.getDemandesAchat.mockResolvedValue({ data: [approuvee] })
    installationsApi.genererBcfDemandeAchat.mockResolvedValue({
      data: { ...approuvee, statut: 'commandee', bon_commande: 55 },
    })
    stockApi.getBonCommandeFournisseur.mockResolvedValue({ data: { id: 55, reference: 'BCF-2026-10-0055' } })
    render(<DemandesAchatList />, { wrapper: makeWrapper() })
    fireEvent.click((await screen.findAllByText('DA-202607-0008'))[0])
    fireEvent.click(await screen.findByRole('button', { name: /Générer le BCF/ }))
    await waitFor(() => expect(installationsApi.genererBcfDemandeAchat).toHaveBeenCalledWith(8))
    const lien = await screen.findByRole('link', { name: 'BCF-2026-10-0055' })
    // F2 — le lien porte l'id du BCF dans le state de navigation (jamais un ?ref= vide).
    expect(lien.getAttribute('href')).toBe('/stock/bons-commande-fournisseur')
  })

  it('F3 : « Générer le BCF » est masqué sans la permission achats_commander', async () => {
    installationsApi.getDemandesAchat.mockResolvedValue({ data: [approuvee] })
    render(<DemandesAchatList />, {
      wrapper: makeWrapper({ permissions: ['stock_voir'] }),
    })
    fireEvent.click((await screen.findAllByText('DA-202607-0008'))[0])
    await screen.findByRole('dialog')
    expect(screen.queryByRole('button', { name: /Générer le BCF/ })).toBeNull()
  })

  it('F3 : « Générer le BCF » reste visible avec achats_commander', async () => {
    installationsApi.getDemandesAchat.mockResolvedValue({ data: [approuvee] })
    render(<DemandesAchatList />, {
      wrapper: makeWrapper({ permissions: ['stock_voir', 'achats_commander'] }),
    })
    fireEvent.click((await screen.findAllByText('DA-202607-0008'))[0])
    expect(await screen.findByRole('button', { name: /Générer le BCF/ })).toBeInTheDocument()
  })

  it('F1 : ?da=<id> ouvre le détail de cette demande, sans ouvrir le formulaire de création', async () => {
    installationsApi.getDemandesAchat.mockResolvedValue({ data: [approuvee] })
    render(<DemandesAchatList />, {
      wrapper: makeWrapper({ initialEntries: ['/chantiers/demandes-achat?da=8'] }),
    })
    // Le détail (bouton d'action propre au détail) s'ouvre ; le formulaire non.
    expect(await screen.findByRole('button', { name: /Générer le BCF/ })).toBeInTheDocument()
    expect(screen.queryByLabelText('Objet')).toBeNull()
    expect(screen.queryByText("Nouvelle demande d'achat")).toBeNull()
  })

  it('sur 409 « approuver-etape », liste les étapes avec Approuver / Rejeter', async () => {
    installationsApi.approuverDemandeAchat.mockRejectedValue({
      response: { status: 409, data: { detail: 'validez les étapes via « approuver-etape ».' } },
    })
    installationsApi.getEtapesApprobationDA.mockResolvedValue({
      data: [{ id: 3, niveau: 1, statut: 'en_attente', statut_display: 'En attente', approbateur_nom: null }],
    })
    render(<DemandesAchatList />, { wrapper: makeWrapper() })
    fireEvent.click((await screen.findAllByText('DA-202607-0007'))[0])
    fireEvent.click(await screen.findByRole('button', { name: /^Approuver$/ }))
    await waitFor(() => expect(installationsApi.getEtapesApprobationDA).toHaveBeenCalledWith(7))
    expect(await screen.findByRole('button', { name: /Rejeter/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Approuver l.étape/ })).toBeInTheDocument()
  })
})
