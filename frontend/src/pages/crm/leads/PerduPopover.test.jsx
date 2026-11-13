import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'

/* AERR117 — un 400 `{motif_perte: […]}` s'affiche SOUS le champ du motif ; la
   popover reste ouverte avec la saisie (le toast générique est celui de
   l'intercepteur global, jamais doublé ici). */

vi.mock('../../../api/crmApi', () => ({
  default: { getMotifsPerte: vi.fn(() => Promise.resolve({ data: { results: [] } })) },
}))

import PerduPopover from './PerduPopover'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('PerduPopover — AERR117', () => {
  it('400 motif_perte : message sous le motif, popover ouverte', async () => {
    const onMarkPerdu = vi.fn(() => Promise.reject({ motif_perte: ['Motif requis.'] }))
    render(<PerduPopover lead={{ id: 5 }} onMarkPerdu={onMarkPerdu} open onOpenChange={() => {}} anchor={<span />} />)
    fireEvent.change(screen.getByPlaceholderText('Motif de perte'), { target: { value: 'Trop cher' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    expect(await screen.findByText('Motif requis.')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Motif de perte')).toHaveValue('Trop cher')
    expect(screen.getByPlaceholderText('Motif de perte')).toHaveAttribute('aria-invalid', 'true')
    fireEvent.change(screen.getByPlaceholderText('Motif de perte'), { target: { value: 'Autre' } })
    await waitFor(() => expect(screen.queryByText('Motif requis.')).not.toBeInTheDocument())
  })
})
