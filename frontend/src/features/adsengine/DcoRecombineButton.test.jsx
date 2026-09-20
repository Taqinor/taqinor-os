import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

/* PUB118 — Bouton « Recombiner (DCO) » : un clic PROPOSE (jamais ne publie),
   et un refus métier du backend s'affiche TEL QUEL, en français. */

const mocks = vi.hoisted(() => ({ recombine: vi.fn() }))

vi.mock('./adsengineApi', () => ({
  default: { dco: { recombine: mocks.recombine } },
}))

import DcoRecombineButton from './DcoRecombineButton'

beforeEach(() => {
  vi.clearAllMocks()
  mocks.recombine.mockResolvedValue({ data: { action: { id: 7 } } })
})

describe('DcoRecombineButton', () => {
  it("ne s'affiche pas sans ad set cible", () => {
    const { container } = render(<DcoRecombineButton adsetMetaId="" />)
    expect(container.firstChild).toBeNull()
  })

  it('propose la recombinaison sur l’ad set et confirme en français', async () => {
    const onProposed = vi.fn()
    render(<DcoRecombineButton adsetMetaId="as-1" adsetName="Toit Casa"
      onProposed={onProposed} />)
    fireEvent.click(screen.getByTestId('ae-dco-recombine-button'))
    await waitFor(() => expect(mocks.recombine).toHaveBeenCalled())
    expect(mocks.recombine.mock.calls[0][0]).toBe('as-1')
    // L'erreur est gérée localement (raison métier FR), pas par le toast global.
    expect(mocks.recombine.mock.calls[0][1]).toEqual(
      expect.objectContaining({ suppressErrorToast: true }))
    await waitFor(() =>
      expect(screen.getByTestId('ae-dco-recombine-ok')).toBeTruthy())
    expect(screen.getByTestId('ae-dco-recombine-ok').textContent)
      .toMatch(/approbations/i)
    expect(onProposed).toHaveBeenCalled()
  })

  it('affiche la raison FR du refus backend, sans rien proposer', async () => {
    mocks.recombine.mockRejectedValue({
      response: { data: { detail: "DCO réservé au démarrage à froid (bootstrap uniquement)." } },
    })
    const onProposed = vi.fn()
    render(<DcoRecombineButton adsetMetaId="as-1" onProposed={onProposed} />)
    fireEvent.click(screen.getByTestId('ae-dco-recombine-button'))
    await waitFor(() =>
      expect(screen.getByTestId('ae-dco-recombine-error')).toBeTruthy())
    expect(screen.getByTestId('ae-dco-recombine-error').textContent)
      .toMatch(/démarrage à froid/)
    expect(onProposed).not.toHaveBeenCalled()
  })

  it('retombe sur un message FR générique si le backend ne détaille pas', async () => {
    mocks.recombine.mockRejectedValue(new Error('boom'))
    render(<DcoRecombineButton adsetMetaId="as-1" />)
    fireEvent.click(screen.getByTestId('ae-dco-recombine-button'))
    await waitFor(() =>
      expect(screen.getByTestId('ae-dco-recombine-error')).toBeTruthy())
    expect(screen.getByTestId('ae-dco-recombine-error').textContent)
      .toMatch(/Rien n'a été proposé/)
  })
})
