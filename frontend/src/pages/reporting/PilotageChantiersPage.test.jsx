import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

function renderPage(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

/* CHT27 — cockpit KPI chantier (reporting/reports/chantier/ + second fetch
   vers installations/chantiers/a-facturer/, réutilisé sans backend nouveau). */

const REPORT_DATA = {
  cycle_time: {
    segments: [
      { de: 'signe', vers: 'planifie', label: 'Signé → Planifié', n: 3, jours_median: 2, jours_moyen: 2.3 },
      { de: 'planifie', vers: 'en_cours', label: 'Planifié → En cours', n: 2, jours_median: 4, jours_moyen: 4 },
      { de: 'en_cours', vers: 'installe', label: 'En cours → Installé', n: 1, jours_median: 5, jours_moyen: 5 },
      { de: 'installe', vers: 'receptionne', label: 'Installé → Réceptionné', n: 1, jours_median: 1, jours_moyen: 1 },
    ],
    par_type_installation: [],
    par_equipe: [],
  },
  taux_reprise_post_mes: { fenetre_jours: 30, nb_eligibles: 4, nb_avec_reprise: 1, taux_pct: 25 },
  chantiers_en_retard: {
    total: 1,
    items: [{ installation_id: 7, reference: 'CH-7', client: 'Client Test', date_pose_prevue: '2026-08-01', jours_retard: 12 }],
  },
}

const A_FACTURER_DATA = [
  { installation_id: 9, reference: 'CH-9', tranche: 'T2', jalon_id: 3, jalon_libelle: 'Pose terminée' },
]

vi.mock('../../api/axios', () => ({
  default: {
    get: vi.fn((url) => {
      if (url === '/reporting/reports/chantier/') {
        return Promise.resolve({ data: REPORT_DATA })
      }
      if (url === '/installations/chantiers/a-facturer/') {
        return Promise.resolve({ data: A_FACTURER_DATA })
      }
      return Promise.reject(new Error(`unexpected url ${url}`))
    }),
  },
}))

import api from '../../api/axios'
import PilotageChantiersPage from './PilotageChantiersPage'

describe('PilotageChantiersPage (CHT27)', () => {
  it('charge et affiche les KPIs, le cycle par étape, les retards et les tranches à facturer', async () => {
    renderPage(<PilotageChantiersPage />)

    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/reporting/reports/chantier/'))
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/installations/chantiers/a-facturer/'))

    // KPI : taux de reprise post-MES
    expect(await screen.findByText('25 %')).toBeInTheDocument()
    // KPI : chantiers en retard (compteur)
    expect(screen.getAllByText('1').length).toBeGreaterThan(0)
    // Table cycle par étape
    expect(screen.getByText('Signé → Planifié')).toBeInTheDocument()
    // Chantier en retard listé, lien vers /chantiers?id=
    const link = screen.getByRole('link', { name: 'CH-7' })
    expect(link.getAttribute('href')).toBe('/chantiers?id=7')
    // Tranche à facturer listée
    expect(screen.getByText('Pose terminée')).toBeInTheDocument()
  })

  it("affiche un état d'erreur si le rapport ne charge pas", async () => {
    api.get.mockImplementationOnce(() => Promise.reject(new Error('boom')))
    renderPage(<PilotageChantiersPage />)
    expect(await screen.findByText('Erreur')).toBeInTheDocument()
  })
})
