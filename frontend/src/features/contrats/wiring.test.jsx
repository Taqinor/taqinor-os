import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* Tests de câblage du module Contrats (CONTRAT12-17 + XCTR17-21) : on vérifie
   que la fiche contrat expose bien les onglets Signatures / Approbation + la
   barre d'actions gardée (statuts-suivants → changer-statut), et que le module
   Location liste les ordres et déclenche la création. Les appels API sont
   mockés — hors réseau. jsdom ne fournit pas ResizeObserver. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const { changerStatut, signer, createOrdreLocation } = vi.hoisted(() => ({
  changerStatut: vi.fn(() => Promise.resolve({ data: {} })),
  signer: vi.fn(() => Promise.resolve({ data: { contrat_signe: false } })),
  createOrdreLocation: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
}))

vi.mock('../../api/contratsApi', () => {
  const empty = () => Promise.resolve({ data: [] })
  const contrat = {
    id: 7, reference: 'CT-2026-07-0001', objet: 'Maintenance PV', statut: 'brouillon',
    type_contrat: 'maintenance', confidentialite: 'interne', montant: '12000.00', devise: 'MAD',
  }
  return {
    default: {
      getContrat: () => Promise.resolve({ data: contrat }),
      getParties: empty,
      getLiens: () => Promise.resolve({ data: [] }),
      getVersions: empty,
      getAvenants: empty,
      getResiliations: empty,
      getHistorique: () => Promise.resolve({ data: [] }),
      getSignatures: () => Promise.resolve({ data: [] }),
      getEtapesApprobation: () => Promise.resolve({ data: [] }),
      getStatutsSuivants: () => Promise.resolve({ data: { statut: 'brouillon', suivants: ['en_approbation'] } }),
      changerStatut,
      signer,
      noter: () => Promise.resolve({ data: {} }),
      getPdf: () => Promise.resolve({ data: new Blob() }),
      lancerApprobation: empty,
      approuverEtape: () => Promise.resolve({ data: {} }),
      rejeterEtape: () => Promise.resolve({ data: {} }),
      renouveler: () => Promise.resolve({ data: {} }),
      creerAvenant: () => Promise.resolve({ data: {} }),
      resilier: () => Promise.resolve({ data: {} }),
      // Location
      getOrdresLocation: empty,
      ordresLocationEnRetard: empty,
      changerStatutOrdreLocation: () => Promise.resolve({ data: {} }),
      createOrdreLocation,
      cautionEncaisser: () => Promise.resolve({ data: {} }),
      cautionRestituer: () => Promise.resolve({ data: {} }),
      cautionRetenir: () => Promise.resolve({ data: {} }),
      cloturerOrdreLocation: () => Promise.resolve({ data: {} }),
      inspecterOrdreLocation: () => Promise.resolve({ data: {} }),
      getBonEnlevement: () => Promise.resolve({ data: new Blob() }),
      getBonRestitution: () => Promise.resolve({ data: new Blob() }),
    },
    contratsPortailApi: {
      mesContrats: empty,
      demander: () => Promise.resolve({ data: {} }),
    },
  }
})

vi.mock('../../api/stockApi', () => ({
  default: { getProduits: () => Promise.resolve({ data: [] }) },
}))
vi.mock('../../api/crmApi', () => ({
  default: { getClients: () => Promise.resolve({ data: [] }) },
}))

import ContratDetail from './ContratDetail'
import LocationPage from './LocationPage'
import { StatutLocation, StatutCautionLocation } from './locationStatus'

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui, { path = '/contrats/7', route = '/contrats/:id' } = {}) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ThemeProvider>
        <Routes>
          <Route path={route} element={ui} />
        </Routes>
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('ContratDetail — actions du cycle de vie (CONTRAT12-17)', () => {
  it('rend les onglets Signatures et Approbation', async () => {
    withProviders(<ContratDetail />)
    await waitFor(() => expect(screen.getByText('CT-2026-07-0001')).toBeInTheDocument())
    expect(screen.getByRole('tab', { name: /Signatures/ })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Approbation/ })).toBeInTheDocument()
  })

  it('propose une transition gardée depuis statuts-suivants et l’applique', async () => {
    withProviders(<ContratDetail />)
    await waitFor(() => expect(screen.getByText('CT-2026-07-0001')).toBeInTheDocument())
    const btn = await screen.findByRole('button', { name: /En approbation/ })
    fireEvent.click(btn)
    await waitFor(() => expect(changerStatut).toHaveBeenCalledWith('7', 'en_approbation'))
  })
})

describe('LocationPage — module de location (XCTR17)', () => {
  it('affiche le titre et le bouton de création', async () => {
    render(
      <MemoryRouter>
        <ThemeProvider><LocationPage /></ThemeProvider>
      </MemoryRouter>,
    )
    await waitFor(() => expect(screen.getByText('Location de matériel')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /Nouvel ordre/ })).toBeInTheDocument()
  })
})

describe('Pastilles de statut de location', () => {
  it('mappe les statuts locaux de l’ordre et de la caution', () => {
    expect(StatutLocation.toneOf('reservee')).toBe('info')
    expect(StatutLocation.toneOf('enlevee')).toBe('success')
    expect(StatutLocation.toneOf('cloturee')).toBe('neutral')
    expect(StatutCautionLocation.toneOf('encaissee')).toBe('success')
    expect(StatutCautionLocation.toneOf('retenue_partielle')).toBe('warning')
  })
})
