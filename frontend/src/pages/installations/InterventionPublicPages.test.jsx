import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

/* WIR264 — les deux jetons publics d'une intervention (XFSM7 « en route » et
   ZFSM2 « compte-rendu signé ») étaient exposés sans page, sans bouton, sans
   envoi. Couvre :
   (1) /intervention/:token rend le suivi hors session ;
   (2) /intervention-rapport/:token rend le compte-rendu + son PDF, sans
       AUCUN coût ni marge ;
   (3) un jeton invalide donne un message FRANÇAIS, jamais du JSON ;
   (4) le panneau « Partager » génère les deux liens depuis la fiche. */

const api = vi.hoisted(() => ({
  getInterventionPublique: vi.fn(),
  getInterventionRapportPublic: vi.fn(),
  getLienClientIntervention: vi.fn(),
  getLienRapportIntervention: vi.fn(),
}))
vi.mock('../../api/installationsApi', () => ({ default: api }))

import InterventionSuiviPublicPage from './InterventionSuiviPublicPage'
import InterventionRapportPublicPage from './InterventionRapportPublicPage'
import InterventionLiensPublicsPanel from '../../features/installations/InterventionLiensPublicsPanel'

const SUIVI = {
  statut: 'en_route',
  statut_display: 'En route',
  technicien_nom: 'Youssef B.',
  fenetre_debut: '2026-08-26T09:00:00Z',
  fenetre_fin: '2026-08-26T11:00:00Z',
  distance_km: 12.4,
  eta_minutes: 19,
  site_ville: 'Bouskoura',
}

const RAPPORT = {
  statut: 'validee',
  statut_display: 'Validée',
  type_intervention_display: 'Maintenance',
  chantier_reference: 'CH-014',
  site_ville: 'Bouskoura',
  date_realisee: '2026-08-20',
  photos: { avant: [{ libelle: 'Toiture', url: '/api/django/records/attachments/3/download/' }], pendant: [], apres: [] },
  serials: [],
  consommation: [{ designation: 'Câble 6mm²', quantite_prevue: '10', quantite_utilisee: '12', variance: 2 }],
  reserves: [{ description: 'Reprise étanchéité', statut: 'Ouverte' }],
  signataire_nom: 'M. Client',
  signe_le: '2026-08-20T16:00:00Z',
  pdf_url: '/api/django/public/installations/intervention-rapport/JETON/pdf/',
}

function renderRoute(path, pattern, element) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes><Route path={pattern} element={element} /></Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  api.getInterventionPublique.mockResolvedValue({ data: SUIVI })
  api.getInterventionRapportPublic.mockResolvedValue({ data: RAPPORT })
  api.getLienClientIntervention.mockResolvedValue({
    data: { token: 'T1', path: '/intervention/T1', url: 'https://erp.example.ma/intervention/T1' },
  })
  api.getLienRapportIntervention.mockResolvedValue({
    data: { token: 'T2', path: '/intervention-rapport/T2', url: 'https://erp.example.ma/intervention-rapport/T2' },
  })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('InterventionSuiviPublicPage — WIR264/XFSM7', () => {
  it('rend le suivi hors session depuis le jeton', async () => {
    renderRoute('/intervention/JETON', '/intervention/:token', <InterventionSuiviPublicPage />)
    await waitFor(() => expect(api.getInterventionPublique).toHaveBeenCalledWith('JETON'))
    expect(await screen.findByTestId('suivi-statut')).toHaveTextContent('En route')
    expect(screen.getByText(/Youssef B\./)).toBeInTheDocument()
    expect(screen.getByTestId('suivi-eta')).toHaveTextContent('19 minutes')
  })

  it('jeton invalide → message FRANÇAIS, jamais du JSON', async () => {
    api.getInterventionPublique.mockRejectedValue({ response: { status: 404 } })
    renderRoute('/intervention/NOPE', '/intervention/:token', <InterventionSuiviPublicPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/introuvable ou a expiré/)
  })
})

describe('InterventionRapportPublicPage — WIR264/ZFSM2', () => {
  it('rend le compte-rendu et son PDF, sans aucun coût ni marge', async () => {
    const { container } = renderRoute(
      '/intervention-rapport/JETON', '/intervention-rapport/:token',
      <InterventionRapportPublicPage />)
    await waitFor(() => expect(api.getInterventionRapportPublic)
      .toHaveBeenCalledWith('JETON'))

    expect(await screen.findByText(/Maintenance/)).toBeInTheDocument()
    expect(screen.getByTestId('rapport-photos-avant')).toHaveTextContent('Toiture')
    expect(screen.getByTestId('rapport-consommation')).toHaveTextContent('Câble 6mm²')
    expect(screen.getByTestId('rapport-reserves')).toHaveTextContent('Reprise étanchéité')
    expect(screen.getByTestId('rapport-signature')).toHaveTextContent('M. Client')
    expect(screen.getByRole('link', { name: /Télécharger le compte-rendu/ }))
      .toHaveAttribute('href', RAPPORT.pdf_url)
    // Aucun coût d'achat ni marge n'apparaît sur une page CLIENT.
    expect(container.textContent).not.toMatch(/prix d.achat|marge|coût d.achat/i)
  })

  it('jeton révoqué → message FRANÇAIS', async () => {
    api.getInterventionRapportPublic.mockRejectedValue({ response: { status: 404 } })
    renderRoute('/intervention-rapport/NOPE', '/intervention-rapport/:token',
      <InterventionRapportPublicPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/introuvable ou a été révoqué/)
  })
})

describe('InterventionLiensPublicsPanel — WIR264 boutons « Partager »', () => {
  it('génère les DEUX liens de page (jetons distincts)', async () => {
    const user = userEvent.setup()
    render(<InterventionLiensPublicsPanel intervention={{ id: 42 }} />)

    await user.click(screen.getByRole('button', { name: /Générer le lien de suivi/ }))
    await waitFor(() => expect(api.getLienClientIntervention).toHaveBeenCalledWith(42))
    expect(await screen.findByLabelText('Partager le suivi « en route »'))
      .toHaveValue('https://erp.example.ma/intervention/T1')

    await user.click(screen.getByRole('button', { name: /Générer le lien du compte-rendu/ }))
    await waitFor(() => expect(api.getLienRapportIntervention).toHaveBeenCalledWith(42))
    expect(await screen.findByLabelText('Partager le compte-rendu signé'))
      .toHaveValue('https://erp.example.ma/intervention-rapport/T2')
  })
})
