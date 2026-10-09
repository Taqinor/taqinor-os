// EDC5 — clavier de l'Édition complète : Entrée n'enregistre JAMAIS le devis
// (la soumission implicite du navigateur faisait quitter l'éditeur) ; Entrée
// dans une cellule de la table passe au même champ de la ligne suivante, et
// sur la dernière ligne ajoute une ligne ; Ctrl/Cmd+S enregistre (même chemin
// qu'un clic) ; Entrée dans le ProduitPicker ouvert garde son sens (sélection).
//
// `user-event` simule la soumission implicite (Entrée dans un champ ⇒ clic du
// bouton submit) : sans la garde, ces tests verraient `replaceLignesDevis`.
// Écran RÉEL rendu, API mockées.
// Run : npx vitest run src/pages/ventes/DevisGeneratorClavier.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

import authReducer from '../../features/auth/store/authSlice'
import ventesReducer from '../../features/ventes/store/ventesSlice'

vi.mock('../../api/crmApi', () => ({
  default: {
    getClients: vi.fn(() => Promise.resolve({ data: [] })),
    getLeads: vi.fn(() => Promise.resolve({ data: [] })),
    getLead: vi.fn(() => Promise.resolve({ data: null })),
  },
}))
vi.mock('../../api/stockApi', () => ({
  default: { getProduits: vi.fn(() => Promise.resolve({ data: [] })) },
}))
vi.mock('../../api/parametresApi', () => ({
  default: { getProfile: vi.fn(() => Promise.resolve({ data: {} })) },
}))
vi.mock('../../api/ventesApi', () => ({
  default: {
    getDevisById: vi.fn(),
    getParametresGammes: vi.fn(() => Promise.resolve({ data: {} })),
    getPrefillSite: vi.fn(() => Promise.resolve({ data: {} })),
    getOffresTaillesDevis: vi.fn(() => Promise.resolve({ data: { editable: false } })),
    lireOverrides: vi.fn(() => Promise.resolve({ data: {} })),
    getPrixApplicable: vi.fn(() => Promise.resolve({ data: null })),
    patchDevis: vi.fn(),
    replaceLignesDevis: vi.fn(),
    createDevisAtomic: vi.fn(),
    patchEtudeParams: vi.fn(),
    poserOverrides: vi.fn(),
    regenererOverride: vi.fn(),
  },
}))

import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'

const PANNEAU = {
  id: 101, nom: 'Panneau Canadien Solar 715W', prix_vente: 1200, tva: 10,
  is_archived: false, prix_achat: 800,
}
const PANNEAU_JINKO = {
  id: 103, nom: 'Panneau Jinko Tiger 600W', prix_vente: 1000, tva: 10,
  is_archived: false, prix_achat: 700,
}
const ONDULEUR = {
  id: 102, nom: 'Onduleur réseau 5kW Monophasé', prix_vente: 9000, tva: 20,
  is_archived: false, prix_achat: 6000,
}
const DEVIS = {
  id: 42, reference: 'DEV-202610-0042', statut: 'brouillon', modifiable: true,
  raison_non_modifiable: '', revision_possible: false, is_active: true,
  lead: null, client: 9, mode_installation: 'residentiel', taux_tva: '20.00',
  remise_globale: '0', updated_at: '2026-10-09T08:00:00Z',
  etude_params: { scenario: 'Sans batterie' },
  lignes: [
    { id: 1, produit: PANNEAU.id, designation: PANNEAU.nom, quantite: '8',
      prix_unitaire: '1200.00', taux_tva: '10.00', ordre: 0,
      type_ligne: 'produit', optionnelle: false },
    { id: 2, produit: ONDULEUR.id, designation: ONDULEUR.nom, quantite: '1',
      prix_unitaire: '9000.00', taux_tva: '20.00', ordre: 1,
      type_ligne: 'produit', optionnelle: false },
  ],
}

function makeStore({ peutRenommer = true } = {}) {
  return configureStore({
    reducer: { auth: authReducer, ventes: ventesReducer },
    preloadedState: {
      auth: peutRenommer
        // Commercial responsable + `stock_creer` : la désignation est
        // modifiable (QP2) — c'est elle qui reçoit le focus d'une ligne
        // ajoutée par Entrée.
        ? {
            user: { id: 1 }, role: 'normal', role_nom: 'Commercial responsable',
            permissions: ['stock_creer'], isAuthenticated: true, loading: false,
          }
        : {
            user: { id: 1 }, role: 'normal', role_nom: 'Commercial',
            permissions: [], isAuthenticated: true, loading: false,
          },
    },
  })
}

function renderEdition(options) {
  return render(
    <Provider store={makeStore(options)}>
      <MemoryRouter initialEntries={['/crm/leads/7']}>
        <DevisGenerator embedded editId={42} onDone={vi.fn()} onCancel={vi.fn()} />
      </MemoryRouter>
    </Provider>,
  )
}

const lignes = () => [...document.querySelectorAll('table.lines-table tbody tr[data-line-key]')]
const qteDe = (tr) => tr.querySelector('[data-role="line-qty"]')
const pause = (ms) => new Promise((r) => setTimeout(r, ms))

