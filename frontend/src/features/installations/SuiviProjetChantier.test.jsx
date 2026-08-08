import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* PACT59 — Suivi projet du chantier : jalons, modèles, comptes-rendus
   (FG293/FG296/FG298). */

function mockMatchMedia() {
  window.matchMedia = (query) => ({
    matches: false, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })
}
beforeAll(() => { if (typeof window.matchMedia !== 'function') mockMatchMedia() })

const inst = vi.hoisted(() => ({
  getInstallations: vi.fn(() => Promise.resolve({ data: { count: 1, results: [
    { id: 9, reference: 'CH-009' },
  ] } })),
  getJalonsProjet: vi.fn(() => Promise.resolve({ data: { count: 1, results: [
    { id: 14, phase: 'etude', phase_display: 'Étude', libelle: 'Étude technique', date_cible: '2026-08-10', date_reelle: null, atteint: false },
  ] } })),
  createJalonProjet: vi.fn(() => Promise.resolve({ data: {} })),
  updateJalonProjet: vi.fn(() => Promise.resolve({ data: {} })),
  deleteJalonProjet: vi.fn(() => Promise.resolve({ data: {} })),
  getModelesProjet: vi.fn(() => Promise.resolve({ data: { count: 1, results: [
    { id: 2, nom: 'Résidentiel standard', type_installation_display: 'Résidentiel', jalons: [{ id: 1 }, { id: 2 }], bom_lignes: [{ id: 1 }] },
  ] } })),
  createModeleProjet: vi.fn(() => Promise.resolve({ data: {} })),
  instancierModeleProjet: vi.fn(() => Promise.resolve({ data: { jalons_crees: 5, bom_lignes_ajoutees: 8 } })),
  getReunionsChantier: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
  createReunionChantier: vi.fn(() => Promise.resolve({ data: {} })),
}))
vi.mock('../../api/installationsApi', () => ({ default: inst }))

import SuiviProjetChantier from './SuiviProjetChantier'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('SuiviProjetChantier (PACT59)', () => {
  it('affiche les jalons du chantier sélectionné', async () => {
    render(<SuiviProjetChantier />)
    expect(await screen.findByTestId('jalon-14')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Jalons' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Modèles de projet' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Réunions de chantier' })).toBeInTheDocument()
  })

  it('marque un jalon atteint', async () => {
    const user = userEvent.setup()
    render(<SuiviProjetChantier />)
    await screen.findByTestId('jalon-14')
    await user.click(screen.getByRole('button', { name: 'Marquer atteint' }))
    await waitFor(() => expect(inst.updateJalonProjet).toHaveBeenCalledWith(
      14, expect.objectContaining({ atteint: true })))
  })

  it('crée un nouveau jalon', async () => {
    const user = userEvent.setup()
    render(<SuiviProjetChantier />)
    await screen.findByTestId('jalon-14')
    await user.click(screen.getByRole('button', { name: /Nouveau jalon/ }))
    await user.type(screen.getByLabelText('Libellé'), 'Pose panneaux')
    await user.click(screen.getByRole('button', { name: 'Créer' }))
    await waitFor(() => expect(inst.createJalonProjet).toHaveBeenCalledWith(
      expect.objectContaining({ installation: 9, libelle: 'Pose panneaux' })))
  })

  it('instancie un modèle de projet sur le chantier (jalons et nomenclature pré-créés)', async () => {
    const user = userEvent.setup()
    render(<SuiviProjetChantier />)
    await screen.findByTestId('jalon-14')
    await user.click(screen.getByRole('tab', { name: 'Modèles de projet' }))
    expect(await screen.findByTestId('modele-projet-2')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Instancier sur ce chantier' }))
    await waitFor(() => expect(inst.instancierModeleProjet).toHaveBeenCalledWith(2, 9))
    expect(await screen.findByTestId('resultat-instanciation')).toHaveTextContent('5 jalon')
  })

  it('rédige un compte-rendu de réunion de chantier', async () => {
    const user = userEvent.setup()
    render(<SuiviProjetChantier />)
    await screen.findByTestId('jalon-14')
    await user.click(screen.getByRole('tab', { name: 'Réunions de chantier' }))
    await user.click(screen.getByRole('button', { name: /Nouveau compte-rendu/ }))
    await user.type(screen.getByLabelText('Titre'), 'Point hebdo semaine 32')
    await user.type(screen.getByLabelText('Date de réunion'), '2026-08-06')
    await user.click(screen.getByRole('button', { name: 'Créer' }))
    await waitFor(() => expect(inst.createReunionChantier).toHaveBeenCalledWith(
      expect.objectContaining({ installation: 9, titre: 'Point hebdo semaine 32', date_reunion: '2026-08-06' })))
  })
})
