import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

/* ADSDEEP35 — composeur EDIT_COPY : avant/après côte à côte, avertissements
   STATIQUES annoncés avant soumission, envoi comme PROPOSITION EngineAction
   (jamais un write Meta direct). */

const mocks = vi.hoisted(() => ({ create: vi.fn() }))

vi.mock('./adsengineApi', () => ({
  default: { actions: { create: mocks.create } },
}))

import EditCopyComposer from './EditCopyComposer'

beforeEach(() => {
  vi.clearAllMocks()
  mocks.create.mockResolvedValue({ data: { id: 99 } })
})

describe('EditCopyComposer (ADSDEEP35)', () => {
  it('montre le diff avant/après et les avertissements statiques', () => {
    render(<EditCopyComposer currentCreative={{ body: 'Ancien texte' }} />)
    expect(screen.getByTestId('ae-composer-current-body')).toHaveValue('Ancien texte')
    expect(screen.getAllByTestId('ae-composer-warning').length).toBeGreaterThanOrEqual(2)
    expect(screen.getByTestId('ae-composer-diff')).toBeInTheDocument()
  })

  it('le bouton reste désactivé tant que les champs requis manquent', () => {
    render(<EditCopyComposer />)
    expect(screen.getByTestId('ae-composer-submit')).toBeDisabled()
    fireEvent.change(screen.getByTestId('ae-composer-ad-id'), { target: { value: 'ad-1' } })
    fireEvent.change(screen.getByTestId('ae-composer-proposed-body'), { target: { value: 'Nouveau texte' } })
    expect(screen.getByTestId('ae-composer-submit')).toBeDisabled() // raison manquante
    fireEvent.change(screen.getByTestId('ae-composer-reason'), { target: { value: 'Rafraîchir.' } })
    expect(screen.getByTestId('ae-composer-submit')).not.toBeDisabled()
  })

  it('soumet une PROPOSITION edit_copy (jamais un write Meta direct)', async () => {
    const onProposed = vi.fn()
    render(<EditCopyComposer adMetaId="ad-42" onProposed={onProposed} />)
    fireEvent.change(screen.getByTestId('ae-composer-proposed-body'),
      { target: { value: 'Nouvelle accroche' } })
    fireEvent.change(screen.getByTestId('ae-composer-reason'),
      { target: { value: "L'accroche actuelle est fatiguée." } })
    fireEvent.click(screen.getByTestId('ae-composer-submit'))

    await waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(1))
    const [payload] = mocks.create.mock.calls[0]
    expect(payload.kind).toBe('edit_copy')
    expect(payload.reason_fr).toBe("L'accroche actuelle est fatiguée.")
    expect(payload.payload.ad_id).toBe('ad-42')
    expect(payload.payload.creative_spec.body).toBe('Nouvelle accroche')
    await waitFor(() => expect(onProposed).toHaveBeenCalled())
    expect(screen.getByTestId('ae-composer-done')).toBeInTheDocument()
  })

  it('erreur API → message affiché, formulaire reste rempli', async () => {
    mocks.create.mockRejectedValue(new Error('403'))
    render(<EditCopyComposer adMetaId="ad-1" />)
    fireEvent.change(screen.getByTestId('ae-composer-proposed-body'), { target: { value: 'X' } })
    fireEvent.change(screen.getByTestId('ae-composer-reason'), { target: { value: 'Raison X.' } })
    fireEvent.click(screen.getByTestId('ae-composer-submit'))
    expect(await screen.findByTestId('ae-composer-err')).toBeInTheDocument()
  })
})
