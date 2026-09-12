import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   CHT20 — Fiche chantier : la passerelle vers ses satellites.
   ----------------------------------------------------------------------------
   La section « Autour de ce chantier » (onglet Aperçu) rassemble des liens
   pré-remplis `?chantier=<id>` vers les 7 écrans satellites (Suivi projet,
   Sous-traitance, Réserves, RFI, Journal, Avenants, DGD) — chacun un
   deep-link RÉEL déjà lu par l'écran cible (CHT19), jamais une URL ad hoc
   (règle WIR176) — + un lien « Projet de facturation » quand un Projet
   gestion_projet est rattaché (CHT18) et un lien vers le RegulatoryDossier du
   devis quand il existe (couche SÉPARÉE de la section 82-21 inline). Fin du
   parcours « re-sélectionner le même chantier dans 4 menus ».
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

const mocks = vi.hoisted(() => ({
  getChantiers: vi.fn(),
  getReglementaire: vi.fn(),
}))

vi.mock('../../api/gestionProjetApi', () => ({
  default: {
    getChantiers: (...args) => mocks.getChantiers(...args),
    creerProjetDepuisDevis: () => Promise.resolve({ data: { id: 1, code: 'PRJ-0001' } }),
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
    getReglementaire: (...args) => mocks.getReglementaire(...args),
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

const CHANTIER = {
  id: 601,
  reference: 'CH-CHT20-601',
  statut: 'signe',
  annule: false,
  client: 12,
  client_nom: 'Client CHT20',
  devis: 88,
  devis_reference: 'DEV-CHT20-0088',
  bom: [],
}

afterEach(() => { cleanup(); vi.clearAllMocks() })

beforeEach(() => {
  mocks.getChantiers.mockResolvedValue({ data: { results: [] } })
  mocks.getReglementaire.mockResolvedValue({ data: { results: [] } })
})

describe('InstallationDetail — « Autour de ce chantier » (CHT20)', () => {
  it('les 7 liens satellites naviguent vers leur route avec ?chantier=<id>', async () => {
    const user = userEvent.setup()
    renderDetail(CHANTIER)

    const attendus = [
      ['Suivi projet', '/chantiers/suivi-projet?chantier=601'],
      ['Sous-traitance', '/chantiers/sous-traitance?chantier=601'],
      ['Réserves', '/btp-chantier/reserves?chantier=601'],
      ['RFI', '/btp-chantier/rfi?chantier=601'],
      ['Journal', '/btp-chantier/journal?chantier=601'],
      ['Avenants', '/btp-chantier/avenants?chantier=601'],
      ['DGD', '/btp-chantier/dgd?chantier=601'],
    ]
    for (const [label, url] of attendus) {
      const bouton = await screen.findByRole('button', { name: label })
      await user.click(bouton)
      expect(navigateMock).toHaveBeenCalledWith(url)
    }
  })

  it('affiche le lien « Projet de facturation » quand un Projet est rattaché, et navigue vers sa fiche', async () => {
    mocks.getChantiers.mockResolvedValue({
      data: {
        results: [
          { id: 5, projet: 17, projet_code: 'PRJ-0017', chantier_id: CHANTIER.id },
        ],
      },
    })
    const user = userEvent.setup()
    renderDetail(CHANTIER)

    const bouton = await screen.findByRole('button', { name: /Projet de facturation \(PRJ-0017\)/ })
    await user.click(bouton)
    expect(navigateMock).toHaveBeenCalledWith('/projets/17')
  })

  it("masque le lien « Projet de facturation » quand aucun Projet n'est rattaché", async () => {
    renderDetail(CHANTIER)
    await waitFor(() => expect(mocks.getChantiers).toHaveBeenCalled())
    await waitFor(() => expect(
      screen.queryByRole('button', { name: /Projet de facturation/ }),
    ).toBeNull())
  })

  it('affiche le lien « Dossier réglementaire » quand un RegulatoryDossier existe pour le devis, et navigue vers la liste', async () => {
    mocks.getReglementaire.mockResolvedValue({
      data: { results: [{ id: 3, devis: CHANTIER.devis, statut: 'depose', statut_label: 'Déposé' }] },
    })
    const user = userEvent.setup()
    renderDetail(CHANTIER)

    const bouton = await screen.findByRole('button', { name: /Dossier réglementaire \(Déposé\)/ })
    await user.click(bouton)
    expect(navigateMock).toHaveBeenCalledWith('/ventes/dossiers-reglementaires')
    expect(mocks.getReglementaire).toHaveBeenCalledWith(
      'dossiers-reglementaires', { devis: CHANTIER.devis })
  })

  it("masque le lien « Dossier réglementaire » quand aucun dossier n'existe", async () => {
    renderDetail(CHANTIER)
    await waitFor(() => expect(mocks.getReglementaire).toHaveBeenCalled())
    await waitFor(() => expect(
      screen.queryByRole('button', { name: /Dossier réglementaire/ }),
    ).toBeNull())
  })
})
