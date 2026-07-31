import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* NTAGR4 — liste des parcelles + démarrage de campagne depuis une parcelle
   libre. Réseau mocké (client API), pas de dépendance à un backend réel. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const {
  campagnesCreate, campagnesList, registrePhytoPdf, exploitationsCreate,
  parcellesCreate, pointsIrrigationCreate, relevesIrrigationCreate,
} = vi.hoisted(() => ({
  campagnesCreate: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
  // WIR52 — vide par défaut : aucun test existant (avant WIR52) n'attend une
  // campagne rattachée, donc aucune action « Registre phytosanitaire » ne
  // doit apparaître tant qu'un test ne surcharge pas explicitement la liste.
  campagnesList: vi.fn(() => Promise.resolve({ data: [] })),
  registrePhytoPdf: vi.fn(() => Promise.resolve({
    data: new Blob(['%PDF-1.4'], { type: 'application/pdf' }),
  })),
  exploitationsCreate: vi.fn(() => Promise.resolve({ data: { id: 9, nom: 'Domaine Est' } })),
  parcellesCreate: vi.fn(() => Promise.resolve({ data: { id: 3 } })),
  pointsIrrigationCreate: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
  relevesIrrigationCreate: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
}))

vi.mock('../../api/agricultureApi', () => ({
  default: {
    exploitations: {
      list: () => Promise.resolve({ data: [{ id: 1, nom: 'Domaine' }] }),
      create: (...args) => exploitationsCreate(...args),
    },
    parcelles: {
      list: () => Promise.resolve({
        data: [
          {
            id: 1, nom: 'Parcelle Nord', code: 'PN-01', culture_principale: 'Blé',
            superficie_ha: '4.2', statut: 'jachere', statut_display: 'Jachère',
            geometrie_gps: [{ lat: 33.29, lng: -8.53 }],
          },
          {
            id: 2, nom: 'Parcelle Sud', code: 'PS-02', culture_principale: 'Orge',
            superficie_ha: '2.1', statut: 'en_culture', statut_display: 'En culture',
            geometrie_gps: null,
          },
        ],
      }),
      create: (...args) => parcellesCreate(...args),
      update: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
    },
    campagnes: {
      create: (...args) => campagnesCreate(...args),
      list: (...args) => campagnesList(...args),
      registrePhytoPdf: (...args) => registrePhytoPdf(...args),
      coutIrrigation: vi.fn(() => Promise.resolve({
        data: { cout_irrigation_mad: '80.00', volume_irrigation_solaire_m3: '25' },
      })),
    },
    pointsIrrigation: {
      list: () => Promise.resolve({ data: [] }),
      create: (...args) => pointsIrrigationCreate(...args),
    },
    relevesIrrigation: {
      list: () => Promise.resolve({ data: [] }),
      create: (...args) => relevesIrrigationCreate(...args),
    },
  },
}))

import ParcellesPage from './ParcellesPage'

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('ParcellesPage (NTAGR4)', () => {
  it('affiche la liste des parcelles avec superficie/culture/statut', async () => {
    withProviders(<ParcellesPage />)
    await waitFor(() => expect(screen.getAllByText('Parcelle Nord').length).toBeGreaterThan(0))
    expect(screen.getAllByText(/4\.2 ha/).length).toBeGreaterThan(0)
  })

  it('démarre une campagne depuis une parcelle libre (jachère)', async () => {
    const user = userEvent.setup()
    withProviders(<ParcellesPage />)
    await waitFor(() => expect(screen.getAllByText('Parcelle Nord').length).toBeGreaterThan(0))

    await user.click(screen.getAllByRole('button', { name: 'Démarrer une campagne' })[0])
    await user.type(screen.getByLabelText('Culture'), 'Tomate')
    await user.click(screen.getByRole('button', { name: 'Démarrer la campagne' }))

    await waitFor(() => expect(campagnesCreate).toHaveBeenCalledWith(
      expect.objectContaining({ parcelle: 1, culture: 'Tomate', statut: 'en_cours' }),
    ))
  })

  it('n’offre pas « Démarrer une campagne » pour une parcelle déjà en culture', async () => {
    withProviders(<ParcellesPage />)
    await waitFor(() => expect(screen.getAllByText('Parcelle Sud').length).toBeGreaterThan(0))
    // DataTable rend desktop + mobile (2 occurrences) — seule Parcelle Nord
    // (jachère) propose l'action, jamais Parcelle Sud (déjà en_culture).
    expect(screen.getAllByRole('button', { name: 'Démarrer une campagne' }).length).toBe(2)
  })
})

