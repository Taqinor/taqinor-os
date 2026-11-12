import { describe, it, expect, vi, beforeAll, onTestFinished } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

beforeAll(polyfillResizeObserver)

function renderPage(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

/* WR7 — Le rapport O&M rend les indicateurs + recommandations depuis
   /configs/{id}/om-report/ et déclenche l'envoi e-mail (/email-om-report/). */

vi.mock('../../api/monitoringApi', () => ({
  default: {
    getConfigs: vi.fn(() => Promise.resolve({
      data: [{ id: 5, installation: 11, provider: 'noop', enabled: true }],
    })),
    getOmReport: vi.fn(() => Promise.resolve({
      data: {
        installation: 11, reference: 'INST-2026-001', period: 'monthly',
        period_days: 30, period_kwh: '1100.00', pr_pct: '94.00',
        availability_pct: '88.00', libelle_indicateur: 'indice de suivi (jours avec relevé)',
        degradation_pct_per_year: '-1.00',
        soiling_suspected: true, open_alarms: 2,
        recommendations: ['Nettoyage des panneaux recommandé.'],
        date_edition: '2026-06-15',
      },
    })),
    emailOmReport: vi.fn(() => Promise.resolve({ data: { sent: true } })),
  },
}))

vi.mock('../../api/installationsApi', async () => (await import('./monitoring.testHelpers.js')).installationsApiAmrani())

// ADRG47 — droit d'écriture du monitoring (`sav_gerer`, palier sav) simulé :
// vrai = porteur (Technicien) ; faux = Commercial du registre (aucun code sav).
const droit = vi.hoisted(() => ({ ecrire: true }))
vi.mock('../../features/sav/useDroitMetier', () => ({ default: () => droit.ecrire }))

import monitoringApi from '../../api/monitoringApi'
import OmReportPage from './OmReportPage'
import { toast } from '../../ui/confirm'
import { polyfillResizeObserver } from '../../test/selectNatif'

describe('OmReportPage (WR7 — rapport O&M)', () => {
  it('rend les indicateurs + recommandations et envoie par e-mail', async () => {
    renderPage(<OmReportPage />)

    await waitFor(() => expect(monitoringApi.getOmReport).toHaveBeenCalledWith('5', { period: 'monthly' }))

    expect(await screen.findByTestId('om-report')).toBeInTheDocument()
    expect(screen.getByText('Production période')).toBeInTheDocument()
    // AMON108 — le libellé servi est affiché, jamais « Disponibilité ».
    expect(screen.getByText('indice de suivi (jours avec relevé)')).toBeInTheDocument()
    expect(screen.queryByText('Disponibilité')).toBeNull()
    expect(screen.getByText('2 alarme(s) ouverte(s)')).toBeInTheDocument()
    expect(screen.getByText('Nettoyage des panneaux recommandé.')).toBeInTheDocument()

    // Envoi e-mail via le dialogue.
    await userEvent.click(screen.getByRole('button', { name: /Envoyer par e-mail/ }))
    const recipient = await screen.findByLabelText('Destinataire (optionnel)')
    await userEvent.type(recipient, 'client@exemple.ma')
    await userEvent.click(screen.getByRole('button', { name: /^Envoyer$/ }))

    await waitFor(() => expect(monitoringApi.emailOmReport).toHaveBeenCalledWith('5', {
      period: 'monthly', recipient: 'client@exemple.ma',
    }))
  })

  it('AMON47 — un destinataire refusé affiche le message du serveur', async () => {
    const erreur = vi.spyOn(toast, 'error')
    monitoringApi.emailOmReport.mockRejectedValueOnce({
      response: { status: 400, data: { recipient: ['Le rapport ne part qu’aux adresses du client du système.'] } },
    })
    renderPage(<OmReportPage />)

    expect(await screen.findByTestId('om-report')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Envoyer par e-mail/ }))
    await userEvent.type(await screen.findByLabelText('Destinataire (optionnel)'), 'tiers@exemple.ma')
    await userEvent.click(screen.getByRole('button', { name: /^Envoyer$/ }))

    await waitFor(() => expect(erreur).toHaveBeenCalledWith(
      'Le rapport ne part qu’aux adresses du client du système.'))
  })

  it('ADRG47 — un Commercial lit le rapport sans « Envoyer par e-mail »', async () => {
    droit.ecrire = false
    onTestFinished(() => { droit.ecrire = true })
    renderPage(<OmReportPage />)
    expect(await screen.findByTestId('om-report')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Télécharger le PDF/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Envoyer par e-mail/ })).toBeNull()
  })
})
