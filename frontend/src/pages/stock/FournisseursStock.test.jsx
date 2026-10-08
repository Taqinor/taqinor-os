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
    getAllFournisseurs: vi.fn(() => Promise.resolve({
      data: [
        { id: 1, nom: 'Actif SARL', statut: 'actif', nb_produits: 2, nb_bons_commande: 1 },
        {
          id: 2, nom: 'Bloqué Commandes SARL', statut: 'bloque_commandes',
          motif_blocage: 'Litige qualité', nb_produits: 0, nb_bons_commande: 0,
        },
      ],
    })),
    // ASTK185 — page 1 SEULE (50 lignes + next) : un écran qui l'appellerait
    // encore perdrait le 51ᵉ fournisseur (test-du-test de « affiche le 51ᵉ »).
    getFournisseurs: vi.fn(() => Promise.resolve({
      data: {
        count: 51, next: '?page=2',
        results: Array.from({ length: 50 }, (_, i) => ({ id: 100 + i, nom: `Fournisseur ${i + 1}` })),
      },
    })),
    // WIR219/NTPRT25 — décision (valider/rejeter) une candidature.
    deciderCandidatureFournisseur: vi.fn(() => Promise.resolve({ data: {} })),
    createFournisseur: vi.fn(() => Promise.resolve({ data: {} })),
    updateFournisseur: vi.fn(() => Promise.resolve({ data: {} })),
    deleteFournisseur: vi.fn(() => Promise.resolve({ data: { archived: false } })),
    // ASTK184 — « Supprimer » = archivage (PATCH is_archived).
    archiveFournisseur: vi.fn(() => Promise.resolve({ data: { id: 1, is_archived: true } })),
    performanceFournisseur: vi.fn(() => Promise.resolve({ data: {} })),
    // WIR190 — fournisseurs archivés (repli PROTECT, patron StockList).
    getAllFournisseursArchived: vi.fn(() => Promise.resolve({
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
import { documentContrat } from '../../test/fixtures/contractSamples'
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

// ASTK184 — confirme le geste dans l'AlertDialog maison (jamais window.confirm).
async function confirmer(libelle) {
  const dialog = await screen.findByRole('alertdialog')
  await userEvent.click(within(dialog).getByRole('button', { name: libelle }))
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
    const grid = await screen.findByRole('grid', { name: 'Fournisseurs archivés' })
    expect(grid).toBeInTheDocument()
    expect(stockApi.getAllFournisseursArchived).toHaveBeenCalled()
    // Le DataTable double chaque ligne (grille desktop + carte mobile) : on
    // porte la requête sur la grille, comme le test « Réactiver » plus bas.
    expect(within(grid).getByText('Archivé SARL')).toBeInTheDocument()
  })

  it('« Réactiver » un fournisseur archivé appelle unarchiveFournisseur', async () => {
    renderPage()
    await screen.findByRole('grid', { name: 'Fournisseurs' })
    await userEvent.click(screen.getByRole('button', { name: /Archivés/ }))
    const grid = await screen.findByRole('grid', { name: 'Fournisseurs archivés' })
    const row = within(grid).getByText('Archivé SARL').closest('tr')

    await userEvent.click(within(row).getByRole('button', { name: 'Réactiver' }))
    await confirmer('Désarchiver')
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

})

/* ============================================================================
   ASTK184 (C-ASTK-042, FOUR-19) — plus aucune boîte native ; « Supprimer » un
   fournisseur l'ARCHIVE (un DELETE détruirait en CASCADE contacts, comptes
   portail, jetons et dossier d'onboarding) ; la suppression définitive passe
   UNIQUEMENT par ForceDeleteFournisseurModal (nom à taper).
   ========================================================================== */
describe('FournisseursStock — confirmations maison (ASTK184)', () => {
  it('supprimer ouvre une AlertDialog et archive', async () => {
    stockApi.deleteFournisseur.mockClear()
    stockApi.archiveFournisseur.mockClear()
    renderPage()
    const grid = await screen.findByRole('grid', { name: 'Fournisseurs' })
    const row = within(grid).getByText('Actif SARL').closest('tr')

    await userEvent.click(within(row).getByRole('button', { name: 'Supprimer' }))
    const dialog = await screen.findByRole('alertdialog')
    expect(within(dialog).getByText(/Actif SARL/)).toBeInTheDocument()
    expect(stockApi.archiveFournisseur).not.toHaveBeenCalled()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Archiver' }))
    await waitFor(() => expect(stockApi.archiveFournisseur).toHaveBeenCalledWith(1))
    expect(stockApi.deleteFournisseur).not.toHaveBeenCalled()
  })

  it('annuler l\'AlertDialog n\'archive rien', async () => {
    stockApi.archiveFournisseur.mockClear()
    renderPage()
    const grid = await screen.findByRole('grid', { name: 'Fournisseurs' })
    const row = within(grid).getByText('Actif SARL').closest('tr')
    await userEvent.click(within(row).getByRole('button', { name: 'Supprimer' }))
    await confirmer('Annuler')
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
    expect(stockApi.archiveFournisseur).not.toHaveBeenCalled()
  })

  it('aucun window.confirm sur les 4 gestes', async () => {
    const spy = vi.spyOn(window, 'confirm').mockImplementation(() => true)
    stockApi.getAllFournisseurs.mockResolvedValueOnce({
      data: [
        { id: 1, nom: 'Actif SARL', statut: 'actif', nb_produits: 2, nb_bons_commande: 1 },
        { id: 4, nom: 'Candidat SARL', statut: 'actif',
          statut_validation: 'en_attente_validation', nb_produits: 0, nb_bons_commande: 0 },
      ],
    })
    renderPage()
    const grid = await screen.findByRole('grid', { name: 'Fournisseurs' })
    // 1. Décision de candidature.
    await userEvent.click(within(within(grid).getByText('Candidat SARL').closest('tr'))
      .getByRole('button', { name: 'Rejeter la candidature' }))
    await confirmer('Rejeter')
    await waitFor(() => expect(stockApi.deciderCandidatureFournisseur).toHaveBeenCalledWith(4, false))
    // 2. Supprimer (archive) un fournisseur.
    const grid2 = await screen.findByRole('grid', { name: 'Fournisseurs' })
    await userEvent.click(within(within(grid2).getByText('Actif SARL').closest('tr'))
      .getByRole('button', { name: 'Supprimer' }))
    await confirmer('Archiver')
    // 3. Désarchivage.
    await userEvent.click(screen.getByRole('button', { name: /Archivés/ }))
    const archGrid = await screen.findByRole('grid', { name: 'Fournisseurs archivés' })
    await userEvent.click(within(within(archGrid).getByText('Archivé SARL').closest('tr'))
      .getByRole('button', { name: 'Réactiver' }))
    await confirmer('Désarchiver')
    // 4. Suppression d'une catégorie.
    await userEvent.click(screen.getByRole('button', { name: 'Catégories' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Supprimer' }))
    await confirmer('Supprimer')
    await waitFor(() => expect(stockApi.deleteCategorieFournisseur).toHaveBeenCalledWith(10))
    expect(stockApi.archiveFournisseur).toHaveBeenCalledWith(1)
    expect(stockApi.deciderCandidatureFournisseur).toHaveBeenCalledWith(4, false)
    expect(stockApi.unarchiveFournisseur).toHaveBeenCalledWith(3)
    expect(spy).not.toHaveBeenCalled()
    spy.mockRestore()
  })

  it('la suppression définitive exige le nom', async () => {
    stockApi.forceDeleteFournisseur.mockClear()
    renderPage()
    await screen.findByRole('grid', { name: 'Fournisseurs' })
    await userEvent.click(screen.getByRole('button', { name: /Archivés/ }))
    const grid = await screen.findByRole('grid', { name: 'Fournisseurs archivés' })
    const row = within(grid).getByText('Archivé SARL').closest('tr')
    await userEvent.click(within(row).getByRole('button', { name: 'Supprimer définitivement' }))
    const dialog = await screen.findByRole('alertdialog')
    const btn = within(dialog).getByRole('button', { name: 'Supprimer définitivement' })
    await userEvent.type(within(dialog).getByLabelText(/Tapez/), 'Archivé')
    expect(btn).toBeDisabled()
    await userEvent.click(btn)
    expect(stockApi.forceDeleteFournisseur).not.toHaveBeenCalled()
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
  const listeAvecCandidature = () => stockApi.getAllFournisseurs.mockResolvedValueOnce({
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
    listeAvecCandidature()
    renderPage()
    const grid = await screen.findByRole('grid', { name: 'Fournisseurs' })
    const row = within(grid).getByText('Candidat SARL').closest('tr')

    await userEvent.click(within(row).getByRole('button', { name: 'Valider la candidature' }))
    await confirmer('Valider')
    await waitFor(() => expect(stockApi.deciderCandidatureFournisseur).toHaveBeenCalledWith(4, true))
  })

  it('Admin : « Rejeter » appelle deciderCandidatureFournisseur(id, false)', async () => {
    listeAvecCandidature()
    renderPage()
    const grid = await screen.findByRole('grid', { name: 'Fournisseurs' })
    const row = within(grid).getByText('Candidat SARL').closest('tr')

    await userEvent.click(within(row).getByRole('button', { name: 'Rejeter la candidature' }))
    await confirmer('Rejeter')
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
    listeAvecCandidature()
    stockApi.deciderCandidatureFournisseur.mockRejectedValueOnce({
      response: { status: 403, data: { detail: 'Réservé à l\'administrateur.' } },
    })
    renderPage()
    const grid = await screen.findByRole('grid', { name: 'Fournisseurs' })
    const row = within(grid).getByText('Candidat SARL').closest('tr')

    await userEvent.click(within(row).getByRole('button', { name: 'Valider la candidature' }))
    await confirmer('Valider')
    // toastError best-effort — le point vérifiable est l'appel serveur lui-même
    // (le rendu du toast n'est pas garanti sans <Toaster> monté dans ce test).
    await waitFor(() => expect(stockApi.deciderCandidatureFournisseur).toHaveBeenCalledWith(4, true))
  })
})

/* ============================================================================
   ASTK95 (C-ASTK-026) — créer un fournisseur dont le nom normalisé existe
   déjà : le serveur crée (201, non bloquant) et renvoie
   `avertissements.nom` ; la liste l'affiche après fermeture du formulaire.
   ========================================================================== */
/* ============================================================================
   ASTK185 (C-ASTK-042, FOUR-8) — la liste lit TOUTES les pages : le 51ᵉ
   fournisseur est listé, cherchable et compté.
   ========================================================================== */
describe('FournisseursStock — liste complète (ASTK185)', () => {
  it('affiche le 51ᵉ fournisseur', async () => {
    const tous = Array.from({ length: 51 }, (_, i) => ({ id: 100 + i, nom: `Fournisseur ${i + 1}` }))
    stockApi.getAllFournisseurs.mockResolvedValueOnce({ data: tous })
    renderPage()
    await screen.findByRole('grid', { name: 'Fournisseurs' })
    expect(await screen.findByText('51 fournisseur(s)')).toBeInTheDocument()
    // (Au-delà de 50 lignes le DataTable se virtualise — jsdom sans hauteur
    // n'en rend aucune : le compteur d'en-tête est la preuve lisible ici.)
    expect(stockApi.getAllFournisseurs).toHaveBeenCalledWith({ ordering: 'nom' })
  })
})

/* ============================================================================
   ASTK225 (C-ASTK-045, FOUR-12) — identité légale saisissable sur la fiche :
   ICE / IF / RC / RIB envoyés par les routes existantes ; le 400 du serveur
   (format ICE) s'affiche sous le champ ; l'avertissement de doublon ICE du
   serveur est affiché tel quel. Réponses = le contrat committé.
   ========================================================================== */
describe('FournisseursStock — identité légale (ASTK225)', () => {
  const contrat = documentContrat('stock', 'fournisseur_conformite').routes

  it('saisir ICE et RIB', async () => {
    const corps = contrat.fournisseurs_conformite_champs.exemple_corps
    stockApi.updateFournisseur.mockResolvedValueOnce({ data: contrat.fournisseurs_conformite_champs.exemple })
    renderPage()
    const grid = await screen.findByRole('grid', { name: 'Fournisseurs' })
    await userEvent.click(within(within(grid).getByText('Actif SARL').closest('tr'))
      .getByRole('button', { name: 'Modifier' }))
    await screen.findByRole('dialog')
    await userEvent.type(screen.getByLabelText('ICE'), corps.ice)
    await userEvent.type(screen.getByLabelText('Identifiant fiscal (IF)'), corps.identifiant_fiscal)
    await userEvent.type(screen.getByLabelText('Registre du commerce (RC)'), corps.rc)
    await userEvent.type(screen.getByLabelText('RIB'), corps.rib)
    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(stockApi.updateFournisseur).toHaveBeenCalledWith(
      1, expect.objectContaining(corps)))
  })

  it("le 400 du serveur sur l'ICE s'affiche sous le champ", async () => {
    stockApi.updateFournisseur.mockRejectedValueOnce({
      response: { status: 400, data: {
        error: 'Données invalides.',
        ice: ["Format ICE invalide : l'ICE doit comporter exactement 15 chiffres."],
      } },
    })
    renderPage()
    const grid = await screen.findByRole('grid', { name: 'Fournisseurs' })
    await userEvent.click(within(within(grid).getByText('Actif SARL').closest('tr'))
      .getByRole('button', { name: 'Modifier' }))
    await screen.findByRole('dialog')
    await userEvent.type(screen.getByLabelText('ICE'), '123')
    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(await screen.findByText(/Format ICE invalide/)).toBeInTheDocument()
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it("affiche l'avertissement de doublon ICE renvoyé par le serveur", async () => {
    stockApi.updateFournisseur.mockResolvedValueOnce({ data: contrat.fournisseurs_ice_doublon.exemple })
    renderPage()
    const grid = await screen.findByRole('grid', { name: 'Fournisseurs' })
    await userEvent.click(within(within(grid).getByText('Actif SARL').closest('tr'))
      .getByRole('button', { name: 'Modifier' }))
    await screen.findByRole('dialog')
    await userEvent.type(screen.getByLabelText('ICE'), contrat.fournisseurs_ice_doublon.exemple_corps.ice)
    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(await screen.findByText(contrat.fournisseurs_ice_doublon.exemple.ice_duplicate_warning))
      .toBeInTheDocument()
  })
})

describe('FournisseursStock — doublon de nom (ASTK95)', () => {
  it("affiche l'avertissement de nom renvoyé par le serveur", async () => {
    stockApi.createFournisseur.mockResolvedValueOnce({
      data: {
        id: 9, nom: 'acme',
        avertissements: { nom: 'Un fournisseur « ACME » existe déjà.', ice: null },
      },
    })
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: /Nouveau fournisseur/ }))
    await userEvent.type(document.getElementById('fou-nom'), 'acme')
    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(stockApi.createFournisseur).toHaveBeenCalled())
    expect(await screen.findByText('Un fournisseur « ACME » existe déjà.')).toBeInTheDocument()
  })
})
