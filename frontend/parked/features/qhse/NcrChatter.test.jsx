import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

/* PACT158 — le chatter NCR doit afficher une entrée 'modification' (la
   valeur RÉELLE écrite par apps/qhse/chatter.py) comme un changement de
   champ libellé, jamais « Enregistrement créé » avec une pastille montrant
   le mot brut. */

const mocks = vi.hoisted(() => ({
  historique: vi.fn(), noter: vi.fn(),
  capaHistorique: vi.fn(), capaNoter: vi.fn(),
}))

vi.mock('../../api/qhseApi', () => ({
  default: {
    nonConformites: {
      historique: mocks.historique,
      noter: mocks.noter,
    },
    capa: {
      historique: mocks.capaHistorique,
      noter: mocks.capaNoter,
    },
  },
}))

import NcrChatter, { CapaChatter } from './NcrChatter'

const MODIFICATION_ENTRY = {
  id: 1,
  kind: 'modification',
  field: 'statut',
  field_label: 'Statut',
  old_value: 'ouverte',
  new_value: 'cloturee',
  user_nom: 'reda',
  created_at: '2026-08-01T10:00:00Z',
}

const CREATION_ENTRY = {
  id: 2,
  kind: 'creation',
  body: '',
  user_nom: 'reda',
  created_at: '2026-08-01T09:00:00Z',
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('NcrChatter', () => {
  it("affiche une entrée 'modification' comme « Champ : ancienne → nouvelle » avec sa pastille libellée", async () => {
    mocks.historique.mockResolvedValue({ data: [MODIFICATION_ENTRY] })
    render(<NcrChatter ncrId={7} />)
    await waitFor(() => expect(mocks.historique).toHaveBeenCalledWith(7))

    expect(await screen.findByText('Statut : ouverte → cloturee')).toBeTruthy()
    expect(screen.getByText('Modification')).toBeTruthy()
    expect(screen.queryByText('Enregistrement créé')).toBeNull()
  })

  it("affiche « Enregistrement créé » pour une entrée de création", async () => {
    mocks.historique.mockResolvedValue({ data: [CREATION_ENTRY] })
    render(<NcrChatter ncrId={7} />)
    await waitFor(() => expect(mocks.historique).toHaveBeenCalledWith(7))

    expect(await screen.findByText('Enregistrement créé')).toBeTruthy()
    expect(screen.getByText('Création')).toBeTruthy()
  })
})

describe('CapaChatter (WIR234 — jumeau NcrChatter pour une CAPA)', () => {
  it('charge l’historique via capa.historique et affiche le titre dédié', async () => {
    mocks.capaHistorique.mockResolvedValue({ data: [CREATION_ENTRY] })
    render(<CapaChatter capaId={12} />)
    await waitFor(() => expect(mocks.capaHistorique).toHaveBeenCalledWith(12))

    expect(await screen.findByText(/Historique CAPA/)).toBeTruthy()
    expect(mocks.historique).not.toHaveBeenCalled()
  })

  it('ajoute une note via capa.noter puis recharge l’historique', async () => {
    mocks.capaHistorique.mockResolvedValue({ data: [] })
    mocks.capaNoter.mockResolvedValue({ data: {} })
    render(<CapaChatter capaId={12} />)
    await waitFor(() => expect(mocks.capaHistorique).toHaveBeenCalledWith(12))

    fireEvent.change(screen.getByPlaceholderText('Ajouter une note…'), {
      target: { value: 'Fournisseur relancé par téléphone.' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Noter' }))

    await waitFor(() => expect(mocks.capaNoter).toHaveBeenCalledWith(
      12, 'Fournisseur relancé par téléphone.'))
    expect(mocks.noter).not.toHaveBeenCalled()
  })
})
