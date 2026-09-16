// QP1 — Filtre du picker produit par type de slot (via classifyProduct). On
// vérifie que `typeFilter` restreint bien la liste affichée au type attendu
// (ex. seuls les onduleurs hybrides pour une ligne « Onduleur hybride ») et
// que sans typeFilter (ligne non typée) la liste reste complète.
//
// QG6 — le picker consulte maintenant le hook de rôle (useCanCreateProduit,
// via react-redux) pour afficher/masquer « + Nouveau ». Les rendus passent
// donc par un Provider Redux minimal (voir renderPicker + ProduitPicker.qg6).

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import authReducer from '../features/auth/store/authSlice'
import ProduitPicker from './ProduitPicker'
import stockApi from '../api/stockApi'

// jsdom n'implémente pas scrollIntoView (utilisé par le picker pour garder le
// curseur visible pendant la navigation clavier) — no-op suffisant en test.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {}
}

const PRODUITS = [
  { id: 1, nom: 'Onduleur Hybride Deye 6kW', prix_vente: 8000, tva: 20, is_archived: false },
  { id: 2, nom: 'Onduleur Réseau Huawei 5kW', prix_vente: 6000, tva: 20, is_archived: false },
  { id: 3, nom: 'Panneau Solaire 550W', prix_vente: 900, tva: 10, is_archived: false },
  { id: 4, nom: 'Batterie Lithium 5kWh', prix_vente: 15000, tva: 20, is_archived: false },
]

function makeStore({ role_nom = 'Magasinier', permissions = [] } = {}) {
  return configureStore({
    reducer: { auth: authReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role: 'normal', role_nom, permissions,
        isAuthenticated: true, loading: false,
      },
    },
  })
}

function renderPicker(props, authState) {
  return render(
    <Provider store={makeStore(authState)}><ProduitPicker {...props} /></Provider>,
  )
}

function openPicker() {
  fireEvent.click(screen.getByRole('button'))
}

describe('ProduitPicker typeFilter (QP1)', () => {
  it('sans typeFilter, affiche tous les produits', () => {
    renderPicker({ produits: PRODUITS, value: '', onChange: () => {} })
    openPicker()
    expect(screen.getByText('Onduleur Hybride Deye 6kW')).toBeInTheDocument()
    expect(screen.getByText('Onduleur Réseau Huawei 5kW')).toBeInTheDocument()
    expect(screen.getByText('Panneau Solaire 550W')).toBeInTheDocument()
    expect(screen.getByText('Batterie Lithium 5kWh')).toBeInTheDocument()
  })

  it('avec typeFilter="onduleur_hybride", ne montre que les onduleurs hybrides', () => {
    renderPicker({ produits: PRODUITS, value: '', onChange: () => {}, typeFilter: 'onduleur_hybride' })
    openPicker()
    expect(screen.getByText('Onduleur Hybride Deye 6kW')).toBeInTheDocument()
    expect(screen.queryByText('Onduleur Réseau Huawei 5kW')).not.toBeInTheDocument()
    expect(screen.queryByText('Panneau Solaire 550W')).not.toBeInTheDocument()
    expect(screen.queryByText('Batterie Lithium 5kWh')).not.toBeInTheDocument()
  })

  it('avec typeFilter="panneau", ne montre que les panneaux', () => {
    renderPicker({ produits: PRODUITS, value: '', onChange: () => {}, typeFilter: 'panneau' })
    openPicker()
    expect(screen.getByText('Panneau Solaire 550W')).toBeInTheDocument()
    expect(screen.queryByText('Onduleur Hybride Deye 6kW')).not.toBeInTheDocument()
  })

  it('avec typeFilter="batterie", ne montre que les batteries', () => {
    renderPicker({ produits: PRODUITS, value: '', onChange: () => {}, typeFilter: 'batterie' })
    openPicker()
    expect(screen.getByText('Batterie Lithium 5kWh')).toBeInTheDocument()
    expect(screen.queryByText('Onduleur Réseau Huawei 5kW')).not.toBeInTheDocument()
  })
})

// QG6 — « + Nouveau produit » n'apparaît que pour Directeur/Commercial
// responsable (hook QG5) ; sélection auto sur la ligne après création.
// STKCAT13 — `getCategories` par défaut résout une liste VIDE (silencieux) :
// un test qui ne s'intéresse pas à la catégorie n'a rien à configurer pour
// que « Nouveau » reste utilisable (les tests STKCAT13 ci-dessous surchargent
// cette résolution pour leurs propres assertions).
vi.mock('../api/stockApi', () => ({
  default: {
    createProduit: vi.fn(),
    getCategories: vi.fn(() => Promise.resolve({ data: { results: [] } })),
  },
}))

