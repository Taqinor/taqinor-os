import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

/* WIR264/XFSM7+ZFSM2 — les actions `lien-client` et `lien-rapport`
   exposaient des jetons SANS page pour les recevoir : le lien partagé au
   client menait à du JSON. Ces deux pages sont les destinations manquantes.

   Charges utiles alignées sur `intervention_public_payload` et
   `intervention_rapport_public_payload` (selectors.py) — jamais une forme
   inventée. Aucune de ces pages n'affiche de coût : le payload serveur n'en
   porte pas (matériel consommé = quantités seules). */

vi.mock('../../api/installationsApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    interventionPublicApi: { suivi: vi.fn(), rapport: vi.fn() },
  }
})

import { interventionPublicApi } from '../../api/installationsApi'
import InterventionSuiviPublicPage from './InterventionSuiviPublicPage'
import InterventionRapportPublicPage from './InterventionRapportPublicPage'

const renderPage = (Comp, chemin) => render(
  <MemoryRouter initialEntries={[`${chemin}/tok-1`]}>
    <Routes><Route path={`${chemin}/:token`} element={<Comp />} /></Routes>
  </MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

describe('WIR264 — suivi public d’intervention', () => {
  it('affiche le statut, le technicien et l’ETA quand elle est servie', async () => {
    interventionPublicApi.suivi.mockResolvedValue({
      data: {
        statut: 'en_route', statut_display: 'En route',
        technicien_nom: 'Youssef', technicien_avatar_url: null,
        fenetre_debut: '2026-07-01T09:00:00Z', fenetre_fin: '2026-07-01T11:00:00Z',
        date_prevue: '2026-07-01T09:00:00Z',
        distance_km: 12.4, eta_minutes: 18, site_ville: 'Casablanca',
      },
    })
    renderPage(InterventionSuiviPublicPage, '/intervention')

    expect(await screen.findByText(/En route/)).toBeInTheDocument()
    expect(interventionPublicApi.suivi).toHaveBeenCalledWith('tok-1')
    expect(screen.getByText(/Youssef/)).toBeInTheDocument()
    expect(screen.getByText(/18 minute/)).toBeInTheDocument()
  })

  it('sans ETA servie : on le dit, on n’en invente pas', async () => {
    interventionPublicApi.suivi.mockResolvedValue({
      data: {
        statut: 'planifiee', statut_display: 'Planifiée',
        technicien_nom: null, technicien_avatar_url: null,
        fenetre_debut: null, fenetre_fin: null, date_prevue: null,
        distance_km: null, eta_minutes: null, site_ville: 'Rabat',
      },
    })
    renderPage(InterventionSuiviPublicPage, '/intervention')

    expect(await screen.findByText(/sera estimée dès que le technicien/))
      .toBeInTheDocument()
    expect(screen.queryByText(/minute\(s\)/)).toBeNull()
  })

  it('jeton invalide : message FR, jamais du JSON brut', async () => {
    interventionPublicApi.suivi.mockRejectedValue({
      response: { status: 404, data: { detail: 'Lien invalide ou expiré.' } },
    })
    renderPage(InterventionSuiviPublicPage, '/intervention')

    const alerte = await screen.findByRole('alert')
    expect(alerte.textContent).not.toMatch(/\{"detail"/)
  })
})

describe('WIR264 — compte-rendu public d’intervention', () => {
  const RAPPORT = {
    statut: 'terminee', statut_display: 'Terminée',
    type_intervention_display: 'Maintenance préventive',
    chantier_reference: 'CH-0001', site_ville: 'Casablanca',
    date_realisee: '2026-07-01',
    equipe: ['Youssef'],
    photos: { avant: [{ libelle: 'Toiture', url: '/a.jpg' }], pendant: [], apres: [] },
    serials: [{ designation: 'Onduleur', numero_serie: 'SN-1' }],
    consommation: [{
      designation: 'Câble 6mm²', quantite_prevue: '50.00',
      quantite_utilisee: '48.00', variance: -2, justification: '',
    }],
    reserves: [{ description: 'Reprendre un serrage', statut: 'Ouverte', assignee: null, resolution: '' }],
    signataire_nom: 'M. Client', signe_le: '2026-07-01',
    pdf_url: '/api/django/public/installations/intervention-rapport/tok-1/pdf/',
  }

  it('rend le compte-rendu + le PDF, et AUCUN montant', async () => {
    interventionPublicApi.rapport.mockResolvedValue({ data: RAPPORT })
    renderPage(InterventionRapportPublicPage, '/intervention-rapport')

    expect(await screen.findByText(/Compte-rendu d'intervention/)).toBeInTheDocument()
    expect(interventionPublicApi.rapport).toHaveBeenCalledWith('tok-1')
    expect(screen.getByRole('link', { name: /Télécharger le compte-rendu/ }))
      .toHaveAttribute('href', RAPPORT.pdf_url)
    expect(screen.getByText('Câble 6mm²')).toBeInTheDocument()
    expect(screen.getByText(/Reprendre un serrage/)).toBeInTheDocument()
    expect(screen.getByText(/Signé par M. Client/)).toBeInTheDocument()

    // GARDE PRODUIT : aucun rendu monétaire nulle part sur cette page client.
    expect(document.body.textContent).not.toMatch(/MAD|DH\b|prix|achat|marge/i)
  })

  it('jeton invalide : message FR, jamais du JSON brut', async () => {
    interventionPublicApi.rapport.mockRejectedValue({
      response: { status: 404, data: { detail: 'Lien invalide ou expiré.' } },
    })
    renderPage(InterventionRapportPublicPage, '/intervention-rapport')

    const alerte = await screen.findByRole('alert')
    expect(alerte.textContent).not.toMatch(/\{"detail"/)
  })
})
