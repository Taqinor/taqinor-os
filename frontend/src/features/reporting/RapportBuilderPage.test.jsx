import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* PACT146 — Générateur de rapports croisés (NTEXT10).

   Les charges utiles reprennent les formes RÉELLES du serveur :
   `RapportDefinitionSerializer` (id/titre/dataset/spec/pivot_spec/partage/
   partage_label/owner_username/created_at/updated_at), le catalogue de
   `core.data_explorer.list_datasets()` ({name,label,fields}) et la réponse de
   l'action `executer` — `{rows}` à plat, `{rows, pivot}` quand la définition
   porte un `pivot_spec`, le pivot ayant exactement la forme rendue par
   `core.pivot.build_pivot` (row_keys/col_keys/cells/row_totals/col_totals/
   grand_total/agg/measure). */

vi.mock('../../api/reportingApi', () => ({
  default: {
    listRapportDefinitions: vi.fn(),
    createRapportDefinition: vi.fn(),
    deleteRapportDefinition: vi.fn(),
    executerRapportDefinition: vi.fn(),
  },
}))
vi.mock('../../api/coreApi', () => ({
  default: { datasetsExplorateur: { list: vi.fn() } },
}))

import reportingApi from '../../api/reportingApi'
import coreApi from '../../api/coreApi'
import RapportBuilderPage from './RapportBuilderPage'

const DATASETS = [
  {
    name: 'sav_tickets',
    label: 'Tickets SAV',
    fields: ['statut', 'technicien__username', 'cout_interne', 'date_creation'],
  },
]

const DEFINITIONS = [
  {
    id: 3, titre: 'Tickets par technicien', dataset: 'sav_tickets',
    spec: { select: ['statut', 'technicien__username'] },
    pivot_spec: {
      rows: ['technicien__username'], columns: ['statut'],
      measure: 'cout_interne', agg: 'sum',
    },
    partage: 'societe', partage_label: 'Société', owner_username: 'reda',
    created_at: '2026-08-01T09:00:00Z', updated_at: '2026-08-01T09:00:00Z',
  },
  {
    id: 4, titre: 'Journal des tickets', dataset: 'sav_tickets',
    spec: { select: ['statut', 'date_creation'] }, pivot_spec: {},
    partage: 'prive', partage_label: 'Privé', owner_username: 'reda',
    created_at: '2026-08-02T09:00:00Z', updated_at: '2026-08-02T09:00:00Z',
  },
]

const RESULTAT_PLAT = {
  rows: [
    { statut: 'ouvert', date_creation: '2026-07-02' },
    { statut: 'clos', date_creation: '2026-07-05' },
  ],
}

const RESULTAT_CROISE = {
  rows: [
    { technicien__username: 'sami', statut: 'ouvert', cout_interne: 300 },
    { technicien__username: 'sami', statut: 'clos', cout_interne: 200 },
    { technicien__username: 'youssef', statut: 'ouvert', cout_interne: 150 },
  ],
  pivot: {
    row_keys: [['sami'], ['youssef']],
    col_keys: [['clos'], ['ouvert']],
    cells: {
      sami: { clos: 200, ouvert: 300 },
      youssef: { clos: 0, ouvert: 150 },
    },
    row_totals: { sami: 500, youssef: 150 },
    col_totals: { clos: 200, ouvert: 450 },
    grand_total: 650,
    agg: 'sum',
    measure: 'cout_interne',
  },
}

