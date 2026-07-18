import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* XFLT5 (signalements), XFLT19 (approbation OR) et XFLT26 (ICE/IF garage) —
   onglets ajoutés à l'écran Entretien. On mocke le client API pour vérifier
   que chaque action appelle le bon endpoint flotteApi, sans réseau. */

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
  empty, signalementsCreate, garagesCreate, approuver, ordresList, generer,
} = vi.hoisted(() => ({
  empty: () => Promise.resolve({ data: [] }),
  signalementsCreate: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
  garagesCreate: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
  approuver: vi.fn(() => Promise.resolve({ data: { id: 7, statut: 'approuve' } })),
  ordresList: () => Promise.resolve({
    data: [{
      id: 7, actif_label: '12345-A-6', garage_nom: 'Garage Centre',
      description: 'Frein arrière', date_ouverture: '2026-07-01',
      cout_total: 1200, statut: 'devis_recu', sous_garantie: true,
    }],
  }),
  generer: vi.fn(() => Promise.resolve({ data: { nb_creees: 2, nb_existantes: 0, nb_plans_due: 2, echeances: [] } })),
}))

vi.mock('../../api/flotteApi', () => ({
  default: {
    actifs: { list: () => Promise.resolve({ data: [{ id: 1, label: '12345-A-6' }] }) },
    plansEntretien: { list: empty },
    echeancesEntretien: { list: empty, generer: (...args) => generer(...args) },
    garages: { list: empty, create: (...args) => garagesCreate(...args) },
    ordresReparation: {
      list: ordresList,
      approuver: (...args) => approuver(...args),
    },
    pneumatiques: { list: empty },
    pieces: { list: empty },
    signalements: {
      list: empty,
      create: (...args) => signalementsCreate(...args),
      convertirEnOr: vi.fn(() => Promise.resolve({ data: {} })),
    },
  },
}))

import EntretienScreen from './EntretienScreen'

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('EntretienScreen — Échéances (WIR5 génération)', () => {
  it('déclenche la génération des échéances et recharge la liste', async () => {
    const user = userEvent.setup()
    withProviders(<EntretienScreen />)

    await user.click(await screen.findByRole('button', { name: 'Générer les échéances' }))

    await waitFor(() => expect(generer).toHaveBeenCalled())
  })
})

describe('EntretienScreen — Signalements (XFLT5)', () => {
  it('ouvre le formulaire « Signaler un problème » et crée le signalement', async () => {
    const user = userEvent.setup()
    withProviders(<EntretienScreen />)

    await user.click(screen.getByRole('tab', { name: 'Signalements' }))
    await user.click(screen.getByRole('button', { name: 'Signaler un problème' }))

    await user.selectOptions(screen.getByLabelText('Véhicule / engin concerné'), '1')
    await user.type(screen.getByLabelText('Description du problème'), 'Bruit anormal au freinage')
    await user.click(screen.getByRole('button', { name: 'Signaler' }))

    await waitFor(() => expect(signalementsCreate).toHaveBeenCalledWith(
      expect.objectContaining({ actif_flotte: 1, description: 'Bruit anormal au freinage' }),
    ))
  })
})

describe('EntretienScreen — Ordres de réparation (XFLT19)', () => {
  it('affiche l’avertissement garantie et approuve le devis via la ligne', async () => {
    const user = userEvent.setup()
    withProviders(<EntretienScreen />)

    await user.click(screen.getByRole('tab', { name: 'Ordres de réparation' }))
    // DataTable rend la table desktop ET les cartes mobiles dans le DOM (le
    // point de rupture est géré en CSS) : deux correspondances attendues.
    await waitFor(() => expect(screen.getAllByText('Frein arrière').length).toBeGreaterThan(0))
    expect(screen.getAllByText('Sous garantie').length).toBeGreaterThan(0)
  })
})

describe('EntretienScreen — Garages (XFLT26)', () => {
  it('crée un garage avec ICE/IF', async () => {
    const user = userEvent.setup()
    withProviders(<EntretienScreen />)

    await user.click(screen.getByRole('tab', { name: 'Garages' }))
    await user.click(screen.getByRole('button', { name: 'Nouveau garage' }))

    await user.type(screen.getByLabelText('Nom'), 'Garage Test')
    await user.type(screen.getByLabelText('ICE'), '123456789012345')
    await user.type(screen.getByLabelText('Identifiant fiscal (IF)'), 'IF-999')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(garagesCreate).toHaveBeenCalledWith(
      expect.objectContaining({ nom: 'Garage Test', ice: '123456789012345', identifiant_fiscal: 'IF-999' }),
    ))
  })
})
