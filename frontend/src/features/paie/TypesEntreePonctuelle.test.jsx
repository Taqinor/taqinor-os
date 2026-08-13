import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* PACT95 — Types d'entrées ponctuelles de paie. `TypeEntreePonctuelle`
   (`apps/paie/models.py:2086`) était déjà exposé à
   `/paie/types-entree-ponctuelle/` (+ l'action `seed-standard`) SANS AUCUN
   écran. `../../api/axios` est mocké directement (pas de wrapper `paieApi`
   dédié pour cet endpoint) — vérifie la liste, la création, l'édition (une
   ligne à la fois, jamais un re-seed complet) et le semis du catalogue
   standard. */

const { apiGet, apiPost, apiPatch } = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(() => Promise.resolve({ data: { id: 99 } })),
  apiPatch: vi.fn(() => Promise.resolve({ data: {} })),
}))

vi.mock('../../api/axios', () => ({
  default: {
    get: (...args) => apiGet(...args),
    post: (...args) => apiPost(...args),
    patch: (...args) => apiPatch(...args),
  },
}))

import TypesEntreePonctuelle from './TypesEntreePonctuelle.jsx'

const TYPE = {
  id: 5, code: 'POURBOIRE', libelle: 'Pourboire', sens: 'gain',
  imposable: false, soumis_cnss: false, soumis_amo: false, actif: true,
}

beforeEach(() => {
  vi.clearAllMocks()
  apiGet.mockResolvedValue({ data: [TYPE] })
  apiPost.mockResolvedValue({ data: { id: 99 } })
  apiPatch.mockResolvedValue({ data: {} })
})

function wrap(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

describe('TypesEntreePonctuelle (PACT95)', () => {
  it('liste les types déjà en base', async () => {
    wrap(<TypesEntreePonctuelle />)
    await waitFor(() => expect(apiGet).toHaveBeenCalledWith('/paie/types-entree-ponctuelle/'))
    expect(await screen.findByText('POURBOIRE')).toBeInTheDocument()
    expect(screen.getByText('Pourboire')).toBeInTheDocument()
  })

  it('crée un nouveau type d’entrée ponctuelle', async () => {
    wrap(<TypesEntreePonctuelle />)
    await screen.findByText('POURBOIRE')

    await userEvent.click(screen.getByRole('button', { name: /Nouveau type/ }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.type(within(dialog).getByLabelText('Code'), 'REMB-NI')
    await userEvent.type(within(dialog).getByLabelText('Libellé'), 'Remboursement non imposable')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Créer le type' }))

    await waitFor(() => expect(apiPost).toHaveBeenCalledWith('/paie/types-entree-ponctuelle/', {
      code: 'REMB-NI', libelle: 'Remboursement non imposable', sens: 'gain',
      imposable: true, soumis_cnss: true, soumis_amo: true, actif: true,
    }))
  })

  it('édite un type existant, UNE ligne à la fois (jamais un re-seed complet)', async () => {
    wrap(<TypesEntreePonctuelle />)
    const row = (await screen.findAllByText('POURBOIRE'))
      .map((el) => el.closest('tr')).find(Boolean)
    expect(row).toBeTruthy()
    await userEvent.click(within(row).getByLabelText("Plus d'actions sur la ligne"))
    await userEvent.click(await screen.findByText('Éditer le type'))

    const dialog = await screen.findByRole('dialog')
    const libelleInput = within(dialog).getByLabelText('Libellé')
    await userEvent.clear(libelleInput)
    await userEvent.type(libelleInput, 'Pourboire client')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Mettre à jour' }))

    await waitFor(() => expect(apiPatch).toHaveBeenCalledWith(
      '/paie/types-entree-ponctuelle/5/',
      expect.objectContaining({ libelle: 'Pourboire client', code: 'POURBOIRE' }),
    ))
    // Un seul appel — pas de semis du catalogue entier.
    expect(apiPost).not.toHaveBeenCalled()
  })

  it('provisionne le catalogue standard (idempotent, additif)', async () => {
    wrap(<TypesEntreePonctuelle />)
    await screen.findByText('POURBOIRE')

    await userEvent.click(screen.getByRole('button', { name: /Catalogue standard/ }))

    await waitFor(() => expect(apiPost).toHaveBeenCalledWith(
      '/paie/types-entree-ponctuelle/seed-standard/',
    ))
  })
})
