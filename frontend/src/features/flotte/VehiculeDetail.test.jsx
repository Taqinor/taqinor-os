import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* XFLT4/XFLT1/XFLT3 — Onglets « Cycle de vie », « Contrats » et « Grand livre »
   du panneau détail véhicule. On mocke le client API pour rester hors réseau
   et vérifier que chaque action (changement de statut, cession, lecture du
   grand livre/contrats) appelle bien le bon endpoint flotteApi. */

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
  changerStatut, ceder, vehiculeHistorique, vehiculeLedger, contratsList,
  actifsList, detenteursCourants, remisesList, remisesCreate, conducteursList, empty,
} = vi.hoisted(() => ({
  changerStatut: vi.fn(() => Promise.resolve({ data: { id: 1, statut: 'actif' } })),
  ceder: vi.fn(() => Promise.resolve({ data: { id: 1, statut: 'vendu' } })),
  vehiculeHistorique: vi.fn(() => Promise.resolve({ data: [] })),
  vehiculeLedger: vi.fn(() => Promise.resolve({ data: { lignes: [] } })),
  contratsList: vi.fn(() => Promise.resolve({ data: [] })),
  actifsList: vi.fn(() => Promise.resolve({ data: [{ id: 77, vehicule: 42, type_actif: 'vehicule' }] })),
  detenteursCourants: vi.fn(() => Promise.resolve({
    data: [{ type: 'cle', type_display: 'Clé', conducteur_id: 1, conducteur_nom: 'Karim', date_remise: '2026-06-01' }],
  })),
  remisesList: vi.fn(() => Promise.resolve({ data: [] })),
  remisesCreate: vi.fn(() => Promise.resolve({ data: { id: 5 } })),
  conducteursList: vi.fn(() => Promise.resolve({ data: [{ id: 1, nom: 'Karim' }] })),
  empty: () => Promise.resolve({ data: null }),
}))

vi.mock('../../api/flotteApi', () => ({
  default: {
    changerStatut: (...args) => changerStatut(...args),
    ceder: (...args) => ceder(...args),
    vehiculeHistorique: (...args) => vehiculeHistorique(...args),
    vehiculeLedger: (...args) => vehiculeLedger(...args),
    vehiculeTco: empty,
    vehiculeTsav: empty,
    vehiculeEcoConduite: empty,
    vehiculeAmortissement: empty,
    contratsVehicule: { list: (...args) => contratsList(...args) },
    actifs: {
      list: (...args) => actifsList(...args),
      detenteursCourants: (...args) => detenteursCourants(...args),
    },
    remisesAccessoire: {
      list: (...args) => remisesList(...args),
      create: (...args) => remisesCreate(...args),
    },
    conducteurs: { list: (...args) => conducteursList(...args) },
  },
}))

import VehiculeDetail from './VehiculeDetail'

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

const VEHICULE = {
  id: 42, immatriculation: '12345-A-6', marque: 'Renault', modele: 'Kangoo',
  statut: 'a_vendre', energie: 'diesel',
}

describe('VehiculeDetail — Cycle de vie (XFLT4)', () => {
  it('affiche le sélecteur de statut et appelle changerStatut à la soumission', async () => {
    const user = userEvent.setup()
    withProviders(<VehiculeDetail vehicule={VEHICULE} onClose={() => {}} />)

    await user.click(screen.getByRole('tab', { name: 'Cycle de vie' }))
    await waitFor(() => expect(vehiculeHistorique).toHaveBeenCalledWith(42))

    const select = screen.getByLabelText('Changer le statut')
    await user.selectOptions(select, 'vendu')
    await user.click(screen.getByRole('button', { name: 'Appliquer' }))

    await waitFor(() => expect(changerStatut).toHaveBeenCalledWith(42, 'vendu'))
  })

  it('propose la cession quand le statut est « à vendre » et appelle ceder()', async () => {
    const user = userEvent.setup()
    withProviders(<VehiculeDetail vehicule={VEHICULE} onClose={() => {}} />)

    await user.click(screen.getByRole('tab', { name: 'Cycle de vie' }))
    await user.click(screen.getByRole('button', { name: 'Céder (vendre) ce véhicule' }))

    const dateInput = screen.getByLabelText('Date de cession')
    const prixInput = screen.getByLabelText('Prix de cession (MAD)')
    await user.type(dateInput, '2026-07-10')
    await user.type(prixInput, '50000')
    await user.click(screen.getByRole('button', { name: 'Confirmer la cession' }))

    await waitFor(() => expect(ceder).toHaveBeenCalledWith(42, expect.objectContaining({
      date_cession: '2026-07-10', prix_cession: '50000',
    })))
  })
})

describe('VehiculeDetail — Contrats (XFLT1) & Grand livre (XFLT3)', () => {
  it('charge les contrats du véhicule sur l’onglet Contrats', async () => {
    const user = userEvent.setup()
    withProviders(<VehiculeDetail vehicule={VEHICULE} onClose={() => {}} />)

    await user.click(screen.getByRole('tab', { name: 'Contrats' }))
    await waitFor(() => expect(contratsList).toHaveBeenCalledWith({ vehicule: 42 }))
  })

  it('charge le grand livre unifié sur l’onglet Grand livre', async () => {
    const user = userEvent.setup()
    withProviders(<VehiculeDetail vehicule={VEHICULE} onClose={() => {}} />)

    await user.click(screen.getByRole('tab', { name: 'Grand livre' }))
    await waitFor(() => expect(vehiculeLedger).toHaveBeenCalledWith(42))
  })
})

describe('VehiculeDetail — Accessoires (XFLT20)', () => {
  it('résout l’actif du véhicule et affiche le détenteur courant', async () => {
    const user = userEvent.setup()
    withProviders(<VehiculeDetail vehicule={VEHICULE} onClose={() => {}} />)

    await user.click(screen.getByRole('tab', { name: 'Accessoires' }))
    await waitFor(() => expect(actifsList).toHaveBeenCalledWith({ type_actif: 'vehicule' }))
    await waitFor(() => expect(detenteursCourants).toHaveBeenCalledWith(77))
    await waitFor(() => expect(remisesList).toHaveBeenCalledWith({ actif_flotte: 77 }))
    await waitFor(() => expect(screen.getByText('Karim', { exact: false })).toBeInTheDocument())
  })
})

describe('VehiculeDetail — Accessoires (WIR47 remise)', () => {
  it('enregistre la remise d’un accessoire à un conducteur depuis l’onglet', async () => {
    const user = userEvent.setup()
    withProviders(<VehiculeDetail vehicule={VEHICULE} onClose={() => {}} />)

    await user.click(screen.getByRole('tab', { name: 'Accessoires' }))
    await waitFor(() => expect(detenteursCourants).toHaveBeenCalledWith(77))

    await user.click(await screen.findByRole('button', { name: 'Remettre un accessoire' }))
    await user.selectOptions(screen.getByLabelText('Conducteur'), '1')
    await user.type(screen.getByLabelText('Date de remise'), '2026-08-01')
    await user.click(screen.getByRole('button', { name: 'Remettre' }))

    await waitFor(() => expect(remisesCreate).toHaveBeenCalledWith(
      expect.objectContaining({ actif_flotte: 77, type_accessoire: 'cle', conducteur: 1, date_remise: '2026-08-01' }),
    ))
  })
})
