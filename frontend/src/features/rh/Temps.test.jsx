import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import Temps from './Temps.jsx'

/* XRH10/11/13 — Temps & présence : le module charge les devices kiosque et
   expose l'onglet Kiosque + l'import CSV. Smoke : ne plante pas au montage. */

vi.mock('../../api/rhApi', () => {
  const empty = () => Promise.resolve({ data: [] })
  return {
    default: {
      getPointages: vi.fn(empty),
      getRoster: vi.fn(empty),
      getPresencesChantier: vi.fn(empty),
      getHeuresSupp: vi.fn(empty),
      getDevicesKiosque: vi.fn(empty),
      pointagerDepart: vi.fn(),
      exportPaieHeuresSupp: vi.fn(empty),
      importPointageCsv: vi.fn(),
      emettreDeviceKiosque: vi.fn(),
      revoquerDeviceKiosque: vi.fn(),
      updatePointage: vi.fn(),
    },
  }
})

function renderTemps() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <Temps />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('Temps — kiosque & import (XRH10/13)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('charge les devices kiosque et propose l’onglet Kiosque', async () => {
    renderTemps()
    expect((await screen.findAllByText('Temps & présence')).length).toBeGreaterThan(0)
    expect(rhApi.getDevicesKiosque).toHaveBeenCalled()
    expect(screen.getByRole('radio', { name: 'Kiosque' })).toBeInTheDocument()
  })

  it('affiche le bouton d’import CSV sur les pointages', async () => {
    renderTemps()
    await screen.findAllByText('Temps & présence')
    expect(screen.getAllByRole('button', { name: /Importer CSV/ })[0]).toBeInTheDocument()
  })
})

describe('Temps — PACT19 : « Export paie » appelle la route qui existe vraiment', () => {
  beforeEach(() => vi.clearAllMocks())

  it('le bouton vit sur « Heures supp. », pas sur « Pointages »', async () => {
    renderTemps()
    await screen.findAllByText('Temps & présence')
    // Vue « Pointages » (défaut) : plus d'export paie ici — il exportait des
    // heures supplémentaires depuis l'écran des pointages, via une route
    // (`/rh/pointages/export-paie/`) qui n'a jamais existé.
    expect(screen.queryByRole('button', { name: /Export paie/ })).toBeNull()

    fireEvent.click(screen.getByRole('radio', { name: 'Heures supp.' }))
    expect((await screen.findAllByRole('button', { name: /Export paie/ }))[0]).toBeInTheDocument()
  })

  it('appelle exportPaieHeuresSupp (/rh/heures-supp/export-paie/) au clic', async () => {
    renderTemps()
    await screen.findAllByText('Temps & présence')
    fireEvent.click(screen.getByRole('radio', { name: 'Heures supp.' }))
    fireEvent.click((await screen.findAllByRole('button', { name: /Export paie/ }))[0])
    await waitFor(() => expect(rhApi.exportPaieHeuresSupp).toHaveBeenCalled())
  })
})
