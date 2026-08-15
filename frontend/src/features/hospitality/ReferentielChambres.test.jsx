import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'

/* WIR211/NTHOT1+NTHOT2 — le module hôtellerie était INERTE : les trois
   endpoints de création (type de chambre, chambre, plan tarifaire) existaient
   et étaient même déjà exposés par `hospitalityApi`, mais aucun écran ne les
   appelait. Depuis une base vide, rien n'était créable — d'où un plan des
   chambres vide, des folios sans nuitées et un RevPAR à 0.

   Charges utiles alignées sur TypeChambreSerializer / ChambreSerializer /
   PlanTarifaireSerializer — jamais une forme inventée. */

vi.mock('../../api/hospitalityApi', () => ({
  default: {
    listTypesChambre: vi.fn(),
    createTypeChambre: vi.fn(),
    listChambres: vi.fn(),
    createChambre: vi.fn(),
    listPlansTarifaires: vi.fn(),
    createPlanTarifaire: vi.fn(),
  },
}))

import hospitalityApi from '../../api/hospitalityApi'
import ReferentielChambres from './ReferentielChambres'

const TYPE = { id: 1, libelle: 'Double', capacite_max: 2, description: '' }
const CHAMBRE = {
  id: 5, type_chambre: 1, type_chambre_libelle: 'Double', numero: '101',
  nom: '', etage: 1, statut: 'libre', statut_display: 'Libre', vue: 'mer',
}
const PLAN = {
  id: 9, type_chambre: 1, canal: 'rack', canal_display: 'Rack (tarif public)',
  date_debut: '2026-07-01', date_fin: '2026-08-31',
  prix_nuit_ht: '900.00', min_nuits: 1,
}

beforeEach(() => {
  vi.clearAllMocks()
  hospitalityApi.listTypesChambre.mockResolvedValue({ data: [] })
  hospitalityApi.listChambres.mockResolvedValue({ data: [] })
  hospitalityApi.listPlansTarifaires.mockResolvedValue({ data: [] })
})
afterEach(() => { cleanup() })

describe('ReferentielChambres (WIR211)', () => {
  it('base vide : crée un type de chambre', async () => {
    hospitalityApi.createTypeChambre.mockResolvedValue({ data: TYPE })
    render(<ReferentielChambres />)

    expect(await screen.findByText(/Aucun type de chambre/)).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText(/Libellé du type/), { target: { value: 'Double' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer le type' }))

    await waitFor(() => expect(hospitalityApi.createTypeChambre).toHaveBeenCalledWith(
      expect.objectContaining({ libelle: 'Double' })))
  })

  it('la chambre exige un type : le bouton est fermé tant qu’il n’y en a pas', async () => {
    render(<ReferentielChambres />)
    await waitFor(() => expect(hospitalityApi.listTypesChambre).toHaveBeenCalled())
    expect(screen.getByRole('button', { name: 'Créer la chambre' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Créer le plan tarifaire' })).toBeDisabled()
  })

  it('avec un type : crée une chambre (étage vide → null, jamais 0 inventé)', async () => {
    hospitalityApi.listTypesChambre.mockResolvedValue({ data: [TYPE] })
    hospitalityApi.createChambre.mockResolvedValue({ data: CHAMBRE })
    render(<ReferentielChambres />)

    await waitFor(() => expect(
      screen.getByRole('button', { name: 'Créer la chambre' })).not.toBeDisabled())
    fireEvent.change(screen.getByLabelText(/^Type de chambre$/, { selector: '#ch-type' }),
      { target: { value: '1' } })
    fireEvent.change(screen.getByLabelText(/Numéro/), { target: { value: '101' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer la chambre' }))

    await waitFor(() => expect(hospitalityApi.createChambre).toHaveBeenCalledTimes(1))
    const corps = hospitalityApi.createChambre.mock.calls[0][0]
    expect(corps).toMatchObject({ type_chambre: '1', numero: '101' })
    expect(corps.etage).toBeNull()
  })

  it('crée un plan tarifaire avec période et prix par nuit', async () => {
    hospitalityApi.listTypesChambre.mockResolvedValue({ data: [TYPE] })
    hospitalityApi.createPlanTarifaire.mockResolvedValue({ data: PLAN })
    render(<ReferentielChambres />)

    await waitFor(() => expect(
      screen.getByRole('button', { name: 'Créer le plan tarifaire' })).not.toBeDisabled())
    fireEvent.change(screen.getByLabelText(/^Type de chambre$/, { selector: '#pt-type' }),
      { target: { value: '1' } })
    fireEvent.change(screen.getByLabelText(/Prix par nuit/), { target: { value: '900' } })
    fireEvent.change(screen.getByLabelText(/Début de la période/), { target: { value: '2026-07-01' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer le plan tarifaire' }))

    await waitFor(() => expect(hospitalityApi.createPlanTarifaire).toHaveBeenCalledTimes(1))
    expect(hospitalityApi.createPlanTarifaire.mock.calls[0][0]).toMatchObject({
      type_chambre: '1', canal: 'rack', prix_nuit_ht: '900',
      date_debut: '2026-07-01',
    })
  })

  it('plan sans prix : refusé côté écran, aucun appel réseau', async () => {
    hospitalityApi.listTypesChambre.mockResolvedValue({ data: [TYPE] })
    render(<ReferentielChambres />)

    await waitFor(() => expect(
      screen.getByRole('button', { name: 'Créer le plan tarifaire' })).not.toBeDisabled())
    fireEvent.change(screen.getByLabelText(/^Type de chambre$/, { selector: '#pt-type' }),
      { target: { value: '1' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer le plan tarifaire' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/prix par nuit/i)
    expect(hospitalityApi.createPlanTarifaire).not.toHaveBeenCalled()
  })

  it('une fois peuplé, chambre et plan sont listés', async () => {
    hospitalityApi.listTypesChambre.mockResolvedValue({ data: [TYPE] })
    hospitalityApi.listChambres.mockResolvedValue({ data: [CHAMBRE] })
    hospitalityApi.listPlansTarifaires.mockResolvedValue({ data: [PLAN] })
    render(<ReferentielChambres />)

    expect(await screen.findByText(/101/)).toBeInTheDocument()
    expect(screen.getByText(/Rack \(tarif public\)/)).toBeInTheDocument()
    expect(screen.getByText(/900\.00/)).toBeInTheDocument()
  })
})