// STKCAT13 — jsdom n'ouvre pas de façon fiable le Radix Select (portail +
// pointer events) : pattern déjà établi du dépôt (paie/PaieDeclarations.test.jsx,
// monitoring/ClientPortalPage.test.jsx, sav/TicketWorksheetPanel.test.jsx) — on
// remplace ses primitives par un <select> natif ; le reste de `../ui` (Dialog,
// Button, Input, Label…) reste RÉEL, donc le test continue de valider la vraie
// modale.
vi.mock('../ui', async (importActual) => {
  const actual = await importActual()
  const Passthrough = ({ children }) => <>{children}</>
  return {
    ...actual,
    Select: ({ value, onValueChange, children }) => (
      <select role="combobox" aria-label="Catégorie" value={value}
        onChange={(e) => onValueChange(e.target.value)}>
        {children}
      </select>
    ),
    SelectTrigger: Passthrough,
    SelectValue: () => null,
    SelectContent: Passthrough,
    SelectItem: ({ value, children }) => <option value={value}>{children}</option>,
  }
})

describe('ProduitPicker — QG6 quick-create (rôle-gated)', () => {
  it("n'affiche pas « Nouveau » pour un rôle non autorisé (Magasinier)", () => {
    renderPicker({ produits: PRODUITS, value: '', onChange: () => {} },
      { role_nom: 'Magasinier', permissions: ['stock_creer'] })
    openPicker()
    expect(screen.queryByTitle('Nouveau produit')).not.toBeInTheDocument()
  })

  it('affiche « Nouveau » pour Directeur et crée + sélectionne le produit', async () => {
    stockApi.createProduit.mockResolvedValue({
      data: { id: 99, nom: 'Onduleur Test', prix_vente: 5000, is_archived: false },
    })
    const onChange = vi.fn()
    const onProduitCreated = vi.fn()
    renderPicker(
      { produits: PRODUITS, value: '', onChange, onProduitCreated },
      { role_nom: 'Directeur', permissions: ['stock_creer'] },
    )
    openPicker()
    fireEvent.click(screen.getByTitle('Nouveau produit'))
    fireEvent.change(screen.getByLabelText(/Nom du produit/), { target: { value: 'Onduleur Test' } })
    fireEvent.click(screen.getByRole('button', { name: /Créer et sélectionner/ }))
    await waitFor(() => expect(stockApi.createProduit).toHaveBeenCalled())
    await waitFor(() => expect(onChange).toHaveBeenCalledWith('99'))
    expect(onProduitCreated).toHaveBeenCalledWith(
      expect.objectContaining({ id: 99, nom: 'Onduleur Test' }))
  })

  it('affiche « Nouveau » pour Commercial responsable', () => {
    renderPicker({ produits: PRODUITS, value: '', onChange: () => {} },
      { role_nom: 'Commercial responsable', permissions: ['stock_creer'] })
    openPicker()
    expect(screen.getByTitle('Nouveau produit')).toBeInTheDocument()
  })
})

// STKCAT12 — UNION jamais substitution : un produit hors mot-clé mais dont la
// CATÉGORIE est typée (ex. « Pergola » rangée en catégorie structure) doit
// être visible et sélectionnable dans la section « Recommandé pour cette
// ligne » — c'était le bug (« Pergola introuvable ») : avant STKCAT12, un
// typeFilter FILTRAIT `actifs` par seul mot-clé et la rendait invisible pour
// toujours, même en cherchant.
const PRODUITS_STKCAT12 = [
  ...PRODUITS,
  {
    id: 5, nom: 'Pergola', prix_vente: '500', tva: 20, is_archived: false,
    categorie_type: 'structure',
    categorie: { nom: 'Structures & fixation', type_equipement: 'structure' },
  },
  {
    id: 6, nom: 'Socles', prix_vente: 300, tva: 20, is_archived: false,
    categorie: { nom: 'Structures & fixation' },
  },
]