beforeEach(() => {
  vi.clearAllMocks()
  reportingApi.listRapportDefinitions.mockResolvedValue({ data: DEFINITIONS })
  reportingApi.createRapportDefinition.mockResolvedValue({ data: { id: 5 } })
  reportingApi.deleteRapportDefinition.mockResolvedValue({ data: {} })
  coreApi.datasetsExplorateur.list.mockResolvedValue({ data: DATASETS })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('RapportBuilderPage (PACT146)', () => {
  it('crée une définition depuis les champs RÉELLEMENT exposés par le dataset', async () => {
    const user = userEvent.setup()
    render(<RapportBuilderPage />)
    await screen.findByTestId('rapport-builder-creation')

    await user.type(screen.getByLabelText('Titre'), 'Coût par technicien')
    await user.selectOptions(screen.getByLabelText('Dataset'), 'sav_tickets')
    // Les champs proposés viennent de la liste blanche du dataset.
    await user.click(screen.getByLabelText('technicien__username'))
    await user.click(screen.getByLabelText('cout_interne'))
    await user.selectOptions(screen.getByLabelText('Lignes'), 'technicien__username')
    await user.selectOptions(screen.getByLabelText('Colonnes'), 'statut')
    await user.selectOptions(screen.getByLabelText('Mesure'), 'cout_interne')
    await user.click(screen.getByRole('button', { name: 'Enregistrer la définition' }))

    expect(reportingApi.createRapportDefinition).toHaveBeenCalledWith({
      titre: 'Coût par technicien',
      dataset: 'sav_tickets',
      spec: { select: ['technicien__username', 'cout_interne'] },
      pivot_spec: {
        rows: ['technicien__username'], columns: ['statut'],
        measure: 'cout_interne', agg: 'sum',
      },
      partage: 'prive',
    })
  })

  it('exécute une définition PLATE et affiche ses lignes', async () => {
    const user = userEvent.setup()
    reportingApi.executerRapportDefinition.mockResolvedValue({ data: RESULTAT_PLAT })
    render(<RapportBuilderPage />)

    const ligne = await screen.findByTestId('rapport-definition-4')
    expect(within(ligne).getByText('À plat')).toBeInTheDocument()
    await user.click(within(ligne).getByRole('button', { name: 'Exécuter' }))

    const resultat = await screen.findByTestId('rapport-builder-resultat')
    expect(reportingApi.executerRapportDefinition).toHaveBeenCalledWith(4)
    expect(within(resultat).getByTestId('rapport-builder-plat')).toBeInTheDocument()
    expect(within(resultat).getByText('ouvert')).toBeInTheDocument()
    expect(within(resultat).getByText('2026-07-05')).toBeInTheDocument()
    expect(within(resultat).getByText('2 ligne(s) servie(s) par le serveur.'))
      .toBeInTheDocument()
  })

  it('exécute une définition CROISÉE et affiche le tableau croisé du serveur (totaux compris)', async () => {
    const user = userEvent.setup()
    reportingApi.executerRapportDefinition.mockResolvedValue({ data: RESULTAT_CROISE })
    render(<RapportBuilderPage />)

    const ligne = await screen.findByTestId('rapport-definition-3')
    expect(within(ligne).getByText('Croisé')).toBeInTheDocument()
    await user.click(within(ligne).getByRole('button', { name: 'Exécuter' }))

    const croise = await screen.findByTestId('rapport-builder-croise')
    expect(reportingApi.executerRapportDefinition).toHaveBeenCalledWith(3)
    // En-têtes de colonnes = axes servis par le serveur.
    const entetes = within(croise).getAllByRole('columnheader').map((th) => th.textContent)
    expect(entetes).toEqual(['technicien__username', 'clos', 'ouvert', 'Total'])
    // Cellules et totaux affichés TELS QUE calculés par le serveur.
    const rangeeSami = within(croise).getByText('sami').closest('tr')
    expect(within(rangeeSami).getAllByRole('cell').map((td) => td.textContent))
      .toEqual(['sami', '200', '300', '500'])
    expect(within(croise).getByText('650')).toBeInTheDocument()
  })

  it('supprime une définition', async () => {
    const user = userEvent.setup()
    render(<RapportBuilderPage />)

    const ligne = await screen.findByTestId('rapport-definition-4')
    await user.click(within(ligne).getByRole('button', { name: 'Supprimer' }))
    expect(reportingApi.deleteRapportDefinition).toHaveBeenCalledWith(4)
  })
})
