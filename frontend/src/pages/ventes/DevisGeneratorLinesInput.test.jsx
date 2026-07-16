// VX137 — la table de lignes du générateur utilise `ui/Input` (design system)
// au lieu de `<input className="form-control">` natif, comme les 9 autres
// cartes du même fichier (VX17 avait déjà retiré les hex codés en dur des
// styles ; ce delta ne portait que sur le remplacement du composant). Garde
// absolue : le formulaire reste `noValidate`/`step="any"` — aucune saisie
// tapée (quantité, prix, TVA) n'est jamais snapée/rejetée.

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

import authReducer from '../../features/auth/store/authSlice'
import ventesReducer from '../../features/ventes/store/ventesSlice'

vi.mock('../../api/crmApi', () => ({
  default: {
    getClients: vi.fn(() => Promise.resolve({ data: [] })),
    getLeads: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))
vi.mock('../../api/stockApi', () => ({
  default: {
    getProduits: vi.fn(() => Promise.resolve({ data: [] })),
    dupliquerProduit: vi.fn(),
  },
}))
vi.mock('../../api/parametresApi', () => ({
  default: { getProfile: vi.fn(() => Promise.resolve({ data: {} })) },
}))
vi.mock('../../api/ventesApi', () => ({
  default: {
    getDevisById: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

// VX188 — espionne les rendus de ProduitPicker (sans changer son comportement
// réel) pour prouver que DevisLineRow (React.memo) saute le re-rendu d'une
// ligne inchangée quand un état SANS RAPPORT (« Note ») change ailleurs dans
// DevisGenerator.
const produitPickerRenderSpy = vi.fn()
vi.mock('../../components/ProduitPicker', async (importOriginal) => {
  const actual = await importOriginal()
  const Real = actual.default
  return {
    default: (props) => {
      produitPickerRenderSpy(props.value)
      return <Real {...props} />
    },
  }
})

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import DevisGenerator from './DevisGenerator'

const PRODUITS = [
  { id: 10, nom: 'Smart Meter Huawei DTSU666', prix_vente: 1500, tva: 20, is_archived: false, prix_achat: 900 },
]

function makeStore() {
  return configureStore({
    reducer: { auth: authReducer, ventes: ventesReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role: 'normal', role_nom: 'Directeur', permissions: ['stock_creer'],
        isAuthenticated: true, loading: false,
      },
    },
  })
}

function renderGenerator() {
  crmApi.getClients.mockResolvedValue({ data: [] })
  crmApi.getLeads.mockResolvedValue({ data: [] })
  stockApi.getProduits.mockResolvedValue({ data: PRODUITS })
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter>
        <DevisGenerator />
      </MemoryRouter>
    </Provider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {}
  if (!window.matchMedia) {
    window.matchMedia = vi.fn().mockImplementation((q) => ({
      matches: false, media: q, onchange: null,
      addListener: vi.fn(), removeListener: vi.fn(),
      addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    }))
  }
  if (!globalThis.ResizeObserver) {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

describe('VX137 — table de lignes : champs design system, saisie jamais rejetée', () => {
  it('le formulaire reste noValidate et les champs de ligne acceptent step="any"', async () => {
    renderGenerator()
    const designation = await screen.findByDisplayValue('Smart Meter Huawei DTSU666')
    const row = designation.closest('tr')
    const qte = row.querySelector('td[data-label="Qté"] input')
    const prix = row.querySelector('td[data-label="Prix unit. TTC"] input')
    const tva = row.querySelector('td[data-label="TVA %"] input')

    expect(document.getElementById('gen-form')).toHaveAttribute('novalidate')
    expect(qte).toHaveAttribute('step', 'any')
    expect(prix).toHaveAttribute('step', 'any')
    expect(tva).toHaveAttribute('step', 'any')
  })

  it('accepte une saisie décimale précise sans la snapper (step="any") ni la rejeter', async () => {
    renderGenerator()
    const designation = await screen.findByDisplayValue('Smart Meter Huawei DTSU666')
    const row = designation.closest('tr')
    const prix = row.querySelector('td[data-label="Prix unit. TTC"] input')

    // `step="any"` : une décimale « impaire » n'est jamais arrondie à l'entier
    // le plus proche (le vrai contrat « ne snappe jamais », form noValidate).
    fireEvent.change(prix, { target: { value: '12.7' } })
    expect(prix.value).toBe('12.7')

    fireEvent.change(prix, { target: { value: '1234.567' } })
    expect(prix.value).toBe('1234.567')
  })

  it('la table de lignes ne contient plus aucun <input class="form-control"> natif', async () => {
    renderGenerator()
    await screen.findByDisplayValue('Smart Meter Huawei DTSU666')
    const table = document.querySelector('.lines-table')
    expect(table.querySelectorAll('input.form-control').length).toBe(0)
  })
})

describe('VX188 — DevisLineRow mémoïsé : taper dans Note ne re-rend pas les lignes inchangées', () => {
  it('taper dans « Note » ne ré-invoque PAS ProduitPicker pour la ligne existante', async () => {
    renderGenerator()
    await screen.findByDisplayValue('Smart Meter Huawei DTSU666')
    produitPickerRenderSpy.mockClear()

    const note = screen.getByPlaceholderText('Conditions de paiement, remarques internes...')
    fireEvent.change(note, { target: { value: 'r' } })
    fireEvent.change(note, { target: { value: 'rd' } })
    fireEvent.change(note, { target: { value: 'rda' } })

    // Le composant DevisGenerator entier re-rend à chaque frappe (state
    // « note » au niveau parent) mais React.memo(DevisLineRow) doit sauter
    // le re-rendu de la ligne inchangée : ProduitPicker n'est jamais
    // ré-invoqué pour elle.
    expect(produitPickerRenderSpy).not.toHaveBeenCalled()
  })
})
