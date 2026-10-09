// EDC2 — l'Édition complète prend toute la largeur : la racine du générateur
// est le conteneur interrogé (`gen-root`), le rail récapitulatif ne porte plus
// AUCUNE classe `lg:` (sa visibilité suit `@container gen`, index.css bloc
// EDC2) et le total condensé du pied n'est plus masqué par `lg:hidden`.
//
// Écran RÉEL rendu (embarqué et pleine page), API mockées.
// Run : npx vitest run src/pages/ventes/DevisGeneratorPleineLargeur.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

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
    getPrixApplicable: vi.fn(),
    patchDevis: vi.fn(),
    replaceLignesDevis: vi.fn(),
    createDevisAtomic: vi.fn(),
    patchEtudeParams: vi.fn(),
  },
}))

import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'

const DEVIS = {
  id: 42, reference: 'DEV-202610-0042', statut: 'brouillon', modifiable: true,
  raison_non_modifiable: '', revision_possible: false, is_active: true,
  lead: null, client: 9, mode_installation: 'residentiel', taux_tva: '20.00',
  remise_globale: '0', etude_params: { scenario: 'Sans batterie' },
  lignes: [
    { id: 1, produit: null, designation: 'Installation', quantite: '1',
      prix_unitaire: '1000.00', taux_tva: '20.00', ordre: 0,
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
  ventesApi.getDevisById.mockResolvedValue({ data: DEVIS })
})

function verifierRail(container) {
  const racine = container.querySelector('.gen-root')
  expect(racine).not.toBeNull()
  const rail = container.querySelector('aside.gen-summary-rail')
  expect(rail).not.toBeNull()
  // Plus aucune classe `lg:` ni `hidden` : la container query décide seule.
  const classes = [...rail.classList]
  expect(classes.filter((c) => c.startsWith('lg:'))).toEqual([])
  expect(classes).not.toContain('hidden')
  // Plus de `top: var(--header-h, 64px)` en ligne (64 px d'un en-tête absent).
  expect(rail.getAttribute('style')).toBeNull()
  // Le rail est bien DANS la racine interrogée (un conteneur ne s'interroge
  // pas lui-même : le rail doit en être un descendant).
  expect(racine.contains(rail)).toBe(true)
  // Total condensé du pied : piloté par `gen-ttc-condense`, plus par lg:hidden.
  const condense = container.querySelector('.gen-actions-sticky .gen-ttc-condense')
  expect(condense).not.toBeNull()
  expect(condense.classList.contains('lg:hidden')).toBe(false)
}

describe('EDC2 — racine gen-root, rail sans classe lg:', () => {
  it('embarqué (Édition complète du panneau) : gen-root + gen-embedded, rail piloté par container query', async () => {
    const { container } = render(
      <Provider store={makeStore()}>
        <MemoryRouter initialEntries={['/crm/leads/7']}>
          <DevisGenerator embedded editId={42} onDone={() => {}} onCancel={() => {}} />
        </MemoryRouter>
      </Provider>,
    )
    await waitFor(() => expect(ventesApi.getDevisById).toHaveBeenCalledWith(42))
    await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    const racine = container.querySelector('.gen-root')
    expect(racine.classList.contains('gen-embedded')).toBe(true)
    verifierRail(container)
  })

  it('pleine page (?edit=) : gen-root + gen-page, rail piloté par container query', async () => {
    const { container } = render(
      <Provider store={makeStore()}>
        <MemoryRouter initialEntries={['/ventes/devis/nouveau?edit=42']}>
          <Routes>
            <Route path="/ventes/devis/nouveau" element={<DevisGenerator />} />
          </Routes>
        </MemoryRouter>
      </Provider>,
    )
    await waitFor(() => expect(ventesApi.getDevisById).toHaveBeenCalledWith('42'))
    await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    const racine = container.querySelector('.gen-root')
    expect(racine.classList.contains('gen-page')).toBe(true)
    verifierRail(container)
  })

  it('table des lignes : largeurs fixes sur les colonnes numériques, Désignation/Produit flexibles', async () => {
    const { container } = render(
      <Provider store={makeStore()}>
        <MemoryRouter initialEntries={['/crm/leads/7']}>
          <DevisGenerator embedded editId={42} onDone={() => {}} onCancel={() => {}} />
        </MemoryRouter>
      </Provider>,
    )
    await screen.findByDisplayValue('Installation')
    const entetes = [...container.querySelectorAll('table.lines-table thead th')]
    const largeur = (texte) => entetes.find((th) => th.textContent.trim() === texte)?.style.width
    expect(largeur('Qté')).toBe('96px')
    expect(largeur('Prix Unit. TTC')).toBe('128px')
    expect(largeur('TVA %')).toBe('72px')
    expect(largeur('Total TTC')).toBe('128px')
    expect(largeur('Option')).toBe('56px')
    expect(largeur('Ordre')).toBe('72px')
    expect(entetes.at(-1).style.width).toBe('40px')
    const designation = entetes.find((th) => th.textContent.trim() === 'Désignation')
    expect(designation.style.width).toBe('')
    expect(designation.style.minWidth).toBe('160px')
  })
})