describe('ProduitPicker — STKCAT12 sections Recommandé / Tout le catalogue', () => {
  it('« Pergola » (catégorie typée structure, pas de mot-clé) est visible et sélectionnable dans Recommandé pour typeFilter="structure"', () => {
    renderPicker({ produits: PRODUITS_STKCAT12, value: '', onChange: () => {}, typeFilter: 'structure' })
    openPicker()
    expect(screen.getByText('Recommandé pour cette ligne')).toBeInTheDocument()
    const btn = screen.getByText('Pergola').closest('button')
    expect(btn).not.toBeNull()
    expect(btn).not.toBeDisabled()
  })

  it('« Pergola » reste dans Recommandé pour typeFilter="structure_acier" (même famille)', () => {
    renderPicker({ produits: PRODUITS_STKCAT12, value: '', onChange: () => {}, typeFilter: 'structure_acier' })
    openPicker()
    const btn = screen.getByText('Pergola').closest('button')
    expect(btn).not.toBeDisabled()
  })

  it('une ligne « socle » liste « Socles » dans Recommandé ; le reste (ex. panneaux) reste atteignable via la recherche, jamais perdu', () => {
    renderPicker({ produits: PRODUITS_STKCAT12, value: '', onChange: () => {}, typeFilter: 'socle' })
    openPicker()
    // Sans recherche : seule la section Recommandé (comportement historique).
    expect(screen.getByText('Socles')).toBeInTheDocument()
    expect(screen.queryByText('Panneau Solaire 550W')).not.toBeInTheDocument()
    expect(screen.queryByText(/Tout le catalogue/)).not.toBeInTheDocument()
    // Indice honnête : annonce le total du catalogue, pas le seul sous-compte.
    expect(screen.getByText(/Tapez pour chercher dans \d+ produits/)).toBeInTheDocument()
    // Dès la recherche : le panneau (hors prédicat socle) redevient visible,
    // groupé sous « Tout le catalogue » — jamais une substitution permanente.
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'panneau' } })
    expect(screen.getByText(/Tout le catalogue/)).toBeInTheDocument()
    expect(screen.getByText('Panneau Solaire 550W')).toBeInTheDocument()
  })

  it('requête vide n\'affiche jamais « Aucun produit pour «  » » — même quand Recommandé est vide (0 ligne)', () => {
    // typeFilter sans aucune correspondance mot-clé NI famille dans PRODUITS :
    // Recommandé est vide et, requête vide, « Tout le catalogue » ne s'affiche
    // pas non plus → 0 ligne. L'état vide doit rester honnête (juste l'indice
    // de recherche), jamais « Aucun produit pour «  » » (pas de recherche tapée).
    renderPicker({ produits: PRODUITS, value: '', onChange: () => {}, typeFilter: 'batterie_gel_inconnue' })
    openPicker()
    expect(screen.queryByText(/Aucun produit pour/)).not.toBeInTheDocument()
    expect(screen.getByText(/Tapez pour chercher dans \d+ produits/)).toBeInTheDocument()
  })

  it('une recherche sans résultat affiche « Aucun produit pour « <query> » »', () => {
    renderPicker({ produits: PRODUITS, value: '', onChange: () => {} })
    openPicker()
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'zzz-inexistant' } })
    expect(screen.getByText(/Aucun produit pour/)).toBeInTheDocument()
  })
})

// STKCAT13 — Création rapide : select Catégorie optionnel + `defaultCategorieId`.
// Directeur/Commercial responsable seulement (même garde QG6) ; la catégorie
// n'est JAMAIS requise, et n'est pré-sélectionnée que quand la famille de la
// ligne désigne SANS AMBIGÜITÉ (exactement une) catégorie typée de la société.
async function ouvrirNouveau(authState) {
  renderPicker(
    { produits: PRODUITS, value: '', onChange: () => {} },
    authState ?? { role_nom: 'Directeur', permissions: ['stock_creer'] },
  )
  openPicker()
  fireEvent.click(screen.getByTitle('Nouveau produit'))
  // Le select Catégorie est toujours affiché (jamais requis) — attendre qu'il
  // ait fini son chargement paresseux avant d'interagir avec le formulaire.
  await waitFor(() => expect(screen.getByRole('combobox', { name: 'Catégorie' })).toBeInTheDocument())
}

