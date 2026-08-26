import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { documentContrat, exempleContrat } from '../../test/fixtures/contractSamples'

/* WIR282/XSAL6 — écran « Plans de commission » sous /parametres.

   PACT10 — les mocks ci-dessous DÉRIVENT du contrat partagé
   `apps/ventes/contract_samples/plan_commission.json` : il est lu à
   l'exécution, jamais recopié à la main. Un écran ne peut donc plus se tester
   contre sa propre hypothèse (incident AO du 03/08/2026). */

const CONTRAT = documentContrat('ventes', 'plan_commission')

// Objets de plan et payload de résolution : tels que le serveur les sert.
const PLAN_DEDIE = exempleContrat('ventes', 'plan_commission', 'exemple_objet_plan')
const PLAN_DEFAUT = exempleContrat(
  'ventes', 'plan_commission', 'exemple_objet_plan_defaut_societe')
const RESOLUTION = exempleContrat('ventes', 'plan_commission')
const RESOLUTION_SANS_PLAN = exempleContrat(
  'ventes', 'plan_commission', 'exemple_resoudre_sans_plan')

const api = vi.hoisted(() => ({
  getPlansCommission: vi.fn(),
  createPlanCommission: vi.fn(),
  updatePlanCommission: vi.fn(),
  deletePlanCommission: vi.fn(),
  resoudrePlanCommission: vi.fn(),
}))
vi.mock('../../api/ventesApi', () => ({ default: api }))

const core = vi.hoisted(() => ({ list: vi.fn() }))
vi.mock('../../api/coreApi', () => ({ default: { utilisateurs: { list: core.list } } }))

import PlansCommissionPage from './PlansCommissionPage'
import config from '../../features/parametres/module.config.jsx'

