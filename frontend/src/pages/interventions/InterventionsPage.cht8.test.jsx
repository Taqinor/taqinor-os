// CHT8 — Page interventions : deep-link ?id= ouvre directement la fiche de
// l'intervention ciblée (même patron ?id= que InstallationsPage.jsx —
// prérequis des liens de notification CHT9, règle WIR176 : jamais un
// paramètre qu'aucune page ne lit).
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import InterventionsPage from './InterventionsPage'
import { ConfirmProvider } from '../../providers/ConfirmProvider'

const { toastWithUndoSpy } = vi.hoisted(() => ({ toastWithUndoSpy: vi.fn() }))
vi.mock('../../lib/toast', async (importOriginal) => ({
  ...(await importOriginal()),
  toastWithUndo: (...a) => toastWithUndoSpy(...a),
}))

vi.mock('../../api/installationsApi', () => ({
  default: {
    getInterventions: vi.fn(),
    getIntervention: vi.fn(),
    updateIntervention: vi.fn(),
    getInterventionHistorique: vi.fn(),
    noterIntervention: vi.fn(),
  },
}))
vi.mock('../../api/crmApi', () => ({
  default: {
    getAssignableUsers: vi.fn(),
  },
}))

import installationsApi from '../../api/installationsApi'
import crmApi from '../../api/crmApi'

const ITEMS = [
  {
    id: 101,
    installation_reference: 'CH-101',
    client_nom: 'Client Cent Un',
    type_intervention: 'pose',
    statut: 'a_preparer',
  },
  {
    id: 202,
    installation_reference: 'CH-202',
    client_nom: 'Client Deux Cent Deux',
    type_intervention: 'controle',
    statut: 'prete',
  },
]

beforeEach(() => {
  vi.clearAllMocks()
  // Vue liste (déterministe) plutôt que le kanban @dnd-kit par défaut — sans
  // incidence sur le comportement du lien profond testé ici.
  try { localStorage.setItem('taqinor.interventions.view', 'liste') } catch { /* indisponible */ }
  installationsApi.getInterventions.mockResolvedValue({ data: ITEMS })
  installationsApi.getInterventionHistorique.mockResolvedValue({ data: [] })
  crmApi.getAssignableUsers.mockResolvedValue({ data: [] })
})

describe('InterventionsPage — CHT8 deep-link ?id=', () => {
  it('?id=<pk> ouvre automatiquement la fiche de la bonne intervention', async () => {
    render(
      <MemoryRouter initialEntries={['/interventions?id=202']}>
        <InterventionsPage />
      </MemoryRouter>,
    )

    // La liste charge d'abord (deux interventions).
    // Le nom du client apparaît sur la carte kanban ET dans la fiche ouverte
  // par le deep-link : getAllByText, jamais getByText (strict-mode RTL).
  await waitFor(() => expect(
    screen.getAllByText('Client Deux Cent Deux').length).toBeGreaterThanOrEqual(1))

    // La fiche (Sheet) s'ouvre SANS clic, sur l'intervention #202 désignée par
    // ?id= — jamais sur #101 (première de la liste).
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText(/CH-202/)).toBeInTheDocument()
    expect(installationsApi.getInterventionHistorique).toHaveBeenCalledWith(202)
  })

  it("sans ?id=, aucune fiche ne s'ouvre automatiquement", async () => {
    render(
      <MemoryRouter initialEntries={['/interventions']}>
        <InterventionsPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('Client Cent Un')).toBeInTheDocument())
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(installationsApi.getInterventionHistorique).not.toHaveBeenCalled()
  })

  it('?id= introuvable affiche un EmptyState inline (jamais une page blanche)', async () => {
    render(
      <MemoryRouter initialEntries={['/interventions?id=999']}>
        <InterventionsPage />
      </MemoryRouter>,
    )

    expect(await screen.findByText('Intervention introuvable')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(installationsApi.getInterventionHistorique).not.toHaveBeenCalled()
  })
})

