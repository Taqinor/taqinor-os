import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
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

/* XPLT6 — CRUD des alertes de seuil sur KPI agrégés (reporting/kpi-alertes/). */

vi.mock('../../api/reportingApi', () => ({
  default: {
    listKpiAlertes: vi.fn(() => Promise.resolve({
      data: [
        {
          id: 1, nom: 'DSO trop élevé', kpi: 'dso', kpi_label: 'DSO (délai moyen de recouvrement, jours)',
          operateur: 'sup', operateur_label: '>', seuil: '60.00',
          derniere_valeur: '45.00', actif: true,
        },
      ],
    })),
    createKpiAlerte: vi.fn(() => Promise.resolve({ data: {} })),
    updateKpiAlerte: vi.fn(() => Promise.resolve({ data: {} })),
    deleteKpiAlerte: vi.fn(() => Promise.resolve({})),
  },
}))

vi.mock('../../api/axios', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({
      data: [{ id: 3, username: 'reda', email: 'reda@taqinor.ma' }],
    })),
  },
}))

import reportingApi from '../../api/reportingApi'
import KpiAlertesPage from './KpiAlertesPage'

describe('KpiAlertesPage (XPLT6 — alertes de seuil sur KPI agrégés)', () => {
  it('liste les alertes existantes', async () => {
    renderPage(<KpiAlertesPage />)

    expect((await screen.findAllByText('DSO trop élevé')).length).toBeGreaterThan(0)
    await waitFor(() => expect(reportingApi.listKpiAlertes).toHaveBeenCalled())
  })

  it('ouvre le dialogue de création', async () => {
    renderPage(<KpiAlertesPage />)
    await screen.findAllByText('DSO trop élevé')

    screen.getByRole('button', { name: /Nouvelle alerte/i }).click()
    expect(await screen.findByText('Nouvelle alerte KPI')).toBeInTheDocument()
  })

  // VX236 — la dernière valeur d'une alerte DSO ouvre la balance âgée (source
  // réelle du KPI) au lieu de rester un chiffre affiché sans suite.
  it('VX236 : la dernière valeur (DSO) est un lien vers la balance âgée', async () => {
    renderPage(<KpiAlertesPage />)
    // DataTable rend simultanément la table desktop (role="grid") et les
    // cartes mobiles (même ligne dupliquée en jsdom, la visibilité CSS
    // responsive n'étant pas évaluée) : on scope au tableau desktop pour
    // ne matcher qu'une seule fois le lien « 45.00 ».
    const grid = await screen.findByRole('grid', { name: 'Alertes KPI' })
    const link = within(grid).getByRole('link', { name: '45.00' })
    expect(link).toHaveAttribute('href', '/reporting/balance-agee')
  })
})
