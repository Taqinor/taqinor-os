// VISCAD5 — SectionVisite montre désormais le VRAI module visites en contenu
// principal (crmApi.getLeadVisites), les champs manuels legacy restent
// fonctionnels mais secondaires, et AppointmentBooker (RDV général) passe
// sous une disclosure repliée (`<details>`, jamais supprimé).
import {
  describe, it, expect, vi, afterEach,
} from 'vitest'
import {
  render, screen, cleanup, fireEvent, waitFor,
} from '@testing-library/react'
import { initState } from '../draftCore'
import { formatDate } from '../../../../lib/format'
import SectionVisite from './SectionVisite'

vi.mock('../../../../pages/crm/leads/AppointmentBooker', () => ({
  default: () => <div data-testid="booker" />,
}))
vi.mock('../../relances/PlanifierVisiteModal', () => ({
  // Stub minimal — le comportement de la modale est couvert par son propre
  // test (`PlanifierVisiteModal.test.jsx`) ; ici on vérifie seulement
  // qu'elle s'OUVRE depuis le bon bouton.
  default: ({ open }) => (open ? <div data-testid="planifier-modal-ouverte" /> : null),
}))

// FIXED API CONTRACT (VISCAD, backend construit en parallèle sur EXACTEMENT
// cette forme) : GET /crm/leads/<id>/visites/ -> {visites: [...]}.
const VISITES = [
  {
    id: 1, statut: 'brouillon', statut_libelle: 'Planifiée',
    date_prevue: '2026-09-22', date_realisee: null,
    commercial_nom: 'Karim', notes: '', retour_disponible: false,
  },
  {
    id: 2, statut: 'validee', statut_libelle: 'Validée',
    date_prevue: '2026-09-10', date_realisee: '2026-09-10',
    commercial_nom: 'Meryem', notes: 'Toiture terrasse, orientation sud confirmée.',
    retour_disponible: true,
  },
]

vi.mock('../../../../api/crmApi', () => ({
  default: {
    getLeadVisites: vi.fn(),
  },
}))
import crmApi from '../../../../api/crmApi'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const base = {
  setField: vi.fn(),
  errors: {},
  mode: 'edit',
  refData: { leadId: 1489 },
}

describe('VISCAD5 SectionVisite', () => {
  it('liste les VRAIES visites (statut_libelle serveur, date, commercial, retour terrain)', async () => {
    crmApi.getLeadVisites.mockResolvedValue({ data: { visites: VISITES } })
    render(<SectionVisite state={initState({ lead: { id: 1489 }, mode: 'edit' })} {...base} />)
    await waitFor(() => expect(crmApi.getLeadVisites).toHaveBeenCalledWith(1489))
    expect(await screen.findByText('Planifiée')).toBeInTheDocument()
    expect(screen.getByText('Validée')).toBeInTheDocument()
    expect(screen.getByText(`Prévue le ${formatDate('2026-09-22')}`)).toBeInTheDocument()
    expect(screen.getByText(/Karim/)).toBeInTheDocument()
    expect(screen.getByText(/Toiture terrasse, orientation sud confirmée\./)).toBeInTheDocument()
  })

  it('aucune visite : message honnête, jamais une liste vide muette', async () => {
    crmApi.getLeadVisites.mockResolvedValue({ data: { visites: [] } })
    render(<SectionVisite state={initState({ lead: { id: 1489 }, mode: 'edit' })} {...base} />)
    expect(await screen.findByText('Aucune visite technique planifiée pour ce lead.')).toBeInTheDocument()
  })

  it('échec réseau : repli honnête, jamais un plantage de la section', async () => {
    crmApi.getLeadVisites.mockRejectedValue(new Error('boom'))
    render(<SectionVisite state={initState({ lead: { id: 1489 }, mode: 'edit' })} {...base} />)
    expect(await screen.findByText('Visites indisponibles pour le moment.')).toBeInTheDocument()
  })

  it('le bouton principal ouvre la modale de planification PARTAGÉE', async () => {
    crmApi.getLeadVisites.mockResolvedValue({ data: { visites: [] } })
    render(<SectionVisite state={initState({ lead: { id: 1489 }, mode: 'edit' })} {...base} />)
    await screen.findByText('Aucune visite technique planifiée pour ce lead.')
    expect(screen.queryByTestId('planifier-modal-ouverte')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /Planifier la visite technique/ }))
    expect(screen.getByTestId('planifier-modal-ouverte')).toBeInTheDocument()
  })

  it('AppointmentBooker (RDV général) est REPLIÉ derrière une disclosure, jamais supprimé', async () => {
    crmApi.getLeadVisites.mockResolvedValue({ data: { visites: [] } })
    render(<SectionVisite state={initState({ lead: { id: 1489 }, mode: 'edit' })} {...base} />)
    await screen.findByText('Aucune visite technique planifiée pour ce lead.')
    expect(screen.getByText('Autre rendez-vous (RDV général)')).toBeInTheDocument()
    // Toujours dans le DOM (jamais supprimé) — repliée par défaut (<details>
    // sans `open`, comme le patron `ContratsMaintenance.jsx` « Avancé »).
    expect(screen.getByTestId('booker')).toBeInTheDocument()
    const details = screen.getByText('Autre rendez-vous (RDV général)').closest('details')
    expect(details).not.toHaveAttribute('open')
  })

  it('les champs manuels legacy restent présents et fonctionnels', () => {
    const setField = vi.fn()
    render(
      <SectionVisite
        state={initState({ lead: { id: 1489, visite_notes: 'Toit accessible' }, mode: 'edit' })}
        {...base} setField={setField}
      />,
    )
    expect(document.getElementById('lf-visite-prevue')).toBeInTheDocument()
    expect(document.getElementById('lf-visite-notes').value).toBe('Toit accessible')
    fireEvent.change(document.getElementById('lf-visite-notes'), { target: { value: 'Accès confirmé' } })
    expect(setField).toHaveBeenCalledWith('visite_notes', 'Accès confirmé')
  })

  it('en CRÉATION (pas de leadId) : ni liste de visites, ni disclosure RDV, aucun appel réseau', () => {
    render(
      <SectionVisite
        state={initState({ mode: 'create' })}
        setField={vi.fn()} errors={{}} mode="create" refData={{}}
      />,
    )
    expect(crmApi.getLeadVisites).not.toHaveBeenCalled()
    expect(screen.queryByTestId('booker')).toBeNull()
    expect(document.getElementById('lf-visite-prevue')).toBeInTheDocument()
  })
})
