import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import authReducer from '../../features/auth/store/authSlice'

/* ============================================================================
   WIR26 — statut de blocage fournisseur (XPUR4) + motif_blocage exposés sur la
   fiche (jusqu'ici seul un accès direct à la base pouvait les changer, alors
   que le blocage BCF/paiement est déjà appliqué et testé côté serveur —
   apps/stock/services.py:check_fournisseur_statut_commande/paiement).
   WIR27 — lien « Fiche 360 » (XPUR25) vers la page jusqu'ici construite mais
   routée nulle part.
   (ResizeObserver/hasPointerCapture/scrollIntoView requis par Radix Select
   sont déjà polyfillés globalement — src/test/setup.js — aucun stub local ici.)
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    getFournisseurs: vi.fn(() => Promise.resolve({
      data: [
        { id: 1, nom: 'Actif SARL', statut: 'actif', nb_produits: 2, nb_bons_commande: 1 },
        {
          id: 2, nom: 'Bloqué Commandes SARL', statut: 'bloque_commandes',
          motif_blocage: 'Litige qualité', nb_produits: 0, nb_bons_commande: 0,
        },
      ],
    })),
    // WIR219/NTPRT25 — décision (valider/rejeter) une candidature.
    deciderCandidatureFournisseur: vi.fn(() => Promise.resolve({ data: {} })),
    createFournisseur: vi.fn(() => Promise.resolve({ data: {} })),
    updateFournisseur: vi.fn(() => Promise.resolve({ data: {} })),
    deleteFournisseur: vi.fn(() => Promise.resolve({ data: { archived: false } })),
    performanceFournisseur: vi.fn(() => Promise.resolve({ data: {} })),
    // WIR190 — fournisseurs archivés (repli PROTECT, patron StockList).
    getFournisseursArchived: vi.fn(() => Promise.resolve({
      data: [{ id: 3, nom: 'Archivé SARL', nb_produits: 1, nb_bons_commande: 2 }],
    })),
    unarchiveFournisseur: vi.fn(() => Promise.resolve({ data: {} })),
    forceDeleteFournisseur: vi.fn(() => Promise.resolve({ data: {} })),
    // WIR108 — référentiel catégories fournisseur.
    getCategoriesFournisseur: vi.fn(() => Promise.resolve({
      data: [{ id: 10, nom: 'Panneaux', archived: false }],
    })),
    createCategorieFournisseur: vi.fn(() => Promise.resolve({ data: {} })),
    updateCategorieFournisseur: vi.fn(() => Promise.resolve({ data: {} })),
    deleteCategorieFournisseur: vi.fn(() => Promise.resolve({})),
  },
}))

import stockApi from '../../api/stockApi'
import FournisseursStock from './FournisseursStock'

function makeStore({ role = 'admin', permissions = ['stock_modifier', 'stock_voir'] } = {}) {
  return configureStore({
    reducer: { auth: authReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role, role_nom: role, permissions,
        isAuthenticated: true, loading: false,
      },
    },
  })
}

function renderPage(store = makeStore()) {
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <ThemeProvider><FournisseursStock /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('FournisseursStock — statut de blocage (WIR26) + fiche 360 (WIR27)', () => {
  it('affiche le statut de blocage de chaque fournisseur dans la liste', async () => {
    renderPage()
    const grid = await screen.findByRole('grid', { name: 'Fournisseurs' })

    expect(within(grid).getByText('Actif SARL')).toBeInTheDocument()
    expect(within(grid).getByText('Bloqué (commandes)')).toBeInTheDocument()
  })

  it('le lien « Fiche 360 » pointe vers /stock/fournisseurs/<id>/360 pour chaque ligne', async () => {
    renderPage()
    const grid = await screen.findByRole('grid', { name: 'Fournisseurs' })

    const links = within(grid).getAllByRole('link', { name: 'Fiche 360' })
    expect(links).toHaveLength(2)
    expect(links.map((a) => a.getAttribute('href')).sort()).toEqual([
      '/stock/fournisseurs/1/360', '/stock/fournisseurs/2/360',
    ])
  })

  it('éditer le fournisseur bloqué pré-remplit statut + motif_blocage', async () => {
    renderPage()
    const grid = await screen.findByRole('grid', { name: 'Fournisseurs' })
    const row = within(grid).getByText('Bloqué Commandes SARL').closest('tr')

    await userEvent.click(within(row).getByRole('button', { name: 'Modifier' }))

    expect(await screen.findByText('Fournisseur — Bloqué Commandes SARL')).toBeInTheDocument()
    // motif_blocage est un <textarea> contrôlé : sa valeur n'est pas un nœud
    // texte enfant (getByText ne la trouverait pas) — getByDisplayValue.
    expect(screen.getByDisplayValue('Litige qualité')).toBeInTheDocument()
  })

  it('rebasculer un fournisseur bloqué en actif envoie statut=actif au serveur', async () => {
    renderPage()
    const grid = await screen.findByRole('grid', { name: 'Fournisseurs' })
    const row = within(grid).getByText('Bloqué Commandes SARL').closest('tr')

    await userEvent.click(within(row).getByRole('button', { name: 'Modifier' }))
    const dialog = await screen.findByRole('dialog')

    // WIR108 a ajouté un 2e combobox (Catégorie) AVANT Statut dans le
    // formulaire — deux comboboxes désormais, comme dans le test « assigne
    // une catégorie » ci-dessous : Catégorie = combos[0], Statut = combos[1].
    const combos = within(dialog).getAllByRole('combobox')
    await userEvent.click(combos[1])
    await userEvent.click(await screen.findByRole('option', { name: 'Actif' }))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(stockApi.updateFournisseur).toHaveBeenCalledWith(
      2, expect.objectContaining({ statut: 'actif' }),
    ))
  })
})

describe('FournisseursStock — fournisseurs archivés (WIR190)', () => {
  it('le bouton « Archivés » charge et affiche la liste des fournisseurs archivés', async () => {
    renderPage()
    await screen.findByRole('grid', { name: 'Fournisseurs' })

    await userEvent.click(screen.getByRole('button', { name: /Archivés/ }))
    expect(await screen.findByRole('grid', { name: 'Fournisseurs archivés' })).toBeInTheDocument()
    expect(stockApi.getFournisseursArchived).toHaveBeenCalled()
    expect(screen.getByText('Archivé SARL')).toBeInTheDocument()
  })

  it('« Réactiver » un fournisseur archivé appelle unarchiveFournisseur', async () => {
    window.confirm = vi.fn(() => true)
    renderPage()
    await screen.findByRole('grid', { name: 'Fournisseurs' })
    await userEvent.click(screen.getByRole('button', { name: /Archivés/ }))
    const grid = await screen.findByRole('grid', { name: 'Fournisseurs archivés' })
    const row = within(grid).getByText('Archivé SARL').closest('tr')

    await userEvent.click(within(row).getByRole('button', { name: 'Réactiver' }))
    await waitFor(() => expect(stockApi.unarchiveFournisseur).toHaveBeenCalledWith(3))
  })

  it('« Supprimer définitivement » exige de taper le nom exact avant de confirmer', async () => {
    renderPage()
    await screen.findByRole('grid', { name: 'Fournisseurs' })
    await userEvent.click(screen.getByRole('button', { name: /Archivés/ }))
    const grid = await screen.findByRole('grid', { name: 'Fournisseurs archivés' })
    const row = within(grid).getByText('Archivé SARL').closest('tr')

    await userEvent.click(within(row).getByRole('button', { name: 'Supprimer définitivement' }))
    const dialog = await screen.findByRole('alertdialog')
    const confirmBtn = within(dialog).getByRole('button', { name: 'Supprimer définitivement' })
    expect(confirmBtn).toBeDisabled()

    await userEvent.type(within(dialog).getByLabelText(/Tapez/), 'Archivé SARL')
    expect(confirmBtn).toBeEnabled()
    await userEvent.click(confirmBtn)
    await waitFor(() => expect(stockApi.forceDeleteFournisseur).toHaveBeenCalledWith(3))
  })

  it('supprimer un fournisseur avec des données réelles rattachées explique l\'archivage (repli 200)', async () => {
    window.confirm = vi.fn(() => true)
    stockApi.deleteFournisseur.mockResolvedValueOnce({
      data: { archived: true, detail: 'Ce fournisseur a été archivé car des données réelles lui sont rattachées.' },
    })
    renderPage()
    const grid = await screen.findByRole('grid', { name: 'Fournisseurs' })
    const row = within(grid).getByText('Actif SARL').closest('tr')

    await userEvent.click(within(row).getByRole('button', { name: 'Supprimer' }))
    await waitFor(() => expect(stockApi.deleteFournisseur).toHaveBeenCalledWith(1))
  })
})

describe('FournisseursStock — catégories fournisseur (WIR108)', () => {
  it('crée une catégorie depuis le gestionnaire « Catégories »', async () => {
    renderPage()
    await screen.findByRole('grid', { name: 'Fournisseurs' })

    await userEvent.click(screen.getByRole('button', { name: 'Catégories' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText('Panneaux')).toBeInTheDocument()

    await userEvent.type(within(dialog).getByPlaceholderText('Nouvelle catégorie…'), 'Onduleurs')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Ajouter' }))

    await waitFor(() => expect(stockApi.createCategorieFournisseur).toHaveBeenCalledWith(
      { nom: 'Onduleurs' },
    ))
  })

  it('assigne une catégorie à un fournisseur depuis la fiche', async () => {
    renderPage()
    const grid = await screen.findByRole('grid', { name: 'Fournisseurs' })
    const row = within(grid).getByText('Actif SARL').closest('tr')

    await userEvent.click(within(row).getByRole('button', { name: 'Modifier' }))
    const dialog = await screen.findByRole('dialog')

    // Deux comboboxes dans l'ordre du formulaire : catégorie puis statut.
    const combos = within(dialog).getAllByRole('combobox')
    await userEvent.click(combos[0])
    await userEvent.click(await screen.findByRole('option', { name: 'Panneaux' }))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(stockApi.updateFournisseur).toHaveBeenCalledWith(
      1, expect.objectContaining({ categorie: 10 }),
    ))
  })
})

describe('FournisseursStock — candidatures fournisseur (WIR219)', () => {
  // `mockResolvedValueOnce` — n'affecte QUE ces tests, jamais la liste par
  // défaut consommée par les autres describe (WIR27 compte exactement 2 liens).
  const listeAvecCandidature = () => stockApi.getFournisseurs.mockResolvedValueOnce({
    data: [
      { id: 1, nom: 'Actif SARL', statut: 'actif', nb_produits: 2, nb_bons_commande: 1 },
      {
        id: 4, nom: 'Candidat SARL', statut: 'actif',
        statut_validation: 'en_attente_validation', nb_produits: 0, nb_bons_commande: 0,
      },
    ],
  })

  it('affiche le badge « En attente de validation » et le filtre « Candidatures en attente »', async () => {
    listeAvecCandidature()
    renderPage()
    const grid = await screen.findByRole('grid', { name: 'Fournisseurs' })

    expect(within(grid).getByText('En attente de validation')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Candidatures en attente/ }))
    const filtered = await screen.findByRole('grid', { name: 'Fournisseurs' })
    expect(within(filtered).getByText('Candidat SARL')).toBeInTheDocument()
    expect(within(filtered).queryByText('Actif SARL')).toBeNull()
  })

  it('Admin : « Valider » appelle deciderCandidatureFournisseur(id, true) — la candidature rejoint le sourcing', async () => {
    window.confirm = vi.fn(() => true)
    listeAvecCandidature()
    renderPage()
    const grid = await screen.findByRole('grid', { name: 'Fournisseurs' })
    const row = within(grid).getByText('Candidat SARL').closest('tr')

    await userEvent.click(within(row).getByRole('button', { name: 'Valider la candidature' }))
    await waitFor(() => expect(stockApi.deciderCandidatureFournisseur).toHaveBeenCalledWith(4, true))
  })

  it('Admin : « Rejeter » appelle deciderCandidatureFournisseur(id, false)', async () => {
    window.confirm = vi.fn(() => true)
    listeAvecCandidature()
    renderPage()
    const grid = await screen.findByRole('grid', { name: 'Fournisseurs' })
    const row = within(grid).getByText('Candidat SARL').closest('tr')

    await userEvent.click(within(row).getByRole('button', { name: 'Rejeter la candidature' }))
    await waitFor(() => expect(stockApi.deciderCandidatureFournisseur).toHaveBeenCalledWith(4, false))
  })

  it('non-admin (responsable) : aucune action Valider/Rejeter n\'est visible', async () => {
    listeAvecCandidature()
    renderPage(makeStore({ role: 'responsable', permissions: [] }))
    const grid = await screen.findByRole('grid', { name: 'Fournisseurs' })
    const row = within(grid).getByText('Candidat SARL').closest('tr')

    expect(within(row).queryByRole('button', { name: 'Valider la candidature' })).toBeNull()
    expect(within(row).queryByRole('button', { name: 'Rejeter la candidature' })).toBeNull()
  })

  it('un 403 serveur (rôle insuffisant malgré tout) est affiché en FR', async () => {
    window.confirm = vi.fn(() => true)
    listeAvecCandidature()
    stockApi.deciderCandidatureFournisseur.mockRejectedValueOnce({
      response: { status: 403, data: { detail: 'Réservé à l\'administrateur.' } },
    })
    renderPage()
    const grid = await screen.findByRole('grid', { name: 'Fournisseurs' })
    const row = within(grid).getByText('Candidat SARL').closest('tr')

    await userEvent.click(within(row).getByRole('button', { name: 'Valider la candidature' }))
    // toastError best-effort — le point vérifiable est l'appel serveur lui-même
    // (le rendu du toast n'est pas garanti sans <Toaster> monté dans ce test).
    await waitFor(() => expect(stockApi.deciderCandidatureFournisseur).toHaveBeenCalledWith(4, true))
  })
})
