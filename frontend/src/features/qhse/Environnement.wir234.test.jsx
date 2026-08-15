import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR234 — les BSD (loi 28-00) et le recyclage des modules PV étaient créables
   mais jamais AVANÇABLES (registres figés au statut initial). On vérifie les
   deux cycles de vie (`emis → enleve → traite`, `collecte → transporte →
   recycle`) depuis les actions de ligne. Réseau mocké. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const { empty, bsdEnlever, bsdTraiter, recTransporter, recRecycler } = vi.hoisted(() => ({
  empty: () => Promise.resolve({ data: [] }),
  bsdEnlever: vi.fn(() => Promise.resolve({ data: {} })),
  bsdTraiter: vi.fn(() => Promise.resolve({ data: {} })),
  recTransporter: vi.fn(() => Promise.resolve({ data: {} })),
  recRecycler: vi.fn(() => Promise.resolve({ data: {} })),
}))

const BSD_ROW = {
  id: 41, reference: 'BSD-000041', dechet_libelle: 'Batteries usagées',
  quantite: 12, eliminateur: 'Eco Recyclage', statut: 'emis',
}
const RECYCLAGE_ROW = {
  id: 51, reference: 'REC-000051', marque: 'Jinko', modele: 'JKM400',
  nombre_modules: 20, motif: 'fin_de_vie', statut: 'collecte',
}

vi.mock('../../api/qhseApi', () => ({
  default: {
    dechets: { list: () => Promise.resolve({ data: [] }), create: vi.fn() },
    bordereauxDechets: {
      list: vi.fn(() => Promise.resolve({ data: [BSD_ROW] })),
      create: vi.fn(),
      enlever: (...a) => bsdEnlever(...a),
      traiter: (...a) => bsdTraiter(...a),
    },
    recyclageModules: {
      list: vi.fn(() => Promise.resolve({ data: [RECYCLAGE_ROW] })),
      create: vi.fn(),
      transporter: (...a) => recTransporter(...a),
      recycler: (...a) => recRecycler(...a),
    },
    conformitesEnvironnementales: { list: empty, create: vi.fn() },
    bilansCarbone: { list: empty, create: vi.fn() },
    indicateursEsg: { list: empty, create: vi.fn() },
    aspectsEnvironnementaux: { list: empty, create: vi.fn() },
    relevesConsommation: { list: empty, create: vi.fn() },
    demandesChangement: { list: empty, create: vi.fn() },
    veillesReglementaires: { list: empty, create: vi.fn() },
  },
}))

vi.mock('../../hooks/useHasPermission', () => ({ useHasPermission: () => false }))

import Environnement from './Environnement'

function withProviders(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

describe('Environnement — cycle BSD et recyclage (WIR234)', () => {
  it('un BSD émis peut être enlevé puis traité', async () => {
    const user = userEvent.setup()
    withProviders(<Environnement />)
    await screen.findAllByText('BSD-000041')

    await user.click(screen.getAllByRole('button', { name: 'Enlever' })[0])
    await waitFor(() => expect(bsdEnlever).toHaveBeenCalledWith(41, {}))

    await user.click(screen.getAllByRole('button', { name: 'Traiter' })[0])
    await waitFor(() => expect(bsdTraiter).toHaveBeenCalledWith(41, {}))
  })

  it('un lot de recyclage collecté peut être transporté puis recyclé', async () => {
    const user = userEvent.setup()
    withProviders(<Environnement />)
    await user.click(screen.getByRole('tab', { name: 'Recyclage PV' }))
    await screen.findAllByText('REC-000051')

    await user.click(screen.getAllByRole('button', { name: 'Transporter' })[0])
    await waitFor(() => expect(recTransporter).toHaveBeenCalledWith(51))

    await user.click(screen.getAllByRole('button', { name: 'Recycler' })[0])
    await waitFor(() => expect(recRecycler).toHaveBeenCalledWith(51, {}))
  })
})
