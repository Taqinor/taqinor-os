// EDC4 — barre d'actions collante EN TÊTE de l'écran devis : présente en
// embarqué ET en pleine page, pastille « Modifications non enregistrées »
// absente à l'ouverture puis présente après une frappe, « Voir le PDF »
// seulement en Édition complète embarquée (jamais en création), hauteur
// mesurée posée sur la racine (`--gen-barre-h`).
//
// Écran RÉEL rendu, API mockées.
// Run : npx vitest run src/pages/ventes/generator/BarreActionsDevis.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

import authReducer from '../../../features/auth/store/authSlice'
import ventesReducer from '../../../features/ventes/store/ventesSlice'

vi.mock('../../../api/crmApi', () => ({
  default: {
    getClients: vi.fn(() => Promise.resolve({ data: [] })),
    getLeads: vi.fn(() => Promise.resolve({ data: [] })),
    getLead: vi.fn(() => Promise.resolve({ data: null })),
  },
}))
vi.mock('../../../api/stockApi', () => ({
  default: { getProduits: vi.fn(() => Promise.resolve({ data: [] })) },
}))
vi.mock('../../../api/parametresApi', () => ({
  default: { getProfile: vi.fn(() => Promise.resolve({ data: {} })) },
}))
vi.mock('../../../api/ventesApi', () => ({
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

import ventesApi from '../../../api/ventesApi'
import DevisGenerator from '../DevisGenerator'
import BarreActionsDevis from './BarreActionsDevis'

const DEVIS = {
  id: 42, reference: 'DEV-202610-0042', statut: 'envoye', date_envoi: null,
  modifiable: true, raison_non_modifiable: '', revision_possible: false, is_active: true,
  lead: null, client: 9, mode_installation: 'residentiel', taux_tva: '20.00',
  remise_globale: '0', updated_at: '2026-10-09T08:00:00Z',
  etude_params: { scenario: 'Sans batterie' },
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

function renderEmbarque(props = {}) {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter initialEntries={['/crm/leads/7']}>
        <DevisGenerator embedded onDone={() => {}} onCancel={() => {}} {...props} />
      </MemoryRouter>
    </Provider>,
  )
}

function renderPage(route) {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/ventes/devis/nouveau" element={<DevisGenerator />} />
        </Routes>
      </MemoryRouter>
    </Provider>,
  )
}

const barre = () => screen.getByRole('toolbar', { name: 'Actions du devis' })

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

describe('EDC4 — barre d\'actions en tête', () => {
  it('Édition complète embarquée : référence, statut, total, Annuler / Enregistrer / Voir le PDF', async () => {
    const onVoirPdf = vi.fn()
    const onCancel = vi.fn()
    const { container } = renderEmbarque({ editId: 42, onVoirPdf, onCancel })
    await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    const b = within(barre())
    await waitFor(() => expect(b.getByText('DEV-202610-0042')).toBeInTheDocument())
    expect(b.getByText('Envoyé')).toBeInTheDocument()
    expect(b.getByText('Total TTC')).toBeInTheDocument()
    // Même valeur que le total condensé du pied (`kpiTotal`, celui du rail).
    expect(b.getByTestId('gen-barre-total').textContent).toMatch(/MAD/)
    expect(b.getByTestId('gen-barre-total').textContent)
      .toBe(container.querySelector('.gen-ttc-condense strong').textContent)
    // Le Enregistrer de la barre soumet LE formulaire du devis (même chemin).
    const enregistrer = b.getByRole('button', { name: 'Enregistrer' })
    expect(enregistrer).toHaveAttribute('type', 'submit')
    expect(enregistrer).toHaveAttribute('form', 'gen-form')
    // La barre vit HORS du <form> (les ancres `#gen-form` ne la voient pas).
    expect(container.querySelector('#gen-form').contains(barre())).toBe(false)
    fireEvent.click(b.getByRole('button', { name: /Voir le PDF/ }))
    expect(onVoirPdf).toHaveBeenCalledTimes(1)
    expect(onVoirPdf).toHaveBeenCalledWith()
    fireEvent.click(b.getByRole('button', { name: 'Annuler' }))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('pleine page (?edit=) : barre présente, jamais de « Voir le PDF »', async () => {
    renderPage('/ventes/devis/nouveau?edit=42')
    await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    const b = within(barre())
    await waitFor(() => expect(b.getByText('DEV-202610-0042')).toBeInTheDocument())
    expect(b.queryByRole('button', { name: /Voir le PDF/ })).toBeNull()
  })

  it('création embarquée : « Nouveau devis », bouton « Créer », pas de « Voir le PDF »', async () => {
    renderEmbarque({ onVoirPdf: vi.fn() })
    const b = within(barre())
    expect(b.getByText('Nouveau devis')).toBeInTheDocument()
    expect(b.getByRole('button', { name: 'Créer' })).toHaveAttribute('form', 'gen-form')
    expect(b.queryByRole('button', { name: /Voir le PDF/ })).toBeNull()
    expect(b.queryByText(/^Envoyé$|^Brouillon$/)).toBeNull()
  })

  it('pastille « Modifications non enregistrées » : absente à l\'ouverture, présente après une frappe', async () => {
    renderEmbarque({ editId: 42 })
    await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    // Fenêtre QJR581 (1,5 s) : la référence « rien n'a changé » est capturée.
    await new Promise((r) => setTimeout(r, 1700))
    expect(within(barre()).queryByText('Modifications non enregistrées')).toBeNull()
    fireEvent.change(screen.getByPlaceholderText(/Conditions particulières/),
      { target: { value: 'Acompte 30 %' } })
    await waitFor(() => expect(
      within(barre()).getByText('Modifications non enregistrées')).toBeInTheDocument())
    // La pastille vit dans une région vivante TOUJOURS montée (annonce polie).
    expect(within(barre()).getByRole('status')).toContainElement(
      within(barre()).getByTestId('gen-barre-non-enregistre'))
  }, 15000)
})

describe('EDC4 — composant seul', () => {
  it('pose --gen-barre-h (hauteur mesurée) et --gen-colle-decalage (padding du défileur) sur .gen-root', () => {
    const observes = []
    const RO = globalThis.ResizeObserver
    globalThis.ResizeObserver = class {
      constructor(cb) { this.cb = cb }
      observe(el) { observes.push(el) }
      disconnect() {}
    }
    const rect = vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect')
      .mockReturnValue({ height: 52.4, width: 900, top: 0, left: 0, bottom: 52.4, right: 900 })
    try {
      const { container } = render(
        <div className="layout-content" style={{ paddingTop: '32px' }}>
          <div className="gen-root">
            <BarreActionsDevis totalTtc={1234.5} onAnnuler={() => {}} />
          </div>
        </div>,
      )
      const racine = container.querySelector('.gen-root')
      expect(racine.style.getPropertyValue('--gen-barre-h')).toBe('53px')
      expect(racine.style.getPropertyValue('--gen-colle-decalage')).toBe('-32px')
      // La barre ET le défileur sont observés (un changement de padding au
      // passage mobile/bureau re-mesure le décalage).
      expect(observes).toContain(container.querySelector('.gen-barre-actions'))
      expect(observes).toContain(container.querySelector('.layout-content'))
    } finally {
      rect.mockRestore()
      globalThis.ResizeObserver = RO
    }
  })

  it('flèches gauche/droite : le focus circule entre les commandes de la barre', () => {
    render(<BarreActionsDevis totalTtc={0} onAnnuler={() => {}} onVoirPdf={() => {}} />)
    const [pdf, annuler, creer] = within(barre()).getAllByRole('button')
    pdf.focus()
    fireEvent.keyDown(pdf, { key: 'ArrowRight' })
    expect(document.activeElement).toBe(annuler)
    fireEvent.keyDown(annuler, { key: 'End' })
    expect(document.activeElement).toBe(creer)
    fireEvent.keyDown(creer, { key: 'ArrowRight' })
    expect(document.activeElement).toBe(pdf)
  })
})
