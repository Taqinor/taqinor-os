import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'

/* AERR105 — « Annuler » un rendez-vous demande une confirmation qui NOMME le
   rendez-vous ; `updateAppointment` ne part qu'après « Confirmer ». Sans
   ConfirmProvider, `useConfirm` retombe sur `window.confirm` (espionné ici). */

vi.mock('../../../api/crmApi', () => ({
  default: {
    getAppointments: vi.fn(),
    updateAppointment: vi.fn(() => Promise.resolve({ data: {} })),
    createAppointment: vi.fn(),
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

describe('AERR176 — refus des notes sous les notes', () => {
  const planifier = async (refus) => {
    fetchAllPages.mockResolvedValue([])
    crmApi.createAppointment.mockRejectedValue({ response: { status: 400, data: refus } })
    render(<AppointmentBooker leadId={9} />)
    fireEvent.click(await screen.findByRole('button', { name: /Planifier/ }))
    fireEvent.change(document.getElementById('appt-scheduled-at'), { target: { value: '2030-11-14T10:00' } })
    fireEvent.change(document.getElementById('appt-notes'), { target: { value: 'x' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await screen.findByRole('alert')
  }

  it('400 {notes} : #appt-notes invalide relié au message, la date reste valide', async () => {
    await planifier({ notes: ['Texte trop long.'] })
    const notes = document.getElementById('appt-notes')
    expect(notes).toHaveAttribute('aria-invalid', 'true')
    expect(notes).toHaveAttribute('aria-describedby', 'appt-error')
    expect(screen.getByRole('alert')).toHaveTextContent('Notes : Texte trop long.')
    const date = document.getElementById('appt-scheduled-at')
    expect(date).not.toHaveAttribute('aria-invalid', 'true')
    expect(date).not.toHaveAttribute('aria-describedby')
  })

  it('400 {scheduled_at} : la date seule est marquée', async () => {
    await planifier({ scheduled_at: ['Date invalide.'] })
    expect(document.getElementById('appt-scheduled-at')).toHaveAttribute('aria-invalid', 'true')
    expect(document.getElementById('appt-notes')).not.toHaveAttribute('aria-invalid', 'true')
  })
})
