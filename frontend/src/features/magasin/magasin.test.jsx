import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

// jsdom n'implémente pas ResizeObserver (mesuré par certains primitifs UI) —
// on le polyfill localement pour que les écrans se montent proprement.
beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

/* Tests de rendu smoke des écrans Magasin (XSTK1). Deux volets : (1) wiring
   API — chaque écran appelle le bon endpoint `installationsApi.*` et ne
   plante pas sur des données vides/undefined ; (2) rendu de base (titre,
   filtres, état vide). API mockée pour rester hors réseau. */

const emptyList = () => Promise.resolve({ data: [] })

vi.mock('../../api/installationsApi', () => ({
  default: {
    getBinLocations: vi.fn(emptyList),
    getBinAffectations: vi.fn(emptyList),
    createBinLocation: vi.fn(),
    getPutAways: vi.fn(emptyList),
    getPutAway: vi.fn(),
    createPutAway: vi.fn(),
    rangerPutAway: vi.fn(),
    getPickLists: vi.fn(emptyList),
    getPickList: vi.fn(),
    createPickList: vi.fn(),
    demarrerPickList: vi.fn(),
    terminerPickList: vi.fn(),
    getPickListLignes: vi.fn(emptyList),
    updatePickListLigne: vi.fn(),
    getColisList: vi.fn(emptyList),
    getColis: vi.fn(),
    createColis: vi.fn(),
    updateColis: vi.fn(),
    controlerColis: vi.fn(),
    expedierColis: vi.fn(),
    getColisLignes: vi.fn(emptyList),
    createColisLigne: vi.fn(),
    updateColisLigne: vi.fn(),
    deleteColisLigne: vi.fn(),
  },
}))

import installationsApi from '../../api/installationsApi'
import MagasinCockpit from './MagasinCockpit'
import BinTreeScreen from './BinTreeScreen'
import PutAwayScreen from './PutAwayScreen'
import PickListScreen from './PickListScreen'
import ColisageScreen from './ColisageScreen'

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('MagasinCockpit', () => {
  it('affiche le titre et appelle les 4 endpoints de synthèse', async () => {
    withProviders(<MagasinCockpit />)
    expect(screen.getByText('Magasin')).toBeInTheDocument()
    await waitFor(() => {
      expect(installationsApi.getBinLocations).toHaveBeenCalledWith({ archived: '0' })
      expect(installationsApi.getPutAways).toHaveBeenCalledWith({ statut: 'a_ranger' })
      expect(installationsApi.getPickLists).toHaveBeenCalledWith({ statut: 'en_cours' })
      expect(installationsApi.getColisList).toHaveBeenCalledWith({ statut: 'preparation' })
    })
  })
})

describe('BinTreeScreen', () => {
  it('affiche le titre et un état vide sans données', async () => {
    withProviders(<BinTreeScreen />)
    expect(screen.getByText('Casiers de rangement')).toBeInTheDocument()
    await waitFor(() => expect(installationsApi.getBinLocations).toHaveBeenCalled())
    await waitFor(() => expect(screen.getByText('Aucun casier')).toBeInTheDocument())
  })

  it('rend l’arborescence sans planter avec des casiers réels', async () => {
    installationsApi.getBinLocations.mockResolvedValueOnce({
      data: [
        {
          id: 1, emplacement: 10, emplacement_nom: 'Dépôt central',
          zone: 'A', allee: '01', casier: '01', code: 'A-01-01',
          archived: false, affectations: [{ id: 1, produit: 5, produit_nom: 'Onduleur', quantite: 3 }],
        },
      ],
    })
    withProviders(<BinTreeScreen />)
    await waitFor(() => expect(screen.getByText('Dépôt central')).toBeInTheDocument())
    expect(screen.getByText('A-01-01')).toBeInTheDocument()
  })
})

describe('PutAwayScreen', () => {
  it('affiche le titre et appelle getPutAways avec le filtre par défaut', async () => {
    withProviders(<PutAwayScreen />)
    expect(screen.getByText('Rangement guidé (put-away)')).toBeInTheDocument()
    await waitFor(() =>
      expect(installationsApi.getPutAways).toHaveBeenCalledWith({ statut: 'a_ranger' }))
  })

  it('ne plante pas avec des données undefined', async () => {
    installationsApi.getPutAways.mockResolvedValueOnce({ data: undefined })
    withProviders(<PutAwayScreen />)
    await waitFor(() => expect(installationsApi.getPutAways).toHaveBeenCalled())
  })
})

describe('PickListScreen', () => {
  it('affiche le titre et appelle getPickLists', async () => {
    withProviders(<PickListScreen />)
    expect(screen.getByText('Bons de prélèvement')).toBeInTheDocument()
    await waitFor(() => expect(installationsApi.getPickLists).toHaveBeenCalled())
  })
})

describe('ColisageScreen', () => {
  it('affiche le titre et appelle getColisList', async () => {
    withProviders(<ColisageScreen />)
    expect(screen.getByText('Colisage')).toBeInTheDocument()
    await waitFor(() => expect(installationsApi.getColisList).toHaveBeenCalled())
  })
})