// ACHT62 + ACHT65 — faux serveur DRF PAGINÉ (50), lien profond hors liste, filtre ?installation=.
const PAGE_SIZE = 50
const TOUTES_ACHT62 = Array.from({ length: 56 }, (_, i) => ({
  id: i + 1,
  installation_reference: `CH-${String(i + 1).padStart(3, '0')}`,
  client_nom: `Client ${i + 1}`,
  type_intervention: 'pose',
  statut: 'a_preparer',
}))


function serveurPagine() {
  installationsApi.getInterventions.mockImplementation(({ page = 1 } = {}) => {
    const debut = (page - 1) * PAGE_SIZE
    return Promise.resolve({
      data: {
        count: TOUTES_ACHT62.length,
        next: debut + PAGE_SIZE < TOUTES_ACHT62.length ? `?page=${page + 1}` : null,
        results: TOUTES_ACHT62.slice(debut, debut + PAGE_SIZE),
      },
    })
  })
}

describe('InterventionsPage — ACHT62', () => {
  it('affiche les 56 interventions, pas seulement la page 1', async () => {
    serveurPagine()
    render(<MemoryRouter initialEntries={['/interventions']}><InterventionsPage /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('Client 56')).toBeInTheDocument())
    expect(screen.getByText('Client 1')).toBeInTheDocument()
  })

  it('un lien profond absent de la liste est résolu par getIntervention(id)', async () => {
    installationsApi.getIntervention.mockResolvedValue({
      data: { id: 999, installation_reference: 'CH-999', client_nom: 'Client Hors Liste', type_intervention: 'pose', statut: 'a_preparer' },
    })
    render(<MemoryRouter initialEntries={['/interventions?id=999']}><InterventionsPage /></MemoryRouter>)
    await waitFor(() => expect(installationsApi.getIntervention).toHaveBeenCalledWith('999'))
    await waitFor(() => expect(screen.getAllByText(/Client Hors Liste/).length).toBeGreaterThan(0))
    expect(screen.queryByText('Intervention introuvable')).not.toBeInTheDocument()
  })

  it('getIntervention en 404 : « introuvable »', async () => {
    installationsApi.getIntervention.mockRejectedValue({ response: { status: 404 } })
    render(<MemoryRouter initialEntries={['/interventions?id=999']}><InterventionsPage /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('Intervention introuvable')).toBeInTheDocument())
  })
})

// ACHT65 — `?installation=<id>` : filtre serveur existant `installation` (faux serveur filtrant).
describe('InterventionsPage — ACHT65 ?installation=', () => {
  it('ne liste que les interventions du chantier demandé', async () => {
    const parChantier = [
      { id: 1, installation: 10, installation_reference: 'CH-010', client_nom: 'Client Dix', type_intervention: 'pose', statut: 'a_preparer' },
      { id: 2, installation: 20, installation_reference: 'CH-020', client_nom: 'Client Vingt', type_intervention: 'pose', statut: 'a_preparer' },
    ]
    installationsApi.getInterventions.mockImplementation(({ installation } = {}) => {
      const rows = parChantier.filter((x) => !installation || String(x.installation) === String(installation))
      return Promise.resolve({ data: { count: rows.length, next: null, results: rows } })
    })
    render(<MemoryRouter initialEntries={['/interventions?installation=10']}><InterventionsPage /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('Client Dix')).toBeInTheDocument())
    expect(screen.queryByText('Client Vingt')).toBeNull()
    expect(installationsApi.getInterventions).toHaveBeenCalledWith(expect.objectContaining({ installation: '10' }))
  })
})

