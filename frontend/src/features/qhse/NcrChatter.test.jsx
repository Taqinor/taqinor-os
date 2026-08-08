import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

/* PACT158 — le chatter NCR doit afficher une entrée 'modification' (la
   valeur RÉELLE écrite par apps/qhse/chatter.py) comme un changement de
   champ libellé, jamais « Enregistrement créé » avec une pastille montrant
   le mot brut. */

const mocks = vi.hoisted(() => ({ historique: vi.fn(), noter: vi.fn() }))

vi.mock('../../api/qhseApi', () => ({
  default: {
    nonConformites: {
      historique: mocks.historique,
      noter: mocks.noter,
    },
  },
}))

import NcrChatter from './NcrChatter'

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