beforeEach(() => {
  api.getPlansCommission.mockResolvedValue({
    data: { count: 2, results: [PLAN_DEDIE, PLAN_DEFAUT] },
  })
  api.createPlanCommission.mockResolvedValue({ data: PLAN_DEDIE })
  api.updatePlanCommission.mockResolvedValue({
    data: { ...PLAN_DEDIE, actif: false },
  })
  api.deletePlanCommission.mockResolvedValue({ data: {} })
  api.resoudrePlanCommission.mockResolvedValue({ data: RESOLUTION })
  core.list.mockResolvedValue({ data: [{ id: 12, username: 'sami' }] })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('PlansCommissionPage — WIR282', () => {
  it('le contrat partagé porte bien les exemples dont ce test dérive', () => {
    expect(CONTRAT.endpoint)
      .toBe('GET /api/django/ventes/plans-commission/resoudre/')
    expect(RESOLUTION).toHaveProperty('source')
    expect(RESOLUTION).toHaveProperty('plan')
    // GARDE MARGE : le contrat ne sert AUCUN montant de marge / prix d'achat.
    for (const objet of [PLAN_DEDIE, PLAN_DEFAUT]) {
      for (const interdit of ['prix_achat', 'marge', 'cout_achat']) {
        expect(objet).not.toHaveProperty(interdit)
      }
    }
  })

  it('est routé sous /parametres et gaté responsable/admin', () => {
    const route = config.routes.find((r) => r.path === '/parametres/plans-commission')
    expect(route).toBeTruthy()
    expect(route.roles).toEqual(['responsable', 'admin'])
    const nav = config.nav.items.find((i) => i.to === '/parametres/plans-commission')
    expect(nav).toBeTruthy()
    expect(nav.roles).toEqual(['responsable', 'admin'])
  })

  it('liste les plans : le plan sans commercial est le défaut société', async () => {
    render(<PlansCommissionPage />)
    await waitFor(() => expect(api.getPlansCommission).toHaveBeenCalled())
    const table = within(await screen.findByTestId('plans-commission-table'))
    expect(table.getAllByTestId('plan-commission-row')).toHaveLength(2)
    expect(table.getByText('sami')).toBeInTheDocument()
    expect(table.getByText('Défaut société')).toBeInTheDocument()
    // Barème rendu selon la base servie par le contrat.
    expect(table.getByText('3.50 %')).toBeInTheDocument()
    expect(table.getByText('250.00 MAD/kWc')).toBeInTheDocument()
  })

  it('crée un plan avec ses paliers (nombres tapés envoyés tels quels)', async () => {
    const user = userEvent.setup()
    render(<PlansCommissionPage />)
    await waitFor(() => expect(core.list).toHaveBeenCalled())

    await user.selectOptions(screen.getByLabelText('Commercial'), '12')
    await user.type(screen.getByLabelText('Taux (%)'), '3.5')

    await user.type(screen.getByLabelText('Seuil d’atteinte (%)'), '100')
    await user.type(screen.getByLabelText('Taux du palier (%)'), '5')
    await user.click(screen.getByRole('button', { name: 'Ajouter le palier' }))
    expect(await screen.findByTestId('plan-paliers'))
      .toHaveTextContent('À partir de 100 % → 5 %')

    await user.click(screen.getByRole('button', { name: 'Créer le plan' }))
    await waitFor(() => expect(api.createPlanCommission).toHaveBeenCalledWith({
      owner: 12,
      base: 'ca_devis_signe',
      taux_pct: '3.5',
      montant_par_kwc: null,
      paliers: [{ seuil_atteinte_pct: 100, taux: 5 }],
    }))
  })

  it('bascule sur MAD/kWc quand la base est « par kWc »', async () => {
    const user = userEvent.setup()
    render(<PlansCommissionPage />)
    await waitFor(() => expect(api.getPlansCommission).toHaveBeenCalled())

    await user.selectOptions(screen.getByLabelText('Base de calcul'), 'par_kwc')
    expect(screen.queryByLabelText('Taux (%)')).toBeNull()
    await user.type(screen.getByLabelText('MAD par kWc'), '250')
    await user.click(screen.getByRole('button', { name: 'Créer le plan' }))

    await waitFor(() => expect(api.createPlanCommission).toHaveBeenCalledWith(
      expect.objectContaining({
        base: 'par_kwc', montant_par_kwc: '250', taux_pct: null,
      })))
  })

  it('le badge « plan appliqué » vient de resoudre/, jamais d’un calcul local', async () => {
    const user = userEvent.setup()
    render(<PlansCommissionPage />)
    await waitFor(() => expect(core.list).toHaveBeenCalled())

    await user.selectOptions(screen.getByLabelText('Plan appliqué à'), '12')
    await user.click(screen.getByRole('button', { name: /Voir le plan appliqué/ }))

    await waitFor(() => expect(api.resoudrePlanCommission).toHaveBeenCalledWith('12'))
    const badge = await screen.findByTestId('plan-applique')
    expect(badge).toHaveTextContent('Plan dédié')
    expect(badge).toHaveTextContent('3.50 %')
  })

  it('sans plan, le badge dit « mode société » (pas de faux plan inventé)', async () => {
    api.resoudrePlanCommission.mockResolvedValue({ data: RESOLUTION_SANS_PLAN })
    const user = userEvent.setup()
    render(<PlansCommissionPage />)
    await waitFor(() => expect(core.list).toHaveBeenCalled())

    await user.click(screen.getByRole('button', { name: /Voir le plan appliqué/ }))
    const badge = await screen.findByTestId('plan-applique')
    expect(badge).toHaveTextContent('Aucun plan — mode société')
    expect(badge).not.toHaveTextContent('%')
  })

  it('désactive un plan (non-régression : le calcul retombe côté serveur)', async () => {
    const user = userEvent.setup()
    render(<PlansCommissionPage />)
    const table = within(await screen.findByTestId('plans-commission-table'))
    await user.click(table.getAllByRole('button', { name: 'Désactiver' })[0])
    await waitFor(() => expect(api.updatePlanCommission)
      .toHaveBeenCalledWith(PLAN_DEDIE.id, { actif: false }))
  })

  it('un 403 est dit en FRANÇAIS, jamais en JSON brut', async () => {
    api.getPlansCommission.mockRejectedValue({
      response: { status: 403, data: { detail: 'Forbidden' } },
    })
    render(<PlansCommissionPage />)
    expect(await screen.findByTestId('plans-commission-erreur'))
      .toHaveTextContent(/Accès refusé/)
  })
})
