import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* XFLT25 — codes défaut moteur (DTC) affichés sur les relevés télématiques,
   et XFLT23 — création d'un plein via le nouveau bouton. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const { empty, anomalies, cartesCreate, syntheseTva, importerReleve, journal } = vi.hoisted(() => ({
  empty: () => Promise.resolve({ data: [] }),
  anomalies: vi.fn(() => Promise.resolve({
    data: {
      nb_pleins: 5,
      nb_anomalies: 1,
      anomalies: [{
        plein_id: 3, type: 'km_recul', gravite: 'haute',
        message: 'Kilométrage en recul détecté', date_plein: '2026-07-01',
      }],
    },
  })),
  cartesCreate: vi.fn(() => Promise.resolve({ data: { id: 6 } })),
  syntheseTva: vi.fn(() => Promise.resolve({
    data: { total_ttc: 12000, tva_recuperable: 1200, tva_non_deductible: 300, nb_pleins: 20 },
  })),
  importerReleve: vi.fn(() => Promise.resolve({
    data: { lignes_creees: 4, lignes_non_rapprochees: 1 },
  })),
  journal: vi.fn(() => Promise.resolve({
    data: {
      nb_trajets: 8, distance_totale_km: 320.5,
      par_chantier: [{ installation_id: 9, chantier_reference: 'CH-0009', nb_trajets: 5, distance_km: 200 }],
    },
  })),
}))

vi.mock('../../api/flotteApi', () => ({
  default: {
    pleins: { list: empty, ocr: vi.fn(), syntheseTva: (...args) => syntheseTva(...args) },
    cartes: {
      list: vi.fn(() => Promise.resolve({ data: [{ id: 55, numero: 'CARTE-0055', actif: true }] })),
      anomalies: (...args) => anomalies(...args),
      create: (...args) => cartesCreate(...args),
      update: vi.fn(() => Promise.resolve({ data: {} })),
      importerReleve: (...args) => importerReleve(...args),
    },
    conducteurs: { list: () => Promise.resolve({ data: [{ id: 2, nom: 'Karim' }] }) },
    sinistres: { list: empty },
    infractions: { list: empty },
    vehicules: { list: () => Promise.resolve({ data: [{ id: 1, immatriculation: '12345-A-6' }] }) },
    relevesTelematiques: { list: () => Promise.resolve({
      data: [{ id: 1, actif_label: '12345-A-6', horodatage: '2026-07-01T08:00:00Z', codes_defaut: ['P0300', 'P0171'] }],
    }) },
    trajetsTelematiques: { list: empty },
    trajetsChantier: { list: empty, journal: (...args) => journal(...args) },
  },
}))

import CarburantScreen from './CarburantScreen'

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('CarburantScreen — Télématique (XFLT25 DTC)', () => {
  it('affiche les codes défaut moteur sur les relevés télématiques', async () => {
    const user = userEvent.setup()
    withProviders(<CarburantScreen />)

    await user.click(screen.getByRole('tab', { name: 'Télématique' }))
    // DataTable rend la table desktop ET les cartes mobiles dans le DOM (le
    // point de rupture est géré en CSS) : deux correspondances attendues.
    await waitFor(() => expect(screen.getAllByText('P0300, P0171').length).toBeGreaterThan(0))
  })
})

describe('CarburantScreen — Cartes (WIR6 anomalies)', () => {
  it('affiche une anomalie détectée sur l’onglet Cartes', async () => {
    const user = userEvent.setup()
    withProviders(<CarburantScreen />)

    await user.click(screen.getByRole('tab', { name: 'Cartes' }))
    await waitFor(() => expect(anomalies).toHaveBeenCalled())
    await waitFor(() => expect(screen.getByText('Kilométrage en recul détecté')).toBeInTheDocument())
  })
})

describe('CarburantScreen — Cartes (WIR43 création)', () => {
  it('crée une carte carburant rattachée à un véhicule et un conducteur', async () => {
    const user = userEvent.setup()
    withProviders(<CarburantScreen />)

    await user.click(screen.getByRole('tab', { name: 'Cartes' }))
    await user.click(await screen.findByRole('button', { name: 'Nouvelle carte' }))

    await user.type(screen.getByLabelText('N° carte'), 'CARTE-001')
    await user.selectOptions(screen.getByLabelText('Véhicule (option.)'), '1')
    await user.selectOptions(screen.getByLabelText('Conducteur (option.)'), '2')
    await user.click(screen.getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(cartesCreate).toHaveBeenCalledWith(
      expect.objectContaining({ numero: 'CARTE-001', vehicule: 1, conducteur: 2 }),
    ))
  })
})

describe('CarburantScreen — Carburant (XFLT23 bouton nouveau plein)', () => {
  it('ouvre le formulaire de nouveau plein', async () => {
    const user = userEvent.setup()
    withProviders(<CarburantScreen />)

    await user.click(screen.getByRole('button', { name: 'Nouveau plein' }))
    expect(screen.getByRole('heading', { name: 'Nouveau plein' })).toBeInTheDocument()
  })
})

describe('CarburantScreen — Synthèse TVA carburant (WIR236)', () => {
  it('affiche la synthèse TVA au clic sur le bouton dédié', async () => {
    const user = userEvent.setup()
    withProviders(<CarburantScreen />)

    await user.click(screen.getByRole('button', { name: 'Synthèse TVA' }))
    await waitFor(() => expect(syntheseTva).toHaveBeenCalled())
    expect(await screen.findByText(/1200.00 MAD/)).toBeInTheDocument()
  })
})

describe('CarburantScreen — Import relevé CSV carte carburant (WIR236)', () => {
  it('importe un relevé CSV depuis l’action de ligne d’une carte', async () => {
    const user = userEvent.setup()
    withProviders(<CarburantScreen />)
    await user.click(screen.getByRole('tab', { name: 'Cartes' }))
    await screen.findAllByText('CARTE-0055')

    await user.click(screen.getAllByRole('button', { name: "Plus d'actions sur la ligne" })[0])
    await user.click(await screen.findByText('Importer un relevé (CSV)'))

    const fichier = new File(['date;montant;litres'], 'releve.csv', { type: 'text/csv' })
    const input = document.querySelector('input[type="file"]')
    await user.upload(input, fichier)
    await user.click(screen.getByRole('button', { name: 'Importer' }))

    await waitFor(() => expect(importerReleve).toHaveBeenCalledWith(55, expect.any(FormData)))
  })
})

describe('CarburantScreen — Journal kilométrique par chantier (WIR236)', () => {
  it('affiche le journal ventilé par chantier au clic sur le bouton dédié', async () => {
    const user = userEvent.setup()
    withProviders(<CarburantScreen />)
    await user.click(screen.getByRole('tab', { name: 'Trajets chantier' }))

    await user.click(await screen.findByRole('button', { name: 'Journal kilométrique' }))
    await waitFor(() => expect(journal).toHaveBeenCalled())
    expect(await screen.findByText('CH-0009')).toBeInTheDocument()
  })
})
