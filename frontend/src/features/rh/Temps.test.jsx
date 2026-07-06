import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
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
      exportPaiePointages: vi.fn(empty),
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
    expect(await screen.findByText('Temps & présence')).toBeInTheDocument()
    expect(rhApi.getDevicesKiosque).toHaveBeenCalled()
    expect(screen.getByRole('radio', { name: 'Kiosque' })).toBeInTheDocument()
  })

  it('affiche le bouton d’import CSV sur les pointages', async () => {
    renderTemps()
    await screen.findByText('Temps & présence')
    expect(screen.getByRole('button', { name: /Importer CSV/ })).toBeInTheDocument()
  })
})
