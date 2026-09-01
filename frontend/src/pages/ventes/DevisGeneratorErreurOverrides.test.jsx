// QJR309 — `messageErreurOverrides` (DevisGenerator.jsx, utilisé aux deux
// points de pose `poserOverride`/`regenererOverride`) ne lisait que
// `err.response.data` : le refus CLIENT de la liste blanche levé par
// `ventesApi.poserOverrides` (AVANT tout réseau, `cheminsRefuses` — voir
// `frontend/src/api/ventesApi.js`) est un `TypeError` NU, sans `.response` —
// il retombait donc sur le message générique « La surcharge a été refusée
// par le serveur. », qui maquille un refus CLIENT en refus SERVEUR et jette
// la vraie raison (le chemin fautif).
//
// Correctif : distinguer les deux et afficher la raison réelle pour un refus
// client, tout en laissant le message SERVEUR inchangé, mot pour mot.
//
// QJR239 (garde `scripts/check_tests_source_regex.py`) interdit tout NOUVEAU
// test de la famille DevisGenerator*/solar*/autoQuote* qui lit le SOURCE via
// `readFileSync` puis asserte par regex : ce fichier MONTE réellement
// DevisGenerator (patron de DevisGeneratorScenarioDefaut.test.jsx —
// `?edit=<id>` réouvre un brouillon), déclenche la POSE d'une surcharge et
// asserte sur le message affiché à l'écran.
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorErreurOverrides.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

import authReducer from '../../features/auth/store/authSlice'
import ventesReducer from '../../features/ventes/store/ventesSlice'

// APIs mockées (aucun appel réseau réel au montage).
vi.mock('../../api/crmApi', () => ({
  default: {
    getClients: vi.fn(() => Promise.resolve({ data: [] })),
    getLeads: vi.fn(() => Promise.resolve({ data: [] })),
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
    getOffresTaillesDevis: vi.fn(() => Promise.resolve({ data: { editable: false } })),
    lireOverrides: vi.fn(() => Promise.resolve({ data: {} })),
    poserOverrides: vi.fn(),
  },
}))

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'

function makeStore() {
  return configureStore({
    reducer: { auth: authReducer, ventes: ventesReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role: 'normal', role_nom: 'Directeur', permissions: [],
        isAuthenticated: true, loading: false,
      },
    },
  })
}

// Un brouillon déjà enregistré : le panneau « Surcharges (registre) »
// n'existe QUE sur un devis avec editDevis?.id (QJR215).
const DEVIS_ROUVERT = {
  id: 7, reference: 'DEV-2026-09-0007', statut: 'brouillon',
  mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0',
  lignes: [],
}

function renderGenerator() {
  crmApi.getClients.mockResolvedValue({ data: [] })
  crmApi.getLeads.mockResolvedValue({ data: [] })
  stockApi.getProduits.mockResolvedValue({ data: [] })
  ventesApi.getDevisById.mockResolvedValue({ data: DEVIS_ROUVERT })
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter initialEntries={['/ventes/devis/nouveau?edit=7']}>
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

async function poserUneSurcharge() {
  await waitFor(() => expect(screen.getByTestId('overrides-panel')).toBeInTheDocument())
  fireEvent.change(screen.getByTestId('overrides-valeur'), { target: { value: '14' } })
  fireEvent.click(screen.getByTestId('overrides-poser'))
}

describe('QJR309 — une erreur CLIENT cesse d’être maquillée en « le serveur a refusé »', () => {
  it('refus CLIENT de la liste blanche (TypeError nu, sans .response) : le message nomme le refus CLIENT et le chemin fautif, JAMAIS le serveur', async () => {
    const cheminFautif = 'profil.equipements.chauffage_piscine'
    // Même gabarit EXACT que celui que `ventesApi.poserOverrides` construit
    // réellement (frontend/src/api/ventesApi.js) — un TypeError levé AVANT
    // tout réseau, donc sans `.response`.
    ventesApi.poserOverrides.mockRejectedValueOnce(
      new TypeError('ventesApi.poserOverrides : chemin(s) '
        + `hors liste blanche du contrat QJR1 — ${cheminFautif}.`))

    renderGenerator()
    await poserUneSurcharge()

    await waitFor(() => expect(screen.getByTestId('overrides-erreur')).toBeInTheDocument())
    const message = screen.getByTestId('overrides-erreur').textContent
    expect(message).toMatch(/chemin\(s\)/)
    expect(message).toMatch(/hors liste blanche du contrat QJR1/)
    expect(message).toContain(cheminFautif)
    expect(message.toLowerCase()).not.toContain('serveur')
  })

  it('une VRAIE erreur serveur (err.response.data) affiche toujours le message du serveur, MOT POUR MOT, comme aujourd’hui', async () => {
    ventesApi.poserOverrides.mockRejectedValueOnce({
      response: { data: { detail: 'Chemin non dérivable pour ce devis.' } },
    })

    renderGenerator()
    await poserUneSurcharge()

    await waitFor(() => expect(screen.getByTestId('overrides-erreur')).toBeInTheDocument())
    expect(screen.getByTestId('overrides-erreur').textContent).toBe('Chemin non dérivable pour ce devis.')
  })
})