// WIR52 — agricultureApi.campagnes.registrePhytoPdf(id) était exposé côté
// client (NTAGR7) sans AUCUN composant appelant : le bouton n'existait nulle
// part. Le lien parcelle → campagne vient de la liste réelle des campagnes
// (jamais de `Parcelle.statut` seul, non synchronisé côté serveur).
describe('ParcellesPage — registre phytosanitaire PDF (WIR52)', () => {
  beforeEach(() => {
    // jsdom n'implémente ni createObjectURL ni un vrai window.open (VX48/QS1).
    URL.createObjectURL = vi.fn(() => 'blob:mock-url')
    URL.revokeObjectURL = vi.fn()
    window.open = vi.fn(() => ({}))
  })

  it('télécharge le PDF depuis l’action de ligne d’une parcelle en campagne', async () => {
    campagnesList.mockResolvedValueOnce({
      data: [{ id: 77, parcelle: 2, culture: 'Orge', statut: 'en_cours' }],
    })
    const user = userEvent.setup()
    withProviders(<ParcellesPage />)
    await waitFor(() => expect(screen.getAllByText('Parcelle Sud').length).toBeGreaterThan(0))

    const boutons = screen.getAllByRole('button', { name: 'Registre phytosanitaire (PDF)' })
    expect(boutons.length).toBeGreaterThan(0)
    await user.click(boutons[0])

    await waitFor(() => expect(registrePhytoPdf).toHaveBeenCalledWith(77))
    await waitFor(() => expect(window.open).toHaveBeenCalledWith('', '_blank', 'noopener'))
  })

  it('n’offre pas le registre phyto pour une parcelle sans campagne en cours', async () => {
    campagnesList.mockResolvedValueOnce({ data: [] })
    withProviders(<ParcellesPage />)
    await waitFor(() => expect(screen.getAllByText('Parcelle Sud').length).toBeGreaterThan(0))
    expect(screen.queryByRole('button', { name: 'Registre phytosanitaire (PDF)' })).not.toBeInTheDocument()
  })
})

// WIR141 — Exploitation/Parcelle n'avaient aucune UI de création ; le duo
// PointIrrigation/RelevePointIrrigation (NTAGR13/14) n'avait aucun écran.
describe('ParcellesPage — création exploitation/parcelle (WIR141)', () => {
  it('crée une exploitation depuis le bouton dédié', async () => {
    const user = userEvent.setup()
    withProviders(<ParcellesPage />)
    await waitFor(() => expect(screen.getAllByText('Parcelle Nord').length).toBeGreaterThan(0))

    await user.click(screen.getByRole('button', { name: /Nouvelle exploitation/ }))
    await user.type(screen.getByLabelText('Nom'), 'Domaine Est')
    await user.click(screen.getByRole('button', { name: 'Créer l’exploitation' }))

    await waitFor(() => expect(exploitationsCreate).toHaveBeenCalledWith(
      expect.objectContaining({ nom: 'Domaine Est' }),
    ))
  })

  it('crée une parcelle rattachée à une exploitation', async () => {
    const user = userEvent.setup()
    withProviders(<ParcellesPage />)
    await waitFor(() => expect(screen.getAllByText('Parcelle Nord').length).toBeGreaterThan(0))

    await user.click(screen.getByRole('button', { name: /Nouvelle parcelle/ }))
    await user.selectOptions(screen.getByLabelText('Exploitation'), '1')
    await user.type(screen.getByLabelText('Nom'), 'Parcelle Ouest')
    await user.click(screen.getByRole('button', { name: 'Créer la parcelle' }))

    await waitFor(() => expect(parcellesCreate).toHaveBeenCalledWith(
      expect.objectContaining({ exploitation: '1', nom: 'Parcelle Ouest' }),
    ))
  })

  it('modifie une parcelle existante depuis l’action de ligne', async () => {
    const user = userEvent.setup()
    withProviders(<ParcellesPage />)
    await waitFor(() => expect(screen.getAllByText('Parcelle Nord').length).toBeGreaterThan(0))

    await user.click(screen.getAllByRole('button', { name: 'Modifier' })[0])
    expect(await screen.findByText('Modifier — Parcelle Nord')).toBeInTheDocument()
  })
})

describe('ParcellesPage — irrigation (WIR141)', () => {
  it('ouvre le dialogue Irrigation et crée un point d’irrigation', async () => {
    const user = userEvent.setup()
    withProviders(<ParcellesPage />)
    await waitFor(() => expect(screen.getAllByText('Parcelle Nord').length).toBeGreaterThan(0))

    await user.click(screen.getAllByRole('button', { name: 'Irrigation' })[0])
    expect(await screen.findByText('Irrigation — Parcelle Nord')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Nouveau point/ }))
    await user.click(screen.getByRole('button', { name: 'Créer le point' }))

    await waitFor(() => expect(pointsIrrigationCreate).toHaveBeenCalledWith(
      expect.objectContaining({ parcelle: 1, type_source: 'puits' }),
    ))
  })

  it('affiche le coût d’irrigation de la campagne en cours de la parcelle', async () => {
    campagnesList.mockResolvedValueOnce({
      data: [{ id: 77, parcelle: 1, culture: 'Blé', statut: 'en_cours' }],
    })
    const user = userEvent.setup()
    withProviders(<ParcellesPage />)
    await waitFor(() => expect(screen.getAllByText('Parcelle Nord').length).toBeGreaterThan(0))

    await user.click(screen.getAllByRole('button', { name: 'Irrigation' })[0])
    expect(await screen.findByText(/80.00 MAD/)).toBeInTheDocument()
    expect(screen.getByText(/25 m³/)).toBeInTheDocument()
  })
})
