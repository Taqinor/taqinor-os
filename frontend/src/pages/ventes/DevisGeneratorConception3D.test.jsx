// PV23bis (fondateur 20/08) — le bouton « Concevoir en 3D » du générateur de
// devis doit désormais TOUJOURS s'ouvrir sur un devis réel, jamais sur un
// lead déconnecté : le formulaire est d'abord enregistré (`persisterDevis`,
// réutilisé par `handleSubmit` ET `ouvrirConception3D`), puis l'outil 3D
// ouvre SUR ce devis. Le chemin lead (`/devis-design/<id>`) ne survit que
// comme repli quand le formulaire n'est pas encore un devis valide
// (`validate()` échoue) — jamais le chemin normal.

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

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
    // PVMRQ — DevisGenerator interroge ce singleton au montage (best-effort) ;
    // sans lui, l'effet lève sur un mock partiel avant même le premier rendu.
    getParametresGammes: vi.fn(() => Promise.resolve({ data: {} })),
    // Site prefill (chemin client SANS lead) — best-effort, best-caught, mais
    // sans mock l'appel lève sur `undefined(...)` avant même son `.catch()`.
    getPrefillSite: vi.fn(() => Promise.resolve({ data: {} })),
    getPrixApplicable: vi.fn(),
    patchDevis: vi.fn(),
    replaceLignesDevis: vi.fn(),
    createDevisAtomic: vi.fn(),
  },
}))

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'

// Catalogue volontairement MAIGRE (aucun panneau ni onduleur) : suffisant
// pour peupler l'effet lead-depuis-l'URL + les lignes par défaut, jamais
// pour rendre le devis valide (garde QX20 — panneau ET onduleur requis).
const PRODUITS_MAIGRES = [
  { id: 1, nom: 'Accessoire de fixation', prix_vente: 50, tva: 20, is_archived: false, prix_achat: 30 },
]

// Catalogue du test 2 : les deux produits que les lignes du devis chargé
// référencent (QX20 — un panneau ET un onduleur, désignations reconnues par
// `isPanel`/`isHybridInverter` dans features/ventes/solar.js).
const PRODUIT_PANNEAU = {
  id: 101, nom: 'Panneau Canadien Solar 710W', prix_vente: 1200, tva: 20,
  is_archived: false, prix_achat: 800,
}
const PRODUIT_ONDULEUR = {
  id: 102, nom: 'Onduleur hybride Deye 10kW', prix_vente: 15000, tva: 20,
  is_archived: false, prix_achat: 10000,
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

function renderGenerator(entree) {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter initialEntries={[entree]}>
        <Routes>
          <Route path="/ventes/devis/nouveau" element={<DevisGenerator />} />
          {/* Sondes : le chemin lead (repli) et le chemin devis (nominal) —
              on vérifie la NAVIGATION plutôt que de rejouer ToitureDesign. */}
          <Route path="/devis-design/:id" element={<div>PROBE-LEAD-MODE</div>} />
          <Route path="/ventes/devis/:id/design" element={<div>PROBE-DEVIS-MODE</div>} />
        </Routes>
      </MemoryRouter>
    </Provider>,
  )
}

// jsdom : shims requis par le générateur (scrollIntoView, matchMedia,
// ResizeObserver via recharts) — mêmes shims que DevisGeneratorRename.test.jsx.
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

describe('PV23bis — « Concevoir en 3D » travaille sur le devis, pas sur un lead déconnecté', () => {
  it('le bouton apparaît même sans repère GPS et retombe en mode lead quand le devis n\'est pas encore valide', async () => {
    const lead = { id: 200, nom: 'Bennani', prenom: 'Yasmine' } // pas de roof_point
    crmApi.getLeads.mockResolvedValue({ data: [lead] })
    crmApi.getClients.mockResolvedValue({ data: [] })
    stockApi.getProduits.mockResolvedValue({ data: PRODUITS_MAIGRES })

    renderGenerator('/ventes/devis/nouveau?lead=200')

    // QX28/PV23bis — le bouton est désormais visible dès qu'un lead est
    // choisi, MÊME SANS repère toit (avant PV23bis il restait entièrement
    // caché tant que `selectedLead.roof_point` était absent).
    const bouton = await screen.findByRole('button', { name: 'Concevoir en 3D' })
    expect(bouton).toBeInTheDocument()

    await userEvent.click(bouton)

    // Catalogue trop maigre (aucun panneau/onduleur) → validate() échoue →
    // repli sur le chemin lead historique. Rien n'est enregistré.
    expect(await screen.findByText('PROBE-LEAD-MODE')).toBeInTheDocument()
    expect(ventesApi.createDevisAtomic).not.toHaveBeenCalled()
    expect(ventesApi.patchDevis).not.toHaveBeenCalled()
  })

  it('en édition, « Concevoir en 3D » enregistre d\'abord puis ouvre l\'outil SUR le devis', async () => {
    crmApi.getLeads.mockResolvedValue({ data: [] })
    crmApi.getClients.mockResolvedValue({ data: [] })
    stockApi.getProduits.mockResolvedValue({ data: [PRODUIT_PANNEAU, PRODUIT_ONDULEUR] })
    ventesApi.getDevisById.mockResolvedValue({
      data: {
        id: 5,
        reference: 'DEV-T',
        statut: 'brouillon',
        lead: null,
        client: 9,
        taux_tva: '20.00',
        remise_globale: '0',
        lignes: [
          {
            id: 1, produit: PRODUIT_PANNEAU.id, designation: PRODUIT_PANNEAU.nom,
            quantite: '24', prix_unitaire: '1000.00', taux_tva: '20.00',
            ordre: 0, type_ligne: 'produit', optionnelle: false,
          },
          {
            id: 2, produit: PRODUIT_ONDULEUR.id, designation: PRODUIT_ONDULEUR.nom,
            quantite: '1', prix_unitaire: '12500.00', taux_tva: '20.00',
            ordre: 1, type_ligne: 'produit', optionnelle: false,
          },
        ],
      },
    })
    ventesApi.patchDevis.mockResolvedValue({ data: {} })
    ventesApi.replaceLignesDevis.mockResolvedValue({ data: {} })

    renderGenerator('/ventes/devis/nouveau?edit=5')

    // Le devis en édition n'a pas de lead (client=9 direct) : le bouton doit
    // quand même apparaître (condition PV23bis élargie à `clientId`).
    const bouton = await screen.findByRole('button', { name: 'Concevoir en 3D' })
    await userEvent.click(bouton)

    // Édition ATOMIQUE (QX21, inchangée) — patch du devis PUIS remplacement
    // des lignes, exactement le chemin qu'aurait pris « Enregistrer ».
    await waitFor(() => expect(ventesApi.patchDevis)
      .toHaveBeenCalledWith(5, expect.any(Object)))
    expect(ventesApi.replaceLignesDevis)
      .toHaveBeenCalledWith(5, expect.any(Array))
    // Un devis en édition n'est jamais RECRÉÉ.
    expect(ventesApi.createDevisAtomic).not.toHaveBeenCalled()
    expect(await screen.findByText('PROBE-DEVIS-MODE')).toBeInTheDocument()
  })
})
