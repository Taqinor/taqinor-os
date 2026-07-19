import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

/* PUB22 — Composeur d'action manuel générique : chaque kind se propose depuis
   l'UI (payload injecté depuis la cible), en `raw` (actions.create) ou `curated`
   (actions.proposeCurated). Toute soumission part en proposition. */

const mocks = vi.hoisted(() => ({
  create: vi.fn(),
  proposeCurated: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: { actions: { create: mocks.create, proposeCurated: mocks.proposeCurated } },
}))

import ManualActionComposer from './ManualActionComposer'
import { findAction } from './manualActions'

beforeEach(() => {
  vi.clearAllMocks()
  mocks.create.mockResolvedValue({ data: { id: 1 } })
  mocks.proposeCurated.mockResolvedValue({ data: { id: 2 } })
})

describe('ManualActionComposer', () => {
  it('kind RAW (set_spend_cap) : injecte l\'id cible et propose via actions.create', async () => {
    const descriptor = findAction('set_spend_cap', 'campaign')
    render(<ManualActionComposer descriptor={descriptor}
      target={{ metaId: 'camp-1', scope: 'campaign' }} />)

    // L'aperçu du payload montre déjà l'id cible injecté (jamais re-saisi).
    expect(screen.getByTestId('ae-maction-preview')).toHaveTextContent('camp-1')

    fireEvent.change(screen.getByTestId('ae-maction-field-spend_cap'), { target: { value: '5000' } })
    fireEvent.change(screen.getByTestId('ae-maction-reason'), { target: { value: 'Limiter la dépense.' } })
    fireEvent.click(screen.getByTestId('ae-maction-submit'))

    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith({
      kind: 'set_spend_cap',
      reason_fr: 'Limiter la dépense.',
      payload: { campaign_id: 'camp-1', spend_cap: 5000 },
    }))
    expect(mocks.proposeCurated).not.toHaveBeenCalled()
  })

  it('kind CURÉ (duplicate) : propose via actions.proposeCurated', async () => {
    const descriptor = findAction('duplicate', 'adset')
    render(<ManualActionComposer descriptor={descriptor}
      target={{ metaId: 'as-1', scope: 'adset' }} />)

    fireEvent.change(screen.getByTestId('ae-maction-reason'), { target: { value: 'Dupliquer le gagnant.' } })
    fireEvent.click(screen.getByTestId('ae-maction-submit'))

    await waitFor(() => expect(mocks.proposeCurated).toHaveBeenCalledWith('duplicate', {
      adset_id: 'as-1', name_suffix: ' (copie)', reason_fr: 'Dupliquer le gagnant.',
    }))
    expect(mocks.create).not.toHaveBeenCalled()
  })

  it('la soumission est bloquée sans raison', () => {
    const descriptor = findAction('pause', 'ad')
    render(<ManualActionComposer descriptor={descriptor}
      target={{ metaId: 'ad-1', scope: 'ad' }} />)
    expect(screen.getByTestId('ae-maction-submit')).toBeDisabled()
  })

  it('un champ JSON invalide bloque et signale l\'erreur', () => {
    const descriptor = findAction('create_ad_study', 'campaign')
    render(<ManualActionComposer descriptor={descriptor}
      target={{ metaId: 'camp-1', scope: 'campaign' }} />)
    fireEvent.change(screen.getByTestId('ae-maction-field-name'), { target: { value: 'E' } })
    fireEvent.change(screen.getByTestId('ae-maction-field-cells'), { target: { value: '{not json' } })
    fireEvent.change(screen.getByTestId('ae-maction-reason'), { target: { value: 'x' } })
    expect(screen.getByTestId('ae-maction-json-err')).toBeInTheDocument()
    expect(screen.getByTestId('ae-maction-submit')).toBeDisabled()
  })
})
