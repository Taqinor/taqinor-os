import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import CallLogPopover from './CallLogPopover'

/* VX87 — CallLogPopover : journal d'appel en un geste (issue + note +
   prochaine relance), 1 requête logInteraction + 1 requête updateLead
   optionnelle. */

vi.mock('../../api/crmApi', () => ({
  default: {
    logInteraction: vi.fn(() => Promise.resolve({ data: {} })),
    updateLead: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

vi.mock('../../lib/toast', () => ({
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}))

import crmApi from '../../api/crmApi'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('CallLogPopover (VX87)', () => {
  it('ouvre le popover au clic sur le déclencheur par défaut', () => {
    render(<CallLogPopover leadId={42} open onOpenChange={() => {}} />)
    expect(screen.getByText('Journaliser un appel')).toBeInTheDocument()
  })

  it('propose les 5 issues + un champ note + 4 délais de prochaine action', () => {
    render(<CallLogPopover leadId={42} open onOpenChange={() => {}} />)
    expect(screen.getByText('Joint')).toBeInTheDocument()
    expect(screen.getByText('Non joint')).toBeInTheDocument()
    expect(screen.getByText('À rappeler')).toBeInTheDocument()
    expect(screen.getByText('Refus')).toBeInTheDocument()
    expect(screen.getByText('Intéressé')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Note (facultative)…')).toBeInTheDocument()
    expect(screen.getByText("Aujourd'hui")).toBeInTheDocument()
    expect(screen.getByText('Demain')).toBeInTheDocument()
  })

  it('« Enregistrer » reste désactivé tant qu\'aucune issue n\'est choisie', () => {
    render(<CallLogPopover leadId={42} open onOpenChange={() => {}} />)
    expect(screen.getByRole('button', { name: 'Enregistrer' })).toBeDisabled()
  })

  it('journalise en 1 requête logInteraction (issue seule, sans prochaine action)', async () => {
    render(<CallLogPopover leadId={42} open onOpenChange={() => {}} />)
    fireEvent.click(screen.getByText('Joint'))
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(crmApi.logInteraction).toHaveBeenCalledWith(
      42, expect.objectContaining({ kind: 'appel', outcome: 'joint' }),
    ))
    expect(crmApi.updateLead).not.toHaveBeenCalled()
  })

  it('pose la relance dans le MÊME geste quand une prochaine action est choisie', async () => {
    render(<CallLogPopover leadId={42} open onOpenChange={() => {}} />)
    fireEvent.click(screen.getByText('À rappeler'))
    fireEvent.click(screen.getByText('Dans 3 j'))
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalledWith(
      42, expect.objectContaining({ relance_date: expect.any(String) }),
    ))
  })

  it('appelle onLogged après journalisation réussie', async () => {
    const onLogged = vi.fn()
    render(<CallLogPopover leadId={42} open onOpenChange={() => {}} onLogged={onLogged} />)
    fireEvent.click(screen.getByText('Intéressé'))
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(onLogged).toHaveBeenCalled())
  })
})
