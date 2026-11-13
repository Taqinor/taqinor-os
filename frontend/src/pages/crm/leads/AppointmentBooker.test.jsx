import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'

/* AERR105 — « Annuler » un rendez-vous demande une confirmation qui NOMME le
   rendez-vous ; `updateAppointment` ne part qu'après « Confirmer ». Sans
   ConfirmProvider, `useConfirm` retombe sur `window.confirm` (espionné ici). */

vi.mock('../../../api/crmApi', () => ({
  default: {
    getAppointments: vi.fn(),
    updateAppointment: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))
vi.mock('../../../utils/fetchAllPages', () => ({
  default: vi.fn(),
}))

import crmApi from '../../../api/crmApi'
import fetchAllPages from '../../../utils/fetchAllPages'
import AppointmentBooker from './AppointmentBooker'

const RDV = { id: 5, statut: 'planifie', scheduled_at: '2030-11-14T10:00:00', notes: '' }

afterEach(() => { cleanup(); vi.clearAllMocks(); vi.restoreAllMocks() })

describe('AppointmentBooker — AERR105', () => {
  it('Annuler un RDV : rien ne part sans confirmation nommée', async () => {
    fetchAllPages.mockResolvedValue([RDV])
    const confirmer = vi.spyOn(window, 'confirm')
      .mockReturnValueOnce(false).mockReturnValueOnce(true)
    render(<AppointmentBooker leadId={9} />)
    const annuler = await screen.findByRole('button', { name: 'Annuler' })

    fireEvent.click(annuler)
    await waitFor(() => expect(confirmer).toHaveBeenCalledTimes(1))
    expect(confirmer.mock.calls[0][0]).toMatch(/14\/11/)
    expect(confirmer.mock.calls[0][0]).toMatch(/10:00/)
    expect(crmApi.updateAppointment).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(crmApi.updateAppointment)
      .toHaveBeenCalledWith(5, { statut: 'annule' }))
    expect(crmApi.updateAppointment).toHaveBeenCalledTimes(1)
  })
})