describe('ProduitPicker — STKCAT13 création rapide : catégorie optionnelle', () => {
  it('payload SANS choix de catégorie : pas de clé categorie_id (jamais requise)', async () => {
    stockApi.getCategories.mockResolvedValue({ data: { results: [] } })
    stockApi.createProduit.mockResolvedValueOnce({
      data: { id: 101, nom: 'Sans Catégorie', prix_vente: 100, is_archived: false },
    })
    await ouvrirNouveau()
    fireEvent.change(screen.getByLabelText(/Nom du produit/), { target: { value: 'Sans Catégorie' } })
    fireEvent.click(screen.getByRole('button', { name: /Créer et sélectionner/ }))
    await waitFor(() => expect(stockApi.createProduit).toHaveBeenCalled())
    const payload = stockApi.createProduit.mock.calls.at(-1)[0]
    expect(payload).not.toHaveProperty('categorie_id')
  })

  it('payload AVEC catégorie choisie manuellement : categorie_id porte l\'id choisi', async () => {
    stockApi.getCategories.mockResolvedValue({
      data: {
        results: [
          { id: 7, nom: 'Structures & fixation', type_equipement: 'structure' },
          { id: 8, nom: 'Onduleurs', type_equipement: null },
        ],
      },
    })
    stockApi.createProduit.mockResolvedValueOnce({
      data: { id: 102, nom: 'Avec Catégorie', prix_vente: 100, is_archived: false },
    })
    await ouvrirNouveau()
    fireEvent.change(screen.getByRole('combobox', { name: 'Catégorie' }), { target: { value: '8' } })
    fireEvent.change(screen.getByLabelText(/Nom du produit/), { target: { value: 'Avec Catégorie' } })
    fireEvent.click(screen.getByRole('button', { name: /Créer et sélectionner/ }))
    await waitFor(() => expect(stockApi.createProduit).toHaveBeenCalled())
    const payload = stockApi.createProduit.mock.calls.at(-1)[0]
    expect(payload.categorie_id).toBe(8)
  })

  it('defaultCategorieId pré-sélectionne SEULEMENT quand la famille désigne EXACTEMENT une catégorie typée', async () => {
    // typeFilter="structure" → famille="structure" ; UNE SEULE catégorie
    // société porte type_equipement="structure" → pré-sélection automatique,
    // sans que le test touche le select.
    stockApi.getCategories.mockResolvedValue({
      data: {
        results: [
          { id: 7, nom: 'Structures & fixation', type_equipement: 'structure' },
          { id: 8, nom: 'Onduleurs', type_equipement: 'onduleur' },
        ],
      },
    })
    stockApi.createProduit.mockResolvedValueOnce({
      data: { id: 103, nom: 'Pergola Auto', prix_vente: 100, is_archived: false },
    })
    renderPicker(
      { produits: PRODUITS, value: '', onChange: () => {}, typeFilter: 'structure' },
      { role_nom: 'Directeur', permissions: ['stock_creer'] },
    )
    openPicker()
    fireEvent.click(screen.getByTitle('Nouveau produit'))
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Catégorie' })).toHaveValue('7'))
    fireEvent.change(screen.getByLabelText(/Nom du produit/), { target: { value: 'Pergola Auto' } })
    fireEvent.click(screen.getByRole('button', { name: /Créer et sélectionner/ }))
    await waitFor(() => expect(stockApi.createProduit).toHaveBeenCalled())
    const payload = stockApi.createProduit.mock.calls.at(-1)[0]
    expect(payload.categorie_id).toBe(7)
  })

  it('defaultCategorieId reste ABSENT quand 2 catégories partagent la même famille (ambigu → l\'utilisateur choisit)', async () => {
    // Deux catégories "structure" (ex. société avec Structures acier ET alu
    // toutes deux typées "structure") : aucune n'est promue par défaut.
    stockApi.getCategories.mockResolvedValue({
      data: {
        results: [
          { id: 7, nom: 'Structures acier', type_equipement: 'structure' },
          { id: 9, nom: 'Structures alu', type_equipement: 'structure' },
        ],
      },
    })
    stockApi.createProduit.mockResolvedValueOnce({
      data: { id: 104, nom: 'Ambigu', prix_vente: 100, is_archived: false },
    })
    renderPicker(
      { produits: PRODUITS, value: '', onChange: () => {}, typeFilter: 'structure' },
      { role_nom: 'Directeur', permissions: ['stock_creer'] },
    )
    openPicker()
    fireEvent.click(screen.getByTitle('Nouveau produit'))
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Catégorie' })).toBeInTheDocument())
    fireEvent.change(screen.getByLabelText(/Nom du produit/), { target: { value: 'Ambigu' } })
    fireEvent.click(screen.getByRole('button', { name: /Créer et sélectionner/ }))
    await waitFor(() => expect(stockApi.createProduit).toHaveBeenCalled())
    const payload = stockApi.createProduit.mock.calls.at(-1)[0]
    expect(payload).not.toHaveProperty('categorie_id')
  })
})
