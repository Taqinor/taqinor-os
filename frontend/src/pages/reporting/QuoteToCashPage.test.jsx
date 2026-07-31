import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

/* WIR84 — l'écran Quote-to-Cash est le CONSOMMATEUR des trois agrégateurs de
   `apps/ventes` restés sans appelant (`/ventes/dashboard/` FG45,
   `/ventes/insights/cash-flow/` FG47, `/ventes/etats/analyse-facturation/`
   ZFAC10). Ce test verrouille les trois appels + le rendu de chaque source :
   si un endpoint redevenait orphelin (appel retiré), il devient rouge. */

vi.mock('../../api/ventesApi', () => ({
  default: {
    getDashboardQuoteToCash: vi.fn(() => Promise.resolve({
      data: {
        devis: {
          total: 10, envoyes: 8, acceptes: 4, refuses: 2, expires: 1,
          taux_acceptation_pct: 50.0, valeur_pipeline: '120000.00',
        },
        factures: {
          total: 6, emises: 3, payees: 2, en_retard: 1, annulees: 0,
          montant_facture: '90000.00', montant_encaisse: '55000.00',
        },
        conversion: {
          devis_envoye_vers_accepte_pct: 50.0,
          devis_accepte_vers_facture_pct: 75.0,
          devis_envoye_vers_facture_pct: 37.5,
        },
        dso_jours: 21.5,
        cycle_moyen_jours: 42.0,
        par_commercial: [
          { commercial: 'Sami Bennani', devis_actifs: 3, valeur_pipeline: '60000.00' },
        ],
      },
    })),
    getCashFlowForecast: vi.fn(() => Promise.resolve({
      data: {
        buckets: {
          en_retard: { montant: '12000.00', count: 2 },
          cette_semaine: { montant: '5000.00', count: 1 },
          semaine_suivante: { montant: '0.00', count: 0 },
          ce_mois: { montant: '0.00', count: 0 },
          mois_suivant: { montant: '0.00', count: 0 },
          au_dela: { montant: '0.00', count: 0 },
          sans_echeance: { montant: '0.00', count: 0 },
        },
        total_en_cours: '17000.00',
        rows: [],
      },
    })),
    getAnalyseFacturation: vi.fn(() => Promise.resolve({
      data: [
        {
          mois: '2026-07', client_id: 42, client_nom: 'ACME SARL',
          statut: 'emise', nb_factures: 2,
          total_ht: '10000.00', total_tva: '2000.00', total_ttc: '12000.00',
        },
      ],
    })),
  },
}))

import ventesApi from '../../api/ventesApi'
import QuoteToCashPage from './QuoteToCashPage'

describe('QuoteToCashPage (WIR84 — consommateur des agrégateurs ventes)', () => {
  it('appelle les trois endpoints ventes et rend chaque source', async () => {
    render(<QuoteToCashPage />)

    await waitFor(() => {
      expect(ventesApi.getDashboardQuoteToCash).toHaveBeenCalled()
    })
    expect(ventesApi.getCashFlowForecast).toHaveBeenCalled()
    expect(ventesApi.getAnalyseFacturation).toHaveBeenCalled()

    // FG45 — KPI + pipeline par commercial.
    expect(await screen.findByText('Sami Bennani')).toBeInTheDocument()
    expect(screen.getByText('50 %')).toBeInTheDocument()
    expect(screen.getByText('21.5 j')).toBeInTheDocument()

    // FG47 — buckets d'encaissement.
    expect(screen.getByText('En retard')).toBeInTheDocument()
    expect(screen.getByText('Total en cours')).toBeInTheDocument()

    // ZFAC10 — analyse de facturation.
    expect(screen.getByText('ACME SARL')).toBeInTheDocument()
    expect(screen.getByText('2026-07')).toBeInTheDocument()
  })
})
