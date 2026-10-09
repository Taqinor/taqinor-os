// EDC6 (suite, orchestrateur 09/10/2026) — « Annuler » du générateur (barre
// en tête, pied, rail) sur un écran MODIFIÉ demande confirmation avant
// d'abandonner, comme Échap et le voile du panneau (EDC6) ; sans modification,
// il sort directement comme avant. Écran RÉEL rendu, API mockées ; la
// confirmation passe par le repli `window.confirm` de `useConfirm()` (aucun
// ConfirmProvider monté ici), bouchonné pour choisir « Rester » ou « Abandonner ».
// Run : npx vitest run src/pages/ventes/DevisGeneratorAnnulerModifie.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

import authReducer from '../../features/auth/store/authSlice'
import ventesReducer from '../../features/ventes/store/ventesSlice'

vi.mock('../../api/crmApi', () => ({
  default: {
    getClients: vi.fn(() => Promise.resolve({ data: [] })),
    getLeads: vi.fn(() => Promise.resolve({ data: [] })),
    getLead: vi.fn(),
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
        <DevisGenerator embedded editId={42} {...props} />
      </MemoryRouter>
    </Provider>,
  )
}

const note = () => screen.getByPlaceholderText(/Conditions particulières/)
// « Annuler » de la barre d'actions en tête (le pied et le rail passent par
// le même `annuler`).
const annulerBarre = () => screen.getByRole('toolbar', { name: /Actions du devis/ })
  .querySelector('.gen-barre-annuler')

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
})

/** Ouvre l'édition et attend la fenêtre de référence QJR581 (1,5 s). */
async function ouvrir() {
  await screen.findByRole('button', { name: /Enregistrer les modifications/ })
  await screen.findByDisplayValue(PANNEAU.nom)
  await new Promise((r) => setTimeout(r, 1700))
}

describe('EDC6 (suite) — « Annuler » du générateur sur un écran modifié', () => {
  it('sans modification : sortie directe, aucune confirmation', async () => {
    const onCancel = vi.fn()
    const confirmSpy = vi.spyOn(window, 'confirm').mockImplementation(() => true)
    renderEdition({ onCancel })
    await ouvrir()
    fireEvent.click(annulerBarre())
    await waitFor(() => expect(onCancel).toHaveBeenCalledTimes(1))
    expect(confirmSpy).not.toHaveBeenCalled()
    confirmSpy.mockRestore()
  })

  it('modifié puis « Rester » : on reste dans l\'éditeur, onCancel jamais appelé', async () => {
    const onCancel = vi.fn()
    const confirmSpy = vi.spyOn(window, 'confirm').mockImplementation(() => false)
    renderEdition({ onCancel })
    await ouvrir()
    fireEvent.change(note(), { target: { value: 'Acompte 30 % à la commande' } })
    await screen.findByTestId('gen-barre-non-enregistre')
    fireEvent.click(annulerBarre())
    await waitFor(() => expect(confirmSpy).toHaveBeenCalledTimes(1))
    expect(confirmSpy.mock.calls[0][0]).toMatch(/pas été enregistrées/)
    await new Promise((r) => setTimeout(r, 50))
    expect(onCancel).not.toHaveBeenCalled()
    expect(note().value).toBe('Acompte 30 % à la commande')
    confirmSpy.mockRestore()
  })

  it('modifié puis « Abandonner » : onCancel appelé une fois', async () => {
    const onCancel = vi.fn()
    const confirmSpy = vi.spyOn(window, 'confirm').mockImplementation(() => true)
    renderEdition({ onCancel })
    await ouvrir()
    fireEvent.change(note(), { target: { value: 'Acompte 30 % à la commande' } })
    await screen.findByTestId('gen-barre-non-enregistre')
    fireEvent.click(annulerBarre())
    await waitFor(() => expect(onCancel).toHaveBeenCalledTimes(1))
    expect(confirmSpy).toHaveBeenCalledTimes(1)
    confirmSpy.mockRestore()
  })
})
