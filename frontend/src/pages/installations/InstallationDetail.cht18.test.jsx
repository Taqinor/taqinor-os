import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { exempleContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   CHT18 — Pont chantier -> projet de facturation (situations de travaux).
   ----------------------------------------------------------------------------
   La fiche chantier (InstallationDetail, onglet Aperçu) gagne une CTA
   « Créer le projet de facturation » : visible quand un devis est présent ET
   qu'AUCUN Projet (gestion_projet) n'est déjà rattaché à ce chantier (lecture
   légère best-effort de `projet-chantiers`, filtrée côté client — l'API ne
   filtre pas par `chantier_id`). Elle appelle l'action XPRJ21 existante
   (qui rattache désormais AUSSI le `ProjetChantier`, EN UN SEUL appel réseau
   côté serveur) puis navigue vers la fiche du projet créé. La facturation à
   l'avancement reste dans gestion_projet (Path B « SituationTravaux sur
   chantier » rejeté).

   Contrat partagé (PACT10) : la charge utile de `creerProjetDepuisDevis` vient
   du fichier COMMITTÉ `apps/gestion_projet/contract_samples/depuis_devis.json`
   — jamais un objet inventé à la main (check_api_shapes).
   ========================================================================== */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

// PACT10 — l'exemple committé, lu depuis le fichier réel.
const PROJET_EXEMPLE = exempleContrat('gestion_projet', 'depuis_devis')

const mocks = vi.hoisted(() => ({
  getChantiers: vi.fn(),
  creerProjetDepuisDevis: vi.fn(),
}))

vi.mock('../../api/gestionProjetApi', () => ({
  default: {
    getChantiers: (...args) => mocks.getChantiers(...args),
    creerProjetDepuisDevis: (...args) => mocks.creerProjetDepuisDevis(...args),
  },
}))

vi.mock('../../api/installationsApi', () => ({
  default: {
    getHistorique: () => Promise.resolve({ data: [] }),
    getTypesIntervention: () => Promise.resolve({ data: [] }),
  },
}))

vi.mock('../../api/savApi', () => ({
  default: {
    getEquipements: () => Promise.resolve({ data: [] }),
    getTickets: () => Promise.resolve({ data: [] }),
    getContrats: () => Promise.resolve({ data: [] }),
  },
}))

vi.mock('../../api/crmApi', () => ({
  default: {
    getAssignableUsers: () => Promise.resolve({ data: [] }),
  },
}))

vi.mock('../../api/ventesApi', () => ({
  default: {
    getDevisById: () => Promise.resolve({ data: { lignes: [] } }),
  },
}))

const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => navigateMock }
})

import InstallationDetail from './InstallationDetail'

function makeStore() {
  return configureStore({
    reducer: {
      // `produits.length !== 0` évite le `dispatch(fetchProduits())` du
      // premier effet — aucun mock de `stockSlice` n'est donc nécessaire.
      stock: (state = { produits: [{ id: 1, nom: 'Panneau' }] }) => state,
    },
  })
}

function renderDetail(installation) {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter initialEntries={['/chantiers']}>
        <ThemeProvider>
          <InstallationDetail installation={installation} onClose={() => {}} onSaved={() => {}} />
        </ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

const CHANTIER_AVEC_DEVIS = {
  id: 501,
  reference: 'CH-CHT18-501',
  statut: 'signe',
  annule: false,
  client: 12,
  client_nom: 'Client CHT18',
  devis: 77,
  devis_reference: 'DEV-CHT18-0077',
  bom: [],
}

const CHANTIER_SANS_DEVIS = {
  ...CHANTIER_AVEC_DEVIS,
  id: 502,
  reference: 'CH-CHT18-502',
  devis: null,
  devis_reference: null,
}

afterEach(() => { cleanup(); vi.clearAllMocks() })

beforeEach(() => {
  mocks.getChantiers.mockResolvedValue({ data: { results: [] } })
  mocks.creerProjetDepuisDevis.mockResolvedValue({ data: PROJET_EXEMPLE })
})

describe('InstallationDetail — CTA « Créer le projet de facturation » (CHT18)', () => {
  it('affiche la CTA quand un devis est présent et aucun projet n\'est rattaché, puis navigue vers le projet créé', async () => {
    const user = userEvent.setup()
    renderDetail(CHANTIER_AVEC_DEVIS)

    const cta = await screen.findByRole('button', { name: /Créer le projet de facturation/ })
    await user.click(cta)

    await waitFor(() => expect(mocks.creerProjetDepuisDevis).toHaveBeenCalledWith(77))
    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith(`/projets/${PROJET_EXEMPLE.id}`))
  })

  it('masque la CTA quand un Projet est déjà rattaché à ce chantier', async () => {
    mocks.getChantiers.mockResolvedValue({
      data: {
        results: [
          { id: 9, projet: 3, projet_code: 'PRJ-0003', chantier_id: CHANTIER_AVEC_DEVIS.id },
        ],
      },
    })
    renderDetail(CHANTIER_AVEC_DEVIS)

    // La lecture légère (getChantiers) se résout de façon asynchrone : on
    // attend que la CTA DISPARAISSE (état initial optimiste), pas seulement
    // que l'appel ait été fait.
    await waitFor(() => expect(mocks.getChantiers).toHaveBeenCalled())
    await waitFor(() => expect(
      screen.queryByRole('button', { name: /Créer le projet de facturation/ }),
    ).toBeNull())
  })

  it('masque la CTA quand le chantier n\'a aucun devis', async () => {
    renderDetail(CHANTIER_SANS_DEVIS)

    // Ici la CTA est absente dès le rendu initial (`current.devis` faux) —
    // indépendamment du résultat de `getChantiers`.
    expect(screen.queryByRole('button', { name: /Créer le projet de facturation/ })).toBeNull()
    await waitFor(() => expect(mocks.getChantiers).toHaveBeenCalled())
    expect(screen.queryByRole('button', { name: /Créer le projet de facturation/ })).toBeNull()
  })

  it('le contrat committé porte bien `id` et `code` (PACT10 — contre le mock inventé)', () => {
    expect(PROJET_EXEMPLE).toHaveProperty('id')
    expect(PROJET_EXEMPLE).toHaveProperty('code')
  })
})
