import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { initState } from './draftCore'
import StageControl from './StageControl'
import { PIPELINE_STAGES, STAGE_LABELS, CONVERSION_STAGE } from '../stages'

/* LW16 — StageControl : rangée d'étapes, rotting, SIGNED gardé. On lit les
   clés/labels depuis stages.js (règle #2), jamais de littéral local. */

afterEach(() => cleanup())

const CONTACTED = PIPELINE_STAGES[1]
const QUOTE_SENT = PIPELINE_STAGES[2]

const makeState = (over = {}) => initState({
  lead: { id: 3, stage: CONTACTED, stage_since_days: 8, ...over },
  mode: 'edit',
})

describe('LW16 — StageControl', () => {
  it('CONTACTED à 8 j affiche l\'ancienneté en classe/rotting warning', () => {
    render(<StageControl state={makeState()} onChangeStage={vi.fn()} onSigne={vi.fn()} />)
    const since = screen.getByText(/depuis 8 j/)
    expect(since).toHaveAttribute('data-rotting', 'warning')
    expect(since.className).toMatch(/lw-stage-since--warning/)
  })

  it('à 2 j sur NEW, aucune teinte d\'alerte (rotting ok)', () => {
    const NEW = PIPELINE_STAGES[0]
    render(<StageControl
      state={makeState({ stage: NEW, stage_since_days: 2 })}
      onChangeStage={vi.fn()}
      onSigne={vi.fn()}
    />)
    expect(screen.getByText(/depuis 2 j/)).toHaveAttribute('data-rotting', 'ok')
  })

  it('cliquer l\'étape signée ouvre la signature (onSigne), jamais un PATCH direct', () => {
    const onChangeStage = vi.fn()
    const onSigne = vi.fn()
    render(<StageControl state={makeState()} onChangeStage={onChangeStage} onSigne={onSigne} />)
    fireEvent.click(screen.getByRole('button', { name: new RegExp(STAGE_LABELS[CONVERSION_STAGE]) }))
    expect(onSigne).toHaveBeenCalledTimes(1)
    expect(onChangeStage).not.toHaveBeenCalled()
  })

  it('cliquer une autre étape appelle onChangeStage(key)', () => {
    const onChangeStage = vi.fn()
    render(<StageControl state={makeState()} onChangeStage={onChangeStage} onSigne={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: new RegExp(STAGE_LABELS[QUOTE_SENT]) }))
    expect(onChangeStage).toHaveBeenCalledWith(QUOTE_SENT)
  })

  it('n\'utilise aucun <select> d\'étape (StatusPill uniquement)', () => {
    const { container } = render(<StageControl state={makeState()} onChangeStage={vi.fn()} onSigne={vi.fn()} />)
    expect(container.querySelector('select')).toBeNull()
  })
})
