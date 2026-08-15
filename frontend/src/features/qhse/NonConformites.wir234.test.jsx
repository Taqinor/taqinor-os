import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR234 — `capa.historique`/`capa.noter` (chatter Odoo-style, patron
   NcrChatter) n'avaient aucun appelant côté écran : aucun panneau détail CAPA
   n'existait. On vérifie que « Historique & notes » ouvre le chatter et
   qu'une note s'enregistre via `capa.noter`. Réseau mocké. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const { empty, capaHistorique, capaNoter } = vi.hoisted(() => ({
  empty: () => Promise.resolve({ data: [] }),
  capaHistorique: vi.fn(() => Promise.resolve({ data: [] })),
  capaNoter: vi.fn(() => Promise.resolve({ data: {} })),
}))

const CAPA_ROW = {
  id: 80, description: 'Renforcer garde-corps', type_action: 'corrective',
  statut: 'en_cours', echeance: '2026-09-01', efficace: null,
}

vi.mock('../../api/qhseApi', () => ({
  default: {
    nonConformites: { list: empty, historique: empty },
    capa: {
      list: vi.fn(() => Promise.resolve({ data: [CAPA_ROW] })),
      enRetard: empty,
      relancerRetards: vi.fn(() => Promise.resolve({ data: { total: 0 } })),
      historique: (...a) => capaHistorique(...a),
      noter: (...a) => capaNoter(...a),
    },
    derogations: { list: empty },
  },
}))

import NonConformites from './NonConformites'

function withProviders(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

describe('NonConformites — chatter CAPA (WIR234)', () => {
  it('ouvre le panneau détail CAPA et charge l’historique', async () => {
    const user = userEvent.setup()
    withProviders(<NonConformites />)
    await user.click(screen.getByRole('tab', { name: 'CAPA' }))
    await screen.findAllByText('Renforcer garde-corps')

    await user.click(screen.getAllByRole('button', { name: "Plus d'actions sur la ligne" })[0])
    await user.click(await screen.findByText('Historique & notes'))

    await waitFor(() => expect(capaHistorique).toHaveBeenCalledWith(80))
  })

  it('ajoute une note sur une CAPA depuis le chatter', async () => {
    const user = userEvent.setup()
    withProviders(<NonConformites />)
    await user.click(screen.getByRole('tab', { name: 'CAPA' }))
    await screen.findAllByText('Renforcer garde-corps')

    await user.click(screen.getAllByRole('button', { name: "Plus d'actions sur la ligne" })[0])
    await user.click(await screen.findByText('Historique & notes'))

    const textarea = await screen.findByPlaceholderText('Ajouter une note…')
    await user.type(textarea, 'Garde-corps commandé.')
    await user.click(screen.getByRole('button', { name: 'Noter' }))

    await waitFor(() => expect(capaNoter).toHaveBeenCalledWith(80, 'Garde-corps commandé.'))
  })
})
