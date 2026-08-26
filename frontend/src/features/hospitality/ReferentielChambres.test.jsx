import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* WIR211 — l'hôtellerie était INERTE : ni type de chambre, ni chambre, ni plan
   tarifaire n'étaient créables (les wrappers existaient sans écran), donc plan
   des chambres vide, folios vides et RevPAR à 0. Couvre la chaîne de mise en
   route depuis une base VIDE : type → chambre → plan, plus l'accès depuis le
   plan des chambres. */

const api = vi.hoisted(() => ({
  listTypesChambre: vi.fn(),
  createTypeChambre: vi.fn(),
  listChambres: vi.fn(),
  createChambre: vi.fn(),
  listPlansTarifaires: vi.fn(),
  createPlanTarifaire: vi.fn(),
}))
vi.mock('../../api/hospitalityApi', () => ({ default: api }))

import ReferentielChambres from './ReferentielChambres'
import PlanChambres from './PlanChambres'
import config from './module.config.jsx'

const TYPE = { id: 4, libelle: 'Suite', capacite_max: 3, description: '' }
const CHAMBRE = {
  id: 12, type_chambre: 4, type_chambre_libelle: 'Suite', numero: '201',
  nom: 'Atlas', etage: '2', statut: 'libre', statut_display: 'Libre',
}
const PLAN = {
  id: 8, type_chambre: 4, canal: 'rack', canal_display: 'Rack (tarif public)',
  date_debut: '2026-09-01', date_fin: '2026-09-30', prix_nuit_ht: '1450.00',
  min_nuits: null,
}

function renderEcran(element) {
  return render(<MemoryRouter>{element}</MemoryRouter>)
}

beforeEach(() => {
  api.listTypesChambre.mockResolvedValue({ data: [] })
  api.listChambres.mockResolvedValue({ data: [] })
  api.listPlansTarifaires.mockResolvedValue({ data: [] })
  api.createTypeChambre.mockResolvedValue({ data: TYPE })
  api.createChambre.mockResolvedValue({ data: CHAMBRE })
  api.createPlanTarifaire.mockResolvedValue({ data: PLAN })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('ReferentielChambres — WIR211', () => {
  it('est routé ET présent dans la nav du module', () => {
    const route = config.routes.find((r) => r.path === '/hospitality/referentiel')
    expect(route).toBeTruthy()
    expect(route.roles).toEqual(['normal', 'responsable', 'admin'])
    const nav = config.nav.items.find((i) => i.to === '/hospitality/referentiel')
    expect(nav).toBeTruthy()
    expect(nav.icon).toBeTruthy()
  })

  it('crée type → chambre → plan tarifaire depuis une base VIDE', async () => {
    const user = userEvent.setup()
    renderEcran(<ReferentielChambres />)
    await waitFor(() => expect(api.listTypesChambre).toHaveBeenCalled())

    // 1) Type de chambre — le seul point de départ possible.
    await user.type(await screen.findByLabelText('Libellé'), 'Suite')
    const capacite = screen.getByLabelText('Capacité max')
    await user.clear(capacite)
    await user.type(capacite, '3')
    await user.click(screen.getByRole('button', { name: 'Ajouter le type' }))
    await waitFor(() => expect(api.createTypeChambre).toHaveBeenCalledWith(
      { libelle: 'Suite', capacite_max: '3', description: '' }))

    // 2) Chambre — le type fraîchement créé est proposé.
    const selectType = await screen.findByLabelText('Type', { selector: '#chambre-type' })
    await user.selectOptions(selectType, '4')
    await user.type(screen.getByLabelText('Numéro'), '201')
    await user.type(screen.getByLabelText('Nom (facultatif)'), 'Atlas')
    await user.type(screen.getByLabelText('Étage'), '2')
    await user.click(screen.getByRole('button', { name: 'Ajouter la chambre' }))
    await waitFor(() => expect(api.createChambre).toHaveBeenCalledWith(
      { type_chambre: 4, numero: '201', nom: 'Atlas', etage: '2', vue: '' }))
    // La chambre créée est listée : elle existe donc pour le plan/calendrier.
    expect(within(await screen.findByTestId('liste-chambres')).getByText(/201/))
      .toBeInTheDocument()

    // 3) Plan tarifaire — sans lui, aucune réservation ne porte de prix/nuit.
    await user.selectOptions(
      screen.getByLabelText('Type', { selector: '#plan-type' }), '4')
    await user.selectOptions(screen.getByLabelText('Canal'), 'rack')
    await user.type(screen.getByLabelText('Du'), '2026-09-01')
    await user.type(screen.getByLabelText('Au'), '2026-09-30')
    await user.type(screen.getByLabelText('Prix/nuit HT'), '1450')
    await user.click(screen.getByRole('button', { name: 'Ajouter le plan' }))
    await waitFor(() => expect(api.createPlanTarifaire).toHaveBeenCalledWith({
      type_chambre: 4, canal: 'rack', date_debut: '2026-09-01',
      date_fin: '2026-09-30', prix_nuit_ht: '1450', min_nuits: null,
    }))
  })

  it('les prix tapés partent TELS QUELS (step="any", formulaires noValidate)', async () => {
    const { container } = renderEcran(<ReferentielChambres />)
    await waitFor(() => expect(api.listPlansTarifaires).toHaveBeenCalled())
    const nombres = container.querySelectorAll('input[type="number"]')
    expect(nombres.length).toBeGreaterThan(0)
    for (const input of nombres) expect(input.getAttribute('step')).toBe('any')
    for (const form of container.querySelectorAll('form')) {
      expect(form).toHaveAttribute('novalidate')
    }
  })
})

describe('PlanChambres — WIR211 accès au référentiel', () => {
  it('propose « Ouvrir le référentiel » quand aucune chambre n’existe', async () => {
    renderEcran(<PlanChambres />)
    const lien = await screen.findByRole('link', { name: /Ouvrir le référentiel/ })
    expect(lien).toHaveAttribute('href', '/hospitality/referentiel')
  })

  it('garde un accès permanent au référentiel quand des chambres existent', async () => {
    api.listChambres.mockResolvedValue({ data: [CHAMBRE] })
    renderEcran(<PlanChambres />)
    const lien = await screen.findByRole('link', { name: /Référentiel/ })
    expect(lien).toHaveAttribute('href', '/hospitality/referentiel')
  })
})
