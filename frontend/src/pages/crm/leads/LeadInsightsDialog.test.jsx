import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'

/* WR9 — fiche « Parcours » d'un lead : timeline multi-touch (FG204) +
   correspondance client existant (FG38). crmApi mocké. */

vi.mock('../../../api/crmApi', () => ({
  default: {
    getLeadPointsContact: vi.fn(() => Promise.resolve({
      data: {
        lead_id: 4,
        count: 2,
        cout_total: '150.00',
        first_touch: { canal: 'site_web', canal_libelle: 'Site web' },
        last_touch: { canal: 'appel', canal_libelle: 'Appel' },
        timeline: [
          {
            id: 11, canal: 'site_web', canal_libelle: 'Site web',
            source: 'formulaire', date_contact: '2026-06-20T09:00:00Z',
            detail: 'Demande de devis', cout: '100.00',
          },
          {
            id: 12, canal: 'appel', canal_libelle: 'Appel',
            source: '', date_contact: '2026-06-22T15:30:00Z',
            detail: '', cout: '50.00',
          },
        ],
      },
    })),
    getLeadClientMatch: vi.fn(() => Promise.resolve({
      data: [{
        id: 9, nom: 'Alaoui Karim', email: 'k@x.ma', telephone: '0611223344',
        nb_devis: 2, nb_chantiers: 1,
      }],
    })),
  },
}))

import crmApi from '../../../api/crmApi'
import LeadInsightsDialog from './LeadInsightsDialog'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const lead = { id: 4, nom: 'Alaoui' }

describe('LeadInsightsDialog (WR9 — FG204/FG38)', () => {
  it('affiche la timeline multi-touch et la correspondance client', async () => {
    render(<LeadInsightsDialog lead={lead} onClose={vi.fn()} />)
    expect(screen.getByText('Parcours du lead — Alaoui')).toBeInTheDocument()

    // FG38 — correspondance client (retour client).
    await waitFor(() =>
      expect(screen.getByTestId('lead-client-match')).toBeInTheDocument())
    expect(screen.getByText('Alaoui Karim')).toBeInTheDocument()
    expect(screen.getByText(/2 devis · 1 chantier/)).toBeInTheDocument()

    // FG204 — timeline ordonnée + résumé d'attribution.
    expect(screen.getByTestId('lead-touchpoints')).toBeInTheDocument()
    expect(screen.getByText(/Premier contact : Site web/)).toBeInTheDocument()
    expect(screen.getByText(/Dernier : Appel/)).toBeInTheDocument()
    expect(screen.getByText('Demande de devis')).toBeInTheDocument()

    expect(crmApi.getLeadPointsContact).toHaveBeenCalledWith(4)
    expect(crmApi.getLeadClientMatch).toHaveBeenCalledWith(4)
  })

  it('ferme via le bouton Fermer', async () => {
    const onClose = vi.fn()
    render(<LeadInsightsDialog lead={lead} onClose={onClose} />)
    await waitFor(() =>
      expect(screen.getByTestId('lead-touchpoints')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Fermer' }))
    expect(onClose).toHaveBeenCalled()
  })

  it('affiche une erreur lisible si le chargement échoue', async () => {
    crmApi.getLeadPointsContact.mockRejectedValueOnce(new Error('x'))
    render(<LeadInsightsDialog lead={lead} onClose={vi.fn()} />)
    await waitFor(() =>
      expect(screen.getByText(/Impossible de charger le parcours/)).toBeInTheDocument())
  })
})