// AERR29 — kanban : Validée / Terminée exigent une confirmation nommée (le ticket
// SAV lié est résolu, sans retour) ; les autres statuts : appliqué + « Annuler ».
describe('InterventionsPage — AERR29 statut depuis le kanban', () => {
  const INT = { id: 42, reference: 'INT-0042', installation_reference: 'CH-042',
    client_nom: 'Client Quarante', type_intervention: 'pose', statut: 'sur_site' }
  const rendre = () => render(
    <MemoryRouter initialEntries={['/interventions']}>
      <ConfirmProvider><InterventionsPage /></ConfirmProvider>
    </MemoryRouter>,
  )

  it('dépôt vers Validée : confirmation nommée, Annuler ⇒ aucun PATCH', async () => {
    localStorage.setItem('taqinor.interventions.view', 'kanban')
    installationsApi.getInterventions.mockResolvedValue({ data: [INT] })
    installationsApi.updateIntervention.mockResolvedValue({ data: { ...INT, statut: 'validee' } })
    rendre()
    const select = (await screen.findAllByLabelText('Changer le statut de Client Quarante'))[0]
    fireEvent.change(select, { target: { value: 'validee' } })
    const dialog = await screen.findByRole('alertdialog')
    expect(dialog).toHaveTextContent('INT-0042')
    expect(dialog).toHaveTextContent('Validée')
    expect(dialog).toHaveTextContent('le ticket SAV lié sera résolu')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
    expect(installationsApi.updateIntervention).not.toHaveBeenCalled()

    fireEvent.change(select, { target: { value: 'validee' } })
    const dialog2 = await screen.findByRole('alertdialog')
    fireEvent.click(within(dialog2).getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(installationsApi.updateIntervention).toHaveBeenCalledWith(
      42, { statut: 'validee' }, { suppressErrorToast: true }))
    expect(toastWithUndoSpy).not.toHaveBeenCalled()
  })

  it('Prête → En route : PATCH immédiat puis « Annuler » qui repasse Prête', async () => {
    localStorage.setItem('taqinor.interventions.view', 'kanban')
    installationsApi.getInterventions.mockResolvedValue({ data: [{ ...INT, statut: 'prete' }] })
    installationsApi.updateIntervention.mockResolvedValue({ data: {} })
    rendre()
    const select = (await screen.findAllByLabelText('Changer le statut de Client Quarante'))[0]
    fireEvent.change(select, { target: { value: 'en_route' } })
    await waitFor(() => expect(installationsApi.updateIntervention).toHaveBeenCalledWith(
      42, { statut: 'en_route' }, { suppressErrorToast: true }))
    expect(screen.queryByRole('alertdialog')).toBeNull()
    await waitFor(() => expect(toastWithUndoSpy).toHaveBeenCalled())
    const opts = toastWithUndoSpy.mock.calls[0][0]
    expect(opts.message).toContain('INT-0042')
    expect(opts.onCommit).toBeUndefined()
    await opts.onUndo()
    expect(installationsApi.updateIntervention).toHaveBeenLastCalledWith(42, { statut: 'prete' })
  })
})

// AERR34 — une relecture de fond rejetée garde la liste, avec un avis + « Réessayer ».
describe('InterventionsPage — AERR34 relecture rejetée', () => {
  it('liste chargée puis relecture rejetée : lignes visibles + Réessayer', async () => {
    localStorage.setItem('taqinor.interventions.view', 'kanban')
    const trois = ITEMS.concat({ id: 303, installation_reference: 'CH-303', client_nom: 'Client Trois',
      type_intervention: 'pose', statut: 'a_preparer' })
    installationsApi.getInterventions.mockResolvedValueOnce({ data: trois })
      .mockRejectedValue(new Error('réseau'))
    installationsApi.updateIntervention.mockResolvedValue({ data: {} })
    render(<MemoryRouter initialEntries={['/interventions']}><ConfirmProvider><InterventionsPage /></ConfirmProvider></MemoryRouter>)
    const select = (await screen.findAllByLabelText('Changer le statut de Client Trois'))[0]
    fireEvent.change(select, { target: { value: 'prete' } })
    const avis = (await screen.findByText(/Liste pas à jour/)).closest('[role="alert"]')
    expect(avis).not.toBeNull()
    expect(within(avis).getByRole('button', { name: 'Réessayer' })).toBeInTheDocument()
    expect(screen.getAllByText('Client Trois').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Client Cent Un').length).toBeGreaterThan(0)
    expect(screen.queryByText('Impossible de charger les interventions')).toBeNull()
  })
})
