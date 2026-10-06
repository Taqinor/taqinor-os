import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import { exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'

/* ADOC140 — « Ma consommation » : série, alertes ouvertes, choix du site, et
   message « non raccordé » (contrat ma_consommation.json). */

vi.mock('../../../api/portailApi', () => ({
  default: { consommation: vi.fn(), chantiers: { liste: vi.fn() } },
}))

import portailApi from '../../../api/portailApi'
import PortailClientConsommation from './PortailClientConsommation.jsx'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderPage() {
  portailApi.chantiers.liste.mockResolvedValue(reponseContrat('portail', 'mes_chantiers_liste'))
  return render(
    <MemoryRouter><ThemeProvider><PortailClientConsommation /></ThemeProvider></MemoryRouter>,
  )
}

describe('PortailClientConsommation — ADOC140', () => {
  it('affiche la série servie et « 1 alerte ouverte », puis relit avec ?chantier=', async () => {
    portailApi.consommation.mockResolvedValue(reponseContrat('portail', 'ma_consommation'))
    renderPage()
    const { points } = exempleContrat('portail', 'ma_consommation')
    await screen.findByText(points[0].energy_kwh)
    expect(screen.getByText(points[1].energy_kwh)).toBeTruthy()
    expect(screen.getByTestId('consommation-alertes').textContent).toBe('1 alerte ouverte')
    expect(portailApi.consommation).toHaveBeenLastCalledWith({})

    await screen.findByRole('option', { name: 'CH-2026-0012' })
    fireEvent.change(screen.getByLabelText('Site'), { target: { value: '12' } })
    await waitFor(() => expect(portailApi.consommation).toHaveBeenLastCalledWith({ chantier: '12' }))
  })

  it('provider_configure:false affiche « Suivi de production non raccordé »', async () => {
    portailApi.consommation.mockResolvedValue(
      reponseContrat('portail', 'ma_consommation', 'exemple_sans_provider'))
    renderPage()
    expect(await screen.findByText('Suivi de production non raccordé')).toBeTruthy()
    expect(screen.queryByRole('table')).toBeNull()
    expect(screen.getByTestId('consommation-alertes').textContent).toBe('Aucune alerte ouverte')
  })
})
