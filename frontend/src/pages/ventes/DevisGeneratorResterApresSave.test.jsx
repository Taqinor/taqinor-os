// EDC7 — moitié générateur du contrat EDC : après « Enregistrer les
// modifications » en Édition complète embarquée, l'écran RESTE dans l'éditeur
// (`onEnregistre(devisId)`, plus de `onDone` qui faisait basculer le panneau
// sur l'aperçu) ; `onDirtyChange` suit `dirty` (vrai après une frappe, faux
// après l'enregistrement) ; sans `onEnregistre`, repli sur `onDone`.
//
// Écran RÉEL rendu, API mockées.
// Run : npx vitest run src/pages/ventes/DevisGeneratorResterApresSave.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

import authReducer from '../../features/auth/store/authSlice'
import ventesReducer from '../../features/ventes/store/ventesSlice'
import { toast } from '../../ui/confirm'

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
    getPrixApplicable: vi.fn(),
    patchDevis: vi.fn(),
    replaceLignesDevis: vi.fn(),
    createDevisAtomic: vi.fn(),
    patchEtudeParams: vi.fn(),
    poserOverrides: vi.fn(),
    regenererOverride: vi.fn(),
  },
}))

import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'

const PANNEAU = {
  id: 101, nom: 'Panneau Canadien Solar 715W', prix_vente: 1200, tva: 10,
  is_archived: false, prix_achat: 800,
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

function makeStore() {
  return configureStore({
    reducer: { auth: authReducer, ventes: ventesReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role: 'normal', role_nom: 'Commercial', permissions: [],
        isAuthenticated: true, loading: false,
      },
    },
  })
}

function renderEdition(props) {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter initialEntries={['/crm/leads/7']}>
        <DevisGenerator embedded editId={42} onCancel={() => {}} {...props} />
      </MemoryRouter>
    </Provider>,
  )
}

const boutonPied = () => screen.getByRole('button', { name: /Enregistrer les modifications/ })
const note = () => screen.getByPlaceholderText(/Conditions particulières/)

beforeEach(async () => {
  vi.clearAllMocks()
  try { window.localStorage.clear() } catch { /* stockage indisponible */ }
  if (!window.matchMedia) {
    window.matchMedia = vi.fn().mockImplementation((q) => ({
      matches: false, media: q, onchange: null,
      addListener: vi.fn(), removeListener: vi.fn(),
      addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    }))
  }
  const stockApi = (await import('../../api/stockApi')).default
  stockApi.getProduits.mockResolvedValue({ data: [PANNEAU, ONDULEUR] })
  ventesApi.getDevisById.mockResolvedValue({ data: DEVIS })
  ventesApi.replaceLignesDevis.mockResolvedValue({ data: { updated_at: '2026-10-09T09:30:00Z' } })
  ventesApi.patchEtudeParams.mockResolvedValue({ data: {} })
})

/** Ouvre, attend la fenêtre de référence QJR581 (1,5 s), tape une note. */
async function ouvrirEtModifier() {
  await screen.findByRole('button', { name: /Enregistrer les modifications/ })
  await screen.findByDisplayValue(PANNEAU.nom)
  await new Promise((r) => setTimeout(r, 1700))
  fireEvent.change(note(), { target: { value: 'Acompte 30 % à la commande' } })
}

/** Clique « Enregistrer » ; un éventuel écart de factures se confirme d'un second clic. */
async function enregistrer() {
  fireEvent.click(boutonPied())
  await waitFor(() => {
    if (!ventesApi.replaceLignesDevis.mock.calls.length
        && screen.queryByTestId('erreur-enregistrement')) {
      fireEvent.click(boutonPied())
    }
    expect(ventesApi.replaceLignesDevis).toHaveBeenCalledTimes(1)
  })
}

describe('EDC7 — rester dans l\'éditeur après « Enregistrer les modifications »', () => {
  it('embarqué + onEnregistre : onEnregistre(42), pas onDone, toast, état conservé, dirty true → false', async () => {
    const onEnregistre = vi.fn()
    const onDone = vi.fn()
    const onDirtyChange = vi.fn()
    const succes = vi.spyOn(toast, 'success')
    renderEdition({ onEnregistre, onDone, onDirtyChange })
    // Valeur initiale : rien n'a changé.
    await waitFor(() => expect(onDirtyChange).toHaveBeenCalled())
    expect(onDirtyChange.mock.calls[0][0]).toBe(false)

    await ouvrirEtModifier()
    await waitFor(() => expect(onDirtyChange).toHaveBeenLastCalledWith(true))

    await enregistrer()
    await waitFor(() => expect(onEnregistre).toHaveBeenCalledWith(42))
    expect(onEnregistre).toHaveBeenCalledTimes(1)
    expect(onDone).not.toHaveBeenCalled()
    expect(succes).toHaveBeenCalledWith('Modifications enregistrées.')
    // `marquerEnregistre()` : dirty repasse à faux, le panneau le sait.
    await waitFor(() => expect(onDirtyChange).toHaveBeenLastCalledWith(false))
    // L'écran est TOUJOURS monté, avec la saisie de l'utilisateur.
    expect(boutonPied()).toBeInTheDocument()
    expect(note()).toHaveValue('Acompte 30 % à la commande')
    expect(screen.getByDisplayValue(PANNEAU.nom)).toBeInTheDocument()
    expect(screen.queryByText('Modifications non enregistrées')).toBeNull()
    succes.mockRestore()
  }, 20000)

  it('le jeton ré-armé part avec l\'enregistrement suivant (pas de faux conflit 409)', async () => {
    const onEnregistre = vi.fn()
    renderEdition({ onEnregistre, onDone: vi.fn() })
    await ouvrirEtModifier()
    await enregistrer()
    await waitFor(() => expect(onEnregistre).toHaveBeenCalledTimes(1))
    fireEvent.change(note(), { target: { value: 'Acompte 40 %' } })
    fireEvent.click(boutonPied())
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalledTimes(2))
    const extra = ventesApi.replaceLignesDevis.mock.calls[1][2]
    expect(extra.expected_updated_at).toBe('2026-10-09T09:30:00Z')
    await waitFor(() => expect(onEnregistre).toHaveBeenCalledTimes(2))
  }, 20000)

  it('sans onEnregistre : repli sur onDone(42), comme avant', async () => {
    const onDone = vi.fn()
    renderEdition({ onDone })
    await ouvrirEtModifier()
    await enregistrer()
    await waitFor(() => expect(onDone).toHaveBeenCalledWith(42))
  }, 20000)
})