beforeEach(() => {
  vi.clearAllMocks()
  try { window.localStorage.clear() } catch { /* stockage indisponible */ }
  if (!window.matchMedia) {
    window.matchMedia = vi.fn().mockImplementation((q) => ({
      matches: false, media: q, onchange: null,
      addListener: vi.fn(), removeListener: vi.fn(),
      addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    }))
  }
  stockApi.getProduits.mockResolvedValue({ data: [PANNEAU, PANNEAU_JINKO, ONDULEUR] })
  ventesApi.getDevisById.mockResolvedValue({ data: DEVIS })
  ventesApi.replaceLignesDevis.mockResolvedValue({ data: { updated_at: '2026-10-09T09:30:00Z' } })
  ventesApi.patchEtudeParams.mockResolvedValue({ data: {} })
})

async function ouvrir(options) {
  renderEdition(options)
  await screen.findByRole('button', { name: /Enregistrer les modifications/ })
  await screen.findByDisplayValue(ONDULEUR.nom)
}

describe('EDC5 — Entrée n\'enregistre jamais le devis', () => {
  it('Entrée dans « Qté » : aucune soumission, focus sur la Qté de la ligne suivante', async () => {
    const user = userEvent.setup()
    await ouvrir()
    const [premiere, seconde] = lignes()
    await user.click(qteDe(premiere))
    await user.keyboard('{Enter}')
    await pause(300)
    expect(ventesApi.replaceLignesDevis).not.toHaveBeenCalled()
    expect(document.activeElement).toBe(qteDe(seconde))
    // Écran inchangé : toujours l'éditeur, même nombre de lignes.
    expect(screen.getByRole('button', { name: /Enregistrer les modifications/ })).toBeInTheDocument()
    expect(lignes()).toHaveLength(2)
  })

  it('Entrée dans « Prix unit. » de la dernière ligne : une ligne de plus, focus sur sa désignation', async () => {
    const user = userEvent.setup()
    await ouvrir()
    const derniere = lignes().at(-1)
    await user.click(derniere.querySelector('td[data-label="Prix unit. TTC"] input'))
    await user.keyboard('{Enter}')
    await waitFor(() => expect(lignes()).toHaveLength(3))
    const nouvelle = lignes().at(-1)
    await waitFor(() => expect(document.activeElement)
      .toBe(nouvelle.querySelector('td[data-label="Désignation"] input')))
    expect(ventesApi.replaceLignesDevis).not.toHaveBeenCalled()
  })

  it('rôle sans droit de renommer (désignation verrouillée) : la ligne ajoutée reçoit le focus sur son sélecteur produit', async () => {
    const user = userEvent.setup()
    await ouvrir({ peutRenommer: false })
    await user.click(qteDe(lignes().at(-1)))
    await user.keyboard('{Enter}')
    await waitFor(() => expect(lignes()).toHaveLength(3))
    const nouvelle = lignes().at(-1)
    await waitFor(() => expect(document.activeElement)
      .toBe(within(nouvelle.querySelector('td[data-label="Produit (stock)"]')).getByRole('button')))
    expect(ventesApi.replaceLignesDevis).not.toHaveBeenCalled()
  })

  it('Entrée dans un champ hors table (puissance cible) et dans la désignation : aucune soumission', async () => {
    const user = userEvent.setup()
    await ouvrir()
    await user.click(screen.getByLabelText('Puissance cible (kWc)'))
    await user.keyboard('{Enter}')
    await user.click(lignes()[0].querySelector('td[data-label="Désignation"] input'))
    await user.keyboard('{Enter}')
    await pause(300)
    expect(ventesApi.replaceLignesDevis).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /Enregistrer les modifications/ })).toBeInTheDocument()
  })

  it('Ctrl+S : enregistre UNE fois, par le chemin normal (replace-lines)', async () => {
    const user = userEvent.setup()
    await ouvrir()
    await user.click(screen.getByPlaceholderText(/Conditions particulières/))
    await user.keyboard('{Control>}s{/Control}')
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalledTimes(1))
    expect(ventesApi.replaceLignesDevis.mock.calls[0][0]).toBe(42)
    await pause(200)
    expect(ventesApi.replaceLignesDevis).toHaveBeenCalledTimes(1)
  })

  it('Ctrl+Entrée dans une cellule : enregistre aussi', async () => {
    const user = userEvent.setup()
    await ouvrir()
    await user.click(qteDe(lignes()[0]))
    await user.keyboard('{Control>}{Enter}{/Control}')
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalledTimes(1))
  })

  it('Entrée dans le ProduitPicker ouvert garde son sens : elle SÉLECTIONNE, sans soumettre', async () => {
    const user = userEvent.setup()
    await ouvrir()
    const premiere = lignes()[0]
    const cellule = premiere.querySelector('td[data-label="Produit (stock)"]')
    await user.click(within(cellule).getByRole('button', { name: /Canadien Solar/ }))
    const recherche = await screen.findByPlaceholderText(/Chercher un produit/)
    await user.type(recherche, 'Jinko')
    await user.keyboard('{Enter}')
    await waitFor(() => expect(within(cellule).getByRole('button', { name: /Jinko Tiger/ })).toBeInTheDocument())
    await waitFor(() => expect(premiere.querySelector('td[data-label="Désignation"] input'))
      .toHaveValue(PANNEAU_JINKO.nom))
    await pause(200)
    expect(ventesApi.replaceLignesDevis).not.toHaveBeenCalled()
    expect(lignes()).toHaveLength(2)
  })
})
