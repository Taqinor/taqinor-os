import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import DashboardFilterBar from './DashboardFilterBar'

vi.mock('../../api/coreApi', () => ({
  default: { dashboards: { updateLayout: vi.fn(() => Promise.resolve({ data: {} })) } },
}))

import coreApi from '../../api/coreApi'

function wrap(ui) {
  return <ThemeProvider>{ui}</ThemeProvider>
}

describe('DashboardFilterBar (XPLT9)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('changer la plage de dates recharge tous les widgets (onReload) et persiste le layout', async () => {
    const onReload = vi.fn()
    const onLayoutChange = vi.fn()
    const layout = { widgets: [{ id: 'w1', params: {} }, { id: 'w2', optOutGlobalFilters: true, params: {} }] }
    render(wrap(
      <DashboardFilterBar dashboardId={7} layout={layout} onLayoutChange={onLayoutChange} onReload={onReload} />,
    ))

    await userEvent.type(screen.getByLabelText('Du'), '2026-01-01')

    await waitFor(() => expect(onReload).toHaveBeenCalled())
    const call = onReload.mock.calls.at(-1)[0]
    expect(call.find((w) => w.id === 'w1').params.dateFrom).toBe('2026-01-01')
    // Le widget opt-out ne reçoit jamais le filtre global.
    expect(call.find((w) => w.id === 'w2').params.dateFrom).toBeUndefined()

    await waitFor(() => expect(coreApi.dashboards.updateLayout).toHaveBeenCalledWith(
      7, expect.objectContaining({ globalFilters: expect.objectContaining({ dateFrom: '2026-01-01' }) }),
    ))
    expect(onLayoutChange).toHaveBeenCalled()
  })

  it('le filtre est mémorisé par dashboard : changer de dashboardId recharge SES filtres', async () => {
    const layoutA = { widgets: [], globalFilters: { canal: 'whatsapp' } }
    const layoutB = { widgets: [], globalFilters: { canal: 'sms' } }
    const { rerender } = render(wrap(
      <DashboardFilterBar dashboardId={1} layout={layoutA} onReload={vi.fn()} />,
    ))
    expect(screen.getByLabelText('Canal')).toHaveValue('whatsapp')

    rerender(wrap(<DashboardFilterBar dashboardId={2} layout={layoutB} onReload={vi.fn()} />))
    expect(screen.getByLabelText('Canal')).toHaveValue('sms')
  })

  it('Réinitialiser efface tous les filtres et recharge les widgets', async () => {
    const onReload = vi.fn()
    const layout = { widgets: [{ id: 'w1', params: {} }], globalFilters: { canal: 'whatsapp', commercial: 'sami' } }
    render(wrap(<DashboardFilterBar dashboardId={1} layout={layout} onReload={onReload} />))
    expect(screen.getByLabelText('Canal')).toHaveValue('whatsapp')

    await userEvent.click(screen.getByRole('button', { name: /Réinitialiser/ }))
    expect(screen.getByLabelText('Canal')).toHaveValue('')
    await waitFor(() => expect(onReload).toHaveBeenCalled())
  })

  it('sans dashboardId (dashboard pas encore enregistré) : aucun appel réseau, pas de crash', async () => {
    const onReload = vi.fn()
    render(wrap(<DashboardFilterBar layout={{ widgets: [] }} onReload={onReload} />))
    await userEvent.type(screen.getByLabelText('Commercial'), 'sami')
    await waitFor(() => expect(onReload).toHaveBeenCalled())
    expect(coreApi.dashboards.updateLayout).not.toHaveBeenCalled()
  })

  it('ne plante pas avec un layout undefined', () => {
    render(wrap(<DashboardFilterBar onReload={vi.fn()} />))
    expect(screen.getByTestId('dashboard-filter-bar')).toBeInTheDocument()
  })
})
